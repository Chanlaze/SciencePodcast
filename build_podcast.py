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


def mp3_duration(path: Path, ffmpeg: str) -> float:
    probe = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if not match:
        raise ValueError(f"Cannot read MP3 duration: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


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
        files = [PARTS / f"{audio_stem}.{ext}" for ext in ("webm", "m4a", "opus", "mp3", "mp4")]
        audio = next((path for path in files if path.is_file()), None)
        if audio is None:
            continue
        shows.setdefault(date, {})[part] = (audio, info)

    built = 0
    for date, parts in sorted(shows.items()):
        if set(parts) != {1, 2, 3, 4}:
            continue
        target = OUTPUT / f"science-frontier-{date}.mp3"
        expected_duration = sum(float(parts[n][1]["duration"]) for n in range(1, 5))
        if (target.is_file() and target.stat().st_size > 0
                and mp3_chapter_count(target) == 4
                and abs(mp3_duration(target, ffmpeg) - expected_duration) <= 5):
            continue
        metadata = OUTPUT / f"{date}.ffmetadata"
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
        inputs = [argument for number in range(1, 5) for argument in ("-i", str(parts[number][0]))]
        result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", *inputs,
                                 "-i", str(metadata), "-filter_complex",
                                 "[0:a:0][1:a:0][2:a:0][3:a:0]concat=n=4:v=0:a=1[a]",
                                 "-map", "[a]", "-map_metadata", "4", "-map_chapters", "4",
                                 "-c:a", "libmp3lame", "-b:a", "80k", "-ac", "1", "-y", str(temp)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode or result.stderr.strip():
            raise RuntimeError(f"{date}: audio join failed: {result.stderr[-2000:]}")
        if mp3_chapter_count(temp) != 4:
            raise ValueError(f"{date}: encoded MP3 does not contain four chapters")
        if abs(mp3_duration(temp, ffmpeg) - expected_duration) > 5:
            raise ValueError(f"{date}: encoded MP3 duration does not match all four source parts")
        os.replace(temp, target)
        built += 1
        print(f"Created {target.name} ({target.stat().st_size / 1024**2:.1f} MiB)")
    if built == 0:
        print("No new complete episodes to build")


if __name__ == "__main__":
    main()
