"""Join each four-part Science Frontier show into a chaptered MP3."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "parts"
OUTPUT = ROOT / "podcasts"
OUTPUT.mkdir(exist_ok=True)


def escaped(value: str) -> str:
    return value.replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", "\\n")


def mp3_chapter_count(path: Path) -> int:
    """Count ID3v2.4 CHAP frames, which ffmpeg's MP3 probe does not display."""
    with path.open("rb") as audio:
        header = audio.read(10)
        if header[:4] != b"ID3\x04":
            return 0
        tag_size = sum(byte << shift for byte, shift in zip(header[6:10], (21, 14, 7, 0)))
        tag = audio.read(tag_size)
    chapters = 0
    offset = 0
    while offset + 10 <= len(tag):
        frame = tag[offset:offset + 10]
        if not frame[:4].strip(b"\x00"):
            break
        size = sum(byte << shift for byte, shift in zip(frame[4:8], (21, 14, 7, 0)))
        if size <= 0 or offset + 10 + size > len(tag):
            return 0
        chapters += frame[:4] == b"CHAP"
        offset += 10 + size
    return chapters


def main() -> None:
    sys.path.insert(0, str(ROOT / ".tools"))
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    shows = {}
    for info_path in PARTS.glob("*.info.json"):
        info = json.loads(info_path.read_text(encoding="utf-8"))
        match = re.search(r"(20\d{2}-\d{2}-\d{2})\s+Part\s*([1-4])", info.get("title", ""), re.I)
        if not match:
            continue
        date, part = match.group(1), int(match.group(2))
        audio_stem = info_path.name.removesuffix(".info.json")
        files = [PARTS / f"{audio_stem}.{ext}" for ext in ("webm", "m4a", "opus", "mp3")]
        audio = next((path for path in files if path.is_file()), None)
        if audio is None:
            continue
        shows.setdefault(date, {})[part] = (audio, info)

    built = 0
    for date, parts in sorted(shows.items()):
        if set(parts) != {1, 2, 3, 4}:
            continue
        target = OUTPUT / f"science-frontier-{date}.mp3"
        if target.is_file() and target.stat().st_size > 0:
            continue
        concat = OUTPUT / f"{date}.concat.txt"
        metadata = OUTPUT / f"{date}.ffmetadata"
        concat.write_text("\n".join(f"file '{parts[n][0].as_posix()}'" for n in range(1, 5)) + "\n", encoding="utf-8")
        lines = [";FFMETADATA1", f"title={escaped('科學新知 ' + date)}", "artist=Science Frontier (科學新知)", f"album=科學新知", f"date={date}"]
        start = 0
        for number in range(1, 5):
            info = parts[number][1]
            end = start + round(float(info["duration"]) * 1000)
            topic = info["title"].split(":", 1)[-1].split("|", 1)[0].strip()
            if date == "2026-09-10" and number == 3:
                topic = "氫氣星雲與伽碼射線"
            topic = topic[:45].rstrip("，。； ")
            lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={start}", f"END={end}", f"title={escaped(f'Part {number}: {topic}')}" ]
            start = end
        metadata.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temp = OUTPUT / f".building-{date}.mp3"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(metadata), "-map", "0:a:0", "-map_metadata", "1", "-map_chapters", "1", "-c:a", "libmp3lame", "-b:a", "80k", "-ac", "1", "-y", str(temp)], check=True)
        if mp3_chapter_count(temp) != 4:
            raise ValueError(f"{date}: encoded MP3 does not contain four chapters")
        os.replace(temp, target)
        built += 1
        print(f"Created {target.name} ({target.stat().st_size / 1024**2:.1f} MiB)")
    if built == 0:
        print("No new complete episodes to build")


if __name__ == "__main__":
    main()
