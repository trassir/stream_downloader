import re
import subprocess
import urllib.request
from argparse import ArgumentParser
from multiprocessing import Pool, cpu_count
from pathlib import Path
from time import sleep
from typing import List, Optional, Tuple

from tqdm import tqdm

from stream_downloader.utils import (prepare_tmp_file_tree, init_driver,
                                     cleanup_tmp_file_tree, concat_videos)

"""
E.G: "https://r4---sn-gqn-p5ns.googlevideo.com/videoplayback?expire=1603041842& ..... 2.20201016.02.00&sq="
The sound link should contain: &mime=audio in it.
"""

SEC_PER_PART = 5
TMP_DIR_NAME = '_tmp_ytsd'
URL_RE = re.compile(r'^(.+?&sq=)(\d+)&')


def download_stream(video_url: str,
                    save_filepath: Path,
                    video_len_hours: float = .25,
                    re_encode: bool = False,
                    download_threads: int = 8):
    tmp_dir = prepare_tmp_file_tree(tmp_parent=save_filepath.parent,
                                    tmp_dir_basename=TMP_DIR_NAME)
    try:
        video_url = _get_video_file_url(video_url)
        videos = _download(video_url, video_len_hours, tmp_dir, pool_size=download_threads)
        videos = _re_encode(videos, tmp_dir) if re_encode else videos
        videos = _filter_valid_video(videos)
        print('Concatenating videos...')
        concat_videos(videos, save_filepath, tmp_dir)
        cleanup_tmp_file_tree(tmp_dir)
    except KeyboardInterrupt:
        print('Keyboard interrupt, cleaning up...')
        cleanup_tmp_file_tree(tmp_dir)


def _get_video_file_url(url: str):
    print('Initializing driver...')
    adblock_filepath = Path(__file__).parent.absolute() / 'adblock.crx'
    driver = init_driver(headless=False, extensions_paths=[adblock_filepath])

    print(f'Connecting to {url}...')
    driver.get(url)

    input('Press any button when you are ready with quality')

    print('Picking video url...')
    target_content_types = ['video/mp4', 'video/webm']

    def is_target(request):
        return (
                'videoplayback' in request.path
                and request.response is not None
                and request.response.headers['Content-Type'] in target_content_types
                and URL_RE.match(request.url) is not None
        )

    target = None
    begin, end = 0, len(driver.requests)
    while True:
        for r in reversed(driver.requests[begin:end]):
            if is_target(r):
                target = r
                break
        else:
            begin, end = end, len(driver.requests)
            continue
        break
    driver.quit()
    return target.url


def _process_download(in_out: Tuple[str, Path],
                      retrieve_count: int = 20) -> Optional[Path]:
    retrieve_count = max(1, retrieve_count)
    url, vid_out = in_out
    for retrieve_idx in range(retrieve_count):
        try:
            _, msg = urllib.request.urlretrieve(url, vid_out)
            return vid_out
        except Exception as e:
            print(f'Unable to download part {vid_out.stem}: {e}. Trying for {retrieve_idx} time')
            sleep(1 + retrieve_idx)
    print(f'Skipped part {vid_out.stem}, unable to download')
    return None


def _download(video_url: str,
              video_len_hours: float,
              tmp_dir: Path,
              pool_size: int = 16) -> List[Path]:
    url, current_part = _parse_video_url(video_url)
    n_parts = int(video_len_hours * 3600 / SEC_PER_PART)
    begin, end = max(1, current_part - n_parts + 1 * bool(n_parts)), current_part

    vid_dir = tmp_dir / 'videos'
    vid_dir.mkdir(parents=True)

    input_output = [(f'{url}{part}', vid_dir / f'{part}.mp4')
                    for part in range(begin, end + 1)]

    with Pool(pool_size) as p:
        result = tqdm(p.imap(_process_download, input_output),
                      desc='Downloading video parts of the stream: ', total=len(input_output))
        result = [r for r in result if r is not None]

    return result


def _parse_video_url(url):
    match = URL_RE.match(url)
    if match is None:
        raise ValueError(f'Wrong video url format \n{url}\n\n')
    return match.group(1), int(match.group(2))


def _process_re_encode(in_out: Tuple[Path, Path],
                       rm_processed: bool = True) -> Optional[Path]:
    video, vid_out = in_out
    process = subprocess.Popen(
        _make_ffmpeg_re_encode_cmd(video, vid_out),
        stdout=subprocess.PIPE,
    )
    process.communicate()
    if rm_processed:
        video.unlink()
    if process.returncode != 0:
        print(f'Unable to re-encode {video}, skipping it')
        return None
    else:
        return vid_out


def _re_encode(videos: List[Path],
               tmp_dir: Path,
               pool_size: int = cpu_count()) -> List[Path]:
    re_enc_dir = tmp_dir / 'fixed'
    re_enc_dir.mkdir(parents=True)

    input_output = [(video, re_enc_dir / video.name) for video in videos]

    with Pool(pool_size) as p:
        result = tqdm(p.imap(_process_re_encode, input_output),
                      desc='Re-encoding video parts of the stream: ', total=len(input_output))
        result = [r for r in result if r is not None]

    return result


def _make_ffmpeg_re_encode_cmd(in_: Path, out: Path):
    return f'ffmpeg -hide_banner -loglevel error -i {in_} -c copy {out}'.split()


def _is_valid(vid: Path) -> bool:
    cmd = _make_ffprobe_cmd(vid)
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    process.communicate()
    if process.returncode != 0:
        print(f'Invalid video {vid}, skipping it')
        return False
    return True


def _filter_valid_video(videos: List[Path],
                        pool_size: int = cpu_count()) -> List[Path]:
    with Pool(pool_size) as p:
        result = tqdm(p.imap(_is_valid, videos),
                      desc='Filtering invalid videos: ', total=len(videos))
        result = [vid for valid, vid in zip(result, videos) if valid]

    return result


def _make_ffprobe_cmd(vid: Path):
    return f'ffprobe -loglevel warning {vid.absolute()}'.split()


def main():
    arg_parser = ArgumentParser('Download youtube video-stream for last hours')
    arg_parser.add_argument('video_url', type=str)
    arg_parser.add_argument('save', type=Path, help='Filepath to save video')
    arg_parser.add_argument('--download_last_hours', type=float, default=.25,
                            help='downloads stream for last given hours')
    arg_parser.add_argument('--re_encode', type=int, default=1)
    arg_parser.add_argument('--download-threads', type=int, default=4)

    args = arg_parser.parse_args()
    download_stream(args.video_url, args.save,
                    args.download_last_hours, args.re_encode, args.download_threads)


if __name__ == '__main__':
    main()
