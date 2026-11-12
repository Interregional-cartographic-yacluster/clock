"""Three-page conventional electrical schematic (no pictorial component leads)."""

W, H = 1600, 1120


def net(s, x, y, name, side="right", color="blue"):
    direction = 1 if side == "right" else -1
    s.line(x, y, x + direction * 28, y, "wire", 2)
    s.text(x + direction * 36, y + 5, name, 15, color,
           "start" if direction > 0 else "end", True)


def ground(s, x, y):
    s.line(x, y, x, y + 16, "wire", 2)
    for dy, half in ((16, 18), (24, 12), (32, 6)):
        s.line(x - half, y + dy, x + half, y + dy, "ink", 2)
    s.text(x + 28, y + 28, "GND", 14, "ink")


def module(s, x, y, w, h, refdes, value, pins, side="left"):
    s.rect(x, y, w, h, "ink", "box", 2, 0)
    if refdes or value:
        s.text(x + w / 2, y + 32, f"{refdes} · {value}", 20, "ink", "middle", True)
    result = {}
    usable = h - 85
    for i, (label, number, net_name) in enumerate(pins):
        py = y + 65 + usable * i / max(1, len(pins) - 1)
        if side == "left":
            px = x
            s.line(px - 18, py, px, py, "wire", 2)
            s.text(px + 12, py + 5, f"{label}  [{number}]", 14, "ink")
        else:
            px = x + w
            s.line(px, py, px + 18, py, "wire", 2)
            s.text(px - 12, py + 5, f"[{number}]  {label}", 14, "ink", "end")
        result[label] = (px, py, net_name)
    return result


def resistor(s, x, y, refdes, left_net, right_net):
    net(s, x - 70, y, left_net, "left")
    s.line(x - 70, y, x - 35, y, "wire", 2)
    s.rect(x - 35, y - 11, 70, 22, "ink", "paper", 2)
    s.line(x + 35, y, x + 70, y, "wire", 2)
    net(s, x + 70, y, right_net, "right")
    s.text(x, y - 22, f"{refdes} · 510 Ω", 14, "ink", "middle", True)


def capacitor(s, x, y, refdes, value):
    net(s, x - 60, y, "+5V", "left", "power")
    s.line(x - 60, y, x - 12, y, "wire", 2)
    s.line(x - 12, y - 16, x - 12, y + 16, "ink", 2)
    s.line(x + 12, y - 16, x + 12, y + 16, "ink", 2)
    s.line(x + 12, y, x + 50, y, "wire", 2)
    s.line(x + 50, y, x + 50, y + 25, "wire", 2)
    ground(s, x + 50, y + 25)
    s.text(x, y - 28, f"{refdes} · {value}", 15, "ink", "middle", True)


def led(s, x, y, refdes, segment, grid_net="GRIDx"):
    net(s, x - 90, y, f"SEG{segment}", "left")
    s.line(x - 90, y, x - 25, y, "wire", 2)
    s.polygon([(x - 25, y - 16), (x - 25, y + 16), (x + 12, y)], "ink", "paper", 2)
    s.line(x + 17, y - 18, x + 17, y + 18, "ink", 2)
    s.line(x + 17, y, x + 85, y, "wire", 2)
    # Light-emission arrows are part of the standard LED symbol, not wires.
    s.line(x - 2, y - 20, x + 13, y - 35, "led", 1.5)
    s.polygon([(x + 13, y - 35), (x + 6, y - 33), (x + 12, y - 27)], "led", "led", 1)
    s.text(x - 3, y - 48, refdes, 14, "ink", "middle", True)
    s.text(x - 42, y + 6, "A", 13, "muted", "end")
    s.text(x + 29, y + 6, "K", 13, "muted")


def title(s, page, name, subtitle):
    s.rect(20, 20, W - 40, H - 40, "ink", "none", 2)
    s.text(50, 65, f"Часы ESP32 · Лист {page}/3 — {name}", 28, "ink", bold=True)
    s.text(50, 96, subtitle, 16, "muted")
    s.text(W - 50, 64, "Рев. 2 · 2026-11-08", 14, "muted", "end")


def page_control(Scene):
    s = Scene()
    title(s, 1, "контроллер и периферия", "Стандартные УГО · линии одного имени электрически соединены · серых условных проводников нет")
    left_order = [
        ("3V3", "+3V3"), ("EN", None), ("SVP", None), ("SVN", None),
        ("P34", None), ("P35", None), ("P32", "CITY_WIFI_BTN"), ("P33", None),
        ("P25", "TM_CLK"), ("P26", "TM_DIN"), ("P27", None), ("P14", None),
        ("P12", None), ("GND", "GND"), ("P13", None), ("SD2", None),
        ("SD3", None), ("CMD", None), ("5V", "+5V"),
    ]
    right_order = [
        ("GND", "GND"), ("P23", "TFT_MOSI"), ("P22", "I2C_SCL"),
        ("TX", None), ("RX", None), ("P21", "I2C_SDA"), ("GND", "GND"),
        ("P19", None), ("P18", "TFT_SCLK"), ("P5", "TFT_CS"),
        ("P17", None), ("P16", None), ("P4", "TFT_RST"), ("P0", None),
        ("P2", None), ("P15", "TFT_DC"), ("CD0", None), ("CD1", None), ("CLK", None),
    ]
    gpio_numbers = {**{f"P{i}": f"GPIO{i}" for i in range(40)},
                    "SVP": "GPIO36", "SVN": "GPIO39", "TX": "GPIO1", "RX": "GPIO3",
                    "SD2": "GPIO9", "SD3": "GPIO10", "CMD": "GPIO11",
                    "CD0": "GPIO7", "CD1": "GPIO8", "CLK": "GPIO6"}
    module(s, 525, 155, 350, 785, "U1", "ESP32-WROOM-32D",
           [(label, gpio_numbers.get(label, label), net_name or "NC") for label, net_name in left_order], "left")
    module(s, 525, 155, 350, 785, "", "", [(label, gpio_numbers.get(label, label), net_name or "NC") for label, net_name in right_order], "right")
    for label, net_name in left_order:
        if net_name:
            index = [x[0] for x in left_order].index(label)
            y = 220 + 700 * index / 18
            net(s, 507, y, net_name, "left", "power" if net_name.startswith("+") else "blue")
    short_names = {"TFT_SCLK": "SCLK", "TFT_MOSI": "MOSI", "TFT_CS": "CS",
                   "TFT_DC": "DC", "TFT_RST": "RST", "I2C_SDA": "SDA", "I2C_SCL": "SCL"}
    for index, (label, net_name) in enumerate(right_order):
        if net_name:
            y = 220 + 700 * index / 18
            net(s, 893, y, short_names.get(net_name, net_name), "right")

    tft_pins = [(x, x, n) for x, n in (("SCLK", "TFT_SCLK"), ("MOSI/SDA", "TFT_MOSI"), ("CS", "TFT_CS"), ("DC", "TFT_DC"), ("RST/RES", "TFT_RST"), ("VCC", "+3V3"), ("BL", "GND"), ("GND", "GND"))]
    tft = module(s, 1150, 145, 300, 340, "A1", "ST7789 284×76", tft_pins)
    for label, (x, y, net_name) in tft.items(): net(s, x - 18, y, short_names.get(net_name, net_name), "left", "power" if label == "VCC" else "blue")

    rtc_pins = [(x, x, n) for x, n in (("SDA", "I2C_SDA"), ("SCL", "I2C_SCL"), ("VCC", "+3V3"), ("GND", "GND"))]
    rtc = module(s, 1150, 555, 300, 240, "U3", "DS3231 RTC", rtc_pins)
    for label, (x, y, net_name) in rtc.items(): net(s, x - 18, y, short_names.get(net_name, net_name), "left", "power" if label == "VCC" else "blue")

    # Existing front-panel button: normally open, internal ESP32 pull-up enabled.
    net(s, 900, 900, "CITY_WIFI_BTN", "left")
    s.line(900, 900, 1010, 900, "wire", 2)
    s.circle(1015, 900, 5, "ink", "paper", 2); s.circle(1080, 900, 5, "ink", "paper", 2)
    s.line(1018, 895, 1075, 870, "ink", 3)
    s.line(1085, 900, 1130, 900, "wire", 2); ground(s, 1130, 900)
    s.text(1048, 845, "SW1 · город / Wi-Fi", 17, "ink", "middle", True)
    s.text(1048, 955, "Коротко: следующий город", 15, "muted", "middle")
    s.text(1048, 982, "Удержание 5 с: настройка Wi-Fi", 15, "muted", "middle")
    s.text(1048, 1009, "Внутренняя подтяжка GPIO32 включена", 15, "muted", "middle")

    s.text(70, 170, "J1 · вход питания", 18, "ink", bold=True)
    net(s, 100, 230, "+5V", "right", "power")
    net(s, 100, 285, "GND", "right", "ink")
    s.text(70, 365, "Питание и примечания", 18, "accent", bold=True)
    notes = [
        "• U1 5V и TM1640 VDD: +5 В; GND общий.",
        "• ST7789 VCC, RTC VCC: 3,3 В.",
        "• ST7789 BL → GND.",
        "• RTC: SDA → P21, SCL → P22.",
        "• DS3231: I²C, адрес 0x68.",
        "• TM_CLK/TM_DIN продолжены на листе 2.",
        "• Внешний резистор для SW1 не нужен.",
    ]
    for i, value in enumerate(notes): s.text(70, 410 + i * 40, value, 15, "muted")
    s.text(70, 770, "Обозначения цепей", 18, "accent", bold=True)
    s.text(70, 812, "TFT_* — дисплей ST7789", 15, "muted")
    s.text(70, 850, "I2C_* — часы реального времени", 15, "muted")
    s.text(70, 888, "TM_* — драйвер большого табло", 15, "muted")
    s.text(70, 926, "CITY_WIFI_BTN — существующая кнопка", 15, "muted")
    return s


def page_driver(Scene, tm_left, tm_right):
    s = Scene()
    title(s, 2, "драйвер TM1640", "Прямое управление от ESP32 · DP отсутствует · R1…R7 = ОМЛТ 510 Ω · выходы на лист 3")
    def tm_net(name):
        if name == "VDD": return "+5V"
        if name == "GND": return "GND"
        if name == "DIN": return "TM_DIN"
        if name == "SCLK": return "TM_CLK"
        if name.startswith("SEG") and int(name[3:]) <= 7: return name + "_DRV"
        if name.startswith("GRID") and int(name[4:]) <= 8: return name
        return "NC"
    left = [(name, number, tm_net(name)) for name, number in tm_left]
    right = [(name, number, tm_net(name)) for name, number in tm_right]
    s.rect(370, 145, 450, 865, "ink", "box", 2)
    s.text(595, 180, "U2 · TM1640 SOP28", 22, "ink", "middle", True)
    for i, (name, number, net_name) in enumerate(left):
        y = 205 + i * 50
        s.line(352, y, 370, y, "wire", 2); s.text(388, y + 5, f"{name} [{number}]", 15, "ink")
        if net_name != "NC": net(s, 352, y, net_name, "left", "power" if net_name == "+5V" else "blue")
        else: s.text(340, y + 5, "NC", 12, "muted", "end")
    for i, (name, number, net_name) in enumerate(right):
        y = 205 + i * 50
        s.line(820, y, 838, y, "wire", 2); s.text(802, y + 5, f"[{number}] {name}", 13, "ink", "end")
        if net_name != "NC": net(s, 838, y, net_name, "right")
        else: s.text(850, y + 5, "NC", 12, "muted")

    for i in range(7): resistor(s, 1280, 205 + i * 70, f"R{i + 1}", f"SEG{i + 1}_DRV", f"SEG{i + 1}")
    for i in range(8): net(s, 1060, 750 + i * 36, f"GRID{i + 1}", "right", "accent")
    s.text(70, 175, "Связь с U1", 19, "accent", bold=True)
    s.text(70, 200, "GPIO25 → TM_CLK → SCLK [8]", 16, "muted")
    s.text(70, 230, "GPIO26 → TM_DIN → DIN [7]", 16, "muted")
    s.text(70, 305, "+5V → VDD [17]", 16, "muted")
    s.text(70, 340, "GND → GND [6]", 16, "muted")
    capacitor(s, 130, 455, "C1", "100 нФ")
    capacitor(s, 130, 530, "C2", "47–100 мкФ")
    s.text(70, 710, "Важно", 19, "power", bold=True)
    s.text(70, 752, "Питание U2: 5 В.", 16, "power")
    s.text(70, 787, "Входной уровень 3,3 В", 16, "power")
    s.text(70, 822, "не гарантирован.", 16, "power")
    s.text(70, 880, "C1/C2 разместить у U2.", 15, "muted")
    s.text(70, 915, "SEG8 и GRID9…16: NC.", 15, "muted")
    s.text(70, 950, "HCT-буфер не используется.", 15, "muted")
    return s


def display_led(s, x, y, refdes, segment, grid):
    """Compact conventional LED placed at its physical seven-segment position."""
    s.line(x - 24, y, x - 12, y, "wire", 1.5)
    s.polygon([(x - 12, y - 8), (x - 12, y + 8), (x + 5, y)], "ink", "paper", 1.5)
    s.line(x + 9, y - 9, x + 9, y + 9, "ink", 1.5)
    s.line(x + 9, y, x + 24, y, "wire", 1.5)
    s.line(x + 1, y - 11, x + 8, y - 18, "led", 1)
    s.polygon([(x + 8, y - 18), (x + 4, y - 17), (x + 8, y - 14)], "led", "led", 0.8)
    s.text(x, y - 26, f"{refdes} · {segment}", 12, "ink", "middle", True)
    s.text(x - 28, y + 4, segment, 11, "blue", "end", True)
    s.text(x + 28, y + 4, f"G{grid}", 10, "accent")


def page_display(Scene):
    s = Scene()
    title(s, 3, "полное LED-табло", "46 LED в физическом порядке · слева анод/SEG · справа катод: G1…G8 = GRID1…GRID8")

    positions = {
        "a": (0, 0), "f": (-55, 55), "b": (55, 55), "g": (0, 110),
        "e": (-55, 165), "c": (55, 165), "d": (0, 220),
    }
    digits = [
        ("H1", 120, 1, 1), ("H2", 310, 2, 8),
        ("M1", 590, 4, 17), ("M2", 780, 5, 24),
        ("S1", 1060, 7, 33), ("S2", 1250, 8, 40),
    ]
    for name, cx, grid, first in digits:
        s.text(cx, 165, f"{name} · GRID{grid}", 17, "accent", "middle", True)
        s.text(cx, 190, f"D{first}…D{first + 6}", 13, "muted", "middle")
        # Thin segment guides show the physical digit shape; they are not wires.
        s.rect(cx - 83, 218, 166, 278, "light", "none", 1, 8)
        for i, segment in enumerate(("a", "b", "c", "d", "e", "f", "g")):
            dx, dy = positions[segment]
            display_led(s, cx + dx, 260 + dy, f"D{first + i}", segment, grid)

    for name, cx, grid, first in (("C1", 450, 3, 15), ("C2", 920, 6, 31)):
        s.text(cx, 230, f"{name} · GRID{grid}", 15, "accent", "middle", True)
        display_led(s, cx, 350, f"D{first}", "upper", grid)
        display_led(s, cx, 450, f"D{first + 1}", "lower", grid)

    # Large segment-name key, spatially identical to every digit above.
    s.text(80, 610, "Обозначения сегментов", 20, "accent", bold=True)
    kx, ky = 210, 680
    s.text(kx, ky - 35, "a — верхний", 14, "ink", "middle")
    s.line(kx - 45, ky, kx + 45, ky, "ink", 5)
    s.text(kx, ky + 20, "a / SEG1", 14, "blue", "middle", True)
    s.line(kx - 55, ky + 20, kx - 55, ky + 85, "ink", 5)
    s.text(kx - 75, ky + 58, "f", 15, "blue", "middle", True)
    s.line(kx + 55, ky + 20, kx + 55, ky + 85, "ink", 5)
    s.text(kx + 75, ky + 58, "b", 15, "blue", "middle", True)
    s.line(kx - 45, ky + 105, kx + 45, ky + 105, "ink", 5)
    s.text(kx, ky + 100, "g / SEG7", 14, "blue", "middle", True)
    s.line(kx - 55, ky + 125, kx - 55, ky + 190, "ink", 5)
    s.text(kx - 75, ky + 163, "e", 15, "blue", "middle", True)
    s.line(kx + 55, ky + 125, kx + 55, ky + 190, "ink", 5)
    s.text(kx + 75, ky + 163, "c", 15, "blue", "middle", True)
    s.line(kx - 45, ky + 210, kx + 45, ky + 210, "ink", 5)
    s.text(kx, ky + 235, "d / SEG4", 14, "blue", "middle", True)
    s.text(390, 690, "a = SEG1 — верхний", 15, "muted")
    s.text(390, 725, "b = SEG2 — верхний правый", 15, "muted")
    s.text(390, 760, "c = SEG3 — нижний правый", 15, "muted")
    s.text(390, 795, "d = SEG4 — нижний", 15, "muted")
    s.text(390, 830, "e = SEG5 — нижний левый", 15, "muted")
    s.text(390, 865, "f = SEG6 — верхний левый", 15, "muted")
    s.text(390, 900, "g = SEG7 — средний", 15, "muted")

    s.text(850, 610, "Назначение цифр и двоеточий", 20, "accent", bold=True)
    headers = ("Модуль", "GRID", "RAM", "LED")
    xs = (850, 1030, 1160, 1320)
    for x, value in zip(xs, headers): s.text(x, 650, value, 14, "ink", bold=True)
    rows = [
        ("H1", "1", "0", "D1…D7"), ("H2", "2", "1", "D8…D14"),
        ("C1", "3", "2", "D15,D16"), ("M1", "4", "3", "D17…D23"),
        ("M2", "5", "4", "D24…D30"), ("C2", "6", "5", "D31,D32"),
        ("S1", "7", "6", "D33…D39"), ("S2", "8", "7", "D40…D46"),
    ]
    for row, values in enumerate(rows):
        y = 690 + row * 40
        if row % 2 == 0: s.rect(835, y - 23, 690, 34, "none", "light", 0)
        for x, value in zip(xs, values): s.text(x, y, value, 14, "ink")
    s.text(850, 1035, "Двоеточия: upper = SEG1, lower = SEG2; RAM 0x03 / 0x00.", 14, "muted")
    s.text(80, 1035, "Катоды каждой цифры — только на её GRID, не на GND. DP отсутствует.", 14, "power")
    return s


def build_scenes(Scene, tm_left, tm_right):
    return [page_control(Scene), page_driver(Scene, tm_left, tm_right), page_display(Scene)]
