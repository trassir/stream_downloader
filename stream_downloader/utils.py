import shutil
from pathlib import Path
from uuid import uuid4 as uuid
from typing import List, Union
import subprocess

from seleniumwire import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller


def prepare_tmp_file_tree(tmp_parent: Path, tmp_dir_basename: str):
    tmp_dir = tmp_parent / f'{tmp_dir_basename}_{uuid().hex}'
    cleanup_tmp_file_tree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    return tmp_dir


def cleanup_tmp_file_tree(tmp_dir):
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)


def concat_videos(videos: List[Path], save_filepath: Path, tmp_dir: Path):
    if len(videos):
        list_filepath = tmp_dir / 'list.txt'
        with open(list_filepath, 'w') as f_out:
            f_out.write('\n'.join(f'file \'{f.absolute()}\'' for f in videos))

        process = subprocess.Popen(
            make_ffmpeg_concat_cmd(list_filepath, save_filepath),
            stdout=subprocess.PIPE
        )
        process.communicate()
        return process.returncode == 0


def make_ffmpeg_concat_cmd(list_filepath: Path, save_filepath: Path):
    cmd = 'ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i {} -c copy {} -nostdin'
    return cmd.format(list_filepath, save_filepath).split()


def init_driver(headless=True,
                extensions_paths: Union[List[Path], None] = None,
                request_storage_base_dir: Union[Path, None] = None):
    chromedriver_autoinstaller.install()
    options = Options()
    options.headless = headless
    options.add_experimental_option('w3c', False)
    if (extensions_paths is not None
            and isinstance(extensions_paths, (list, tuple))):
        for ext in extensions_paths:
            options.add_extension(str(ext))
    cap = DesiredCapabilities.CHROME
    cap['loggingPrefs'] = {'performance': 'ALL'}
    kwargs = dict(
        desired_capabilities=cap,
        options=options
    )
    if request_storage_base_dir is not None:
        kwargs['seleniumwire_options'] = {
            'request_storage_base_dir': str(request_storage_base_dir)
        }
    driver = webdriver.Chrome(**kwargs)
    return driver
