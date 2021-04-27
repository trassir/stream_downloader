#!/usr/bin/python3

import urllib.request
import subprocess
from argparse import ArgumentParser
from pathlib import Path
import shutil
import re
from typing import List
from uuid import uuid4 as uuid

from tqdm import tqdm

"""
E.G: "https://r4---sn-gqn-p5ns.googlevideo.com/videoplayback?expire=1603041842& ..... 2.20201016.02.00&sq="
The sound link should contain: &mime=audio in it.
"""

SEC_PER_PART = 5
TMP_DIR_NAME = '_tmp_ytsd'


def download_stream(video_url: str,
                    save_filepath: Path,
                    video_len_hours: float = .25,
                    re_encode: bool = False):
    tmp_dir = _prepare_tmp_file_tree(save_filepath)

    videos = _download(video_url, video_len_hours, tmp_dir)
    videos = _re_encode(videos, tmp_dir) if re_encode else videos
    print('Filtering invalid videos...')
    videos = _filter_valid_video(videos)
    print('Concatenating videos...')
    _concat(videos, save_filepath, tmp_dir)
    _cleanup_tmp_file_tree(tmp_dir)


def _prepare_tmp_file_tree(save_filepath: Path):
    tmp_dir = save_filepath.parent / f'{TMP_DIR_NAME}_{uuid().hex}'
    _cleanup_tmp_file_tree(tmp_dir)
    tmp_dir.mkdir(parents=True)
    return tmp_dir


def _cleanup_tmp_file_tree(tmp_dir):
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)


def _download(video_url: str,
              video_len_hours: float,
              tmp_dir: Path) -> List[Path]:
    url, current_part = _parse_video_url(video_url)
    n_parts = int(video_len_hours * 3600 / SEC_PER_PART)
    begin, end = max(1, current_part - n_parts + 1 * bool(n_parts)), current_part

    result = []
    vid_dir = tmp_dir / 'videos'
    vid_dir.mkdir(parents=True)

    for part in tqdm(range(begin, end + 1),
                     desc='Downloading video parts of the stream: '):
        vid_out = vid_dir / f'{part}.mp4'
        try:
            urllib.request.urlretrieve(f'{url}{part}', vid_out)
            result.append(vid_out)
        except Exception as e:
            print(f'Unable to download part {part}, skipping it: {e}')
            continue

    return result


def _parse_video_url(url):
    rexp = re.compile(r'^(.+?&sq=)(\d+)&')
    match = rexp.match(url)
    if match is None:
        raise ValueError(f'Wrong video url format \n{url}\n\n')
    return match.group(1), int(match.group(2))


def _re_encode(videos: List[Path],
               tmp_dir: Path,
               rm_processed: bool = True) -> List[Path]:
    re_enc_dir = tmp_dir / 'fixed'
    re_enc_dir.mkdir(parents=True)
    result = []

    for video in tqdm(videos, desc='Re-encoding video parts of the stream: '):
        vid_out = re_enc_dir / video.name
        process = subprocess.Popen(
            _make_ffmpeg_re_encode_cmd(video, vid_out),
            stdout=subprocess.PIPE,
        )
        process.communicate()
        if rm_processed:
            video.unlink()
        if process.returncode != 0:
            print(f'Unable to re-encode {video}, skipping it')
            continue
        result.append(vid_out)

    return result


def _make_ffmpeg_re_encode_cmd(in_: Path, out: Path):
    return f'ffmpeg -hide_banner -loglevel error -i {in_} -c copy {out}'.split()


def _filter_valid_video(videos: List[Path]) -> List[Path]:
    def is_valid(vid: Path):
        cmd = _make_ffprobe_cmd(vid)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        process.communicate()
        if process.returncode != 0:
            print(f'Invalid video {vid}, skipping it')
            return False
        return True
    return list(filter(is_valid, videos))


def _make_ffprobe_cmd(vid: Path):
    return f'ffprobe -loglevel warning {vid.absolute()}'.split()


def _concat(videos: List[Path], save_filepath: Path, tmp_dir: Path):
    list_filepath = tmp_dir / 'list.txt'
    with open(list_filepath, 'w') as f_out:
        f_out.write('\n'.join(f'file \'{f.absolute()}\'' for f in videos))

    process = subprocess.Popen(
        _make_ffmpeg_concat_cmd(list_filepath, save_filepath),
        stdout=subprocess.PIPE
    )
    process.communicate()
    if process.returncode != 0:
        print('Unable to concat files')
    else:
        print(f'DONE! Saved to {save_filepath}')


def _make_ffmpeg_concat_cmd(list_filepath: Path, save_filepath: Path):
    cmd = 'ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i {} -c copy {}'
    return cmd.format(list_filepath, save_filepath).split()


arg_parser = ArgumentParser('Download youtube video-stream for last hours')
arg_parser.add_argument('--video_url', type=str)
arg_parser.add_argument('--save', type=Path, help='Filepath to save video')
arg_parser.add_argument('--download_last_hours', type=float, default=.25,
                        help='downloads stream for last given hours')
arg_parser.add_argument('--re_encode', type=int, default=1)


if __name__ == '__main__':
    args = arg_parser.parse_args()
    download_stream(args.video_url, args.save, args.download_last_hours, args.re_encode)
