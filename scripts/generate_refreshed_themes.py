#!/usr/bin/env python3
"""Build the 2026 starter theme artwork and editable theme documents.

Artwork is drawn from shapes, so the release assets are reproducible and do
not depend on an external image service or fonts embedded in raster files.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
W, H, FRAMES = 1920, 462, 8

SPECS = {
    "amber_hi_fi": ("Amber Hi-Fi", (240, 182, 89), (19, 13, 10), "Analog listening room"),
    "crimson_telemetry": ("Crimson Telemetry", (255, 91, 86), (15, 9, 15), "Racing telemetry"),
    "linux_matrix_green": ("Neon Frame Arena", (124, 242, 153), (5, 16, 18), "Linux gaming terminal"),
    "nordic_forecast": ("Nordic Forecast", (127, 223, 223), (8, 19, 36), "Aurora weather observatory"),
    "obsidian_pulse": ("Obsidian Pulse", (91, 221, 244), (6, 11, 20), "Precision hardware monitor"),
    "verdant_bloom": ("Verdant Bloom", (152, 231, 147), (7, 24, 20), "Biophilic desktop"),
    "kernel_console": ("Kernel Console", (169, 236, 174), (8, 18, 16), "Unix workstation"),
    "penguin_circuit": ("Penguin Circuit", (112, 196, 255), (9, 17, 31), "Linux desktop telemetry"),
}


def rgba(rgb: tuple[int, int, int], a: int = 255) -> list[int]:
    return [*rgb, a]


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def art(name: str, frame: int) -> Image.Image:
    _, accent, base, _ = SPECS[name]
    phase = frame / FRAMES * math.tau
    img = Image.new("RGB", (W, H))
    dr = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        dr.line((0, y, W, y), fill=mix(base, (17, 30, 42), t * 0.43), width=1)
    # Common instrument-board grid, intentionally faint below live data.
    grid = mix(base, accent, 0.13)
    for x in range(0, W, 80):
        dr.line((x, 0, x, H), fill=grid, width=1)
    for y in range(0, H, 38):
        dr.line((0, y, W, y), fill=grid, width=1)
    dr.line((22, 24, W - 22, 24), fill=mix(base, accent, 0.48), width=2)
    dr.line((22, H - 23, W - 22, H - 23), fill=mix(base, accent, 0.38), width=2)
    highlight = mix(base, accent, 0.63)
    dim = mix(base, accent, 0.28)

    if name == "amber_hi_fi":
        dr.rounded_rectangle((18, 54, 465, 435), radius=24, fill=(27, 20, 16), outline=dim, width=2)
        cx, cy = 239, 237
        for r in range(177, 18, -9):
            color = mix((19, 16, 16), accent, 0.13 + (r % 27) / 180)
            dr.ellipse((cx-r, cy-r, cx+r, cy+r), outline=color, width=2)
        dr.ellipse((cx-55, cy-55, cx+55, cy+55), fill=(164, 95, 44), outline=accent, width=4)
        dr.ellipse((cx-10, cy-10, cx+10, cy+10), fill=(15, 15, 18))
        a = phase * 0.10
        dr.line((380, 82, 380 - 70 * math.sin(a), 82 + 187 * math.cos(a)), fill=(216, 194, 151), width=7)
        for i in range(0, 390, 17):
            x = 500 + i
            height = 16 + int((math.sin(i * 0.047 + phase) + 1) * 13)
            dr.line((x, 315-height, x, 315+height), fill=dim, width=5)
        cards(dr, [(488, 70, 1282, 432), (1300, 70, 1896, 432)], base, accent)
        dr.line((505, 348, 1265, 348), fill=dim, width=1)
        dr.line((1317, 348, 1879, 348), fill=dim, width=1)
    elif name == "crimson_telemetry":
        for k in range(14):
            x = 100 + k * 150 + int(18 * math.sin(phase))
            dr.polygon([(x, 80), (x+72, 80), (x-72, 430), (x-144, 430)], fill=mix(base, accent, 0.055 + (k % 3) * 0.03))
        cx, cy = 270, 258
        for r in (145, 163, 180):
            dr.arc((cx-r, cy-r, cx+r, cy+r), 145, 395, fill=highlight, width=2)
        sweep = math.radians(146 + frame * 31)
        dr.line((cx, cy, cx + 135 * math.cos(sweep), cy + 135 * math.sin(sweep)), fill=accent, width=5)
        cards(dr, [(28, 70, 548, 417), (574, 70, 1362, 417), (1388, 70, 1895, 417)], base, accent)
        # Small radar sweep beside the large live FPS readout.
        sx, sy = 445, 245
        dr.ellipse((sx-59, sy-59, sx+59, sy+59), outline=dim, width=2)
        dr.arc((sx-59, sy-59, sx+59, sy+59), frame*45, frame*45+66, fill=accent, width=5)
        dr.line((sx, sy, sx+51*math.cos(phase), sy+51*math.sin(phase)), fill=highlight, width=2)
    elif name in ("linux_matrix_green", "kernel_console"):
        for col in range(42):
            x = 32 + col * 44
            for row in range(6):
                y = ((col * 37 + row * 83 + frame * 16) % 500) - 20
                dr.line((x, y, x, y + 8), fill=mix(base, accent, 0.20 + row * 0.035), width=2)
        cards(dr, [(28, 70, 540, 418), (568, 70, 1356, 418), (1384, 70, 1894, 418)], base, accent)
        for k in range(15):
            y = 101 + k * 21
            width = 90 + ((k * 97) % 260)
            dr.line((52, y, 52 + width, y), fill=mix(base, accent, 0.14 + (k % 3) * 0.08), width=2)
        scan_y = 76 + frame * 42
        dr.line((45, scan_y, 525, scan_y), fill=highlight, width=2)
    elif name == "nordic_forecast":
        # Layered aurora ribbons and a low mountain horizon.
        for band in range(4):
            points = []
            for x in range(0, W+1, 16):
                y = 48 + band * 28 + 27 * math.sin(x / 220 + phase + band * 0.7)
                points.append((x, int(y)))
            dr.line(points, fill=mix(base, accent, 0.13 + band * 0.09), width=10 - band)
        for n in range(34):
            x = (n * 223) % W
            y = 33 + (n * 113) % 160
            r = 1 + n % 2
            dr.ellipse((x-r, y-r, x+r, y+r), fill=highlight)
        ridge = [(0, 352)] + [(x, int(320 + 27 * math.sin(x/125) + 14 * math.sin(x/41))) for x in range(0, W+1, 25)] + [(W, H)]
        dr.polygon(ridge, fill=mix(base, accent, 0.17))
        cards(dr, [(28, 82, 580, 341), (605, 82, 1894, 341), (28, 348, 1894, 430)], base, accent)
    elif name == "obsidian_pulse":
        cx, cy = 255, 232
        for r in (91, 116, 145, 180):
            dr.ellipse((cx-r, cy-r, cx+r, cy+r), outline=mix(base, accent, 0.25 + r/650), width=2)
        for n in range(64):
            a = n * math.tau/64
            r1, r2 = 155, 164 + (n % 4 == 0) * 10
            dr.line((cx+r1*math.cos(a), cy+r1*math.sin(a), cx+r2*math.cos(a), cy+r2*math.sin(a)), fill=highlight, width=2)
        pulse = 101 + frame * 8
        dr.arc((cx-pulse, cy-pulse, cx+pulse, cy+pulse), 270, 270 + 125, fill=accent, width=8)
        cards(dr, [(488, 70, 1278, 430), (1300, 70, 1894, 430)], base, accent)
        dr.line((505, 349, 1261, 349), fill=dim, width=1)
        dr.line((1317, 349, 1877, 349), fill=dim, width=1)
    elif name == "verdant_bloom":
        for j in range(11):
            x = 20 + j * 42
            bend = int(12 * math.sin(phase + j))
            dr.arc((x-130+bend, 40, x+140+bend, 470), 240, 335, fill=dim, width=2)
            for k in range(3):
                y = 100 + k * 86 + j % 3 * 14
                dr.ellipse((x+bend-11, y-22, x+bend+14, y+22), outline=highlight, width=2)
        for n in range(27):
            x = (n*149 + frame*8) % 510
            y = (n*97 + frame*5) % 410 + 25
            dr.ellipse((x, y, x+3, y+3), fill=accent)
        cards(dr, [(505, 70, 1298, 336), (1320, 70, 1894, 336), (505, 340, 1894, 435)], base, accent)
        dr.line((522, 270, 1281, 270), fill=dim, width=1)
        dr.line((1337, 270, 1877, 270), fill=dim, width=1)
    elif name == "penguin_circuit":
        # Original geometric penguin, with no trademarked distro mark.
        cx = 257
        dr.ellipse((cx-144, 78, cx+144, 404), fill=(16, 32, 51), outline=highlight, width=3)
        dr.ellipse((cx-85, 133, cx+85, 386), fill=(196, 219, 228))
        dr.ellipse((cx-42, 128, cx-8, 161), fill=(10, 22, 38))
        dr.ellipse((cx+8, 128, cx+42, 161), fill=(10, 22, 38))
        dr.polygon([(cx-22, 172), (cx+22, 172), (cx, 199)], fill=(246, 180, 94))
        dr.ellipse((cx-118, 385, cx-10, 412), fill=(246, 180, 94))
        dr.ellipse((cx+10, 385, cx+118, 412), fill=(246, 180, 94))
        for n in range(10):
            x = 462 + n * 155
            y = 96 + (n * 83) % 290
            dr.line((x-20, y, x+48, y, x+48, y+30), fill=dim, width=2)
            dr.ellipse((x+44, y+26, x+52, y+34), fill=accent)
        cards(dr, [(488, 70, 1278, 420), (1300, 70, 1894, 420)], base, accent)
        dr.arc((cx-153, 68, cx+153, 414), frame*45, frame*45+74, fill=accent, width=4)
    # Moving luminous strip is visible in every theme but stays behind text.
    strip_x = 35 + frame * 230
    dr.line((strip_x, 440, min(W - 35, strip_x + 168), 440), fill=accent, width=4)
    return img


def cards(dr: ImageDraw.ImageDraw, rects: list[tuple[int, int, int, int]], base, accent) -> None:
    for x0, y0, x1, y1 in rects:
        dr.rounded_rectangle((x0, y0, x1, y1), radius=22, fill=mix(base, (0, 0, 0), 0.35), outline=mix(base, accent, 0.39), width=2)
        if y1 - y0 > 110:
            dr.line((x0+20, y0+16, x0+90, y0+16), fill=accent, width=3)


def text(value: str, x: int, y: int, size: int, color, width: int = 360, bold: bool = False) -> dict:
    return {"id": f"txt_{len(ITEMS['texts'])}", "text": value, "x": x, "y": y,
            "box_width": width, "box_height": size+12, "font_size": size,
            "font_bold": bold, "color": rgba(color)}


def stat(source: str, x: int, y: int, size: int, color, width: int = 220, fmt: str = "{value}", **extra) -> dict:
    return {"id": f"stat_{len(ITEMS['stats'])}", "source": source, "x": x, "y": y,
            "box_width": width, "box_height": max(34, size+12), "font_size": size,
            "font_bold": True, "format": fmt, "value_color": rgba(color), **extra}


def add_text(*args, **kwargs):
    ITEMS["texts"].append(text(*args, **kwargs))


def add_stat(*args, **kwargs):
    ITEMS["stats"].append(stat(*args, **kwargs))


def pair(label: str, source: str, x: int, y: int, accent, value_color=(237, 246, 249), width=205, size=28):
    add_text(label, x, y, 12, accent, width, True)
    add_stat(source, x, y+22, size, value_color, width)


def widget(kind: str, rect, accent, template: str, style: str | None = None) -> None:
    original = json.loads((THEMES / f"{template}.json").read_text())
    sample = next(w for w in original["widgets"] if w["kind"] == kind)
    item = deepcopy(sample)
    item["id"] = f"widget_{len(ITEMS['widgets'])}"
    item["rect"] = list(rect)
    if style is not None:
        item["style"] = style
    settings = item["settings"]
    settings["panel_enabled"] = False
    settings["backdrop_enabled"] = False
    settings["day_color"] = rgba(accent)
    settings["equalizer_color"] = rgba(accent)
    settings["title_color"] = [237, 246, 249, 255]
    settings["temp_color"] = rgba(accent)
    settings["title_marquee"] = True
    settings["animate_icons"] = True
    if kind == "media_now_playing":
        settings["equalizer_color_preset"] = "custom"
        settings["title_font_size"] = 31
        settings["artist_font_size"] = 20
        settings["equalizer_bars"] = 24
    ITEMS["widgets"].append(item)


def build_document(name: str, frames: list[str]) -> dict:
    title, accent, base, description = SPECS[name]
    white = (237, 246, 249)
    add_text(title.upper(), 36, 31, 27, accent, 620, True)
    add_text(description.upper() + "  /  LIVE", 765, 37, 13, mix(accent, white, 0.35), 620, True)
    add_stat("time_hms", 1645, 28, 29, white, 245)

    if name == "amber_hi_fi":
        add_text("SIDE A  /  NOW PLAYING", 515, 91, 14, accent, 570, True)
        widget("media_now_playing", (515, 129, 742, 188), accent, "amber_hi_fi")
        add_text("OUTSIDE", 1325, 91, 14, accent, 420, True)
        widget("weather_current", (1324, 130, 535, 180), accent, "amber_hi_fi")
        for label, source, x, width in (("CPU", "cpu_usage_percent", 520, 225),
                                         ("GPU", "gpu_load", 770, 225),
                                         ("RAM", "mem_percent", 1020, 225),
                                         ("VOLUME", "volume_percent", 1330, 225),
                                         ("UPTIME", "uptime_human", 1615, 245)):
            pair(label, source, x, 366, accent, width=width)
    elif name == "crimson_telemetry":
        add_text("SESSION / LIVE", 57, 91, 14, accent, 410, True)
        add_stat("game_fps", 64, 147, 97, white, 350)
        add_text("FRAMES / SECOND", 72, 259, 15, accent, 320, True)
        pair("1% LOW", "game_fps_1pct_low", 64, 340, accent, width=170)
        pair("FRAMETIME", "game_frametime_ms", 285, 340, accent, width=225)
        add_text("GPU", 610, 92, 14, accent, 240, True)
        add_text("CPU", 842, 92, 14, accent, 240, True)
        add_text("MEMORY", 1078, 92, 14, accent, 240, True)
        for i, source in enumerate(("gpu_load", "cpu_usage_percent", "mem_percent")):
            add_stat(source, 604+i*233, 124, 24, white, 215, box_height=183, display="gauge", gauge_ring_size=148,
                     track_color=[70, 29, 38, 230], fill_color=rgba(accent))
        for i, (label, source) in enumerate((("GPU TEMP", "gpu_temp"), ("CPU TEMP", "cpu_temp_c"), ("VRAM", "vram_percent"))):
            pair(label, source, 613+i*234, 345, accent, width=210, size=24)
        add_text("TOP MEMORY", 1415, 91, 14, accent, 360, True)
        for i in range(1, 5):
            y = 137+(i-1)*65
            add_stat(f"process_ram_{i}_name", 1415, y, 18, white, 300)
            add_stat(f"process_ram_{i}_gib", 1730, y, 18, accent, 135)
            add_text(f"0{i}", 1416, y+29, 11, accent, 50)
    elif name == "linux_matrix_green":
        add_text("$ systemctl status desktop", 56, 92, 19, accent, 440, True)
        pair("HOST", "hostname", 59, 143, accent, width=430, size=27)
        pair("UPTIME", "uptime_human", 59, 214, accent, width=430, size=27)
        pair("LOAD", "load_average", 59, 285, accent, width=430, size=27)
        add_text("GAME SESSION  /  PROTON", 596, 92, 14, accent, 610, True)
        add_stat("game_name", 598, 128, 29, white, 715)
        add_stat("game_fps", 599, 182, 79, accent, 330)
        add_text("FPS", 610, 273, 14, accent, 150, True)
        pair("1% LOW", "game_fps_1pct_low", 945, 196, accent, width=175, size=30)
        pair("FRAME TIME", "game_frametime_ms", 1135, 196, accent, width=195, size=30)
        for i, (label, source) in enumerate((("GPU", "gpu_load"), ("CPU", "cpu_usage_percent"), ("RAM", "mem_percent"))):
            pair(label, source, 600+i*230, 330, accent, width=210, size=26)
        add_text("DESKTOP", 1410, 92, 14, accent, 380, True)
        widget("weather_current", (1410, 132, 450, 164), accent, "linux_matrix_green")
        add_text("AUDIO", 1410, 307, 13, accent, 360, True)
        widget("media_now_playing", (1410, 334, 444, 66), accent, "amber_hi_fi", "mini")
    elif name == "nordic_forecast":
        add_text("CURRENT CONDITIONS", 58, 103, 14, accent, 470, True)
        widget("weather_current", (57, 145, 496, 171), accent, "nordic_forecast")
        add_text("7 DAY OUTLOOK", 630, 103, 14, accent, 1150, True)
        widget("weather_forecast_7d", (626, 144, 1238, 168), accent, "nordic_forecast")
        for i, (label, source) in enumerate((("HUMIDITY", "weather_humidity_percent"), ("WIND", "weather_wind_kph"), ("RAIN", "weather_precip_mm"), ("CPU", "cpu_usage_percent"), ("UPTIME", "uptime_human"))):
            pair(label, source, 58+i*365, 365, accent, width=335, size=25)
    elif name == "obsidian_pulse":
        add_text("HARDWARE / PULSE", 57, 92, 14, accent, 410, True)
        add_stat("cpu_usage_percent", 134, 176, 63, white, 260)
        add_text("CPU LOAD", 154, 265, 13, accent, 200, True)
        add_text("LISTENING", 518, 91, 14, accent, 730, True)
        widget("media_now_playing", (514, 127, 725, 185), accent, "obsidian_pulse")
        add_text("WEATHER", 1325, 91, 14, accent, 445, True)
        widget("weather_current", (1324, 129, 534, 178), accent, "obsidian_pulse")
        for label, source, x, width in (("CPU TEMP", "cpu_temp_c", 515, 225),
                                         ("GPU LOAD", "gpu_load", 770, 225),
                                         ("GPU TEMP", "gpu_temp", 1025, 225),
                                         ("MEMORY", "mem_percent", 1325, 225),
                                         ("VRAM", "vram_percent", 1600, 260)):
            pair(label, source, x, 367, accent, width=width, size=25)
    elif name == "verdant_bloom":
        add_text("CURRENT SONG", 533, 91, 14, accent, 720, True)
        widget("media_now_playing", (533, 128, 716, 126), accent, "verdant_bloom")
        add_text("FOREST WEATHER", 1347, 91, 14, accent, 470, True)
        widget("weather_current", (1343, 131, 518, 134), accent, "verdant_bloom")
        widget("weather_forecast_7d", (531, 349, 1329, 80), accent, "verdant_bloom")
        ITEMS["widgets"][-1]["settings"].update({
            "location_font_size": 15,
            "day_font_size": 15,
            "temp_max_font_size": 19,
            "temp_min_font_size": 13,
            "condition_font_size": 11,
        })
        for label, source, x, width in (("CPU", "cpu_usage_percent", 540, 220),
                                         ("GPU", "gpu_load", 790, 220),
                                         ("RAM", "mem_percent", 1040, 220),
                                         ("UPTIME", "uptime_human", 1345, 280)):
            pair(label, source, x, 276, accent, width=width, size=23)
    elif name == "kernel_console":
        add_text("abigor@trofeo:~$", 57, 95, 22, accent, 445, True)
        add_text("uname -a  /  htop  /  sensors", 58, 135, 17, white, 450)
        pair("HOST", "hostname", 59, 189, accent, width=430, size=27)
        pair("IPV4", "ip_local", 59, 260, accent, width=430, size=24)
        pair("UPTIME", "uptime_human", 59, 333, accent, width=430, size=25)
        add_text("PROCESS / RESOURCES", 594, 92, 14, accent, 670, True)
        for i, (label, source) in enumerate((("CPU", "cpu_usage_percent"), ("GPU", "gpu_load"), ("RAM", "mem_percent"), ("DISK", "disk_percent"))):
            x, y = 600+(i%2)*364, 140+(i//2)*130
            pair(label, source, x, y, accent, width=320, size=37)
            add_stat(source, x, y+74, 12, accent, 310, display="progress", show_value_text=False, stroke_width=9)
        add_text("NETWORK / TRAFFIC", 1410, 92, 14, accent, 400, True)
        pair("DOWNLOAD", "net_dl_kbps", 1414, 145, accent, width=410, size=27)
        pair("UPLOAD", "net_ul_kbps", 1414, 231, accent, width=410, size=27)
        pair("KERNEL LOAD", "load_average", 1414, 318, accent, width=410, size=27)
    elif name == "penguin_circuit":
        add_text("LINUX / DESKTOP", 518, 91, 14, accent, 740, True)
        pair("HOST", "hostname", 523, 133, accent, width=710, size=35)
        for i, (label, source) in enumerate((("CPU", "cpu_usage_percent"), ("GPU", "gpu_load"), ("MEM", "mem_percent"))):
            pair(label, source, 524+i*239, 224, accent, width=220, size=32)
        pair("UPTIME", "uptime_human", 524, 332, accent, width=280, size=27)
        pair("NETWORK", "net_dl_kbps", 867, 332, accent, width=320, size=25)
        add_text("WEATHER / AUDIO", 1325, 91, 14, accent, 455, True)
        widget("weather_current", (1324, 128, 530, 138), accent, "obsidian_pulse")
        widget("media_now_playing", (1325, 287, 527, 113), accent, "amber_hi_fi", "mini")

    return {
        "schema_version": 1,
        "meta": {"name": title, "author": "Open Trofeo LCD", "description": description + "; live telemetry with subtle looped artwork.",
                 "tags": ["starter-pack", "animated", "linux"] if name in ("linux_matrix_green", "kernel_console", "penguin_circuit") else ["starter-pack", "animated"]},
        "canvas": {"width": W, "height": H, "rotation": 180},
        "background": {"kind": "image", "path": frames[0], "fit": "cover", "base_color": list(base),
                       "accent_color": list(accent), "texture_alpha": 0.0, "panels": []},
        "texts": ITEMS["texts"], "stats": ITEMS["stats"], "images": [], "widgets": ITEMS["widgets"],
        "effects": {"animation": {"enabled": True, "use_as_background": True, "fps": 4,
                                  "loop": True, "smooth_loop": False, "current_frame": 0,
                                  "frame_paths": frames, "frame_durations_ms": [250]*FRAMES}},
    }


def main() -> None:
    global ITEMS
    for name in SPECS:
        assets = THEMES / f"{name}_assets" / "2026-10-10" / "frames"
        assets.mkdir(parents=True, exist_ok=True)
        frames = []
        for idx in range(FRAMES):
            file = assets / f"{name}_frame_{idx:04d}.jpg"
            art(name, idx).save(file, quality=88, subsampling=0, optimize=True)
            frames.append(file.relative_to(THEMES).as_posix())
        ITEMS = {"texts": [], "stats": [], "widgets": []}
        output = THEMES / f"{name}.json"
        output.write_text(json.dumps(build_document(name, frames), indent=2, ensure_ascii=False) + "\n")
        print(f"{output.relative_to(ROOT)}: {len(frames)} frames")


if __name__ == "__main__":
    main()
