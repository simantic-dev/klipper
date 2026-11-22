"""Render klipper-move.gif from a `sim run --record` bundle: host<->MCU UART bytes and STEP/DIR edges.
Usage: uv run --with pillow make_gif.py <rec_dir> [out.gif]"""
import json, sys
from PIL import Image, ImageDraw

rec, out = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "klipper-move.gif")
load = lambda k: [json.loads(l) for l in open(f"{rec}/{k}.jsonl")]
uart = [(e["t"], e["label"], len(e["text"].encode("utf-8", "surrogateescape"))) for e in load("uart")]
gpio = [(e["t"], e["pin"], e["level"]) for e in load("gpio") if e["port"] == "gpioPortB"]
T0, T1 = 0.405, 0.447                      # window: config commands -> end of the 100-step move
W, H, L = 900, 360, 150
x = lambda t: L + (t - T0) / (T1 - T0) * (W - L - 20)
rows = {"host -> MCU": 70, "MCU -> host": 120, "DIR  PB1": 200, "STEP PB0": 270}

def wave(d, pin, y, tnow):
    lvl, px = 0, x(T0)
    for t, p, v in gpio:
        if p != pin or t < T0: lvl = v if p == pin else lvl; continue
        if t > tnow: break
        d.line([(px, y - 25 * lvl), (x(t), y - 25 * lvl), (x(t), y - 25 * v)], fill="#2b7", width=2)
        px, lvl = x(t), v
    d.line([(px, y - 25 * lvl), (x(min(tnow, T1)), y - 25 * lvl)], fill="#2b7", width=2)

frames = []
for i in range(60):
    tnow = T0 + (T1 - T0) * (i + 1) / 60
    im = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(im)
    d.text((10, 10), "Klipper v0.14.0 on simulated STM32F446 (pyrite) - scripted host sends a 100-step move", fill="black")
    for name, y in rows.items(): d.text((10, y - 12), name, fill="black")
    for t, lab, n in uart:
        if T0 <= t <= tnow:
            y = rows["host -> MCU" if "←" in lab else "MCU -> host"]
            d.rectangle([x(t), y - 4 - min(n, 40) / 2, x(t) + 3, y + 4], fill="#36c")
    wave(d, 1, rows["DIR  PB1"], tnow); wave(d, 0, rows["STEP PB0"], tnow)
    steps = sum(1 for t, p, v in gpio if p == 0 and v == 1 and t <= tnow)
    d.text((10, 320), f"virtual t = {tnow*1e3:7.2f} ms    steps = {steps}/100 (commanded 100 x 100 us)", fill="black")
    frames.append(im)
frames[0].save(out, save_all=True, append_images=frames[1:] + [frames[-1]] * 20, duration=80, loop=0)
print(out, len(frames))
