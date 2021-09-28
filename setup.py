import version
from setuptools import setup, find_packages


def parse_requirements(filename: str):
    with open(filename, 'r') as f:
        lines = f.readlines()
    return [
        line.strip()
        for line in lines
        if line and not line.startswith('#')
    ]


setup(
    name='stream_downloader',
    version=version.__version__,
    install_requires=parse_requirements('./requirements.txt'),
    packages=find_packages(),
    url='https://github.com/trassir/stream_downloader',
    license='commercial',
    author='trassir',
    description='Downloading streams from youtube and ivideon',
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'ivideon_stream_downloader=stream_downloader.ivideon:main',
            'youtube_stream_downloader=stream_downloader.youtube:main',
            'youtube_video_downloader=stream_downloader.youtube_video:main',
        ]
    },
)
