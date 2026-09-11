"""Prepare the two photos the README uses, and dump the ASCII titles.

The README's text is plain markdown - titles are dos_rebel ASCII inside code
fences, body copy is ordinary prose - so nothing here rasterises text any more.
What the photos still need is a common ground: both are white-on-black, and
GitHub's dark canvas is #0d1117, so their black is mapped onto that value and
they sit on the page without a visible rectangle around them.

Run from the repo root: python .build/render.py
"""

import io
import os

import pyfiglet
from PIL import Image

OUT = "assets"
SRC = ".build/src"
GROUND = (13, 17, 23)          # #0d1117 - GitHub dark canvas

TITLES = ["Persus", "About", "Stack", "Work", "Projects", "Now", "Contact"]


def onto_ground(img):
    """Map a white-on-black photo so its black becomes the GitHub ground."""
    g = img.convert("L")
    return Image.merge("RGB", [
        g.point(lambda v, c=c: int(c + v * (255 - c) / 255)) for c in GROUND])


def photo(src_name, out_name, level_from=0, scale=1):
    im = Image.open(os.path.join(SRC, src_name)).convert("L")
    if level_from:
        # The poster's own background sits at this level, not at black.
        span = 255 - level_from
        im = im.point(lambda v: max(0, min(255, int((v - level_from) * 255 / span))))
    im = onto_ground(im)
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.LANCZOS)
    path = os.path.join(OUT, out_name)
    im.save(path)
    print("%-24s %dx%d" % (path, im.width, im.height))


def dump_titles():
    """Write the ASCII titles out so they can be pasted into the README."""
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
