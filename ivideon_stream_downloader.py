import time
import base64
from argparse import ArgumentParser
from pathlib import Path
import json

from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options

from utils import prepare_tmp_file_tree, cleanup_tmp_file_tree, concat_videos

TMP_DIR_NAME = '_tmp_ivsd'


def process(url: str, save_path: Path):
    tmp_dir = prepare_tmp_file_tree(tmp_parent=save_path.parent,
                                    tmp_dir_basename=TMP_DIR_NAME)

    print(
        f'Press Ctrl+C to stop dumping *.ts files '
        f'and concat them into {save_path}'
    )
    try:
        dumped_log = tqdm(total=0, bar_format='{desc}')
        dump_dir = tmp_dir / 'dump'
        dump_dir.mkdir(parents=True)

        dumped = []
        for idx, (event, body) in enumerate(get_response_with_video(url)):
            date, body = event['params']['headers']['date'], body['body']
            out = dump_dir / f'{idx}.ts'
            try:
                dump_body(body, out)
                dumped.append(out)
                dumped_log.set_description_str(f'Dumped {out}: {date}')
            except Exception as e:
                dumped_log.set_description_str(f'Unable to dump {out}: {e}')
    except KeyboardInterrupt:
        if len(dumped):
            print(f'Concatenating {len(dumped)} video files')
            try:
                concat_videos(dumped, save_path, tmp_dir)
            except Exception as e:
                print(
                    f'Unable to concat videos: {e}. '
                    f'All downloaded video parts could be found in {dump_dir}'
                )
            else:
                cleanup_tmp_file_tree(tmp_dir)
        else:
            print('Nothing to concat :(')
            cleanup_tmp_file_tree(tmp_dir)


def get_response_with_video(url):
    driver = init_driver(url)
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
        return driver.execute_cdp_cmd(
            'Network.getResponseBody',
            {'requestId': response['params']['requestId']}
        )

    while True:
        time.sleep(5)
        logs = driver.get_log('performance')
        for item in filter(is_video, map(parse_response, logs)):
            yield item, get_body(item)
    driver.close()


def init_driver(url):
    options = Options()
    options.headless = True
    options.add_experimental_option('w3c', False)
    cap = DesiredCapabilities.CHROME
    cap['loggingPrefs'] = {'performance': 'ALL'}
    driver = webdriver.Chrome(desired_capabilities=cap, options=options)
    driver.get(url)
    return driver


def dump_body(body, out):
    res = base64.b64decode(body)
    with open(out, 'wb') as f:
        f.write(res)


arg_parser = ArgumentParser('Downloading streams from tv.ivideon.com')
arg_parser.add_argument('url', help='Stream url', type=str)
arg_parser.add_argument('save', help='Directory to save video', type=Path, default='.')


if __name__ == '__main__':
    args = arg_parser.parse_args()
    process(args.url, args.save)
