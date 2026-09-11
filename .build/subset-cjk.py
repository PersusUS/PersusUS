"""Cut Noto Sans SC down to the handful of characters the margin uses.

VT323 has no CJK, and the Noto Sans SC that ships with Windows is 17.8 MB -
more than the rest of this repository put together, for six characters.
Pinning the variable font to its regular weight and subsetting to just those
characters brings it under 5 KB, small enough to live beside VT323 in here so
the build does not depend on what a given machine happens to have installed.

Noto is under the SIL Open Font License; NotoSansSC-OFL.txt carries the notice
and the licence, which is what the OFL asks of anything derived from it.

Run from the repo root: python .build/subset-cjk.py
"""

import io
import os

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC = os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                   "Fonts", "NotoSansSC-VF.ttf")
OUT = ".build/NotoSansSC-subset.ttf"
LICENCE = ".build/NotoSansSC-OFL.txt"

# The margin of the tagline: the Instrumentality Project.
TEXT = "人類補完計画"


def main():
    src = TTFont(SRC)
    missing = [c for c in TEXT if ord(c) not in src.getBestCmap()]
    if missing:
        raise SystemExit("not in the font: " + " ".join(missing))

    font = instancer.instantiateVariableFont(TTFont(SRC), {"wght": 400},
                                             inplace=True)
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
