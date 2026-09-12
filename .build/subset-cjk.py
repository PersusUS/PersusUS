"""Cut DotGothic16 down to the handful of characters the margin uses.

VT323 has no CJK. DotGothic16 is the nearest thing to it that does: a dot
matrix face, drawn on a grid the way a screen font is, so the kanji in the
margin read as something a terminal put there rather than as type set beside
one. Noto Sans SC, which stood here before, is a clean humanist sans - correct,
but it never looks like a machine drew it.

The upstream release is 2 MB for six characters, so it is fetched once into a
cache outside the repository and subset down to just those, which brings it
under 5 KB - small enough to live beside VT323 in here, so the build does not
depend on what a given machine happens to have installed.

DotGothic16 is under the SIL Open Font License; DotGothic16-OFL.txt carries the
notice and the licence, which is what the OFL asks of anything derived from it.

Run from the repo root: python .build/subset-cjk.py
"""

import io
import os
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont

URL = ("https://raw.githubusercontent.com/google/fonts/main/ofl/"
       "dotgothic16/DotGothic16-Regular.ttf")
CACHE = os.path.join(".build", "cache", "DotGothic16-Regular.ttf")
OUT = ".build/DotGothic16-subset.ttf"
LICENCE = ".build/DotGothic16-OFL.txt"

# The margin of the tagline (the Instrumentality Project) and the standing
# entry in the work block: in progress.
TEXT = ("\u4eba\u985e\u88dc\u5b8c\u8a08\u753b"      # the Instrumentality Project
        "\u9032\u884c\u4e2d"                  # in progress
        "\u30da\u30eb\u30b5\u30b9"              # Persus, in katakana
        "\u7d39\u4ecb\u9053\u5177\u7d4c\u6b74\u4f5c\u54c1\u73fe\u5728\u9023\u7d61")  # the section names


def source():
    """The upstream regular, downloaded on first run and kept out of git."""
    if not os.path.exists(CACHE):
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        urllib.request.urlretrieve(URL, CACHE)
        print("%-28s %d KB fetched" % (CACHE, os.path.getsize(CACHE) // 1024))
    return CACHE


def main():
    src_path = source()
    src = TTFont(src_path)
    missing = [c for c in TEXT if ord(c) not in src.getBestCmap()]
    if missing:
        raise SystemExit("not in the font: " + " ".join(missing))

    font = TTFont(src_path)
    opts = subset.Options()
    opts.name_IDs = ["*"]
    opts.name_legacy = True
    opts.notdef_outline = True
    opts.layout_features = []
    cut = subset.Subsetter(options=opts)
    cut.populate(text=TEXT)
    cut.subset(font)
    font.save(OUT)

    names = {r.nameID: r.toUnicode() for r in src["name"].names
             if r.platformID == 3 and r.nameID in (0, 13)}
    io.open(LICENCE, "w", encoding="utf-8", newline="\n").write(
        names[0] + "\n\n" + names[13] + "\n\nFull licence: http://scripts.sil.org/OFL\n")

    print("%-28s %d glyphs  %d KB" % (OUT, len(set(TEXT)),
                                      os.path.getsize(OUT) // 1024))


if __name__ == "__main__":
    main()
