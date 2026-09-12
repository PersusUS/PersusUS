"""Prepare the two photos the README stands on, one copy of each per theme.

The source is white-on-black line art. A photo cannot take its colour from a
stylesheet the way the typeset blocks do, so it is written out twice instead:
`p-hands.png` puts the drawing in white on GitHub's dark canvas, and
`p-hands-l.png` puts it in GitHub's dark ink on white. The README picks between
them with <picture media="(prefers-color-scheme: light)">, so neither theme gets
a black rectangle dropped into it. The poster that closes the page is handled
the same way.

Also dumps the dos_rebel titles, which `.build/textsvg.py` typesets.

Run from the repo root: python .build/render.py
"""

import io
import os

import pyfiglet
from PIL import Image

OUT = "assets"
SRC = ".build/src"
DARK_GROUND = (13, 17, 23)     # #0d1117 - GitHub's dark canvas
LIGHT_INK = (31, 35, 40)       # #1f2328 - GitHub's ink on its light canvas
RAMP = 16                      # steps kept between the ground and the ink

TITLES = ["Persus", "About", "Stack", "Work", "Projects", "Now", "Contact"]


def onto_ground(img, ground):
    """White-on-black art, with its black moved onto `ground`."""
    g = img.convert("L")
    return Image.merge("RGB", [
        g.point(lambda v, c=c: int(c + v * (255 - c) / 255)) for c in ground])


def onto_white(img, ink):
    """The same art inverted: white ground, the drawing itself in `ink`."""
    g = img.convert("L")
    return Image.merge("RGB", [
        g.point(lambda v, c=c: int(255 - v * (255 - c) / 255)) for c in ink])


def photo(src_name, out_name, level_from=0, scale=1):
    """Write the dark copy and, beside it, the light one."""
    im = Image.open(os.path.join(SRC, src_name)).convert("L")
    if level_from:
        # The poster's own background sits at this level, not at black.
        span = 255 - level_from
        im = im.point(lambda v: max(0, min(255, int((v - level_from) * 255 / span))))
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)

    stem, ext = os.path.splitext(out_name)
    for suffix, art in (("", onto_ground(im, DARK_GROUND)),
                        ("-l", onto_white(im, LIGHT_INK))):
        path = os.path.join(OUT, stem + suffix + ext)
        # The art only ever runs along one ramp, from the ground to the ink, so
        # sixteen steps of it are indistinguishable from the full 24-bit image
        # and a fifth of the weight - and this one is the first thing the page
        # asks the reader to download.
        art = art.quantize(colors=RAMP, method=Image.Quantize.MEDIANCUT,
                           dither=Image.Dither.NONE)
        art.save(path, optimize=True)
        print("%-24s %dx%d  %d KB"
              % (path, art.width, art.height, os.path.getsize(path) // 1024))


def dump_titles():
    """Write the ASCII titles out so textsvg.py and the eye can both read them."""
    path = os.path.join(".build", "ascii-titles.txt")
    with io.open(path, "w", encoding="utf-8") as fh:
        for word in TITLES:
            art = [line.rstrip() for line
                   in pyfiglet.figlet_format(word, font="dos_rebel").split("\n")]
            while art and not art[-1]:
                art.pop()
            while art and not art[0]:
                art.pop(0)
            fh.write("@@@ %s\n%s\n\n" % (word, "\n".join(art)))
    print("%-24s %d titles" % (path, len(TITLES)))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    photo("01-hands.png", "p-hands.png")
    photo("02-creative-ecstasy.jpg", "p-angel.png")
    dump_titles()
