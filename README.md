# 科學新知｜音頻版

Podcast feed: https://chanlaze.github.io/SciencePodcast/feed.xml

Complete 科學新知 shows from 2026-09-10 onward are available as chaptered MP3 files in `podcasts/`. Each episode combines the original four YouTube parts in order. `chapters/` contains Podcasting 2.0 chapter files, and `cover.jpg` is a podcast-size rendering of the supplied `cover-original.png`.

The audio and show originate from [Science Frontier's YouTube playlist](https://www.youtube.com/playlist?list=PL0jaUPVBk3akYF-CYI6k6VY6j5do3XgHq). This repository is an independent audio feed, not the original channel.

For the daily update, install `yt-dlp`, `yt-dlp-ejs`, and `imageio-ffmpeg` into `.tools/` and make Node.js available. Run `python check_new_episodes.py`. It prints `NO_NEW_COMPLETE_EPISODES` until all four parts of a newer dated show are available. For each new show, it downloads the source media into the ignored `parts/` directory and creates one four-chapter MP3 without rebuilding older episodes. Add a concise topic title covering the four parts to `episode_titles.json`, then run `python build_feed.py`. Verify the feed and new audio before committing and pushing the changed files to GitHub.

From 2026-10-26 onward, the same feed also accepts new single-video episodes from [科學回憶錄](https://www.youtube.com/playlist?list=PL0jaUPVBk3an6l25NwqOV4KYLf37GOKMp). Run `python check_memoir_episodes.py` during the daily check. It excludes the existing playlist backlog and prints `NO_NEW_MEMOIR_EPISODES` when there is nothing new. A new video becomes a one-chapter `science-memoir-YYYY-MM-DD.mp3`; add its concise topic title to `episode_titles.json` under `memoir-YYYY-MM-DD`, then run `python build_feed.py` and verify the feed and audio before publishing. Both series share `cover.jpg` and the same RSS feed.
