"""Add only new, single-video Science Memoir episodes to the podcast workspace."""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import date as calendar_date
from pathlib import Path
from xml.etree import ElementTree as ET

from build_podcast import escaped, mp3_chapter_count


ROOT = Path(__file__).resolve().parent
PLAYLIST = "https://www.youtube.com/playlist?list=PL0jaUPVBk3an6l25NwqOV4KYLf37GOKMp"
LIVE_FEED = "https://chanlaze.github.io/SciencePodcast/feed.xml"
START_DATE = "2026-10-26"  # The user requested future releases only; do not backfill.
DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2})-?(\d{2})-?(\d{2})(?!\d)")


def episode_date(title: str) -> str | None:
    if "科學回憶錄" not in title:
        return None
    match = DATE_PATTERN.search(title)
    if not match:
        return None
    try:
        return calendar_date(*map(int, match.groups())).isoformat()
    except ValueError:
        return None


def main() -> None:
    sys.path.insert(0, str(ROOT / ".tools"))
    import imageio_ffmpeg
    import yt_dlp

    with yt_dlp.YoutubeDL({"extract_flat": "in_playlist", "skip_download": True, "quiet": True, "ignoreerrors": True}) as ydl:
        playlist = ydl.extract_info(PLAYLIST, download=False)
    if not playlist or not playlist.get("entries"):
        raise RuntimeError("Could not read the Science Memoir YouTube playlist")

    with urllib.request.urlopen(LIVE_FEED, timeout=30) as response:
        channel = ET.fromstring(response.read()).find("channel")
    if channel is None:
        raise RuntimeError("The live podcast feed has no channel")
    published = {item.findtext("guid") for item in channel.findall("item")}
    combined_dates = {
        item.findtext("guid").removeprefix("science-frontier-")
        for item in channel.findall("item")
        if item.findtext("guid") and "science-combined-" in (item.find("enclosure").get("url", "") if item.find("enclosure") is not None else "")
    }

    candidates = {}
    for entry in playlist["entries"]:
        if not entry:
            continue
        title = entry.get("title") or ""
        date = episode_date(title)
        if date and date >= START_DATE and date not in combined_dates and f"science-memoir-{date}" not in published:
            if date in candidates and candidates[date].get("id") != entry.get("id"):
                raise RuntimeError(f"Multiple Science Memoir videos are dated {date}; review before publishing")
            candidates[date] = entry
    if not candidates:
        print("NO_NEW_MEMOIR_EPISODES")
        return

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    parts_dir = ROOT / "parts"
    output_dir = ROOT / "podcasts"
    parts_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    completed = {}
    for date, entry in sorted(candidates.items()):
        video_id = entry.get("id")
        if not video_id:
            raise RuntimeError(f"Missing Science Memoir video ID for {date}")
        stem = f"memoir-{date}-{video_id}"
        template = str(parts_dir / f"memoir-{date}-%(id)s.%(ext)s")
        options = {"format": "bestaudio/best", "outtmpl": template, "writeinfojson": True,
                   "overwrites": False, "noplaylist": True, "quiet": True, "noprogress": True,
                   "extractor_args": {"youtube": {"player_client": ["android"]}}}
        if node := shutil.which("node"):
            options["js_runtimes"] = {"node": {"path": node}}
        for attempt in range(3):
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    result = ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                if result != 0:
                    raise RuntimeError(f"Download failed: {video_id}")
                break
            except yt_dlp.utils.DownloadError:
                if attempt == 2:
                    raise
                time.sleep(2)

        info_path = parts_dir / f"{stem}.info.json"
        info = json.loads(info_path.read_text(encoding="utf-8"))
        audio = next((parts_dir / f"{stem}.{ext}" for ext in ("webm", "m4a", "opus", "mp3", "mp4")
                      if (parts_dir / f"{stem}.{ext}").is_file()), None)
        if audio is None:
            raise RuntimeError(f"Downloaded Science Memoir audio missing for {date}")
        target = output_dir / f"science-memoir-{date}.mp3"
        if not target.is_file() or target.stat().st_size == 0:
            topic = info["title"].split("科學回憶錄", 1)[-1].lstrip("：: -").split("|", 1)[0].strip()
            chapter_title = topic[:45].rstrip("，。； ")
            end = round(float(info["duration"]) * 1000)
            metadata = output_dir / f"memoir-{date}.ffmetadata"
            metadata.write_text("\n".join([
                ";FFMETADATA1", f"title={escaped('科學回憶錄 ' + date)}",
                "artist=Science Frontier (科學新知)", "album=科學回憶錄", f"date={date}",
                "[CHAPTER]", "TIMEBASE=1/1000", "START=0", f"END={end}",
                f"title={escaped(chapter_title)}", "",
            ]), encoding="utf-8")
            temp = output_dir / f".building-memoir-{date}.mp3"
            subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(audio),
                            "-i", str(metadata), "-map", "0:a:0", "-map_metadata", "1",
                            "-map_chapters", "1", "-c:a", "libmp3lame", "-b:a", "80k",
                            "-ac", "1", "-y", str(temp)], check=True)
            if mp3_chapter_count(temp) != 1:
                raise ValueError(f"{date}: encoded Science Memoir MP3 does not contain one chapter")
            os.replace(temp, target)
            print(f"Created {target.name} ({target.stat().st_size / 1024**2:.1f} MiB)")
        completed[date] = {"title": info["title"], "video": info["webpage_url"]}

    subprocess.run([sys.executable, str(ROOT / "build_combined.py")], check=True)
    audio_bytes = sum(p.stat().st_size for p in output_dir.glob("science-*.mp3"))
    if audio_bytes > 900 * 1024 * 1024:
        raise RuntimeError("Podcast audio is approaching GitHub Pages' 1 GB site limit; review hosting before publishing")
    print("NEW_MEMOIR_EPISODES " + json.dumps(completed, ensure_ascii=False))
    print("Add a concise Traditional Chinese topic title for each new date under memoir-YYYY-MM-DD in episode_titles.json, then run python build_feed.py and publish.")


if __name__ == "__main__":
    main()
