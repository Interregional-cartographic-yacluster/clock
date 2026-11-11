#!/usr/bin/env python3
"""Static checks for pin validity and actual breadboard electrical continuity."""

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
D = json.loads((ROOT / "diagram.json").read_text(encoding="utf-8"))
parts = {p["id"]: p["type"] for p in D["parts"]}
assert len(parts) == len(D["parts"])
assert Counter(parts.values())["wokwi-breadboard-half"] == 2
assert Counter(p["id"].split("_")[0] for p in D["parts"] if p["type"] == "wokwi-led")["H1"] == 7
assert sum(p["type"] == "wokwi-led" for p in D["parts"]) == 46
assert sum(p["type"] == "wokwi-resistor" for p in D["parts"]) == 7
assert not any(p["type"] == "chip-hct245" for p in D["parts"])

chip = set(json.loads((ROOT / "tm1640.chip.json").read_text())["pins"])
known = {
    "board-esp32-devkit-c-v4": {"5V", "3V3", "GND", "25", "26", "21", "22", "18", "23", "5", "15", "4", "32", "TX", "RX"},
    "wokwi-resistor": {"1", "2"}, "wokwi-led": {"A", "C"},
    "wokwi-ds3231": {"VCC", "GND", "SDA", "SCL"},
    "wokwi-st7789": {"VCC", "GND", "SCLK", "MOSI", "CS", "DC", "RST", "BLK"},
    "wokwi-pushbutton": {"1.l", "2.l"}, "wokwi-text": set(), "chip-tm1640": chip,
}
for a, b, *_ in D["connections"]:
    for endpoint in (a, b):
        if endpoint.startswith("$serialMonitor:"):
            continue
        part, pin = endpoint.split(":", 1)
        assert part in parts, endpoint
        if parts[part] == "wokwi-breadboard-half":
            assert re.fullmatch(r"(?:[1-9]|[12][0-9]|30)[tb]\.[a-j]|(?:[tb][pn])\.(?:[1-9]|[12][0-9]|30)", pin), endpoint
        else:
            assert pin in known[parts[part]], endpoint

parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def union(a, b):
    a, b = find(a), find(b)
    if a != b:
        parent[b] = a

for bb in ("bbMain", "bbDriver"):
    for row in range(1, 31):
        for group in ("t", "b"):
            holes = [f"{bb}:{row}{group}.{c}" for c in "abcde" if group == "t"]
            holes += [f"{bb}:{row}{group}.{c}" for c in "fghij" if group == "b"]
            for hole in holes[1:]:
                union(holes[0], hole)
    for rail in ("tp", "tn"):
        for number in range(2, 31):
            union(f"{bb}:{rail}.1", f"{bb}:{rail}.{number}")
for a, b, *_ in D["connections"]:
    if not a.startswith("$") and not b.startswith("$"):
        union(a, b)

def connected(a, b):
    return find(a) == find(b)

for a, b in [
    ("esp:25", "driver:SCLK"), ("esp:26", "driver:DIN"),
    ("esp:21", "rtc:SDA"), ("esp:22", "rtc:SCL"),
    ("esp:18", "display:SCLK"), ("esp:23", "display:MOSI"),
    ("esp:5", "display:CS"), ("esp:15", "display:DC"), ("esp:4", "display:RST"),
    ("esp:32", "cityButton:1.l"), ("esp:5V", "driver:VDD"), ("esp:GND", "driver:GND"),
    ("H1_a:C", "driver:GRID1"), ("H2_a:C", "driver:GRID2"),
    ("H1_a:A", "H2_a:A"), ("C1_upper:A", "H1_a:A"),
]:
    assert connected(a, b), f"Not connected: {a} / {b}"
for a, b in [
    ("esp:25", "driver:SEG5"), ("esp:21", "rtc:SCL"),
    ("H1_a:A", "H1_b:A"), ("H1_a:C", "H2_a:C"),
    ("display:VCC", "driver:VDD"), ("H1_a:A", "driver:SEG1"),
]:
    assert not connected(a, b), f"Unexpected short: {a} / {b}"
print("PASS: 2 breadboards, 46 LEDs, 7 resistors, valid pins and no tested GPIO/SEG/GRID shorts")
