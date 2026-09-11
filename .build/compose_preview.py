"""Compose a single PNG that shows how the README will look on GitHub.

Stacks the real assets at their README widths on GitHub's dark canvas and draws
stand-ins for the remote badge rows. Preview only - not referenced by README.md.
Run from the repo root: python .build/compose_preview.py
"""

import os

from PIL import Image, ImageDraw, ImageFont

W = 1012                      # GitHub's readme content width
CANVAS = (13, 17, 23)         # #0d1117, the page ground we cannot change
PAD = 40
S = 2                         # supersample, for legible text in the export

VT323 = ".build/VT323-Regular.ttf"

# (kind, payload) - "img": (path, css_width); "gap": px; "badges": (labels, inverted)
LAYOUT = [
    ("img", ("assets/p-hands.png", W - 2 * PAD)),
    ("gap", 28),
    ("img", ("assets/t-persus.png", 440)),
    ("gap", 12),
    ("img", ("assets/b-tagline.png", 760)),
    ("gap", 12),
    ("img", ("assets/b-tags.png", 820)),
    ("gap", 34),
    ("img", ("assets/t-about.png", 400)),
    ("gap", 12),
    ("img", ("assets/b-about.png", 880)),
    ("gap", 34),
    ("img", ("assets/t-stack.png", 390)),
    ("gap", 12),
    ("img", ("assets/b-stack.png", 900)),
    ("gap", 34),
    ("img", ("assets/t-work.png", 375)),
    ("gap", 12),
    ("img", ("assets/b-work.png", 720)),
    ("gap", 12),
    ("img", ("assets/b-education.png", 800)),
    ("gap", 34),
    ("img", ("assets/t-projects.png", 560)),
    ("gap", 12),
    ("img", ("assets/b-projects.png", 960)),
    ("gap", 16),
    ("badges", (["WMF BENCHMARK", "PERSEO", "HYBRIDMAMBA-11", "JETSON ORIN",
                 "MULTILINGUAL", "NETKEY"], False)),
    ("gap", 8),
    ("badges", (["ALL PROJECTS ->"], True)),
    ("gap", 34),
    ("img", ("assets/t-now.png", 300)),
    ("gap", 12),
    ("img", ("assets/b-now.png", 800)),
    ("gap", 34),
    ("img", ("assets/t-contact.png", 560)),
    ("gap", 12),
    ("badges", (["WEBSITE", "EMAIL", "LINKEDIN", "TWITTER", "INSTAGRAM"], False)),
    ("gap", 12),
    ("img", ("assets/b-coords.png", 400)),
    ("gap", 28),
    ("img", ("assets/p-angel.png", W - 2 * PAD)),
]

BADGE_H = 28
STATS_H = 150


def scaled(path, width):
    im = Image.open(path).convert("RGB")
    h = round(im.height * width / im.width)
    return im.resize((width * S, h * S), Image.LANCZOS), h


def badge_row(labels, inverted, font):
    """Approximate a shields.io for-the-badge row in pure black and white."""
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    pad, gap = 14, 6
    widths = [int(probe.textlength(t, font=font) / S) + 2 * pad for t in labels]
    total = sum(widths) + gap * (len(widths) - 1)
    strip = Image.new("RGB", (total * S, BADGE_H * S), CANVAS)
    d = ImageDraw.Draw(strip)
    x = 0
    for text, bw in zip(labels, widths):
        bg = (255, 255, 255) if inverted else CANVAS
        fg = (0, 0, 0) if inverted else (255, 255, 255)
        d.rectangle([x * S, 0, (x + bw) * S - 1, BADGE_H * S - 1], fill=bg)
        tw = probe.textlength(text, font=font)
        d.text((x * S + (bw * S - tw) / 2, BADGE_H * S * 0.18), text, font=font, fill=fg)
        x += bw + gap
    return strip, total


def main():
    font = ImageFont.truetype(VT323, 20 * S)
    blocks = []
    y = PAD
    for kind, payload in LAYOUT:
        if kind == "gap":
            y += payload
        elif kind == "img":
            path, width = payload
            im, h = scaled(path, width)
            blocks.append((im, width, y))
            y += h
        elif kind == "badges":
            labels, inverted = payload
            im, width = badge_row(labels, inverted, font)
            blocks.append((im, width, y))
            y += BADGE_H
        elif kind == "stats":
            im = Image.new("RGB", (740 * S, STATS_H * S), CANVAS)
            d = ImageDraw.Draw(im)
            d.text((24 * S, 60 * S),
                   "[ github-readme-stats - renders on GitHub ]",
                   font=font, fill=(150, 150, 150))
            blocks.append((im, 740, y))
            y += STATS_H

    canvas = Image.new("RGB", (W * S, (y + PAD) * S), CANVAS)
    for im, width, top in blocks:
        canvas.paste(im, (int((W - width) / 2 * S), top * S))

    out = os.path.join(".build", "preview.png")
    canvas.resize((W, canvas.height // S), Image.LANCZOS).save(out)
    print("%s  %dx%d" % (out, W, canvas.height // S))


if __name__ == "__main__":
    main()
