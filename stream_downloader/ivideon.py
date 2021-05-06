from time import sleep
import base64
from argparse import ArgumentParser
from pathlib import Path
import json
from datetime import datetime, timedelta
import logging
from multiprocessing import Process

from tqdm import tqdm
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver import ActionChains

from utils import (init_driver, prepare_tmp_file_tree, cleanup_tmp_file_tree,
                   concat_videos)

logging.getLogger('urllib3').setLevel(logging.ERROR)

TMP_DIR_NAME = '_tmp_ivsd'


def download_video(url: str, save_path: Path, proc_idx: int):
    tmp_dir = prepare_tmp_file_tree(tmp_parent=save_path.parent,
                                    tmp_dir_basename=TMP_DIR_NAME)

    def with_prefix(msg):
        return f'{save_path.name}: {msg}'

    log = tqdm(total=0,
               position=proc_idx,
               bar_format='{desc} {elapsed}',
               desc=with_prefix('waiting for video chunks...'))

    def log_msg(msg, prefix=True):
        log.set_description_str(with_prefix(msg) if prefix else msg)

    try:
        dump_dir = tmp_dir / 'dump'
        dump_dir.mkdir(parents=True)

        dumped = []
        driver = init_driver()
        for idx, (event, body) in enumerate(get_response_with_video(driver, url)):
            body = body['body']
            out = dump_dir / f'{idx}.ts'
            try:
                dump_body(body, out)
                dumped.append(out)
                log_msg(f'downloaded {idx + 1} chunks')
            except Exception as e:
                log_msg(f'unable to download {out.name}. {e}')
    except KeyboardInterrupt:
        driver.quit()
        if len(dumped):
            log_msg(f'concatenating {len(dumped)} video files')
            try:
                ok = concat_videos(dumped, save_path, tmp_dir)
                if ok:
                    log_msg(f'DONE! Saved to {save_path}')
                else:
                    log_msg(f'unable to concat videos {ok}')
            except Exception as e:
                log_msg(
                    f'unable to concat videos: {e}. '
                    f'All downloaded video parts could be found in {dump_dir}'
                )
                log.close()
                return
        else:
            log_msg('nothing to concat :(')
        cleanup_tmp_file_tree(tmp_dir)
        log.close()


def get_response_with_video(driver, url, reload_every_sec=10*60):
    driver.get(url)
    run_video_if_needed(driver)
    target_content_type = 'video/MP2T'
    
    def get_content_type(response):
        return response['params'].get('headers', {}).get('content-type')

    def parse_response(raw_event):
        return json.loads(raw_event['message'])['message']
    
    def is_video(event):
        return (
            'Network.responseReceived' in event['method']
            and get_content_type(event) == target_content_type
        )
    
    def get_body(response):
        try:
            result = driver.execute_cdp_cmd(
                'Network.getResponseBody',
                {'requestId': response['params']['requestId']}
            )
        except WebDriverException:
            result = None
        return result
    timeout_between_reloads = timedelta(seconds=reload_every_sec)
    timeout_between_checks_sec = 5
    next_reload = datetime.now() + timeout_between_reloads
    while True:
        now = datetime.now()
        if now >= next_reload:
            next_reload = now + timeout_between_reloads
            driver.get(url)
        sleep(timeout_between_checks_sec)
        logs = driver.get_log('performance')
        for item in filter(is_video, map(parse_response, logs)):
            body = get_body(item)
            if body is not None:
                yield item, body


def run_video_if_needed(driver):
    try:
        frame = driver.find_element_by_class_name('iv-tv-embed-iframe')
        driver.switch_to_frame(frame)
        play = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable(
                (By.CLASS_NAME, 'b-embed-btn-play-image')
            )
        )
        ActionChains(driver).move_to_element(play).click().perform()
    except:
        return


def dump_body(body, out):
    res = base64.b64decode(body)
    with open(out, 'wb') as f:
        f.write(res)


def main():
    arg_parser = ArgumentParser('Downloading streams from tv.ivideon.com')
    arg_parser.add_argument('--urls', type=str, nargs='+',
                            help='space separated ivideon video URLs')
    arg_parser.add_argument('--result_dir', type=Path,
                            help='path to save downloaded videos')
    arg_parser.add_argument('--result_files', type=str, nargs='+',
                            help='space separated file names to save ivideon videos')

    args = arg_parser.parse_args()
    assert args.urls is not None, 'Specify urls to download'
    assert args.result_dir is not None, 'Specify dir to save videos'
    assert args.result_files is not None, 'Specify output video filenames'
    assert len(args.urls) == len(args.result_files), \
        'Number of videos should be equal to the number of output files'
    args.result_dir.mkdir(parents=True, exist_ok=True)
    sep = f'\n{"=" * 80}\n'
    tqdm.write(
        f'{sep}\tPress Ctrl+C to stop downloading chunks '
        f'and save output video files{sep}',
    )
    processes = []
    for idx, (url, filename) in enumerate(zip(args.urls, args.result_files)):
        p = Process(target=download_video,
                    args=(url, args.result_dir / filename, idx))
        p.start()
        processes.append(p)
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
