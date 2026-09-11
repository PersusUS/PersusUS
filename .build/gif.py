"""Put the Now section's shark loop behind an old television.

Dropped in as it came, the clip is a grey-on-white underwater shot and reads
as a lit rectangle on a dark page. Rather than redraw it, this runs it through
the things that made a CRT picture look the way it did: the greys are pulled
down and mapped onto the page ground, the highlights bloom into their
neighbours, every other line is darkened into a scanline, a little grain is
laid over the top, and the corners are rounded and dimmed the way the glass
fell away at the edge of the tube.

Run from the repo root: python .build/gif.py
"""

import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageSequence

SRC = ".build/src/03-shark.gif"
OUT = "assets/g-shark.gif"

GROUND = (13, 17, 23)          # #0d1117 - GitHub dark canvas
WIDTH = 240                    # px across; the height follows the clip
CEILING = 150                  # brightest the picture is allowed to get
GAMMA = 1.25                   # >1 keeps the water off the white end
BLOOM = 0.45                   # how much of the blurred copy is added back
SCANLINE = 0.55                # every other line is scaled by this
GRAIN = 4                      # +/- levels of noise per pixel
RADIUS = 16                    # px the corners are rounded by
EDGE = 0.30                    # share of each axis the edge dimming spans


def tube(size):
    """Bright in the middle, falling away at the glass, square at no corner."""
    w, h = size
    mask = Image.new("L", size)
    px = mask.load()
    for y in range(h):
        fy = min(1.0, min(y, h - 1 - y) / (h * EDGE))
        for x in range(w):
            fx = min(1.0, min(x, w - 1 - x) / (w * EDGE))
            px[x, y] = int(255 * (0.35 + 0.65 * (fx * fy) ** 0.8))
    corners = Image.new("L", size, 0)
    ImageDraw.Draw(corners).rounded_rectangle([0, 0, w - 1, h - 1], RADIUS, fill=255)
    return ImageChops.multiply(mask, corners)


def picture(frame, size):
    """One frame as a CRT would have shown it, still a single grey channel."""
    g = frame.convert("L").resize(size, Image.LANCZOS)
    g = g.point(lambda v: int((v / 255) ** GAMMA * CEILING))
    g = ImageChops.add(g, g.filter(ImageFilter.GaussianBlur(2.2)).point(
        lambda v: int(v * BLOOM)))
    px = g.load()
    w, h = size
    for y in range(h):
        line = SCANLINE if y % 2 else 1.0
        for x in range(w):
            v = px[x, y] * line + random.randint(-GRAIN, GRAIN)
            px[x, y] = max(0, min(255, int(v)))
    return g


def main():
    src = Image.open(SRC)
    w, h = src.size
    size = (WIDTH, round(WIDTH * h / w))
    mask = tube(size)
    ground = Image.new("RGB", size, GROUND)

    random.seed(0)             # the grain stays put between runs
    frames = []
    for fr in ImageSequence.Iterator(src):
        g = ImageChops.multiply(picture(fr, size), mask)
        # Map the grey onto the page ground, so black is the canvas itself.
        im = Image.merge("RGB", [
            g.point(lambda v, c=c: int(c + v * (255 - c) / 255)) for c in GROUND])
        frames.append(Image.composite(im, ground, mask)
                      .convert("P", palette=Image.ADAPTIVE, colors=32))

    frames[0].save(OUT, save_all=True, append_images=frames[1:],
                   duration=src.info.get("duration", 80), loop=0, optimize=True)
    print("%-24s %dx%d  %d frames  %d KB"
          % (OUT, size[0], size[1], len(frames), os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
