import argparse
import json
import os
import shutil
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


def process_candidate_configs(base_dir, version):
    print('Processing new results...')
    repo = Repo('./')
    repo.git.pull('origin')
    do_push = False

    p = Path(base_dir)
    result_paths = list(p.glob('**/plots/**/result.json'))
    for new_result_path in result_paths:
        try:
            new_result = json.load(open(new_result_path, encoding='utf-8'))
        except Exception as e:
            raise Exception('failed to load result file', new_result_path, e)

        current_result_path = Path(f"configs/live/{version}/{new_result['symbol']}/{new_result['market_type']}")
        current_result_path.mkdir(parents=True, exist_ok=True)
        current_result = None
        if len(list(current_result_path.glob("result.json"))) > 0:
            try:
                current_result = json.load(open(f"{current_result_path}/result.json", encoding='utf-8'))
            except Exception as e:
                raise Exception('failed to load result file', new_result_path, e)

        if new_result_better(current_result, new_result):
            do_push = True
            print(f'Replacing configuration for {new_result["symbol"]}')
            if current_result_path.exists():
                # remove all existing files
                existing_files = list(Path(current_result_path).glob("**/*.*"))
                [os.remove(f) for f in existing_files]

            # copy the new files
            new_files = list(Path(os.path.split(new_result_path)[0]).glob("**/*.*"))
            [shutil.copy(f, current_result_path) for f in new_files]
        else:
            print(f'New optimize result for {new_result["symbol"]} is not better than previous result, ignoring result')

    rmtree(base_dir)

    # add all changes &  push to git repository
    if do_push:
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='Optimize', description='Optimize passivbot config.')
    parser.add_argument('-v', '--version', type=str, required=True, dest='version',
                        default=None,
                        help='The version of the config files being processed')
    args = parser.parse_args()
    process_candidate_configs('/Users/erwinhoeckx/passivbot_configs/backtests', args.version)
