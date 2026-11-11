"""Render multiple Scene pages to one vector PDF and one stacked SVG."""

import html
from reportlab.pdfgen import canvas as pdfcanvas


def rgb(colors, value):
    value = colors.get(value, value)
    if value == "none": return None
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def write_svg(scenes, path, width, height, colors):
    gap = 40
    total_height = len(scenes) * height + (len(scenes) - 1) * gap
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}">',
           '<title>ESP32 complete electrical schematic</title>',
           '<desc>Three conventional schematic sheets: ESP32 peripherals, TM1640 and LED modules</desc>',
           '<rect width="100%" height="100%" fill="#dce3ec"/>']
    for page, scene in enumerate(scenes):
        offset = page * (height + gap)
        out.append(f'<g transform="translate(0 {offset})">')
        out.append(f'<rect width="{width}" height="{height}" fill="#ffffff"/>')
        for kind, p in scene.items:
            if kind == "line":
                dash = f' stroke-dasharray="{p["dash"]}"' if p["dash"] else ""
                out.append(f'<line x1="{p["x1"]}" y1="{p["y1"]}" x2="{p["x2"]}" y2="{p["y2"]}" stroke="{colors.get(p["color"], p["color"])}" stroke-width="{p["width"]}"{dash}/>')
            elif kind == "rect":
                out.append(f'<rect x="{p["x"]}" y="{p["y"]}" width="{p["w"]}" height="{p["h"]}" rx="{p["rx"]}" stroke="{colors.get(p["stroke"], p["stroke"])}" fill="{colors.get(p["fill"], p["fill"])}" stroke-width="{p["width"]}"/>')
            elif kind == "circle":
                out.append(f'<circle cx="{p["x"]}" cy="{p["y"]}" r="{p["r"]}" stroke="{colors.get(p["stroke"], p["stroke"])}" fill="{colors.get(p["fill"], p["fill"])}" stroke-width="{p["width"]}"/>')
            elif kind == "polygon":
                pts = " ".join(f'{x},{y}' for x, y in p["points"])
                out.append(f'<polygon points="{pts}" stroke="{colors.get(p["stroke"], p["stroke"])}" fill="{colors.get(p["fill"], p["fill"])}" stroke-width="{p["width"]}"/>')
            elif kind == "text":
                weight = "700" if p["bold"] else "400"
                value = html.escape(str(p["value"]))
                out.append(f'<text x="{p["x"]}" y="{p["y"]}" font-family="DejaVu Sans,Arial,sans-serif" font-size="{p["size"]}" font-weight="{weight}" text-anchor="{p["anchor"]}" fill="{colors.get(p["color"], p["color"])}">{value}</text>')
        out.append('</g>')
    out.append('</svg>')
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def write_pdf(scenes, path, width, height, colors):
    c = pdfcanvas.Canvas(str(path), pagesize=(width, height), pageCompression=1)
    c.setTitle("ESP32 clock — complete electrical schematic")
    c.setAuthor("Clock project")
    for scene in scenes:
        for kind, p in scene.items:
            if kind == "line":
                c.setStrokeColorRGB(*rgb(colors, p["color"])); c.setLineWidth(p["width"])
                if p["dash"]: c.setDash(p["dash"].split(","))
                c.line(p["x1"], height - p["y1"], p["x2"], height - p["y2"])
                if p["dash"]: c.setDash()
            elif kind == "rect":
                stroke = rgb(colors, p["stroke"])
                if stroke: c.setStrokeColorRGB(*stroke)
                c.setLineWidth(p["width"])
                fill = rgb(colors, p["fill"])
                if fill: c.setFillColorRGB(*fill)
                c.roundRect(p["x"], height - p["y"] - p["h"], p["w"], p["h"], p["rx"], stroke=1 if stroke else 0, fill=1 if fill else 0)
            elif kind == "circle":
                c.setStrokeColorRGB(*rgb(colors, p["stroke"])); c.setLineWidth(p["width"])
                fill = rgb(colors, p["fill"])
                if fill: c.setFillColorRGB(*fill)
                c.circle(p["x"], height - p["y"], p["r"], stroke=1, fill=1 if fill else 0)
            elif kind == "polygon":
                c.setStrokeColorRGB(*rgb(colors, p["stroke"])); c.setLineWidth(p["width"])
                fill = rgb(colors, p["fill"])
                if fill: c.setFillColorRGB(*fill)
                obj = c.beginPath(); obj.moveTo(p["points"][0][0], height - p["points"][0][1])
                for x, y in p["points"][1:]: obj.lineTo(x, height - y)
                obj.close(); c.drawPath(obj, stroke=1, fill=1 if fill else 0)
            elif kind == "text":
                c.setFillColorRGB(*rgb(colors, p["color"])); c.setFont("DVB" if p["bold"] else "DV", p["size"])
                if p["anchor"] == "middle": c.drawCentredString(p["x"], height - p["y"], str(p["value"]))
                elif p["anchor"] == "end": c.drawRightString(p["x"], height - p["y"], str(p["value"]))
                else: c.drawString(p["x"], height - p["y"], str(p["value"]))
        c.showPage()
    c.save()
