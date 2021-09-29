# Installation
1. Chrome browser should be installed
2. ```python3 -m pip install git+https://github.com/trassir/stream_downloader```
3. Install `ffmpeg`
# Usage
## Ivideon
```
ivideon_stream_downloader
--urls https://tv.ivideon.com/camera/xxx/111/ https://tv.ivideon.com/camera/yyy/111/
--result_dir /path/to/save/dir
--result_files 1.mp4 2.mp4
--move_request_dir
```
`urls` - space separated ivideon urls

`result_dir` - directory to save output

`result_files` - space separated filenames wrt urls

`move_request_dir` - enabling this flag will result in moving all temporary files into `result_dir`. Otherwise, some temporary data will be stored in home dir. It is strongly recommended to enable the flag if you don't have sufficient space in home dir.
## Youtube
```
youtube_stream_downloader
--urls https://www.youtube.com/watch?v=video-1-id https://www.youtube.com/watch?v=video-2-id
--result_dir /path/to/save/dir
--result_files 1.mp4 2.mp4
--download_last_hours 12
--re_encode
--download-threads 4
--quality_changed_timeout_sec 2
```
`urls` - space separated youtube urls

`result_dir` - directory to save output

`result_files` - space separated filenames wrt urls

`download_last_hours` - hours to download

`re_encode` - re-encodes video chunks downloaded from yt

`download-threads` - number of threads to download stream chunks

`quality_changed_timeout_sec` - timeout between switching to the best video quality and starting to download.