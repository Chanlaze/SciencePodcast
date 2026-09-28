# 科學新知｜音頻版

Podcast feed: https://chanlaze.github.io/SciencePodcast/feed.xml

The three most recent complete shows (2026-09-10, 2026-09-17, and 2026-09-24) are available as chaptered MP3 files in `podcasts/`. Each episode combines the original four YouTube parts in order. `chapters/` contains Podcasting 2.0 chapter files, and `cover.jpg` is a podcast-size rendering of the supplied `cover-original.png`.

The audio and show originate from [Science Frontier's YouTube playlist](https://www.youtube.com/playlist?list=PL0jaUPVBk3akYF-CYI6k6VY6j5do3XgHq). This repository is an independent audio feed, not the original channel.

For the daily update, install `yt-dlp` and `imageio-ffmpeg` into `.tools/` and run `python check_new_episodes.py`. It prints `NO_NEW_COMPLETE_EPISODES` until all four parts of a newer dated show are available. For each new show, it downloads the source audio into the ignored `parts/` directory and creates one four-chapter MP3 without rebuilding older episodes. Add a concise topic title covering the four parts to `episode_titles.json`, then run `python build_feed.py`. Verify the feed and new audio before committing and pushing the changed files to GitHub.
