#!/usr/bin/env python3
"""Regenerate the complete 52-LED Wokwi diagram (standard library only)."""

import json
from pathlib import Path

OUT = Path(__file__).with_name("diagram.json")
parts = []
connections = []


def part(part_id, part_type, left, top, attrs=None, rotate=None):
    item = {"id": part_id, "type": part_type, "left": left, "top": top}
    if rotate is not None:
        item["rotate"] = rotate
    item["attrs"] = attrs or {}
    parts.append(item)


def wire(source, target, color="green", path=None):
    connections.append([source, target, color, path or []])


def text(part_id, value, left, top):
    part(part_id, "wokwi-text", left, top, {"text": value})


text("title", "ESP32 + TM1640 — HH:MM:SS, 52 LEDs", 100, 0)
text("subtitle", "SEG1…SEG8 = a…g,DP  |  GRID3/6 = colons", 100, 30)

part("esp", "board-esp32-devkit-c-v4", 40, 650)
part("level", "chip-hct245", 390, 690)
part("driver", "chip-tm1640", 760, 620)
part("colonButton", "wokwi-pushbutton", 1120, 670,
     {"color": "orange", "label": "C: colon mode", "key": "C", "bounce": "0"})
part("dpButton", "wokwi-pushbutton", 1120, 800,
     {"color": "blue", "label": "D: decimal points", "key": "D", "bounce": "0"})
text("powerNote", "Real hardware: 5 V, common GND, 100 nF + 100 uF near TM1640", 390, 970)
text("buttonsNote", "C: steady / 1 Hz / off\nD: decimal points", 1120, 900)

segment_colors = [
    "#e53935", "#fb8c00", "#fdd835", "#43a047",
    "#1e88e5", "#8e24aa", "#d81b60", "#90a4ae",
]
segments = ("a", "b", "c", "d", "e", "f", "g", "DP")
for index, segment in enumerate(segments, 1):
    part(f"seg{index}", "wokwi-resistor", 100 + (index - 1) * 125, 470,
         {"value": "330"}, rotate=90)
    text(f"segLabel{index}", f"SEG{index} / {segment}", 80 + (index - 1) * 125, 430)
    wire(f"driver:SEG{index}", f"seg{index}:1", segment_colors[index - 1])

# Placement and RAM mapping: H1,H2,colon,M1,M2,colon,S1,S2 = GRID1…GRID8.
items = ["H1", "H2", "C1", "M1", "M2", "C2", "S1", "S2"]
x = 100
positions = {}
for grid, name in enumerate(items, 1):
    positions[name] = (x, grid)
    if name.startswith("C"):
        text(f"label{name}", name, x - 5, 55)
        x += 75
    else:
        text(f"label{name}", name, x + 35, 55)
        x += 145

segment_positions = {
    "a": (45, 0, 90),
    "f": (0, 42, 0),
    "b": (85, 42, 0),
    "g": (45, 76, 90),
    "e": (0, 115, 0),
    "c": (85, 115, 0),
    "d": (45, 150, 90),
    "DP": (105, 150, 0),
}
led_count = 0
for name, (base_x, grid) in positions.items():
    if name.startswith("C"):
        # Both dots share GRID3/6; upper dot uses SEG1 and lower dot SEG2.
        for suffix, dx, dy, seg_index in (("upper", 0, 65, 1), ("lower", 0, 115, 2)):
            led_id = f"{name}_{suffix}"
            part(led_id, "wokwi-led", base_x, 90 + dy,
                 {"color": "red", "label": suffix})
            wire(f"seg{seg_index}:2", f"{led_id}:A", segment_colors[seg_index - 1])
            wire(f"{led_id}:C", f"driver:GRID{grid}", "green")
            led_count += 1
        continue

    for seg_index, segment in enumerate(segments, 1):
        dx, dy, rotation = segment_positions[segment]
        led_id = f"{name}_{segment}"
        part(led_id, "wokwi-led", base_x + dx, 90 + dy,
             {"color": "red", "label": segment}, rotate=rotation)
        wire(f"seg{seg_index}:2", f"{led_id}:A", segment_colors[seg_index - 1])
        wire(f"{led_id}:C", f"driver:GRID{grid}", "green")
        led_count += 1

# Power and the two HCT-buffered TM1640 signals.
wire("esp:5V", "level:VCC", "red")
wire("esp:5V", "driver:VDD", "red")
wire("esp:GND", "level:GND", "black")
wire("esp:GND", "driver:GND", "black")
wire("esp:5V", "level:DIR", "red")
wire("esp:GND", "level:OE", "black")
wire("esp:25", "level:A1", "#1e88e5")
wire("esp:26", "level:A2", "#8e24aa")
wire("level:B1", "driver:SCLK", "#1e88e5")
wire("level:B2", "driver:DIN", "#8e24aa")
for index in range(3, 9):
    wire("esp:GND", f"level:A{index}", "black")

wire("esp:32", "colonButton:1.l", "#fb8c00")
wire("esp:GND", "colonButton:2.l", "black")
wire("esp:33", "dpButton:1.l", "#1e88e5")
wire("esp:GND", "dpButton:2.l", "black")
wire("esp:TX", "$serialMonitor:RX", "", [])
wire("esp:RX", "$serialMonitor:TX", "", [])

assert led_count == 52, led_count
assert len(parts) == 3 + 2 + 8 + 52 + 20, len(parts)

diagram = {
    "version": 1,
    "author": "Clock project",
    "editor": "wokwi",
    "parts": parts,
    "connections": connections,
    "serialMonitor": {"display": "always", "newline": "lf"},
}
OUT.write_text(json.dumps(diagram, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {OUT.name}: {led_count} LEDs, {len(parts)} parts, {len(connections)} connections")
