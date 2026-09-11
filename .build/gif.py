"""Type the Now section's shark loop out in characters, quietly.

Dropped in as it came, the clip is a grey-on-white underwater shot and reads
as a lit rectangle on a dark page. Typed out instead, it belongs to the same
terminal as everything around it: each frame is sampled down to a character
grid and every cell replaced by the ramp glyph nearest its darkness, set in
VT323 at the size the README shows the loop, so the characters stay crisp
rather than being scaled by the browser.

The ramp runs against the brightness - the water is the bright half of the
shot and thins out to bare ground, the shark is the dark half and is what
gets drawn - and it stops well short of the solid glyphs, in the two dimmest
inks the page uses. The picture is meant to sit behind the text beside it,
not next to it. The only thing done to the frame itself is rounding off its
corners.

Run from the repo root: python .build/gif.py
"""

import os

from PIL import Image, ImageDraw, ImageFont, ImageSequence

SRC = ".build/src/03-shark.gif"
OUT = "assets/g-shark.gif"
FONT = ".build/VT323-Regular.ttf"

GROUND = (13, 17, 23)          # #0d1117 - GitHub dark canvas
FG = (125, 133, 144)           # the brightest any cell is allowed to be
DIM = (47, 54, 62)             # and the thin ones barely leave the ground

RAMP = " .:-=+"                # thinnest to densest
COLS = 80                      # characters across; the height follows the clip
SIZE = 8                       # px of VT323 per character
FLOOR, CEIL = 95, 240          # source levels the ramp is stretched between
GAMMA = 1.8                    # >1 holds the water back to bare ground
BRIGHT = 0.70                  # above this the cell takes the brighter ink
RADIUS = 16                    # px the corners are rounded by


def rounded(size):
    """The frame, with its corners taken off."""
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size[0] - 1, size[1] - 1], RADIUS, fill=255)
    return mask


def main():
    src = Image.open(SRC)
    font = ImageFont.truetype(FONT, SIZE)
    cell_w = font.getlength("#")
    cell_h = SIZE * 0.72        # VT323 sits well inside its line box
    w, h = src.size
    rows = round(COLS * (h / w) * (cell_w / cell_h))
    size = (round(cell_w * COLS), round(cell_h * rows))
    mask = rounded(size)
    ground = Image.new("RGB", size, GROUND)

    frames = []
    for fr in ImageSequence.Iterator(src):
        px = fr.convert("L").resize((COLS, rows), Image.LANCZOS).load()
        im = Image.new("RGB", size, GROUND)
        draw = ImageDraw.Draw(im)
        for y in range(rows):
            for x in range(COLS):
                v = min(1.0, max(0.0, (CEIL - px[x, y]) / (CEIL - FLOOR))) ** GAMMA
                glyph = RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))]
                if glyph != " ":
                    draw.text((x * cell_w, y * cell_h - SIZE * 0.22), glyph,
                              font=font, fill=FG if v > BRIGHT else DIM)
        frames.append(Image.composite(im, ground, mask)
                      .convert("P", palette=Image.ADAPTIVE, colors=16))

    frames[0].save(OUT, save_all=True, append_images=frames[1:],
                   duration=src.info.get("duration", 80), loop=0, optimize=True)
    print("%-24s %dx%d  %d chars across  %d frames  %d KB"
          % (OUT, size[0], size[1], COLS, len(frames), os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
