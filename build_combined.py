"""Join same-date Science Frontier and Science Memoir shows into five chapters."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from build_podcast import escaped, mp3_chapter_count, mp3_duration

ROOT = Path(__file__).resolve().parent


def main() -> None:
    sys.path.insert(0, str(ROOT / ".tools"))
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    output = ROOT / "podcasts"
    for frontier in sorted(output.glob("science-frontier-*.mp3")):
        date = frontier.stem.removeprefix("science-frontier-")
        memoir = output / f"science-memoir-{date}.mp3"
        if not memoir.is_file():
            continue
        target = output / f"science-combined-{date}.mp3"
        expected_duration = mp3_duration(frontier, ffmpeg) + mp3_duration(memoir, ffmpeg)
        if (target.is_file() and mp3_chapter_count(target) == 5
                and abs(mp3_duration(target, ffmpeg) - expected_duration) <= 5):
            continue
        if mp3_chapter_count(frontier) != 4 or mp3_chapter_count(memoir) != 1:
            raise ValueError(f"{date}: source MP3 chapter count is invalid")
        info = {}
        for path in (ROOT / "parts").glob("*.info.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            match = re.search(r"(20\d{2}-\d{2}-\d{2})\s+Part\s*([1-4])", data.get("title", ""), re.I)
            if match and match.group(1) == date:
                info[int(match.group(2))] = data
        memoir_infos = list((ROOT / "parts").glob(f"memoir-{date}-*.info.json"))
        if set(info) != {1, 2, 3, 4} or len(memoir_infos) != 1:
            raise ValueError(f"{date}: expected four Frontier and one Memoir source")
        memoir_info = json.loads(memoir_infos[0].read_text(encoding="utf-8"))
        lines = [";FFMETADATA1", f"title={escaped('科學新知與科學回憶錄 ' + date)}",
                 "artist=Science Frontier (科學新知)", "album=科學新知｜音頻版", f"date={date}"]
        start = 0
        for number in range(1, 5):
            data = info[number]
            topic = data["title"].split(":", 1)[-1].split("|", 1)[0].strip()
            if date == "2026-09-10" and number == 3:
                topic = "氫氣星雲與伽碼射線"
            end = start + round(float(data["duration"]) * 1000)
            lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={start}", f"END={end}",
                      f"title={escaped(f'科學新知 {number}：{topic[:45]}')}"]
            start = end
        memoir_topic = memoir_info["title"].split("科學回憶錄", 1)[-1].lstrip("：: -").split("|", 1)[0].strip()
        end = start + round(float(memoir_info["duration"]) * 1000)
        lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={start}", f"END={end}",
                  f"title={escaped('科學回憶錄：' + memoir_topic[:45])}"]
        metadata = output / f"combined-{date}.ffmetadata"
        metadata.write_text("\n".join(lines) + "\n", encoding="utf-8")
        temp = output / f".building-combined-{date}.mp3"
        result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error",
                                 "-i", str(frontier), "-i", str(memoir), "-i", str(metadata),
                                 "-filter_complex", "[0:a:0][1:a:0]concat=n=2:v=0:a=1[a]",
                                 "-map", "[a]", "-map_metadata", "2", "-map_chapters", "2",
                                 "-c:a", "libmp3lame", "-b:a", "80k", "-ac", "1", "-y", str(temp)],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode or result.stderr.strip():
            raise RuntimeError(f"{date}: combined audio failed: {result.stderr[-2000:]}")
        if mp3_chapter_count(temp) != 5 or abs(mp3_duration(temp, ffmpeg) - expected_duration) > 5:
            raise ValueError(f"{date}: combined audio missing content or chapters")
        os.replace(temp, target)
        print(f"Created {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
