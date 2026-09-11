"""Redraw the Now section's shark loop as ASCII art.

The clip is an ordinary grey-on-white underwater shot, so dropped into the
README as a photo it read as a lit rectangle on a dark page. Typed out
instead, it belongs to the same terminal as everything around it: each frame
is sampled down to a character grid and every cell replaced by the ramp glyph
nearest its darkness, set in VT323 at the size the README shows the loop, so
the characters stay crisp rather than being scaled by the browser. The ramp
stops before the solid glyphs, which keeps the loop from reading as a hard
block of ink beside the text. A hairline in GitHub's own border grey closes
the frame, so the grid reads as a picture rather than as spilled characters.

The ramp runs against the brightness. The water is the bright half of the
shot and thins out to bare ground; the shark is the dark half, and is what
actually gets drawn.

Run from the repo root: python .build/gif.py
"""

import os

from PIL import Image, ImageDraw, ImageFont, ImageSequence

SRC = ".build/src/03-shark.gif"
OUT = "assets/g-shark.gif"
FONT = ".build/VT323-Regular.ttf"

GROUND = (13, 17, 23)          # #0d1117 - GitHub dark canvas
RULE = (48, 54, 61)            # #30363d - GitHub's own border grey
FG = (230, 237, 243)           # GitHub's own body ink
DIM = (139, 148, 158)

RAMP = " .:-=+*#"             # thinnest to densest; stopping short of the
                               # solid glyphs keeps the shark from filling in
COLS = 66                      # characters across; the height follows the clip
SIZE = 8                       # px of VT323 per character
FLOOR, CEIL = 95, 240          # source levels the ramp is stretched between
GAMMA = 1.35                   # >1 holds the water back, keeps the shark solid
BRIGHT = 0.62                  # above this the cell is set in the body ink


def main():
    src = Image.open(SRC)
    font = ImageFont.truetype(FONT, SIZE)
    cell_w = font.getlength("#")
    cell_h = SIZE * 0.72        # VT323 sits well inside its line box
    w, h = src.size
    rows = round(COLS * (h / w) * (cell_w / cell_h))
    out_size = (round(cell_w * COLS), round(cell_h * rows))

    frames = []
    for fr in ImageSequence.Iterator(src):
        px = fr.convert("L").resize((COLS, rows), Image.LANCZOS).load()
        im = Image.new("RGB", out_size, GROUND)
        draw = ImageDraw.Draw(im)
        for y in range(rows):
            for x in range(COLS):
                v = min(1.0, max(0.0, (CEIL - px[x, y]) / (CEIL - FLOOR))) ** GAMMA
                glyph = RAMP[min(len(RAMP) - 1, int(v * len(RAMP)))]
                if glyph != " ":
                    draw.text((x * cell_w, y * cell_h - SIZE * 0.22), glyph,
                              font=font, fill=FG if v > BRIGHT else DIM)
        draw.rectangle([0, 0, out_size[0] - 1, out_size[1] - 1], outline=RULE)
        frames.append(im.convert("P", palette=Image.ADAPTIVE, colors=8))

    frames[0].save(OUT, save_all=True, append_images=frames[1:],
                   duration=src.info.get("duration", 80), loop=0, optimize=True)
    print("%-24s %dx%d  %d chars across  %d frames  %d KB"
          % (OUT, out_size[0], out_size[1], COLS, len(frames),
             os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
