import argparse
import json
import os
import shutil
import datetime
import time
from pathlib import Path
from shutil import rmtree

from git import Repo


def splitall(path):
    allparts = []
    while 1:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path:  # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts


def process_candidate_configs(base_dir, version, delete, do_push):
    print('Processing new results...')
    repo = Repo('./')
    repo.git.pull('origin')
    results_changed = False

    p = Path(base_dir)
    result_paths = list(p.glob('**/plots/**/result.json'))
    for new_result_path in result_paths:
        try:
            new_result = json.load(open(new_result_path, encoding='utf-8'))
        except Exception as e:
            raise Exception('failed to load result file', new_result_path, e)

        start_date=(new_result['start_date'].strip('T00:00'))
        end_date=(new_result['end_date'].strip('T00:00'))
        
        if start_date != '2021-01-01' or end_date != '2021-07-31':
            print(f'{new_result_path} does not match required start_date of 01-01-2021 and/or end_date 31-07-2021')
            continue

        current_result_path = Path(f"configs/live/{new_result['exchange']}/{new_result['symbol']}/{version}/{new_result['market_type']}")
        current_result_path.mkdir(parents=True, exist_ok=True)
        current_result = None
        if len(list(current_result_path.glob("result.json"))) > 0:
            try:
                current_result = json.load(open(f"{current_result_path}/result.json", encoding='utf-8'))
            except Exception as e:
                raise Exception('failed to load result file', new_result_path, e)

        if new_result_better(current_result, new_result):
            results_changed = True
            print(f'Replacing configuration for {new_result["symbol"]}')
            if current_result_path.exists():
                # remove all existing files
                existing_files = list(Path(current_result_path).glob("**/*.*"))
                [os.remove(f) for f in existing_files]

            # copy the new files
            new_files = list(Path(os.path.split(new_result_path)[0]).glob("**/*.*"))
            [shutil.copy(f, current_result_path) for f in new_files]

            if delete:
                rmtree(new_result_path.parent.absolute())
        else:
            print(f'New optimize result for {new_result["symbol"]} is not better than previous result, ignoring result')

    generate_overview_md()

    # add all changes &  push to git repository
    if results_changed and do_push:
        repo.git.add(all=True)
        repo.git.commit('-m', 'Better configs found during automated processing')
        print('Pushing result to repository')
        try:
            repo.git.push('origin')
        except Exception as e:
            print('Error pushing to git', e)

    print('Finished processing results')


def new_result_better(current, new) -> bool:
    if current is None:
        return True

    current_adg = current['result']['average_daily_gain']
    current_closest_bkr = current['result']['closest_bkr']

    new_adg = new['result']['average_daily_gain']
    new_closest_bkr = new['result']['closest_bkr']

    # if the new ADG is bigger than the current ADG, use it
    return new_adg > current_adg


def generate_overview_md():
    with open("summary.md", "w") as summary:
        summary.write('| exchange | symbol | version | market_type | adg | closest_bkr | long | short |\n'
                      '|----------|--------|---------|-------------| --- | ----------- | ---- | ----- |\n')

        p = Path('configs')
        result_paths = list(p.glob('**/result.json'))
        for result_path in result_paths:
            try:
                result = json.load(open(result_path, encoding='utf-8'))
                summary.write(f'| {result["exchange"]} | {result["symbol"]} | 4.0.0 | {result["market_type"]} | {result["result"]["average_daily_gain"]} | {result["result"]["closest_bkr"]} | {result["do_long"]} | {result["do_shrt"]} |\n')
            except Exception as e:
                print('failed to load result file', result_path, e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Optimize', description='Optimize passivbot config.')
    parser.add_argument('-v', '--version', type=str, required=True, dest='version',
                        default=None,
                        help='The version of the config files being processed')
    parser.add_argument('-d', '--delete', required=False, dest='delete',
                        default=False, help='Indicates if the folders that have been processed need to be deleted')
    parser.add_argument('-p', '--push', required=False, dest='push',
                        default='True', help='Setting to define if result should be pushed to git or not')
    parser.add_argument('-s', '--source', type=str, required=True, dest='source',
                        default='./backtests',
                        help='The root folder to use, defaults to ./backtests')
    args = parser.parse_args()
    process_candidate_configs(args.source, args.version, args.delete == 'True', args.push == 'True')
