import shutil
from pathlib import Path
from uuid import uuid4 as uuid
from typing import List
import subprocess


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
        if process.returncode != 0:
            print('Unable to concat files')
        else:
            print(f'DONE! Saved to {save_filepath}')


def make_ffmpeg_concat_cmd(list_filepath: Path, save_filepath: Path):
    cmd = 'ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i {} -c copy {}'
    return cmd.format(list_filepath, save_filepath).split()

