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


ROOT = Path(__file__).resolve().parent
BASE = "https://chanlaze.github.io/SciencePodcast"
ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
PODCAST = "https://podcastindex.org/namespace/1.0"
EPISODE_TITLES = {
    "2026-09-24": "漸凍症療法、腦演化、外星訊號與核子鐘",
    "2026-09-17": "AI太空競賽、微型核電、量子傳送與細胞通訊",
    "2026-09-10": "PISA、AI解數學、伽碼射線與量子引力",
}
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
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    tag(channel, "title", "科學新知｜音頻版")
    tag(channel, "link", BASE + "/")
    tag(channel, "description", "Science Frontier（科學新知）粵語科學新聞節目。每集集合原節目的四個部分，附章節導航。")
    tag(channel, "language", "zh-HK")
    tag(channel, f"{{{ITUNES}}}author", "Science Frontier (科學新知)")
    tag(channel, f"{{{ITUNES}}}summary", "每週粵語科學新聞：四個主題，合為一集。")
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
    for audio in sorted((ROOT / "podcasts").glob("science-frontier-*.mp3"), reverse=True):
        date = audio.stem.removeprefix("science-frontier-")
        info_files = sorted((ROOT / "parts").glob("[0-9][0-9][0-9]-*.info.json"))
        part_info = {}
        for path in info_files:
            if path.name.startswith("000-"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            match = re.search(r"(2026-\d{2}-\d{2})\s+Part\s*([1-4])", data["title"], re.I)
            if match and match.group(1) == date:
                part_info[int(match.group(2))] = data
        if set(part_info) != {1, 2, 3, 4}:
            raise ValueError(f"Missing source part for {date}")

        probe = subprocess.run([ffmpeg, "-hide_banner", "-i", str(audio)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
        if not duration_match:
            raise ValueError(f"Cannot read duration for {audio}")
        hours, minutes, seconds = duration_match.groups()
        total_seconds = round(int(hours) * 3600 + int(minutes) * 60 + float(seconds))
        if probe.stderr.count("Chapter #0:") != 4:
            raise ValueError(f"Expected four MP3 chapters in {audio}")

        chapters = []
        start = 0
        details = []
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
        chapter_file = chapter_dir / f"{date}.json"
        chapter_file.write_text(json.dumps({"version": "1.2.0", "chapters": chapters}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        episode = ET.SubElement(channel, "item")
        title = f"科學新知 {date}｜{EPISODE_TITLES[date]}"
        tag(episode, "title", title)
        tag(episode, "description", "\n".join(details))
        tag(episode, "link", BASE + "/")
        tag(episode, "guid", f"science-frontier-{date}", isPermaLink="false")
        published = datetime.fromisoformat(date).replace(hour=12, tzinfo=timezone(timedelta(hours=8)))
        tag(episode, "pubDate", format_datetime(published))
        ET.SubElement(episode, "enclosure", url=BASE + "/podcasts/" + audio.name, length=str(audio.stat().st_size), type="audio/mpeg")
        tag(episode, f"{{{ITUNES}}}author", "Science Frontier (科學新知)")
        tag(episode, f"{{{ITUNES}}}duration", str(total_seconds))
        tag(episode, f"{{{ITUNES}}}episodeType", "full")
        tag(episode, f"{{{ITUNES}}}explicit", "false")
        ET.SubElement(episode, f"{{{PODCAST}}}chapters", url=BASE + "/chapters/" + chapter_file.name, type="application/json+chapters")
        cards.append(f'<article><h2>{html.escape(title)}</h2><audio controls preload="none" src="podcasts/{audio.name}"></audio><p><a href="podcasts/{audio.name}">下載 MP3</a> · <a href="chapters/{date}.json">章節</a></p></article>')

    ET.indent(rss, space="  ")
    ET.ElementTree(rss).write(ROOT / "feed.xml", encoding="utf-8", xml_declaration=True)
    page = '''<!doctype html><html lang="zh-HK"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>科學新知｜音頻版</title><style>body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;line-height:1.6;background:#0b1526;color:#f6e9b8}a{color:#f5c65f}header{text-align:center}img{width:180px;height:180px;border-radius:12px}article{padding:1rem 0;border-top:1px solid #59627a}audio{width:100%}</style><header><img src="cover.jpg" alt="科學新知"><h1>科學新知｜音頻版</h1><p>粵語科學新聞，每集四個章節。</p><p><a href="feed.xml">訂閱 Podcast RSS feed</a></p></header>''' + "\n".join(cards) + "</html>\n"
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print("Built feed.xml, index.html, and three chapter files")


if __name__ == "__main__":
    main()
