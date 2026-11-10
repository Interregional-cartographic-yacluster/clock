"""Pictorial, crossing-free wiring scene for the ESP32/TM1640 display."""

import math


def wire(s, points, color, width=4):
    for a, b in zip(points, points[1:]):
        s.line(a[0], a[1], b[0], b[1], color, width)


def junction(s, x, y, color):
    s.circle(x, y, 6, color, color, 1)


def ground(s, x, y):
    s.line(x, y, x, y + 14, "ink", 3)
    s.line(x - 15, y + 14, x + 15, y + 14, "ink", 3)
    s.line(x - 10, y + 21, x + 10, y + 21, "ink", 3)
    s.line(x - 5, y + 28, x + 5, y + 28, "ink", 3)


def terminal(s, x, y, value, width=86):
    s.rect(x, y - 14, width, 28, "#176b4d", "#b7e4c7", 2, 4)
    s.circle(x + 9, y, 4, "#176b4d", "#f8f9fa", 1)
    s.text(x + width / 2 + 5, y + 4, value, 11, "ink", "middle", True)


def resistor(s, x, y, refdes):
    s.line(x - 42, y, x - 25, y, "#6c757d", 3)
    s.rect(x - 25, y - 10, 50, 20, "#6b4f2c", "#e9c46a", 2, 8)
    for dx, color in ((-14, "#f8e71c"), (-5, "#7048e8"), (5, "#7a3e00"), (15, "#b7791f")):
        s.rect(x + dx - 2, y - 9, 4, 18, color, color, 0)
    s.line(x + 25, y, x + 42, y, "#6c757d", 3)
    s.text(x, y - 18, f"{refdes} 330 Ω", 11, "ink", "middle", True)


def capacitor(s, x, y, refdes, value):
    s.line(x, y - 25, x, y - 10, "#6c757d", 3)
    s.rect(x - 18, y - 10, 36, 48, "#163c5e", "#1971c2", 2, 8)
    s.circle(x, y - 8, 16, "#163c5e", "#74c0fc", 2)
    s.text(x, y + 15, "+", 15, "paper", "middle", True)
    s.text(x, y + 58, f"{refdes} {value}", 11, "ink", "middle", True)
    s.line(x, y + 38, x, y + 48, "#6c757d", 3)


def button(s, x, y, refdes):
    s.line(x - 42, y, x - 18, y, "#6c757d", 3)
    s.rect(x - 18, y - 18, 36, 36, "#343a40", "#adb5bd", 2, 5)
    s.circle(x, y - 14, 11, "#343a40", "#e03131", 2)
    s.line(x + 18, y, x + 42, y, "#6c757d", 3)
    s.text(x, y - 36, refdes, 12, "ink", "middle", True)


def physical_led(s, x, y, refdes, name, color="#e03131"):
    # Dome and two through-hole leads, similar to a pictorial wiring diagram.
    s.rect(x - 27, y - 6, 54, 10, color, color, 1, 3)
    points = [(x - 24, y - 6)]
    for i in range(13):
        angle = math.pi - math.pi * i / 12
        points.append((x + 24 * math.cos(angle), y - 8 - 30 * math.sin(angle)))
    points.append((x + 24, y - 6))
    s.polygon(points, color, color, 2)
    s.line(x - 9, y + 4, x - 9, y + 28, "#6c757d", 3)
    s.line(x + 9, y + 4, x + 9, y + 28, "#6c757d", 3)
    s.text(x - 14, y + 20, "A", 10, "ink", "end", True)
    s.text(x + 14, y + 20, "K", 10, "ink", "start", True)
    caption = f"{refdes}·{name}"
    s.text(x, y - 15, caption, 9 if len(caption) <= 6 else 7.5, "paper", "middle", True)


def build_scene(Scene, leds, groups, group_titles):
    s = Scene()
    s.rect(18, 18, 2364, 1944, "muted", "none", 2)
    s.text(45, 58, "ESP32 + TM1640 — монтажная схема HH:MM:SS", 30, "ink", bold=True)
    s.text(45, 86, "Без 74HCT245 и DP · 46 LED · цветные провода без перекрёстков · соединения через одноимённые клеммы", 16, "muted")

    # ESP32 module: power is routed above/below, signals leave from the right.
    s.rect(80, 180, 350, 340, "#152d46", "#245b8a", 4, 12)
    s.rect(145, 260, 210, 110, "#495057", "#dee2e6", 3, 5)
    s.text(250, 315, "ESP32", 26, "ink", "middle", True)
    s.text(250, 345, "WROOM-32D", 14, "ink", "middle")
    s.text(250, 215, "U1", 18, "paper", "middle", True)
    esp_gpio = {}
    for i, (pin, net) in enumerate((("25", "TM_CLK"), ("26", "TM_DIN"), ("32", "COLON_BTN"))):
        y = 260 + i * 60
        s.line(430, y, 452, y, "#6c757d", 4)
        s.circle(430, y, 6, "#d4af37", "#f8e71c", 2)
        s.text(414, y + 4, f"GPIO{pin}", 13, "paper", "end", True)
        esp_gpio[pin] = (452, y, net)
    s.line(200, 180, 200, 158, "#6c757d", 4); s.text(218, 170, "5V", 13, "paper")
    s.line(200, 520, 200, 542, "#6c757d", 4); s.text(218, 535, "GND", 13, "paper")

    # TM1640 driver board with functionally arranged labeled terminals.
    s.rect(900, 140, 400, 740, "#28342b", "#40634b", 4, 12)
    s.rect(1000, 280, 200, 200, "#101010", "#212529", 3, 5)
    s.text(1100, 365, "TM1640", 24, "paper", "middle", True)
    s.text(1100, 395, "SOP28", 15, "paper", "middle")
    s.text(1100, 175, "U2 · драйвер", 18, "paper", "middle", True)
    s.line(1050, 140, 1050, 118, "#6c757d", 4); s.text(1070, 132, "VDD · 17", 12, "paper")
    s.line(1050, 880, 1050, 902, "#6c757d", 4); s.text(1070, 895, "GND · 6", 12, "paper")
    for name, number, y in (("SCLK", "8", 260), ("DIN", "7", 320)):
        s.line(878, y, 900, y, "#6c757d", 4); s.circle(900, y, 6, "#d4af37", "#f8e71c", 2)
        s.text(920, y + 4, f"{name} · {number}", 13, "paper", bold=True)
    for i in range(16):
        y = 210 + i * 40
        s.line(1300, y, 1322, y, "#6c757d", 3); s.circle(1300, y, 5, "#d4af37", "#f8e71c", 1)
        label = f"SEG{i + 1} · {9 + i}" if i < 8 else f"GRID{i - 7} · {18 + i - 8}"
        s.text(1282, y + 4, label, 11, "paper", "end", True)

    # Power input and rails. Junction dots appear only at real branches.
    terminal(s, 55, 110, "+5V", 90); terminal(s, 55, 950, "GND", 90)
    wire(s, [(145, 110), (2320, 110)], "#e03131", 6)
    wire(s, [(200, 110), (200, 158)], "#e03131", 5); junction(s, 200, 110, "#e03131")
    wire(s, [(1050, 110), (1050, 118)], "#e03131", 5); junction(s, 1050, 110, "#e03131")
    wire(s, [(145, 950), (1050, 950)], "#212529", 6)
    wire(s, [(200, 542), (200, 950)], "#212529", 5); junction(s, 200, 950, "#212529")
    wire(s, [(1050, 902), (1050, 950)], "#212529", 5); junction(s, 1050, 950, "#212529")

    # Direct 3.3 V control wires, separated into independent orthogonal channels.
    x, y, _ = esp_gpio["25"]
    wire(s, [(x, y), (650, y), (650, 260), (878, 260)], "#1971c2", 5)
    s.text(675, 251, "GPIO25 → SCLK", 12, "blue")
    x, y, _ = esp_gpio["26"]
    wire(s, [(x, y), (740, y), (740, 320), (878, 320)], "#7048e8", 5)
    s.text(755, 311, "GPIO26 → DIN", 12, "accent")

    # The colon button uses a local ground symbol; no DP button is present.
    for pin, by, refdes, net in (("32", 380, "SW1", "COLON_BTN"),):
        x, y, _ = esp_gpio[pin]
        wire(s, [(x, y), (560, y), (560, by)], "#f08c00", 4)
        button(s, 602, by, refdes)
        wire(s, [(644, by), (680, by)], "#212529", 4); ground(s, 680, by)
        s.text(700, by + 4, net, 12, "muted")

    # Decoupling capacitors connect to the top +5 V rail and local ground symbols.
    for x, refdes, value in ((2220, "C1", "100 nF"), (2320, "C2", "47–100 µF")):
        junction(s, x, 110, "#e03131"); wire(s, [(x, 110), (x, 135)], "#e03131", 4)
        capacitor(s, x, 160, refdes, value); wire(s, [(x, 208), (x, 238)], "#212529", 3); ground(s, x, 238)

    # SEG resistors and labeled harness terminals; all wires are parallel.
    s.text(1390, 150, "Резисторы и клеммы жгута", 17, "ink", bold=True)
    seg_colors = ("#e03131", "#f08c00", "#e3b505", "#2f9e44", "#1971c2", "#7048e8", "#d6336c", "#087f5b")
    for i in range(7):
        y = 210 + i * 40
        rx = 1490 + i * 105
        wire(s, [(1322, y), (rx - 42, y)], seg_colors[i], 3)
        resistor(s, rx, y, f"R{i + 1}")
        terminal(s, rx + 48, y, f"SEG{i + 1}", 74)
        s.text(rx + 48, y - 18, f"SEG{i + 1}_DRV", 9, "muted")
    s.text(1332, 494, "NC · без DP", 11, "muted")
    for i in range(8):
        y = 530 + i * 40
        terminal(s, 1400, y, f"GRID{i + 1}", 92)
        wire(s, [(1322, y), (1400, y)], "#2f9e44", 3)

    s.text(1390, 865, "Прямое управление 3,3 → 5 В выполнено по требованию.", 13, "power", bold=True)
    s.text(1390, 895, "Для TM1640 при VDD=5 В оно не гарантировано datasheet.", 13, "power")
    s.text(1390, 925, "Одноимённые клеммы соединить отдельными проводами жгута.", 13, "muted")

    s.text(45, 1040, "Светодиодные модули — короткие провода без пересечений", 23, "accent", bold=True)
    s.text(45, 1080, "A — анод к SEG через соответствующий резистор; K — катод к общему GRID модуля. Точки на проводах обозначают реальное объединение катодов.", 14, "muted")

    panel_y = 1120
    for i, group in enumerate(groups):
        gx = 30 + i * 295
        grid = i + 1
        s.rect(gx, panel_y, 275, 700, "muted", "light", 2, 8)
        s.text(gx + 137, panel_y + 34, f"{group} · GRID{grid}", 17, "ink", "middle", True)
        s.text(gx + 137, panel_y + 57, group_titles[group], 11, "muted", "middle")
        group_leds = [d for d in leds if d["group"] == group]
        rail_x = gx + 225
        cathode_points = []
        for j, d in enumerate(group_leds):
            y = panel_y + 105 + j * 70
            physical_led(s, gx + 135, y, d["ref"], d["name"], "#f08c00" if group.startswith("C") else "#e03131")
            terminal(s, gx + 10, y + 28, f'SEG{d["seg"]}', 72)
            wire(s, [(gx + 82, y + 28), (gx + 126, y + 28)], seg_colors[d["seg"] - 1], 3)
            wire(s, [(gx + 144, y + 28), (rail_x, y + 28)], "#2f9e44", 3)
            cathode_points.append(y + 28)
        if len(cathode_points) > 1:
            wire(s, [(rail_x, cathode_points[0]), (rail_x, cathode_points[-1])], "#2f9e44", 4)
        for cy in cathode_points: junction(s, rail_x, cy, "#2f9e44")
        bottom_y = panel_y + 655
        wire(s, [(rail_x, cathode_points[-1]), (rail_x, bottom_y), (gx + 185, bottom_y)], "#2f9e44", 4)
        terminal(s, gx + 90, bottom_y, f"GRID{grid}", 95)
        if group.startswith("C"):
            s.text(gx + 137, panel_y + 340, "upper → SEG1", 13, "blue", "middle")
            s.text(gx + 137, panel_y + 365, "lower → SEG2", 13, "blue", "middle")
            s.text(gx + 137, panel_y + 400, "RAM: 0x03 / 0x00", 12, "muted", "middle")
        else:
            s.text(gx + 137, panel_y + 680, f"RAM[{i}]", 11, "muted", "middle")

    s.text(45, 1870, "Монтаж: +5 В на ESP32 5V и TM1640 VDD; GND общий. Катоды не подключать напрямую к GND.", 15, "power", bold=True)
    s.text(45, 1900, "Цвета SEG повторяются во всех модулях. Одноимённые клеммы — одна цепь; пересекать провода на реальной плате не требуется при использовании жгута/разъёмов.", 14, "muted")
    s.text(45, 1930, "Внимание: прямое 3,3-вольтовое управление TM1640 при питании 5 В может быть нестабильным; вариант выбран по вашему требованию без HCT-буфера.", 14, "power")
    return s
