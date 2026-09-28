# 科學新知｜音頻版

Podcast feed: https://chanlaze.github.io/SciencePodcast/feed.xml

The three most recent complete shows (2026-09-10, 2026-09-17, and 2026-09-24) are available as chaptered MP3 files in `podcasts/`. Each episode combines the original four YouTube parts in order. `chapters/` contains Podcasting 2.0 chapter files, and `cover.jpg` is a podcast-size rendering of the supplied `cover-original.png`.

The audio and show originate from [Science Frontier's YouTube playlist](https://www.youtube.com/playlist?list=PL0jaUPVBk3akYF-CYI6k6VY6j5do3XgHq). This repository is an independent audio feed, not the original channel.

To rebuild locally, install `yt-dlp` and `imageio-ffmpeg` into `.tools/`, download the source parts into `parts/`, then run `python build_podcast.py` and `python build_feed.py`.
