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

W, H = 1800, 1320
SEGMENTS = ("a", "b", "c", "d", "e", "f", "g", "DP")
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
assert len(LEDS) == 52

TM_LEFT = [("VDD", "17"), ("GND", "6"), ("DIN", "7"), ("SCLK", "8")]
TM_RIGHT = [(f"SEG{i}", str(i + 8)) for i in range(1, 9)] + [(f"GRID{i}", str(17 + i)) for i in range(1, 9)] + [("GRID9", "26"), ("GRID10", "27"), ("GRID11", "28"), ("GRID12", "1"), ("GRID13", "2"), ("GRID14", "3"), ("GRID15", "4"), ("GRID16", "5")]
HCT_LEFT = [("DIR", "1"), ("OE", "19")] + [(f"A{i}", str(i + 1)) for i in range(1, 9)] + [("GND", "10")]
HCT_RIGHT = [("VCC", "20")] + [(f"B{i}", str(19 - i)) for i in range(1, 9)]
ESP_LEFT = [("5V", "5V"), ("GND", "GND")]
ESP_RIGHT = [("GPIO25", "25"), ("GPIO26", "26"), ("GPIO32", "32"), ("GPIO33", "33")]


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


def rgb(value):
    value = COLORS.get(value, value)
    if value == "none":
        return None
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def write_svg(scene, path):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<title>ESP32 TM1640 HH:MM:SS schematic</title>',
           '<desc>Vector electrical schematic with 52 LEDs, 74HCT245 and TM1640</desc>',
           '<rect width="100%" height="100%" fill="#ffffff"/>']
    for kind, p in scene.items:
        if kind == "line":
            dash = f' stroke-dasharray="{p["dash"]}"' if p["dash"] else ""
            out.append(f'<line x1="{p["x1"]}" y1="{p["y1"]}" x2="{p["x2"]}" y2="{p["y2"]}" stroke="{COLORS.get(p["color"], p["color"])}" stroke-width="{p["width"]}"{dash}/>')
        elif kind == "rect":
            out.append(f'<rect x="{p["x"]}" y="{p["y"]}" width="{p["w"]}" height="{p["h"]}" rx="{p["rx"]}" stroke="{COLORS.get(p["stroke"], p["stroke"])}" fill="{COLORS.get(p["fill"], p["fill"])}" stroke-width="{p["width"]}"/>')
        elif kind == "circle":
            out.append(f'<circle cx="{p["x"]}" cy="{p["y"]}" r="{p["r"]}" stroke="{COLORS.get(p["stroke"], p["stroke"])}" fill="{COLORS.get(p["fill"], p["fill"])}" stroke-width="{p["width"]}"/>')
        elif kind == "polygon":
            pts = " ".join(f'{x},{y}' for x, y in p["points"])
            out.append(f'<polygon points="{pts}" stroke="{COLORS.get(p["stroke"], p["stroke"])}" fill="{COLORS.get(p["fill"], p["fill"])}" stroke-width="{p["width"]}"/>')
        elif kind == "text":
            weight = "700" if p["bold"] else "400"
            value = html.escape(str(p["value"]))
            out.append(f'<text x="{p["x"]}" y="{p["y"]}" font-family="DejaVu Sans,Arial,sans-serif" font-size="{p["size"]}" font-weight="{weight}" text-anchor="{p["anchor"]}" fill="{COLORS.get(p["color"], p["color"])}">{value}</text>')
    out.append("</svg>")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_pdf(scene, path):
    c = pdfcanvas.Canvas(str(path), pagesize=(W, H), pageCompression=1)
    c.setTitle("ESP32 + TM1640 HH:MM:SS — electrical schematic")
    c.setAuthor("Clock project")
    for kind, p in scene.items:
        if kind == "line":
            c.setStrokeColorRGB(*rgb(p["color"])); c.setLineWidth(p["width"])
            if p["dash"]: c.setDash(p["dash"].split(","))
            c.line(p["x1"], H - p["y1"], p["x2"], H - p["y2"])
            if p["dash"]: c.setDash()
        elif kind == "rect":
            c.setStrokeColorRGB(*rgb(p["stroke"])); c.setLineWidth(p["width"])
            fill = rgb(p["fill"])
            if fill: c.setFillColorRGB(*fill)
            c.roundRect(p["x"], H - p["y"] - p["h"], p["w"], p["h"], p["rx"], stroke=1, fill=1 if fill else 0)
        elif kind == "circle":
            c.setStrokeColorRGB(*rgb(p["stroke"])); c.setLineWidth(p["width"])
            fill = rgb(p["fill"])
            if fill: c.setFillColorRGB(*fill)
            c.circle(p["x"], H - p["y"], p["r"], stroke=1, fill=1 if fill else 0)
        elif kind == "polygon":
            c.setStrokeColorRGB(*rgb(p["stroke"])); c.setLineWidth(p["width"])
            fill = rgb(p["fill"])
            if fill: c.setFillColorRGB(*fill)
            path_obj = c.beginPath()
            path_obj.moveTo(p["points"][0][0], H - p["points"][0][1])
            for x, y in p["points"][1:]: path_obj.lineTo(x, H - y)
            path_obj.close(); c.drawPath(path_obj, stroke=1, fill=1 if fill else 0)
        elif kind == "text":
            c.setFillColorRGB(*rgb(p["color"])); c.setFont("DVB" if p["bold"] else "DV", p["size"])
            if p["anchor"] == "middle": c.drawCentredString(p["x"], H - p["y"], str(p["value"]))
            elif p["anchor"] == "end": c.drawRightString(p["x"], H - p["y"], str(p["value"]))
            else: c.drawString(p["x"], H - p["y"], str(p["value"]))
    c.showPage(); c.save()


def ic(scene, x, y, w, h, refdes, value, left, right):
    scene.rect(x, y, w, h, "ink", "box", 2, 8)
    scene.text(x + w / 2, y + 25, f"{refdes}  {value}", 18, "ink", "middle", True)
    usable = h - 60
    result = {}
    for side, pins in (("left", left), ("right", right)):
        for i, (name, number) in enumerate(pins):
            py = y + 45 + (usable * i / max(1, len(pins) - 1))
            if side == "left":
                px = x; scene.line(px - 12, py, px, py, "wire", 1.6)
                scene.text(px + 8, py + 4, f"{name} · {number}", 11, "ink")
            else:
                px = x + w; scene.line(px, py, px + 12, py, "wire", 1.6)
                scene.text(px - 8, py + 4, f"{number} · {name}", 11, "ink", "end")
            result[name] = (px, py, side)
    return result


def led(scene, x, y, refdes, name, seg, grid):
    # Standard diode/LED symbol, anode left, cathode right.
    scene.line(x - 30, y, x - 10, y, "wire", 1.4)
    scene.polygon([(x - 10, y - 8), (x - 10, y + 8), (x + 5, y)], "led", "none", 1.8)
    scene.line(x + 7, y - 9, x + 7, y + 9, "led", 1.8)
    scene.line(x + 7, y, x + 28, y, "wire", 1.4)
    scene.line(x, y - 8, x + 8, y - 17, "led", 1.2)
    scene.polygon([(x + 8, y - 17), (x + 3, y - 16), (x + 7, y - 12)], "led", "led", 1)
    scene.text(x - 34, y - 7, f"{refdes} {name}", 10, "muted", "end")
    scene.text(x - 34, y + 14, f"SEG{seg}", 10, "blue", "end")
    scene.text(x + 32, y + 4, f"GRID{grid}", 10, "accent")


def resistor(scene, x, y, refdes, seg):
    scene.line(x - 45, y, x - 30, y, "wire", 1.6)
    pts = [(x - 30, y)]
    for i in range(8): pts.append((x - 25 + i * 7, y + (-7 if i % 2 == 0 else 7)))
    pts.extend([(x + 30, y), (x + 45, y)])
    for a, b in zip(pts, pts[1:]): scene.line(*a, *b, "ink", 1.6)
    scene.text(x, y - 20, f"{refdes}  330 Ω", 13, "ink", "middle", True)
    scene.text(x, y + 28, f"SEG{seg}_DRV → SEG{seg} / {SEGMENTS[seg - 1]}", 12, "blue", "middle")


def build_scene():
    s = Scene()
    s.rect(18, 18, W - 36, H - 36, "muted", "none", 2)
    s.text(45, 58, "ESP32 + TM1640 — табло HH:MM:SS", 30, "ink", bold=True)
    s.text(45, 84, "Принципиальная схема · 52 LED · общий катод · SEG1…8 = a…g,DP", 16, "muted")
    s.text(W - 45, 58, "Ревизия 1 · 2026-11-08", 14, "muted", "end")

    s.text(45, 122, "1. Управление и питание", 21, "accent", bold=True)
    esp = ic(s, 150, 145, 200, 155, "U1", "ESP32 module", ESP_LEFT, ESP_RIGHT)
    hct = ic(s, 530, 140, 260, 210, "U2", "74HCT245", HCT_LEFT, HCT_RIGHT)
    tm = ic(s, 1030, 140, 290, 330, "U3", "TM1640 SOP28", TM_LEFT, TM_RIGHT)
    s.text(60, 175, "J1", 15, "ink", bold=True); s.text(60, 197, "+5V input", 13, "power")
    s.line(90, 205, 138, 205, "power", 2); s.label(138, 205, "+5V", "left", "power")
    s.text(60, 240, "GND", 13, "muted"); s.line(90, 245, 138, 245, "wire", 1.6); s.label(138, 245, "GND", "left")

    # Net labels make the drawing compact while retaining every electrical connection.
    for name, net in (("5V", "+5V"), ("GND", "GND"), ("GPIO25", "CLK_3V3"), ("GPIO26", "DIN_3V3"), ("GPIO32", "COLON_BTN"), ("GPIO33", "DP_BTN")):
        x, y, side = esp[name]; s.label(x, y, net, side, "power" if net == "+5V" else "blue")
    for name in hct:
        net = {"DIR": "+5V", "OE": "GND", "GND": "GND", "VCC": "+5V", "A1": "CLK_3V3", "A2": "DIN_3V3", "B1": "CLK_5V", "B2": "DIN_5V"}.get(name)
        if net is None and name.startswith("A"): net = "GND"
        x, y, side = hct[name]
        if net: s.label(x, y, net, side, "power" if net == "+5V" else "blue")
        else: s.text(x + (16 if side == "left" else -16), y + 4, "NC", 11, "muted", "start" if side == "left" else "end")
    for name in tm:
        net = {"VDD": "+5V", "GND": "GND", "DIN": "DIN_5V", "SCLK": "CLK_5V"}.get(name)
        if name.startswith("SEG"): net = name + "_DRV"
        if name.startswith("GRID") and int(name[4:]) <= 8: net = name
        x, y, side = tm[name]
        if net: s.label(x, y, net, side, "power" if net == "+5V" else "blue")
        else: s.text(x + 16, y + 4, "NC", 11, "muted")
    s.text(530, 380, "3,3 В → 5 В · DIR=1, OE=0 · A3…A8 → GND", 14, "gold", bold=True)

    # Decoupling and buttons.
    s.text(1610, 150, "Развязка U3", 15, "ink", bold=True)
    for y, refdes, value in ((190, "C1", "100 nF"), (240, "C2", "47–100 µF")):
        s.text(1580, y + 4, refdes, 12, "ink", "end"); s.text(1670, y + 4, value, 12, "ink")
        s.line(1600, y, 1620, y, "wire"); s.line(1620, y - 9, 1620, y + 9, "ink", 2); s.line(1628, y - 9, 1628, y + 9, "ink", 2); s.line(1628, y, 1650, y, "wire")
        s.label(1600, y, "+5V", "left", "power"); s.label(1650, y, "GND", "right")
    for y, refdes, net in ((320, "SW1", "COLON_BTN"), (370, "SW2", "DP_BTN")):
        s.text(1580, y + 4, refdes, 12, "ink", "end")
        s.line(1600, y, 1620, y, "wire"); s.circle(1622, y, 3, "ink", "paper", 1); s.circle(1650, y, 3, "ink", "paper", 1); s.line(1624, y - 2, 1647, y - 12, "ink", 2); s.line(1652, y, 1672, y, "wire")
        s.label(1600, y, net, "left"); s.label(1672, y, "GND", "right")
        s.text(1710, y + 4, "GPIO32" if refdes == "SW1" else "GPIO33", 12, "muted")

    s.text(45, 515, "2. Светодиодное табло — каждый LED имеет собственное обозначение", 21, "accent", bold=True)
    group_w = 215
    for i, group in enumerate(GROUPS):
        gx = 35 + i * group_w
        grid = i + 1
        s.rect(gx, 540, 200, 470, "muted", "light", 1.5, 6)
        s.text(gx + 100, 568, f"{group} · GRID{grid}", 17, "ink", "middle", True)
        s.text(gx + 100, 590, GROUP_TITLES[group], 11, "muted", "middle")
        group_leds = [d for d in LEDS if d["group"] == group]
        for j, d in enumerate(group_leds):
            led(s, gx + 100, 625 + j * 43, d["ref"], d["name"], d["seg"], grid)
        if group.startswith("C"):
            s.text(gx + 100, 870, "Верхняя точка: SEG1", 12, "blue", "middle")
            s.text(gx + 100, 895, "Нижняя точка: SEG2", 12, "blue", "middle")
            s.text(gx + 100, 930, "RAM = 0x03 / 0x00", 12, "muted", "middle")
        else:
            s.text(gx + 100, 985, f"RAM[{i}]", 12, "muted", "middle")

    s.text(45, 1055, "3. Токоограничивающие резисторы — по одному на общую SEG-линию", 20, "accent", bold=True)
    for i in range(8): resistor(s, 145 + i * 215, 1110, f"R{i + 1}", i + 1)
    s.line(45, 1170, W - 45, 1170, "muted", 1)
    s.text(45, 1202, "Питание: +5 В на ESP32 5V, U2 VCC и U3 VDD; GND общий. Катоды LED подключаются только к GRID, не напрямую к GND.", 15, "power", bold=True)
    s.text(45, 1232, "Коды цифр: 0=3F  1=06  2=5B  3=4F  4=66  5=6D  6=7D  7=07  8=7F  9=6F; DP добавляет 0x80.", 14, "muted")
    s.text(45, 1262, "Для реальной платы используйте 74HCT245/74HCT125, не 74HC245. Сопротивление 220–330 Ω подобрать по яркости и току.", 14, "muted")
    s.text(W - 45, 1295, "PDF/SVG и KiCad созданы из одного описания цепей", 12, "muted", "end")
    return s


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
        ("clock:74HCT245", "U", "74HCT245", HCT_LEFT, HCT_RIGHT, 45, None, None),
        ("clock:TM1640", "U", "TM1640", TM_LEFT, TM_RIGHT, 55, None, None),
        ("clock:R", "R", "330R", [], [], 10, None, "R"),
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

    add("clock:ESP32_MODULE", "U1", "ESP32-WROOM-32D", 60, 60,
        {"5V": "+5V", "GND": "GND", "25": "CLK_3V3", "26": "DIN_3V3", "32": "COLON_BTN", "33": "DP_BTN"})
    add("clock:74HCT245", "U2", "74HCT245", 150, 90,
        {"DIR": "+5V", "OE": "GND", "GND": "GND", "VCC": "+5V", "A1": "CLK_3V3", "A2": "DIN_3V3", "B1": "CLK_5V", "B2": "DIN_5V", **{f"A{i}": "GND" for i in range(3, 9)}},
        nc={f"B{i}" for i in range(3, 9)})
    add("clock:TM1640", "U3", "TM1640", 250, 110,
        {"VDD": "+5V", "GND": "GND", "DIN": "DIN_5V", "SCLK": "CLK_5V", **{f"SEG{i}": f"SEG{i}_DRV" for i in range(1, 9)}, **{f"GRID{i}": f"GRID{i}" for i in range(1, 9)}},
        nc={f"GRID{i}" for i in range(9, 17)})
    add("clock:CONN2", "J1", "+5V input", 30, 110, {"1": "+5V", "2": "GND"})
    add("clock:C", "C1", "100nF", 315, 55, {"1": "+5V", "2": "GND"})
    add("clock:C", "C2", "47-100uF", 315, 75, {"1": "+5V", "2": "GND"})
    add("clock:SW", "SW1", "Colon mode", 330, 100, {"1": "COLON_BTN", "2": "GND"})
    add("clock:SW", "SW2", "Decimal points", 330, 120, {"1": "DP_BTN", "2": "GND"})

    for i in range(8):
        # Driver and LED sides are distinct nets joined only through the resistor.
        add("clock:R", f"R{i + 1}", "330R", 40 + i * 45, 270,
            {"1": f"SEG{i + 1}_DRV", "2": f"SEG{i + 1}"})

    positions = {}
    for i, group in enumerate(GROUPS):
        for j, d in enumerate([x for x in LEDS if x["group"] == group]):
            x = 35 + i * 140 + (j // 4) * 55
            y = 320 + (j % 4) * 30
            positions[d["ref"]] = (x, y)
            add("clock:LED", d["ref"], f'{group}_{d["name"]}', x, y, {"A": f'SEG{d["seg"]}', "K": f'GRID{d["grid"]}'})

    out += [f'  (no_connect (at {x} {y}) (uuid {uid(f"nc-{x}-{y}")}))' for x, y in no_connects]
    notes = [
        (35, 25, "CONTROL AND POWER"),
        (35, 250, "SEG CURRENT-LIMITING RESISTORS"),
        (35, 295, "52-LED DISPLAY: H1 H2 C1 M1 M2 C2 S1 S2"),
        (35, 455, "All cathodes connect to their assigned GRID. Never connect a digit common cathode directly to GND."),
        (35, 465, "+5V: U1 5V, U2 VCC/DIR, U3 VDD. Common GND. C1/C2 next to U3."),
        (35, 475, "SEG1...8 = a,b,c,d,e,f,g,DP. Colon RAM values: 0x03 ON, 0x00 OFF."),
        (35, 485, "TM1640 GRID9...16 and 74HCT245 B3...B8 are intentionally not connected."),
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
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Reference", "Value / function", "Quantity"])
        for refdes, value in components: writer.writerow([refdes, value, 1])
    with (ROOT / "connections.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
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
    scene = build_scene()
    write_svg(scene, ROOT / "ESP32_TM1640_HHMMSS.svg")
    write_pdf(scene, ROOT / "ESP32_TM1640_HHMMSS.pdf")
    sch, components, nets = generate_kicad()
    check_sexpr(sch.read_text(encoding="utf-8"))
    print(f"Generated PDF/SVG and KiCad schematic: {len(components)} components, {len(LEDS)} LEDs")
