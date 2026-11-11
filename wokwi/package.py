#!/usr/bin/env python3
"""Create the portable Wokwi project archive."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
files = ("diagram.json", "sketch.ino", "libraries.txt", "tm1640.chip.json", "tm1640.chip.c", "README.md")
with ZipFile(root / "clock-tm1640-wokwi.zip", "w", ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root / name, f"clock-tm1640-wokwi/{name}")
print("Packed clock-tm1640-wokwi.zip")
