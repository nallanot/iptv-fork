#!/usr/bin/env python3
"""Check M3U structure without upstream catalogue or duplicate restrictions."""
import sys
from pathlib import Path
from urllib.parse import urlsplit


def validate(path):
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0].split(maxsplit=1)[0:1] != ["#EXTM3U"]:
        raise ValueError("missing #EXTM3U header")
    pending = False
    count = 0
    for number, raw in enumerate(lines[1:], 2):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            raise ValueError(f"line {number}: duplicate header")
        if line.startswith("#EXTINF:"):
            if pending or "," not in line:
                raise ValueError(f"line {number}: missing URL or invalid EXTINF")
            pending = True
        elif not line.startswith("#"):
            url = urlsplit(line)
            if not pending or not url.scheme or not url.netloc or any(c.isspace() for c in line):
                raise ValueError(f"line {number}: unexpected text or invalid stream URL")
            pending = False
            count += 1
    if pending or not count:
        raise ValueError("missing stream URL or empty playlist")
    return count


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: validate-custom-playlist.py FILE [FILE ...]")
    for filename in sys.argv[1:]:
        try:
            print(f"{filename}: {validate(filename)} entries OK")
        except (OSError, UnicodeError, ValueError) as error:
            sys.exit(f"{filename}: {error}")
