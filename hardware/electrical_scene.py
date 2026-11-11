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
    s.text(x, y - 22, f"{refdes} · ОМЛТ 510 Ω", 15, "ink", "middle", True)


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
    esp_pins = [
        ("GPIO18", "18", "TFT_SCLK"), ("GPIO23", "23", "TFT_MOSI"),
        ("GPIO5", "5", "TFT_CS"), ("GPIO15", "15", "TFT_DC"),
        ("GPIO4", "4", "TFT_RST"), ("GPIO21", "21", "I2C_SDA"),
        ("GPIO22", "22", "I2C_SCL"), ("GPIO25", "25", "TM_CLK"),
        ("GPIO26", "26", "TM_DIN"), ("GPIO32", "32", "CITY_WIFI_BTN"),
    ]
    esp = module(s, 425, 155, 350, 785, "U1", "ESP32-WROOM-32D", esp_pins, "right")
    net(s, 425, 235, "+5V", "left", "power"); s.text(439, 240, "5V", 14, "ink")
    net(s, 425, 285, "GND", "left", "ink"); s.text(439, 290, "GND", 14, "ink")
    for label, (x, y, net_name) in esp.items(): net(s, x + 18, y, net_name, "right")

    tft_pins = [(x, x, n) for x, n in (("SCLK", "TFT_SCLK"), ("MOSI/SDA", "TFT_MOSI"), ("CS", "TFT_CS"), ("DC", "TFT_DC"), ("RST/RES", "TFT_RST"), ("VCC", "VCC_ST7789"), ("GND", "GND"))]
    tft = module(s, 1050, 145, 300, 340, "A1", "ST7789 284×76", tft_pins)
    for label, (x, y, net_name) in tft.items(): net(s, x - 18, y, net_name, "left", "power" if label == "VCC" else "blue")

    rtc_pins = [(x, x, n) for x, n in (("SDA", "I2C_SDA"), ("SCL", "I2C_SCL"), ("VCC", "VCC_RTC"), ("GND", "GND"))]
    rtc = module(s, 1050, 555, 300, 240, "U3", "DS3231 RTC", rtc_pins)
    for label, (x, y, net_name) in rtc.items(): net(s, x - 18, y, net_name, "left", "power" if label == "VCC" else "blue")

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
        "• VCC_ST7789: по спецификации модуля.",
        "• Подсветка ST7789 включена постоянно.",
        "• VCC_RTC: по спецификации модуля DS3231.",
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
    left = [(name, number, {"VDD": "+5V", "GND": "GND", "DIN": "TM_DIN", "SCLK": "TM_CLK"}[name]) for name, number in tm_left]
    right = []
    for name, number in tm_right:
        if name.startswith("SEG") and int(name[3:]) <= 7: net_name = name + "_DRV"
        elif name.startswith("GRID") and int(name[4:]) <= 8: net_name = name
        else: net_name = "NC"
        right.append((name, number, net_name))
    s.rect(370, 145, 450, 865, "ink", "box", 2)
    s.text(595, 180, "U2 · TM1640 SOP28", 22, "ink", "middle", True)
    for i, (name, number, net_name) in enumerate(left):
        y = 260 + i * 100
        s.line(352, y, 370, y, "wire", 2); s.text(388, y + 5, f"{name} [{number}]", 15, "ink")
        net(s, 352, y, net_name, "left", "power" if net_name == "+5V" else "blue")
    for i, (name, number, net_name) in enumerate(right):
        y = 205 + i * 32
        s.line(820, y, 838, y, "wire", 2); s.text(802, y + 5, f"[{number}] {name}", 13, "ink", "end")
        if net_name != "NC": net(s, 838, y, net_name, "right")
        else: s.text(850, y + 5, "NC", 12, "muted")

    for i in range(7): resistor(s, 1190, 205 + i * 70, f"R{i + 1}", f"SEG{i + 1}_DRV", f"SEG{i + 1}")
    for i in range(8): net(s, 1100, 735 + i * 38, f"GRID{i + 1}", "right", "accent")
    s.text(70, 175, "Связь с U1", 19, "accent", bold=True)
    s.text(70, 200, "GPIO25 → TM_CLK → SCLK [8]", 16, "muted")
    s.text(70, 230, "GPIO26 → TM_DIN → DIN [7]", 16, "muted")
    s.text(70, 305, "+5V → VDD [17]", 16, "muted")
    s.text(70, 340, "GND → GND [6]", 16, "muted")
    capacitor(s, 180, 455, "C1", "100 нФ")
    capacitor(s, 180, 570, "C2", "47–100 мкФ")
    s.text(70, 710, "Важно", 19, "power", bold=True)
    s.text(70, 752, "Питание U2: 5 В.", 16, "power")
    s.text(70, 787, "Входной уровень 3,3 В", 16, "power")
    s.text(70, 822, "не гарантирован datasheet.", 16, "power")
    s.text(70, 880, "C1/C2 разместить у U2.", 15, "muted")
    s.text(70, 915, "SEG8 и GRID9…16: NC.", 15, "muted")
    s.text(70, 950, "HCT-буфер не используется.", 15, "muted")
    return s


def page_display(Scene):
    s = Scene()
    title(s, 3, "цифры и двоеточия", "Одна типовая цифра повторяется 6 раз · всего 46 LED · катоды объединяются только внутри своего GRID")
    s.text(90, 145, "Типовая цифра DGx", 20, "accent", bold=True)
    s.text(90, 175, "n — первый номер LED из таблицы ниже", 15, "muted")
    rail_x = 650
    ys = []
    for i, segment in enumerate(("a", "b", "c", "d", "e", "f", "g"), 1):
        y = 240 + (i - 1) * 82
        led(s, 390, y, f"D(n+{i - 1}) · {segment}", i)
        s.line(475, y, rail_x, y, "wire", 2)
        s.circle(rail_x, y, 5, "wire", "wire", 1)
        ys.append(y)
    s.line(rail_x, ys[0], rail_x, ys[-1] + 65, "wire", 3)
    net(s, rail_x, ys[-1] + 65, "GRIDx", "right", "accent")
    s.text(90, 855, "Двоеточие COLx", 20, "accent", bold=True)
    led(s, 280, 930, "D(c) · upper", 1)
    led(s, 280, 1020, "D(c+1) · lower", 2)
    s.line(365, 930, 560, 930, "wire", 2); s.line(365, 1020, 560, 1020, "wire", 2)
    s.line(560, 930, 560, 1020, "wire", 3)
    s.circle(560, 930, 5, "wire", "wire", 1); s.circle(560, 1020, 5, "wire", "wire", 1)
    net(s, 560, 1020, "GRIDx", "right", "accent")

    s.text(900, 150, "Назначение модулей и LED", 20, "accent", bold=True)
    headers = ("Модуль", "GRID", "RAM", "LED / n или c")
    xs = (900, 1100, 1200, 1320)
    for x, value in zip(xs, headers): s.text(x, 195, value, 15, "ink", bold=True)
    rows = [
        ("H1", "1", "0", "D1…D7 / n=1"),
        ("H2", "2", "1", "D8…D14 / n=8"),
        ("C1", "3", "2", "D15,D16 / c=15"),
        ("M1", "4", "3", "D17…D23 / n=17"),
        ("M2", "5", "4", "D24…D30 / n=24"),
        ("C2", "6", "5", "D31,D32 / c=31"),
        ("S1", "7", "6", "D33…D39 / n=33"),
        ("S2", "8", "7", "D40…D46 / n=40"),
    ]
    for row, values in enumerate(rows):
        y = 240 + row * 55
        if row % 2 == 0: s.rect(885, y - 25, 650, 42, "none", "light", 0)
        for x, value in zip(xs, values): s.text(x, y, value, 15, "ink")
    s.text(900, 745, "Правила монтажа", 20, "accent", bold=True)
    rules = [
        "• SEG1…7 = a,b,c,d,e,f,g.",
        "• Анод каждого LED — на свой SEG после R.",
        "• Катоды цифры — на её GRID, не на GND.",
        "• Двоеточие: upper=SEG1, lower=SEG2.",
        "• Включено: RAM[colon]=0x03.",
        "• Выключено: RAM[colon]=0x00.",
        "• SEG8/DP и GRID9…16 не используются.",
    ]
    for i, value in enumerate(rules): s.text(900, 790 + i * 38, value, 15, "muted")
    return s


def build_scenes(Scene, tm_left, tm_right):
    return [page_control(Scene), page_driver(Scene, tm_left, tm_right), page_display(Scene)]
