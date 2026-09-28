"""Download newly completed four-part shows from the Science Frontier playlist."""

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
PLAYLIST = "https://www.youtube.com/playlist?list=PL0jaUPVBk3akYF-CYI6k6VY6j5do3XgHq"
LIVE_FEED = "https://chanlaze.github.io/SciencePodcast/feed.xml"
PART_PATTERN = re.compile(r"(20\d{2}-\d{2}-\d{2})\s+Part\s*([1-4])\b", re.I)


def main() -> None:
    sys.path.insert(0, str(ROOT / ".tools"))
    import yt_dlp

    with yt_dlp.YoutubeDL({"extract_flat": "in_playlist", "skip_download": True, "quiet": True, "ignoreerrors": True}) as ydl:
        playlist = ydl.extract_info(PLAYLIST, download=False)
    if not playlist or not playlist.get("entries"):
        raise RuntimeError("Could not read the YouTube playlist")

    shows = {}
    for entry in playlist["entries"]:
        if not entry:
            continue
        match = PART_PATTERN.search(entry.get("title") or "")
        if not match:
            continue
        date, part = match.group(1), int(match.group(2))
        shows.setdefault(date, {})[part] = entry

    with urllib.request.urlopen(LIVE_FEED, timeout=30) as response:
        live_xml = ET.fromstring(response.read())
    published = [
        guid.text.removeprefix("science-frontier-")
        for item in live_xml.find("channel").findall("item")
        if (guid := item.find("guid")) is not None and guid.text
    ]
    if not published:
        raise RuntimeError("The live podcast feed has no published episodes")
    newest = max(published, default="0000-00-00")
    new_shows = {date: parts for date, parts in sorted(shows.items()) if date > newest and set(parts) == {1, 2, 3, 4}}
    if not new_shows:
        print("NO_NEW_COMPLETE_EPISODES")
        return

    (ROOT / "parts").mkdir(exist_ok=True)
    for date, parts in new_shows.items():
        for number in range(1, 5):
            entry = parts[number]
            video_id = entry.get("id")
            if not video_id:
                raise RuntimeError(f"Missing video ID for {date} Part {number}")
            template = str(ROOT / "parts" / f"{date}-part{number}-%(id)s.%(ext)s")
            with yt_dlp.YoutubeDL({"format": "bestaudio", "outtmpl": template, "writeinfojson": True, "overwrites": False, "noplaylist": True, "quiet": True}) as ydl:
                result = ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                if result != 0:
                    raise RuntimeError(f"Download failed for {date} Part {number}: {video_id}")

    subprocess.run([sys.executable, str(ROOT / "build_podcast.py")], check=True)
    audio_bytes = sum(p.stat().st_size for p in (ROOT / "podcasts").glob("science-frontier-*.mp3"))
    if audio_bytes > 900 * 1024 * 1024:
        raise RuntimeError("Podcast audio is approaching GitHub Pages' 1 GB site limit; choose another GitHub hosting layout before publishing more episodes")
    summary = {
        date: [parts[number]["title"] for number in range(1, 5)]
        for date, parts in new_shows.items()
    }
    print("NEW_COMPLETE_EPISODES " + json.dumps(summary, ensure_ascii=False))
    print("Add a short four-topic title for each new date to episode_titles.json, then run python build_feed.py and publish the changed files.")


if __name__ == "__main__":
    main()
