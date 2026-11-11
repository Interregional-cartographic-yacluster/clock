#!/usr/bin/env python3
"""Generate the breadboard ESP32/DS3231/ST7789/TM1640 Wokwi project."""

import json
from pathlib import Path

OUT = Path(__file__).with_name("diagram.json")
parts, connections = [], []


def part(part_id, part_type, left, top, attrs=None, rotate=None):
    item = {"id": part_id, "type": part_type, "left": left, "top": top, "attrs": attrs or {}}
    if rotate is not None:
        item["rotate"] = rotate
    parts.append(item)


def wire(source, target, color="green", path=None):
    connections.append([source, target, color, path or []])


def text(part_id, value, left, top):
    part(part_id, "wokwi-text", left, top, {"text": value})


text("title", "ESP32 clock on breadboards — ST7789 + DS3231 + TM1640", 70, 0)
text("subtitle", "46 LEDs, no DP, 7x OMLT 510R, direct GPIO25/26, button GPIO32-GND", 70, 30)

# Controller and peripheral breadboard.
part("esp", "board-esp32-devkit-c-v4", 20, 800)
part("bbMain", "wokwi-breadboard-half", 30, 430)
part("display", "wokwi-st7789", 370, 820,
     {"width": 284, "height": 76, "offsetX": 0, "offsetY": 0, "rotate": 0, "invertColors": False, "bgr": False})
part("rtc", "wokwi-ds3231", 740, 820)
part("cityButton", "wokwi-pushbutton", 980, 830,
     {"color": "orange", "label": "City / hold 5s Wi-Fi", "key": "C", "bounce": "0"})
text("mainLabel", "BB1: ESP32 peripherals and button", 45, 400)

# Driver breadboard and custom TM1640.
part("bbDriver", "wokwi-breadboard-half", 650, 430)
part("driver", "chip-tm1640", 1030, 440)
part("displayNote", "wokwi-text", 1030, 710, {"text": "BB2: TM1640, 7 resistors, SEG/GRID harness"})
text("warning", "Real hardware: direct 3.3 V control is not guaranteed at TM1640 VDD=5 V", 1030, 745)

# Seven resistors across the central gap of BB2, rows 1...7.
for i in range(7):
    part(f"seg{i + 1}", "wokwi-resistor", 650 + i * 85, 760, {"value": "510"}, rotate=90)
    wire(f"driver:SEG{i + 1}", f"bbDriver:{i + 1}t.a", "#e53935")
    wire(f"bbDriver:{i + 1}t.e", f"seg{i + 1}:1", "#e53935")
    wire(f"seg{i + 1}:2", f"bbDriver:{i + 1}b.f", "#e53935")

# Power rails and direct TM1640 signals through breadboard rows.
wire("esp:5V", "bbMain:tp.1", "red")
wire("bbMain:tp.2", "bbDriver:tp.1", "red")
wire("bbDriver:tp.17", "driver:VDD", "red")
wire("esp:GND", "bbMain:tn.1", "black")
wire("bbMain:tn.2", "bbDriver:tn.1", "black")
wire("bbDriver:tn.6", "driver:GND", "black")
wire("esp:25", "bbMain:5t.a", "#1e88e5")
wire("bbMain:5t.e", "bbDriver:25t.a", "#1e88e5")
wire("bbDriver:25t.e", "driver:SCLK", "#1e88e5")
wire("esp:26", "bbMain:6t.a", "#8e24aa")
wire("bbMain:6t.e", "bbDriver:26t.a", "#8e24aa")
wire("bbDriver:26t.e", "driver:DIN", "#8e24aa")

# DS3231 on I2C rows 10/11 of BB1.
wire("esp:21", "bbMain:10t.a", "green")
wire("bbMain:10t.e", "rtc:SDA", "green")
wire("esp:22", "bbMain:11t.a", "#1e88e5")
wire("bbMain:11t.e", "rtc:SCL", "#1e88e5")
wire("bbMain:tp.10", "rtc:VCC", "red")
wire("bbMain:tn.10", "rtc:GND", "black")

# ST7789 on rows 12...16 of BB1. VCC/backlight are 3.3 V in this virtual module.
for gpio, row, pin, color in ((18, 12, "SCLK", "#fb8c00"), (23, 13, "MOSI", "#1e88e5"),
                              (5, 14, "CS", "#fdd835"), (15, 15, "DC", "#43a047"), (4, 16, "RST", "#8e24aa")):
    wire(f"esp:{gpio}", f"bbMain:{row}t.a", color)
    wire(f"bbMain:{row}t.e", f"display:{pin}", color)
wire("esp:3V3", "display:VCC", "red")
wire("esp:3V3", "display:BLK", "red")
wire("bbMain:tn.16", "display:GND", "black")

# Existing button: short press selects a city; holding five seconds shows Wi-Fi setup.
wire("esp:32", "bbMain:20t.a", "#fb8c00")
wire("bbMain:20t.e", "cityButton:1.l", "#fb8c00")
wire("cityButton:2.l", "bbMain:tn.20", "black")

# LED scoreboard: GRID1/2 H1/H2, GRID3 colon, GRID4/5 M1/M2,
# GRID6 colon, GRID7/8 S1/S2. No decimal points.
segments = ("a", "b", "c", "d", "e", "f", "g")
segment_positions = {
    "a": (45, 0, 90), "f": (0, 42, 0), "b": (85, 42, 0),
    "g": (45, 76, 90), "e": (0, 115, 0), "c": (85, 115, 0),
    "d": (45, 150, 0),
}
segment_colors = ("#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#d81b60")
items = ("H1", "H2", "C1", "M1", "M2", "C2", "S1", "S2")
x = 70
led_count = 0
for grid, name in enumerate(items, 1):
    text(f"label{name}", f"{name} / GRID{grid}", x, 65)
    if name.startswith("C"):
        for suffix, dy, seg in (("upper", 65, 1), ("lower", 115, 2)):
            led_id = f"{name}_{suffix}"
            part(led_id, "wokwi-led", x, 90 + dy, {"color": "red", "label": suffix})
            wire(f"bbDriver:{seg}b.j", f"{led_id}:A", segment_colors[seg - 1])
            wire(f"{led_id}:C", f"bbDriver:{9 + grid}t.e", "green")
            led_count += 1
        x += 75
        continue
    for seg, segment in enumerate(segments, 1):
        dx, dy, rotation = segment_positions[segment]
        led_id = f"{name}_{segment}"
        part(led_id, "wokwi-led", x + dx, 90 + dy,
             {"color": "red", "label": segment}, rotate=rotation)
        wire(f"bbDriver:{seg}b.j", f"{led_id}:A", segment_colors[seg - 1])
        wire(f"{led_id}:C", f"bbDriver:{9 + grid}t.e", "green")
        led_count += 1
    x += 145

# GRID inputs from TM1640 into the corresponding BB2 rows.
for grid in range(1, 9):
    wire(f"driver:GRID{grid}", f"bbDriver:{9 + grid}t.a", "green")

wire("esp:TX", "$serialMonitor:RX", "", [])
wire("esp:RX", "$serialMonitor:TX", "", [])
assert led_count == 46

diagram = {
    "version": 1,
    "author": "Clock project",
    "editor": "wokwi",
    "parts": parts,
    "connections": connections,
    "serialMonitor": {"display": "always", "newline": "lf"},
}
OUT.write_text(json.dumps(diagram, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {OUT.name}: 2 breadboards, {led_count} LEDs, {len(parts)} parts, {len(connections)} connections")
