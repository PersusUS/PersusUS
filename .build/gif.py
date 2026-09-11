"""Tone the Now section's shark loop to the page's ground.

The source clip is an ordinary grey-on-white underwater shot, so dropped into
the README it reads as a lit rectangle on a dark page. Two things fix that: the
greys are mapped onto GitHub's dark canvas the way render.py maps the photos,
and the frame's edges are faded out, so the clip dissolves into the page
instead of ending at a border.

Run from the repo root: python .build/gif.py
"""

import os

from PIL import Image, ImageSequence

SRC = ".build/src/03-shark.gif"
OUT = "assets/g-shark.gif"
GROUND = (13, 17, 23)          # #0d1117 - GitHub dark canvas
W, H = 300, 271
FEATHER = 0.5                  # share of each axis the fade spans
POWER = 1.6                    # higher holds the middle and drops the edges faster
COLORS = 96


def fade_mask():
    """Opaque in the middle, transparent at every edge."""
    mask = Image.new("L", (W, H))
    px = mask.load()
    for y in range(H):
        fy = min(1.0, min(y, H - 1 - y) / (H * FEATHER))
        for x in range(W):
            fx = min(1.0, min(x, W - 1 - x) / (W * FEATHER))
            px[x, y] = int(255 * (fx * fy) ** POWER)
    return mask


def onto_ground(g):
    """Map a grey frame so its black becomes the GitHub ground."""
    return Image.merge("RGB", [
        g.point(lambda v, c=c: int(c + v * (255 - c) / 255)) for c in GROUND])


def main():
    src = Image.open(SRC)
    mask = fade_mask()
    ground = Image.new("RGB", (W, H), GROUND)
    frames = [
        Image.composite(onto_ground(fr.convert("L").resize((W, H), Image.LANCZOS)),
                        ground, mask).convert("P", palette=Image.ADAPTIVE,
                                              colors=COLORS)
        for fr in ImageSequence.Iterator(src)]
    frames[0].save(OUT, save_all=True, append_images=frames[1:],
                   duration=src.info.get("duration", 80), loop=0, optimize=True)
    print("%-24s %dx%d  %d frames  %d KB"
          % (OUT, W, H, len(frames), os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
