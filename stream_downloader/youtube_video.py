from argparse import ArgumentParser
from pathlib import Path
import logging
from enum import Enum
from multiprocessing import Process
from multiprocessing import RLock, freeze_support

from tqdm import tqdm
import pafy
import youtube_dl


logging.getLogger('urllib3').setLevel(logging.ERROR)


class DownloadBackend(str, Enum):
    PAFY = 'pafy'
    YTDL = 'ytdl'


def main():
    arg_parser = ArgumentParser('Downloading videos from youtube')
    arg_parser.add_argument('--urls', type=str, nargs='+',
                            help='space separated youtube video URLs')
    arg_parser.add_argument('--result_dir', type=Path,
                            help='path to save downloaded videos')
    arg_parser.add_argument('--result_files', type=str, nargs='+',
                            help='space separated file names to save videos')
    arg_parser.add_argument('--backend', type=DownloadBackend,
                            default=DownloadBackend.PAFY,
                            help='Lib to save video. Possible options: pafy, ytdl')
    args = arg_parser.parse_args()
    assert args.urls is not None, 'Specify urls to download'
    assert args.result_dir is not None, 'Specify dir to save videos'
    assert args.result_files is not None, 'Specify output video filenames'
    assert len(args.urls) == len(args.result_files), \
        'Number of videos should be equal to the number of output files'
    args.result_dir.mkdir(parents=True, exist_ok=True)
    freeze_support()  # for Windows support
    tqdm.set_lock(RLock())  # for managing output contention
    processes = []
    for idx, (url, filename) in enumerate(zip(args.urls, args.result_files)):
        p = Process(
            target=download_video,
            args=(url, args.result_dir / filename, idx, args.backend)
        )
        p.start()
        processes.append(p)
    for p in processes:
        p.join()


def download_video(url: str,
                   save_path: Path,
                   proc_idx: int,
                   backend: DownloadBackend):
    tqdm.set_lock(tqdm.get_lock())
    log_msg, close = make_tqdm_logger(
        proc_idx,
        prefix=f'{save_path.stem} ({backend.name})'
    )
    if backend == DownloadBackend.PAFY:
        downloader = pafy_download
    elif backend == DownloadBackend.YTDL:
        downloader = ytdl_download
    else:
        assert False
    try:
        filename = downloader(url, save_path, log_msg)
        msg = f'Downloaded'
        if filename.is_file():
            msg += f'. File size: {int(b_to_mb(filename.stat().st_size))} MB'
        log_msg(msg)
    except Exception as e:
        log_msg(f'Unable to download {save_path}: {e}')
    # close()


def make_tqdm_logger(position: int, prefix: str = None):
    prefix = '' if prefix is None else f'{prefix}: '

    def with_prefix(msg):
        return f'{prefix}{msg}'

    log = tqdm(position=position,
               bar_format='{desc}',
               desc=with_prefix('starting download...'))
    max_msg_len = [0]

    def log_msg(msg, prefix=True):
        msg = with_prefix(msg) if prefix else msg
        if len(msg) > max_msg_len[0]:
            max_msg_len[0] = len(msg)
        log.set_description_str(f'{msg: <{max_msg_len[0]}}')
    return log_msg, log.close


def b_to_mb(n_bytes) -> float:
    return n_bytes / 2**20


def b_to_kb(n_bytes) -> float:
    return n_bytes / 2**10


def get_progress_string(downloaded_ratio: float,
                        speed_kbps: float,
                        eta_sec: float,
                        total_bytes: float):
    def apply_if_not_none(value, fun, fallback='unknown'):
        result = fallback
        if value is not None:
            result = fun(value)
        return result
    downloaded_ratio = apply_if_not_none(
        downloaded_ratio, lambda v: f'{int(v * 100):0.2f}%'
    )
    speed_kbps = apply_if_not_none(
        speed_kbps, lambda v: f'{int(speed_kbps)} kbps', 'unknown speed'
    )
    eta_sec = apply_if_not_none(eta_sec, lambda v: f'{int(v)} sec')
    total_bytes = apply_if_not_none(
        total_bytes, lambda v: f'{int(b_to_mb(v))} MB'
    )
    return f'{downloaded_ratio} {speed_kbps} ETA {eta_sec} total {total_bytes}'


def pafy_download(url: str, output: Path, log_msg) -> Path:
    video = pafy.new(url)
    best = video.getbestvideo()
    filepath = output.parent / f'{output.stem}.{best.extension}'
    callback = _mk_pafy_callback(log_msg)
    result = best.download(filepath=filepath, quiet=True, callback=callback)
    return Path(result)


def _mk_pafy_callback(log_msg):
    def callback(bytes_total: int,
                 bytes_downloaded: int,
                 downloaded_ratio: float,
                 rate: float,
                 eta_sec: float):
        log_msg(get_progress_string(
            downloaded_ratio=downloaded_ratio,
            speed_kbps=rate,
            eta_sec=eta_sec,
            total_bytes=bytes_total
        ))
    return callback


def ytdl_download(url: str, output: Path, log_msg) -> Path:
    class Logger(object):
        def debug(self, msg):
            pass

        def warning(self, msg):
            pass

        def error(self, msg):
            log_msg(msg)

    def hook(d):
        status = d['status']
        if status == 'finished':
            log_msg('converting...')
        elif status == 'downloading':
            total_bytes = d.get('total_bytes')
            if total_bytes:
                downloaded_ratio = d['downloaded_bytes'] / total_bytes
            else:
                downloaded_ratio = None
            log_msg(get_progress_string(
                downloaded_ratio=downloaded_ratio,
                speed_kbps=None if d['speed'] is None else b_to_kb(d['speed']),
                eta_sec=d['eta'],
                total_bytes=total_bytes or 0
            ))

    opts = dict(
        logger=Logger(),
        progress_hooks=[hook],
        outtmpl=str(output.parent / f'{output.stem}.%(ext)s'),
        verbose=False,
    )
    with youtube_dl.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = Path(ydl.prepare_filename(info))
    return filename


if __name__ == '__main__':
    main()
