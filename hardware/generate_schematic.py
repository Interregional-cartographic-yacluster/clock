#!/usr/bin/env python3
"""Generate matching PDF/SVG schematics and an editable KiCad 6+ project.

Only ReportLab is required for PDF generation. The KiCad source is generated as
an S-expression schematic (format 20211123), which newer KiCad versions upgrade
when opening. All coordinates in the KiCad schematic are millimetres.
"""

from __future__ import annotations

import csv
import html
import json
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KICAD = ROOT / "kicad"
KICAD.mkdir(exist_ok=True)
if Path("/tmp/clock-schematic-deps").exists():  # Sandbox-local optional dependency path.
    sys.path.insert(0, "/tmp/clock-schematic-deps")
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas as pdfcanvas  # noqa: E402

def find_font(regular=True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf" if regular else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arial.ttf" if regular else "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf" if regular else "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError("Install DejaVu Sans or Arial to regenerate the PDF")


FONT = find_font(True)
FONT_BOLD = find_font(False)
pdfmetrics.registerFont(TTFont("DV", FONT))
pdfmetrics.registerFont(TTFont("DVB", FONT_BOLD))

W, H = 1600, 1120
SEGMENTS = ("a", "b", "c", "d", "e", "f", "g")
GROUPS = ("H1", "H2", "C1", "M1", "M2", "C2", "S1", "S2")
GROUP_TITLES = {
    "H1": "Часы — десятки", "H2": "Часы — единицы",
    "C1": "Двоеточие 1", "M1": "Минуты — десятки",
    "M2": "Минуты — единицы", "C2": "Двоеточие 2",
    "S1": "Секунды — десятки", "S2": "Секунды — единицы",
}
COLORS = {
    "ink": "#172033", "muted": "#526079", "blue": "#1769aa",
    "wire": "#087f5b", "power": "#d6336c", "box": "#e7f0fa",
    "accent": "#7048e8", "led": "#e03131", "paper": "#ffffff",
    "light": "#f5f7fb", "gold": "#b7791f",
}

# One authoritative component/net description shared by every output format.
LEDS = []
ref = 1
for grid, group in enumerate(GROUPS, 1):
    items = (("upper", 1), ("lower", 2)) if group.startswith("C") else tuple((s, i + 1) for i, s in enumerate(SEGMENTS))
    for name, seg in items:
        LEDS.append({"ref": f"D{ref}", "group": group, "grid": grid, "name": name, "seg": seg})
        ref += 1
assert len(LEDS) == 46

TM_LEFT = [("VDD", "17"), ("GND", "6"), ("DIN", "7"), ("SCLK", "8")]
TM_RIGHT = [(f"SEG{i}", str(i + 8)) for i in range(1, 9)] + [(f"GRID{i}", str(17 + i)) for i in range(1, 9)] + [("GRID9", "26"), ("GRID10", "27"), ("GRID11", "28"), ("GRID12", "1"), ("GRID13", "2"), ("GRID14", "3"), ("GRID15", "4"), ("GRID16", "5")]
# Physical order of the user's ESP32-WROOM-32D development board.
ESP_LEFT = [
    ("3V3", "3V3"), ("EN", "EN"), ("SVP", "GPIO36"), ("SVN", "GPIO39"),
    ("P34", "GPIO34"), ("P35", "GPIO35"), ("P32", "GPIO32"),
    ("P33", "GPIO33"), ("P25", "GPIO25"), ("P26", "GPIO26"),
    ("P27", "GPIO27"), ("P14", "GPIO14"), ("P12", "GPIO12"),
    ("GND", "GND1"), ("P13", "GPIO13"), ("SD2", "GPIO9"),
    ("SD3", "GPIO10"), ("CMD", "GPIO11"), ("5V", "5V"),
]
ESP_RIGHT = [
    ("GND", "GND2"), ("P23", "GPIO23"), ("P22", "GPIO22"),
    ("TX", "GPIO1"), ("RX", "GPIO3"), ("P21", "GPIO21"), ("GND", "GND3"),
    ("P19", "GPIO19"), ("P18", "GPIO18"), ("P5", "GPIO5"),
    ("P17", "GPIO17"), ("P16", "GPIO16"), ("P4", "GPIO4"),
    ("P0", "GPIO0"), ("P2", "GPIO2"), ("P15", "GPIO15"),
    ("CD0", "GPIO7"), ("CD1", "GPIO8"), ("CLK", "GPIO6"),
]
TFT_PINS = [("SCLK", "SCLK"), ("MOSI", "SDA"), ("CS", "CS"), ("DC", "DC"),
            ("RST", "RST"), ("VCC", "VCC"), ("BL", "BL"), ("GND", "GND")]
RTC_PINS = [("SDA", "SDA"), ("SCL", "SCL"), ("VCC", "VCC"), ("GND", "GND")]


class Scene:
    def __init__(self):
        self.items = []

    def line(self, x1, y1, x2, y2, color="ink", width=2, dash=None):
        self.items.append(("line", locals().copy()))

    def rect(self, x, y, w, h, stroke="ink", fill="none", width=2, rx=0):
        self.items.append(("rect", locals().copy()))

    def circle(self, x, y, r, stroke="ink", fill="none", width=2):
        self.items.append(("circle", locals().copy()))

    def polygon(self, points, stroke="ink", fill="none", width=2):
        self.items.append(("polygon", locals().copy()))

    def text(self, x, y, value, size=16, color="ink", anchor="start", bold=False):
        self.items.append(("text", locals().copy()))

    def label(self, x, y, value, side="left", color="blue"):
        # side describes the IC side: labels always extend away from the body.
        direction = -1 if side == "left" else 1
        self.line(x, y, x + direction * 12, y, "wire", 1.6)
        self.text(x + direction * 16, y + 4, value, 12, color,
                  "end" if side == "left" else "start")


from electrical_scene import build_scenes
from electrical_render import write_pdf, write_svg


# --------------------------- KiCad generator ---------------------------
NS = uuid.UUID("f4bf2e1c-c2f5-4dbb-948a-e3b2d621ee89")
def uid(key): return str(uuid.uuid5(NS, key))
def q(value): return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'
def effects(size=1.27, justify=None, hide=False):
    return f"(effects (font (size {size} {size}))" + (f" (justify {justify})" if justify else "") + (" hide" if hide else "") + ")"

def prop(name, value, ident, x, y, hide=False):
    return f'    (property {q(name)} {q(value)} (id {ident}) (at {x} {y} 0) {effects(hide=hide)})'

def lib_symbol(lib_id, ref_prefix, value, left, right, body_w=40, body_h=None, passive=None):
    name = lib_id.split(":", 1)[1]
    body_h = body_h or max(25, (max(len(left), len(right)) - 1) * 6.35 + 15)
    top, bottom = -body_h / 2, body_h / 2
    out = [f'    (symbol {q(lib_id)} (pin_names (offset 0.5)) (in_bom yes) (on_board yes)',
           prop("Reference", ref_prefix, 0, 0, top - 4), prop("Value", value, 1, 0, bottom + 4),
           prop("Footprint", "", 2, 0, 0, True), prop("Datasheet", "", 3, 0, 0, True),
           f'      (symbol "{name}_1_1"']
    if passive == "R":
        out.append('        (rectangle (start -5.08 -1.27) (end 5.08 1.27) (stroke (width 0.254) (type default)) (fill (type none)))')
    elif passive == "LED":
        out += ['        (polyline (pts (xy -2.54 -2.54) (xy -2.54 2.54) (xy 2.54 0) (xy -2.54 -2.54)) (stroke (width 0.254) (type default)) (fill (type none)))',
                '        (polyline (pts (xy 2.54 -2.54) (xy 2.54 2.54)) (stroke (width 0.254) (type default)) (fill (type none)))']
    elif passive == "C":
        out += ['        (polyline (pts (xy -2.54 -0.762) (xy 2.54 -0.762)) (stroke (width 0.508) (type default)) (fill (type none)))',
                '        (polyline (pts (xy -2.54 0.762) (xy 2.54 0.762)) (stroke (width 0.508) (type default)) (fill (type none)))']
    elif passive == "SW":
        out += ['        (circle (center -2.54 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none)))',
                '        (circle (center 2.54 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none)))',
                '        (polyline (pts (xy -2.032 -0.508) (xy 2.032 -3.048)) (stroke (width 0.254) (type default)) (fill (type none)))']
    else:
        out.append(f'        (rectangle (start {-body_w / 2} {top}) (end {body_w / 2} {bottom}) (stroke (width 0.254) (type default)) (fill (type background)))')
    if passive:
        pins = [("1", "A" if passive == "LED" else "1", -5.08, 0, 0), ("2", "K" if passive == "LED" else "2", 5.08, 0, 180)]
    else:
        pins = []
        for side, entries in (("left", left), ("right", right)):
            for i, (pin_name, number) in enumerate(entries):
                py = top + 7.62 + i * ((body_h - 15.24) / max(1, len(entries) - 1))
                px = -body_w / 2 - 5.08 if side == "left" else body_w / 2 + 5.08
                pins.append((number, pin_name, round(px, 2), round(py, 2), 0 if side == "left" else 180))
    for number, pin_name, px, py, angle in pins:
        out.append(f'        (pin passive line (at {px} {py} {angle}) (length 5.08) (name {q(pin_name)} {effects()}) (number {q(number)} {effects()}))')
    out += ["      )", "    )"]
    return "\n".join(out), pins


def generate_kicad():
    definitions = {}
    specs = [
        ("clock:ESP32_MODULE", "U", "ESP32-WROOM-32D", ESP_LEFT, ESP_RIGHT, 40, None, None),
        ("clock:TM1640", "U", "TM1640", TM_LEFT, TM_RIGHT, 55, None, None),
        ("clock:ST7789_MODULE", "A", "ST7789 284x76", TFT_PINS, [], 35, None, None),
        ("clock:DS3231_MODULE", "U", "DS3231 RTC", RTC_PINS, [], 30, None, None),
        ("clock:R", "R", "OMLT 510R", [], [], 10, None, "R"),
        ("clock:LED", "D", "LED", [], [], 10, None, "LED"),
        ("clock:C", "C", "C", [], [], 10, None, "C"),
        ("clock:SW", "SW", "SW_PUSH", [], [], 10, None, "SW"),
        ("clock:CONN2", "J", "+5V_INPUT", [("1", "1"), ("2", "2")], [], 15, 20, None),
    ]
    for spec in specs:
        lib_id = spec[0]
        definitions[lib_id] = lib_symbol(*spec)
    out = ['(kicad_sch (version 20211123) (generator eeschema)', f'  (uuid {uid("sheet")})', '  (paper "A0")',
           '  (title_block (title "ESP32 + TM1640 HH:MM:SS") (date "2026-11-08") (rev "1") (company "Clock project"))', '  (lib_symbols']
    out += [definitions[s[0]][0] for s in specs]
    out.append("  )")
    components = []
    nets = []
    no_connects = []

    def add(lib_id, refdes, value, x, y, pin_nets=None, nc=()):
        definition, pins = definitions[lib_id]
        key = refdes
        out.extend([f'  (symbol (lib_id {q(lib_id)}) (at {x} {y} 0) (unit 1)', f'    (in_bom yes) (on_board yes) (uuid {uid(key)})',
                    prop("Reference", refdes, 0, x, y - 8), prop("Value", value, 1, x, y + 8),
                    prop("Footprint", "", 2, x, y, True), prop("Datasheet", "", 3, x, y, True)])
        for number, _, _, _, _ in pins: out.append(f'    (pin {q(number)} (uuid {uid(key + "-pin-" + number)}))')
        out.append("  )")
        components.append((refdes, value))
        pin_nets = pin_nets or {}
        for number, pin_name, px, py, angle in pins:
            wx, wy = round(x + px, 2), round(y + py, 2)
            if number in nc or pin_name in nc:
                no_connects.append((wx, wy)); continue
            net = pin_nets.get(number) or pin_nets.get(pin_name)
            if not net: continue
            direction = 1 if angle == 0 else -1
            # For left pins the wire/label extends left; for right pins right.
            direction = -direction
            lx = round(wx + direction * 5.08, 2)
            out.append(f'  (wire (pts (xy {wx} {wy}) (xy {lx} {wy})) (stroke (width 0) (type default) (color 0 0 0 0)) (uuid {uid(key + "-wire-" + number)}))')
            justify = "right" if direction < 0 else "left"
            out.append(f'  (label {q(net)} (at {lx} {wy} 0) {effects(justify=justify)} (uuid {uid(key + "-label-" + number)}))')
            nets.append((refdes, pin_name, number, net))

    esp_nets = {"5V": "+5V", "3V3": "+3V3", "GND1": "GND", "GND2": "GND", "GND3": "GND",
                "GPIO18": "TFT_SCLK", "GPIO23": "TFT_MOSI", "GPIO5": "TFT_CS",
                "GPIO15": "TFT_DC", "GPIO4": "TFT_RST", "GPIO21": "I2C_SDA",
                "GPIO22": "I2C_SCL", "GPIO25": "TM_CLK", "GPIO26": "TM_DIN", "GPIO32": "CITY_WIFI_BTN"}
    esp_unused = {number for _, number in ESP_LEFT + ESP_RIGHT} - set(esp_nets)
    add("clock:ESP32_MODULE", "U1", "ESP32-WROOM-32D", 60, 60, esp_nets, nc=esp_unused)
    add("clock:TM1640", "U2", "TM1640", 250, 110,
        {"VDD": "+5V", "GND": "GND", "DIN": "TM_DIN", "SCLK": "TM_CLK", **{f"SEG{i}": f"SEG{i}_DRV" for i in range(1, 8)}, **{f"GRID{i}": f"GRID{i}" for i in range(1, 9)}},
        nc={f"GRID{i}" for i in range(9, 17)} | {"SEG8"})
    add("clock:CONN2", "J1", "+5V input", 30, 110, {"1": "+5V", "2": "GND"})
    add("clock:C", "C1", "100nF", 315, 55, {"1": "+5V", "2": "GND"})
    add("clock:C", "C2", "47-100uF", 315, 75, {"1": "+5V", "2": "GND"})
    add("clock:SW", "SW1", "City / Wi-Fi setup", 330, 100, {"1": "CITY_WIFI_BTN", "2": "GND"})
    add("clock:ST7789_MODULE", "A1", "ST7789 284x76", 450, 65,
        {"SCLK": "TFT_SCLK", "MOSI": "TFT_MOSI", "CS": "TFT_CS", "DC": "TFT_DC",
         "RST": "TFT_RST", "VCC": "+3V3", "BL": "GND", "GND": "GND"})
    add("clock:DS3231_MODULE", "U3", "DS3231 RTC", 560, 65,
        {"SDA": "I2C_SDA", "SCL": "I2C_SCL", "VCC": "+3V3", "GND": "GND"})

    for i in range(7):
        # Driver and LED sides are distinct nets joined only through the resistor.
        add("clock:R", f"R{i + 1}", "OMLT 510R", 40 + i * 45, 270,
            {"1": f"SEG{i + 1}_DRV", "2": f"SEG{i + 1}"})

    positions = {}
    # Physical H1 H2 : M1 M2 : S1 S2 arrangement, matching the PDF/SVG sheet.
    digit_origins = {"H1": 40, "H2": 165, "M1": 335, "M2": 460, "S1": 630, "S2": 755}
    colon_origins = {"C1": 280, "C2": 580}
    segment_offsets = {"a": (45, 0), "f": (0, 30), "b": (90, 30), "g": (45, 60),
                       "e": (0, 90), "c": (90, 90), "d": (45, 120),
                       "upper": (0, 45), "lower": (0, 95)}
    for group in GROUPS:
        for d in [x for x in LEDS if x["group"] == group]:
            dx, dy = segment_offsets[d["name"]]
            x = (digit_origins.get(group) or colon_origins[group]) + dx
            y = 315 + dy
            positions[d["ref"]] = (x, y)
            add("clock:LED", d["ref"], f'{group}_{d["name"]}', x, y, {"A": f'SEG{d["seg"]}', "K": f'GRID{d["grid"]}'})

    out += [f'  (no_connect (at {x} {y}) (uuid {uid(f"nc-{x}-{y}")}))' for x, y in no_connects]
    notes = [
        (35, 25, "CONTROL AND POWER"),
        (35, 250, "SEG CURRENT-LIMITING RESISTORS"),
        (35, 295, "46-LED DISPLAY, NO DP: H1 H2 C1 M1 M2 C2 S1 S2"),
        (35, 455, "All cathodes connect to their assigned GRID. Never connect a digit common cathode directly to GND."),
        (35, 465, "+5V: U1 5V and U2 VDD. +3V3: A1 VCC and U3 VCC. A1 BL=GND. Common GND. C1/C2 next to U2."),
        (35, 475, "SEG1...7 = a,b,c,d,e,f,g. Colon RAM values: 0x03 ON, 0x00 OFF. DP is omitted."),
        (35, 485, "TM1640 SEG8 and GRID9...16 are not connected. No 74HCT245 is used in this variant."),
        (35, 495, "A1 ST7789: 18/23/5/15/4, VCC=3V3, BL=GND. U3 DS3231: SDA21/SCL22, VCC=3V3, I2C 0x68."),
        (35, 505, "SW1: GPIO32 to GND. Short press selects city; hold 5 s opens Wi-Fi setup; internal pull-up enabled."),
    ]
    for x, y, value in notes: out.append(f'  (text {q(value)} (at {x} {y} 0) {effects(2.5, "left bottom")} (uuid {uid("note-" + value)}))')
    out.append(")")
    text = "\n".join(out) + "\n"
    sch = KICAD / "ESP32_TM1640_Clock.kicad_sch"
    sch.write_text(text, encoding="utf-8")
    project = {
        "board": {}, "boards": [], "cvpcb": {"equivalence_files": []}, "erc": {},
        "libraries": {}, "meta": {"filename": "ESP32_TM1640_Clock.kicad_pro", "version": 1},
        "net_settings": {"classes": [], "meta": {"version": 3}}, "pcbnew": {},
        "schematic": {}, "sheets": [], "text_variables": {},
    }
    (KICAD / "ESP32_TM1640_Clock.kicad_pro").write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
    with (ROOT / "bom.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\n")
        writer.writerow(["Reference", "Value / function", "Quantity"])
        for refdes, value in components: writer.writerow([refdes, value, 1])
    with (ROOT / "connections.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\n")
        writer.writerow(["Component", "Pin name", "Pin number", "Net"])
        writer.writerows(nets)
    return sch, components, nets


def check_sexpr(text):
    # Lightweight syntax validation: strings, escapes and balanced parentheses.
    depth, quoted, escaped = 0, False, False
    for ch in text:
        if quoted:
            if escaped: escaped = False
            elif ch == "\\": escaped = True
            elif ch == '"': quoted = False
        elif ch == '"': quoted = True
        elif ch == "(": depth += 1
        elif ch == ")":
            depth -= 1
            assert depth >= 0, "Unbalanced closing parenthesis"
    assert depth == 0 and not quoted, "Invalid S-expression structure"


if __name__ == "__main__":
    scenes = build_scenes(Scene, TM_LEFT, TM_RIGHT)
    write_svg(scenes, ROOT / "ESP32_TM1640_HHMMSS.svg", W, H, COLORS)
    write_pdf(scenes, ROOT / "ESP32_TM1640_HHMMSS.pdf", W, H, COLORS)
    sch, components, nets = generate_kicad()
    check_sexpr(sch.read_text(encoding="utf-8"))
    print(f"Generated PDF/SVG and KiCad schematic: {len(components)} components, {len(LEDS)} LEDs")
