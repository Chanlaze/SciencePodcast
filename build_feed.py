"""Create the public podcast feed, chapter files, and landing page."""

import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from build_podcast import mp3_chapter_count


ROOT = Path(__file__).resolve().parent
BASE = "https://chanlaze.github.io/SciencePodcast"
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
PODCAST = "https://podcastindex.org/namespace/1.0"
EPISODE_TITLES = json.loads((ROOT / "episode_titles.json").read_text(encoding="utf-8"))
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)
ET.register_namespace("podcast", PODCAST)


def tag(parent, name, value, **attributes):
    element = ET.SubElement(parent, name, attributes)
    element.text = str(value)
    return element


def main():
    sys.path.insert(0, str(ROOT / ".tools"))
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    memoir_audio = list((ROOT / "podcasts").glob("science-memoir-*.mp3"))
    has_memoir = bool(memoir_audio)
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    tag(channel, "title", "科學新知｜音頻版")
    tag(channel, "link", BASE + "/")
    description = "Science Frontier（科學新知）粵語科學新聞節目。每集集合原節目的四個部分，附章節導航。"
    if has_memoir:
        description += " 同時收錄科學回憶錄，每集一個科學故事。"
    tag(channel, "description", description)
    tag(channel, "language", "zh-HK")
    tag(channel, f"{{{ITUNES}}}author", "Science Frontier (科學新知)")
    summary = "每週粵語科學新聞：四個主題，合為一集。"
    if has_memoir:
        summary += " 另有科學回憶錄。"
    tag(channel, f"{{{ITUNES}}}summary", summary)
    tag(channel, f"{{{ITUNES}}}explicit", "false")
    tag(channel, f"{{{ITUNES}}}type", "episodic")
    ET.SubElement(channel, f"{{{ITUNES}}}category", text="Science")
    ET.SubElement(channel, f"{{{ITUNES}}}image", href=BASE + "/cover.jpg")
    image = ET.SubElement(channel, "image")
    tag(image, "url", BASE + "/cover.jpg")
    tag(image, "title", "科學新知｜音頻版")
    tag(image, "link", BASE + "/")
    ET.SubElement(channel, f"{{{ATOM}}}link", href=BASE + "/feed.xml", rel="self", type="application/rss+xml")

    cards = []
    chapter_dir = ROOT / "chapters"
    chapter_dir.mkdir(exist_ok=True)
    combined_dates = {audio.stem.removeprefix("science-combined-")
                      for audio in (ROOT / "podcasts").glob("science-combined-*.mp3")}
    audio_files = [(audio.stem.removeprefix("science-frontier-"), "frontier", audio)
                   for audio in (ROOT / "podcasts").glob("science-frontier-*.mp3")]
    audio_files += [(audio.stem.removeprefix("science-memoir-"), "memoir", audio)
                    for audio in memoir_audio]
    audio_files = [(date, series, audio) for date, series, audio in audio_files
                   if date not in combined_dates]
    audio_files += [(audio.stem.removeprefix("science-combined-"), "combined", audio)
                    for audio in (ROOT / "podcasts").glob("science-combined-*.mp3")]
    for date, series, audio in sorted(audio_files, reverse=True):
        if series in ("frontier", "combined"):
            part_info = {}
            for path in sorted((ROOT / "parts").glob("*.info.json")):
                if path.name.startswith(("000-", "memoir-")):
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                match = re.search(r"(20\d{2}-\d{2}-\d{2})\s+Part\s*([1-4])", data.get("title", ""), re.I)
                if match and match.group(1) == date:
                    part_info[int(match.group(2))] = data
            if set(part_info) != {1, 2, 3, 4}:
                raise ValueError(f"Missing source part for {date}")
        if series in ("memoir", "combined"):
            info_files = list((ROOT / "parts").glob(f"memoir-{date}-*.info.json"))
            if len(info_files) != 1:
                raise ValueError(f"Expected one Science Memoir source for {date}")
            memoir_info = json.loads(info_files[0].read_text(encoding="utf-8"))
            if "科學回憶錄" not in memoir_info.get("title", ""):
                raise ValueError(f"Science Memoir source title mismatch for {date}")

        probe = subprocess.run([ffmpeg, "-hide_banner", "-i", str(audio)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
        if not duration_match:
            raise ValueError(f"Cannot read duration for {audio}")
        hours, minutes, seconds = duration_match.groups()
        total_seconds = round(int(hours) * 3600 + int(minutes) * 60 + float(seconds))
        expected_chapters = {"frontier": 4, "memoir": 1, "combined": 5}[series]
        if mp3_chapter_count(audio) != expected_chapters:
            raise ValueError(f"Expected {expected_chapters} MP3 chapters in {audio}")

        chapters = []
        details = []
        if series in ("frontier", "combined"):
            start = 0
            for number in range(1, 5):
                data = part_info[number]
                topic = data["title"].split(":", 1)[-1].split("|", 1)[0].strip()
                if date == "2026-09-10" and number == 3:
                    short_topic = "氫氣星雲與伽碼射線"
                else:
                    short_topic = topic
                chapters.append({"startTime": start, "title": f"Part {number}: {short_topic}", "url": data["webpage_url"]})
                details.append(f"{number}. {topic} — {data['webpage_url']}")
                start += float(data["duration"])
            if series == "frontier":
                chapter_file = chapter_dir / f"{date}.json"
                title = f"科學新知 {date}｜{EPISODE_TITLES[date]}"
                guid = f"science-frontier-{date}"
        if series in ("memoir", "combined"):
            topic = memoir_info["title"].split("科學回憶錄", 1)[-1].lstrip("：: -").split("|", 1)[0].strip()
            memoir_start = start if series == "combined" else 0
            chapters.append({"startTime": memoir_start, "title": "科學回憶錄：" + topic if series == "combined" else topic,
                             "url": memoir_info["webpage_url"]})
            details.append(f"{topic} — {memoir_info['webpage_url']}")
            if series == "memoir":
                chapter_file = chapter_dir / f"memoir-{date}.json"
                title = f"科學回憶錄 {date}｜{EPISODE_TITLES['memoir-' + date]}"
                guid = f"science-memoir-{date}"
            else:
                chapter_file = chapter_dir / f"combined-{date}.json"
                title = f"科學新知與科學回憶錄 {date}｜{EPISODE_TITLES[date]}；{EPISODE_TITLES['memoir-' + date]}"
                guid = f"science-frontier-{date}"
        chapter_file.write_text(json.dumps({"version": "1.2.0", "chapters": chapters}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        episode = ET.SubElement(channel, "item")
        tag(episode, "title", title)
        tag(episode, "description", "\n".join(details))
        tag(episode, "link", BASE + "/")
        tag(episode, "guid", guid, isPermaLink="false")
        published = datetime.fromisoformat(date).replace(hour=12, tzinfo=timezone(timedelta(hours=8)))
        tag(episode, "pubDate", format_datetime(published))
        ET.SubElement(episode, "enclosure", url=BASE + "/podcasts/" + audio.name, length=str(audio.stat().st_size), type="audio/mpeg")
        tag(episode, f"{{{ITUNES}}}author", "Science Frontier (科學新知)")
        tag(episode, f"{{{ITUNES}}}duration", str(total_seconds))
        tag(episode, f"{{{ITUNES}}}episodeType", "full")
        tag(episode, f"{{{ITUNES}}}explicit", "false")
        ET.SubElement(episode, f"{{{PODCAST}}}chapters", url=BASE + "/chapters/" + chapter_file.name, type="application/json+chapters")
        cards.append(f'<article><h2>{html.escape(title)}</h2><audio controls preload="none" src="podcasts/{audio.name}"></audio><p><a href="podcasts/{audio.name}">下載 MP3</a> · <a href="chapters/{chapter_file.name}">章節</a></p></article>')

    ET.indent(rss, space="  ")
    ET.ElementTree(rss).write(ROOT / "feed.xml", encoding="utf-8", xml_declaration=True)
    intro = "粵語科學新聞，每集四個章節。"
    if has_memoir:
        intro = "粵語科學新聞與科學回憶錄。"
    page = '''<!doctype html><html lang="zh-HK"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>科學新知｜音頻版</title><style>body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6;background:#0b1526;color:#f6e9b8}a{color:#f5c65f}header{text-align:center}img{width:180px;height:180px;border-radius:12px}article{padding:1rem 0;border-top:1px solid #59627a}audio{width:100%}</style><header><img src="cover.jpg" alt="科學新知"><h1>科學新知｜音頻版</h1><p>''' + intro + '''</p><p><a href="feed.xml">訂閱 Podcast RSS feed</a></p></header>''' + "\n".join(cards) + "</html>\n"
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"Built feed.xml, index.html, and {len(cards)} chapter files")


if __name__ == "__main__":
    main()
