"""Join each four-part Science Frontier show into a chaptered MP3."""

import json
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


def main() -> None:
    sys.path.insert(0, str(ROOT / ".tools"))
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    shows = {}
    for info_path in PARTS.glob("[0-9][0-9][0-9]-*.info.json"):
        if info_path.name.startswith("000-"):
            continue
        info = json.loads(info_path.read_text(encoding="utf-8"))
        match = re.search(r"(2026-\d{2}-\d{2})\s+Part\s*([1-4])", info["title"], re.I)
        if not match:
            continue
        date, part = match.group(1), int(match.group(2))
        audio = info_path.with_suffix("").with_suffix(".webm")
        if not audio.is_file():
            raise FileNotFoundError(audio)
        shows.setdefault(date, {})[part] = (audio, info)

    if len(shows) != 3:
        raise ValueError(f"Expected three shows, found {len(shows)}")

    for date, parts in sorted(shows.items()):
        if set(parts) != {1, 2, 3, 4}:
            raise ValueError(f"{date}: expected parts 1–4, found {sorted(parts)}")
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
            lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={start}", f"END={end}", f"title={escaped(f'Part {number}: {topic}')}" ]
            start = end
        metadata.write_text("\n".join(lines) + "\n", encoding="utf-8")
        target = OUTPUT / f"science-frontier-{date}.mp3"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-i", str(metadata), "-map", "0:a:0", "-map_metadata", "1", "-map_chapters", "1", "-c:a", "libmp3lame", "-b:a", "80k", "-ac", "1", "-y", str(target)], check=True)
        print(f"Created {target.name} ({target.stat().st_size / 1024**2:.1f} MiB)")


if __name__ == "__main__":
    main()
