"""Typeset the README's body copy as SVG set in VT323.

GitHub renders README markdown in its own font and strips every stylesheet, so
plain text cannot be given a typeface. An <img> pointing at an SVG can: the text
stays vector text rather than a rasterised PNG, and the glyph outlines travel
inside the file, so nothing has to be fetched at render time.

Each glyph is emitted as a <path> taken from the VT323 outlines. Paths render
identically everywhere, including inside GitHub's image proxy, where an
@font-face would be at the mercy of the sandbox.

Every block is written twice: `s-<name>.svg` at reading width, and
`s-<name>-n.svg` folded to about forty columns. The README picks between them
with <picture media="(max-width: 600px)">, because an 850px block shown on a
375px phone is scaled to 44% and its 22px type lands at nine.

Colour is not written into the paths. Each fill names a role, that role becomes
a class, and one stylesheet at the top of the file resolves the four of them
against the reader's theme - so the same asset sits on GitHub's dark canvas and
on its light one.

Run from the repo root: python .build/textsvg.py
"""

import glob
import os

import matplotlib
import pyfiglet
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

FONT = ".build/VT323-Regular.ttf"
# The dos_rebel titles are drawn out of block and shade characters, which VT323
# does not carry; DejaVu Sans Mono does, and ships with matplotlib.
MONO = glob.glob(os.path.join(
    os.path.dirname(matplotlib.__file__),
    "mpl-data", "fonts", "ttf", "DejaVuSansMono.ttf"))[0]
# VT323 carries no CJK. DotGothic16 does, drawn on a dot grid the way a screen
# font is, and `.build/subset-cjk.py` cuts it down to the characters the margins
# use. It is under the SIL Open Font License, which travels with it in
# DotGothic16-OFL.txt.
CJK = ".build/DotGothic16-subset.ttf"
OUT = "assets"

# A colour is referred to by the name of its role, never by a hex value: the
# name is written out as a class, and THEME resolves it at render time against
# whichever theme the reader is in.
GROUND = "bg"
FG = "ink"
DIM = "dim"
RULE = "rule"

LIGHT = {"bg": "#ffffff", "ink": "#1f2328", "dim": "#59636e", "rule": "#d1d9e0"}
DARK = {"bg": "#0d1117", "ink": "#e6edf3", "dim": "#8b949e", "rule": "#30363d"}

# prefers-color-scheme follows the operating system, not GitHub's own theme
# switch, so a reader who has forced one against the other keeps the dark block
# they see today. It is never worse than that, and for everyone else it is right.
THEME = (
    ":root{%s}"
    "@media(prefers-color-scheme:dark){:root{%s}}"
    ".bg{fill:var(--bg)}.ink{fill:var(--ink)}.dim{fill:var(--dim)}"
    ".rule{fill:none;stroke:var(--rule)}"
    % (";".join("--%s:%s" % kv for kv in LIGHT.items()),
       ";".join("--%s:%s" % kv for kv in DARK.items()))
)

RADIUS = 18             # px the bordered blocks are rounded by
PAD = 16                # px of ground around the text
PAD_TIGHT = 3           # px above and below a line meant to stack
NOTE_GAP = 64           # px between a line and the note set out to its right
CJK_FIT = 0.74          # kanji are cut to this of the size the line was set at

# The tagline is typed out rather than simply being there. Timings are in
# seconds, and are spent from a clock that starts when the image loads.
LEAD = 0.30             # cursor blinks this long before the first character
CHAR = 0.026            # one typed character
SWEEP = 0.006           # one character of a line that is swept, not typed
PAUSE = 0.06            # between one line finishing and the next starting
BLINK = 1.06            # a full cursor cycle


class Typesetter:
    def __init__(self, path, size):
        self.font = TTFont(path)
        self.upem = self.font["head"].unitsPerEm
        self.scale = size / self.upem
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.hmtx = self.font["hmtx"]
        self.size = size
        self._cache = {}

    def glyph_name(self, ch):
        return self.cmap.get(ord(ch))

    def advance(self, ch):
        name = self.glyph_name(ch) or self.cmap.get(ord("?"))
        # A subset face carries neither a space nor a question mark to stand
        # in for what it is missing; a character it cannot set takes no width.
        return self.hmtx[name][0] * self.scale if name else 0.0

    def path(self, ch):
        """Outline of one glyph, in font units."""
        name = self.glyph_name(ch)
        if name is None:
            return ""
        if name not in self._cache:
            pen = SVGPathPen(self.glyphs)
            self.glyphs[name].draw(pen)
            self._cache[name] = pen.getCommands()
        return self._cache[name]

    def width(self, text):
        return sum(self.advance(c) for c in text)


def _plain(line):
    """A line as flat text, whether it was given as one or in coloured runs."""
    return line if isinstance(line, str) else "".join(run[0] for run in line)


def _runs(line, fill, font):
    """A line as (text, colour, face) runs, filling in what it left unsaid."""
    if isinstance(line, str):
        return [(line, fill, font)]
    return [(run[0], run[1], run[2] if len(run) > 2 else font) for run in line]


def svg(lines, name, size=20, leading=1.0, colors=None, font=FONT,
        pad=PAD, border=False, animate=None, delay=0.0,
        notes=None, note_size=24, note_color=None, note_font=None,
        cursor=None, note_gap=NOTE_GAP, min_width=0, pad_y=None):
    """Render lines of text to assets/<name>.svg, reusing each glyph outline.

    A line is either a string, which takes its colour from `colors`, or a list
    of (text, colour) runs - (text, colour, face) to change typeface mid-line -
    which is how a name and its description share one baseline in two inks.

    `cursor` parks a blinking block at the end of the line it names, which is
    what a terminal does when it is waiting for the next thing.

    Pass `animate` a mode per line - "type" to have it typed a character at a
    time behind a cursor, "wipe" to have it swept in - and the block plays
    itself out on load. `delay` holds the whole sequence back, which is how a
    block in a second file falls in behind the one above it.

    `notes` sets (line, text) pairs in the margin the short lines leave on the
    right - the command that would have printed the block, in the dim ink. A
    third element overrides `note_size`, `note_font` and `note_color` for that
    one note. The line may be fractional, which sets the note between two of
    them. They fade up once the block has finished playing. `note_gap` closes
    that margin up, which is how the narrow variant keeps a note inside it.

    `pad_y` sets the ground above and below apart from the ground at the sides,
    which is how eight files stack into one list instead of eight paragraphs.

    `min_width` holds the block open to a width it would not have reached on
    its own. Four files that must read as one list have to come out the same
    width, or the browser scales each of them by a different amount and the
    column they share stops being a column.
    """
    pad_y = pad if pad_y is None else pad_y
    faces = {}

    def face(path):
        # DotGothic16 fills its em where VT323 leaves a third of it empty, so
        # kanji set in a line of VT323 are cut to the height of the caps beside
        # them rather than to the size the line was set at.
        if path not in faces:
            faces[path] = Typesetter(path, size * (CJK_FIT if path == CJK else 1))
        return faces[path]

    t = face(font)
    flat = [_plain(line) for line in lines]
    drawn = [_runs(line, FG if colors is None else colors[i], font)
             for i, line in enumerate(lines)]
    line_h = size * leading
    w = max(sum(face(f).width(text) for text, _, f in runs)
            for runs in drawn) + 2 * pad
    h = line_h * len(lines) + 2 * pad_y

    if cursor is not None:
        # Leave the cursor somewhere to sit, or it lands on the right edge.
        w = max(w, t.width(flat[cursor]) + t.advance("M") * 1.4 + 2 * pad)

    if notes:
        base = dict(size=note_size, font=note_font or font,
                    color=note_color or FG)
        notes = [(i, text, dict(base, **(over[0] if over else {})))
                 for i, text, *over in notes]
        setters = {}

        def note_face(opt):
            key = (opt["font"], opt["size"])
            if key not in setters:
                setters[key] = Typesetter(*key)
            return setters[key]

        # The margin has to be there before a note can be set in it: widen the
        # block until the line a note shares a baseline with clears it by the gap.
        w = max([w] + [t.width(flat[round(i)]) + note_gap
                       + note_face(opt).width(text) + 2 * pad
                       for i, text, opt in notes])

    w = max(w, min_width)

    # Each distinct glyph is defined once and placed with <use>; VT323 repeats
    # enough that this is roughly a tenth of the size of one path per glyph.
    missing = sorted({ch for runs in drawn for text, _, f in runs
                      for ch in text if ch != " " and not face(f).path(ch)})
    if missing:
        # Silently dropping a glyph still spends its advance, so the block comes
        # out with a hole in it at the right width. Say so instead.
        print("%-26s no glyph for %s" % (name, " ".join(missing)))

    used = sorted({(f, ch) for runs in drawn for text, _, f in runs
                   for ch in text if ch != " " and face(f).path(ch)})
    ids = {key: "g%d" % i for i, key in enumerate(used)}
    defs = "".join('<path id="%s" d="%s"/>' % (ids[(f, ch)], face(f).path(ch))
                   for f, ch in used)

    if notes:
        marks = sorted({(opt["font"], opt["size"], ch) for _, text, opt in notes
                        for ch in text if note_face(opt).path(ch)})
        nids = {key: "j%d" % i for i, key in enumerate(marks)}
        defs += "".join('<path id="%s" d="%s"/>'
                        % (nids[(f, sz, ch)], setters[(f, sz)].path(ch))
                        for f, sz, ch in marks)

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" '
             'xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" '
             'viewBox="0 0 %d %d" role="img">'
             % (round(w), round(h), round(w), round(h)),
             '<style>%s</style>' % THEME,
             '<rect class="bg" width="100%" height="100%"/>',
             '<defs>%s</defs>' % defs]

    if border:
        parts.append('<rect class="rule" x="0.5" y="0.5" width="%.1f" '
                     'height="%.1f" rx="%d"/>'
                     % (round(w) - 1, round(h) - 1, RADIUS))

    for i, runs in enumerate(drawn):
        # Baseline: the ascender sits just under the top padding.
        baseline = pad_y + line_h * i + size * 0.78
        x = pad
        for text, fill, f in runs:
            tf = face(f)
            parts.append('<g class="%s" transform="translate(0 %.2f) '
                         'scale(%.5f %.5f)">'
                         % (fill, baseline, tf.scale, -tf.scale))
            for ch in text:
                if ch != " " and (f, ch) in ids:
                    parts.append('<use xlink:href="#%s" x="%.1f"/>'
                                 % (ids[(f, ch)], x / tf.scale))
                x += tf.advance(ch)
            parts.append("</g>")

    if animate:
        parts.extend(_animation(flat, animate, t, size, line_h, pad, pad_y,
                                round(w), round(h), delay))

    if cursor is not None:
        # A block left waiting at the end of a line, blinking on the same
        # cycle as the one that types the tagline out.
        baseline = pad_y + line_h * cursor + size * 0.78
        parts.append('<style>@keyframes bk{50%%{opacity:0}}'
                     '.cr{animation:bk %.2fs step-end infinite}'
                     '@media (prefers-reduced-motion:reduce){.cr{animation:none}}'
                     '</style>' % BLINK)
        parts.append('<rect class="cr ink" x="%.1f" y="%.1f" width="%.1f" '
                     'height="%.1f"/>'
                     % (pad + t.width(flat[cursor]) + t.advance("M") * 0.3,
                        baseline - size * 0.74, t.advance("M"), size * 0.8))

    if notes:
        # Painted after the covers, so a cover parked to the right of the line
        # it has just uncovered cannot sit on top of the margin.
        if animate:
            parts.append("<style>@keyframes fade{to{opacity:1}}"
                         ".nt{opacity:0;animation:fade .6s %.3fs forwards}"
                         "@media (prefers-reduced-motion:reduce)"
                         "{.nt{opacity:1;animation:none}}</style>"
                         % (delay + _runtime(flat, animate)))
        for i, text, opt in notes:
            tn = note_face(opt)
            baseline = pad_y + line_h * i + size * 0.78
            x = w - pad - tn.width(text)
            parts.append('<g class="nt %s" transform="translate(0 %.2f) '
                         'scale(%.5f %.5f)">'
                         % (opt["color"], baseline, tn.scale, -tn.scale))
            for ch in text:
                key = (opt["font"], opt["size"], ch)
                if key in nids:
                    parts.append('<use xlink:href="#%s" x="%.1f"/>'
                                 % (nids[key], x / tn.scale))
                x += tn.advance(ch)
            parts.append("</g>")

    parts.append("</svg>")

    path = os.path.join(OUT, name + ".svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    print("%-26s %dx%d  %d KB" % (path, round(w), round(h),
                                  os.path.getsize(path) // 1024))
    return round(w), round(h)


def _animation(lines, modes, t, size, line_h, pad, pad_y, w, h, delay):
    """Cover every line, then slide the covers off in turn.

    Revealing by sliding an opaque rectangle the colour of the ground, rather
    than by clipping, buys the widest support there is: the only things put in
    motion are `transform` and `opacity`. A typed line steps its cover off one
    character at a time - VT323 is monospaced, so a step is exactly a glyph -
    with a block cursor riding the edge; a swept line is uncovered in one go.

    The cover takes its fill from the theme rather than from a fixed value, or
    a reader on the light theme would watch black bands slide off white ground.
    """
    adv = t.advance("M")
    css = [".cv{fill:var(--bg)}.cu{fill:var(--ink)}",
           "@keyframes bl{50%{opacity:0}}",
           "@keyframes on{to{opacity:1}}@keyframes off{to{opacity:0}}"]
    body = []
    clock = delay + LEAD
    last_typed = max((i for i, m in enumerate(modes) if m == "type"
                      and lines[i]), default=None)

    for i, mode in enumerate(modes):
        n = len(lines[i])
        if not n:
            continue
        # Bands do not overlap, or a cover still in place would hold down the
        # line above it; the first and last reach the edge for a little slack.
        y0 = 0 if i == 0 else pad_y + line_h * i
        y1 = h if i == len(lines) - 1 else pad_y + line_h * (i + 1)
        run = t.width(lines[i])
        dur = n * (CHAR if mode == "type" else SWEEP)

        css.append("@keyframes k%d{to{transform:translateX(%.1fpx)}}" % (i, run + 4))
        css.append(".k%d{animation:k%d %.3fs %s %.3fs forwards}"
                   % (i, i, dur,
                      "steps(%d)" % n if mode == "type" else "ease-out",
                      clock))
        body.append('<rect class="cv k%d" x="%.1f" y="%.1f" width="%d" height="%.1f"/>'
                    % (i, pad - 2, y0, w, y1 - y0))

        if mode == "type":
            # The gate hides the cursor until this line's turn and, unless it
            # is the last one typed, takes it away again once the line is out.
            gate = ".g%d{opacity:0;animation:on 0s %.3fs forwards" % (i, clock)
            if i != last_typed:
                gate += ",off 0s %.3fs forwards" % (clock + dur)
            css.append(gate + "}")
            css.append("@keyframes m%d{to{transform:translateX(%.1fpx)}}"
                       % (i, n * adv))
            css.append(".m%d{animation:m%d %.3fs steps(%d) %.3fs forwards,"
                       "bl %.2fs step-end infinite}"
                       % (i, i, dur, n, clock, BLINK))
            baseline = pad_y + line_h * i + size * 0.78
            body.append('<g class="g%d"><rect class="cu m%d" x="%.1f" y="%.1f" '
                        'width="%.1f" height="%.1f"/></g>'
                        % (i, i, pad, baseline - size * 0.74, adv, size * 0.8))

        clock += dur + PAUSE

    # Anyone who has asked for less movement gets the finished block instead.
    css.append("@media (prefers-reduced-motion:reduce){"
               ".cv{transform:translateX(%dpx)}"
               ".cv,.cu,g[class^=g]{animation:none!important}"
               "g[class^=g]{opacity:0}}" % (w + 8))
    return ["<style>%s</style>" % "".join(css)] + body

def fold(text, cols):
    """`text` broken on spaces so no line runs past `cols` characters.

    Japanese is written without them, and a full-width character takes about
    two columns, so text with nothing to break on is cut to length instead.
    """
    if " " not in text:
        half = max(1, cols // 2)
        return [text[i:i + half] for i in range(0, len(text), half)] or [""]
    out, line = [], ""
    for word in text.split(" "):
        if line and len(line) + 1 + len(word) > cols:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    return out + [line]


def _runtime(lines, modes):
    """How long a block takes to play itself out, in seconds."""
    return LEAD + sum(len(line) * (CHAR if mode == "type" else SWEEP) + PAUSE
                      for line, mode in zip(lines, modes) if line)


# The two lines that say who he is are typed; the two that qualify it are
# swept in behind them, which keeps the whole opening under three seconds
# instead of the four it would take to type all 137 characters.
TAGLINE = [
    "JESUS PEREZ BAZAROT - 21 - SEVILLE",
    "I WORK ON THE PARTS OF AI THAT BREAK.",
    "I MEAN TO MOVE THE WORLD. AI IS THE LEVER.",
    "SEARCHING FOR SAFE AGI.",
]
TAGLINE_MODES = ["type", "type", "wipe", "wipe"]

# The same four lines with the longest one broken across the two that are
# swept. The kanji stay in the margin of the first line, where they have always
# been; what gives way on a phone is the width of that margin, not what is in it.
TAGLINE_N = [
    "JESUS PEREZ BAZAROT - 21 - SEVILLE",
    "I WORK ON THE PARTS OF AI THAT BREAK.",
    "I MEAN TO MOVE THE WORLD. AI IS THE",
    "LEVER. SEARCHING FOR SAFE AGI.",
]

BLOCKS = {
    # The Instrumentality Project, in the margin the two short lines leave,
    # on the first line's own baseline and in the bright ink.
    "tagline": {
        "opts": dict(size=30, leading=1.15, colors=[FG, FG, DIM, DIM],
                     animate=TAGLINE_MODES,
                     notes=[(0, "人類補完計画")],
                     note_size=26, note_font=CJK),
        "wide": TAGLINE,
        "narrow": TAGLINE_N,
        "narrow_opts": dict(size=26, note_size=22, note_gap=26),
    },
    # Tags is a second file, so it cannot share a clock with the block above
    # it - it can only be held back by what that block is known to take. A
    # sweep tolerates the few milliseconds the two images load apart; a typed
    # line, locked to the character, would not.
    "tags": {
        "opts": dict(size=27, colors=[DIM], animate=["wipe"],
                     delay=_runtime(TAGLINE, TAGLINE_MODES) - LEAD),
        "wide": ["AI/ML RESEARCH  /  CONTINUAL LEARNING  /  BENCHMARKS  /  EDGE"],
        "narrow": ["AI/ML RESEARCH  /  CONTINUAL LEARNING",
                   "BENCHMARKS  /  EDGE"],
        "narrow_opts": dict(size=22, colors=[DIM, DIM], animate=["wipe", "wipe"],
                            delay=_runtime(TAGLINE_N, TAGLINE_MODES) - LEAD),
    },
    "about": {
        "opts": dict(size=28.5, leading=1.25),
        "wide": [
            "Fourth-year Computer & Electronics Engineering at the UNIVERSIDAD",
            "DE SEVILLA, back from a year of Data Science & AI at the BEIJING",
            "INSTITUTE OF TECHNOLOGY. I learn by building, breaking and rebuilding.",
            "Long term: a master's in AI at MIT, pointed at something worth keeping.",
        ],
        "narrow_opts": dict(size=22),
        "narrow": [
            "Fourth-year Computer & Electronics",
            "Engineering at the UNIVERSIDAD DE",
            "SEVILLA, back from a year of Data",
            "Science & AI at the BEIJING INSTITUTE",
            "OF TECHNOLOGY.",
            "",
            "I learn by building, breaking and",
            "rebuilding. Long term: a master's in AI",
            "at MIT, pointed at something worth",
            "keeping.",
        ],
    },
    # Label in the bright ink, what it holds in the dim one, on one baseline.
    # A phone has no room for two columns, so there the label takes its own
    # line and what it holds is indented under it.
    "stack": {
        "opts": dict(size=25.6, leading=1.3),
        "wide": [
            [("LANGUAGES        ", FG), ("Python / C / C++ / Assembly", DIM)],
            [("DEEP LEARNING    ", FG), ("PyTorch / CUDA / Triton / quantisation", DIM)],
            [("AI / ML          ", FG),
             ("Transformers / state space models / RAG / benchmarking / agents", DIM)],
            [("BACKEND & DATA   ", FG),
             ("FastAPI / React / PostgreSQL / pgvector / Docker / Neo4j", DIM)],
            [("SPOKEN           ", FG),
             ("Spanish / English / Chinese / Japanese (work in progress)", DIM)],
        ],
        "narrow_opts": dict(size=21),
        "narrow": [
            [("LANGUAGES", FG)],
            [("  Python / C / C++ / Assembly", DIM)],
            [("DEEP LEARNING", FG)],
            [("  PyTorch / CUDA / Triton / quantisation", DIM)],
            [("AI / ML", FG)],
            [("  Transformers / state space models /", DIM)],
            [("  RAG / benchmarking / agents", DIM)],
            [("BACKEND & DATA", FG)],
            [("  FastAPI / React / PostgreSQL /", DIM)],
            [("  pgvector / Docker / Neo4j", DIM)],
            [("SPOKEN", FG)],
            [("  Spanish / English / Chinese /", DIM)],
            [("  Japanese (work in progress)", DIM)],
        ],
    },
    "work": {
        "opts": dict(size=23.5, leading=1.3),
        "wide": [
            [("2026 - now    ", FG), ("進行中", DIM, CJK)],
            [("2025 - 2026   ", FG),
             ("Independent AI/ML research - world models, continual", DIM)],
            [("              ", FG),
             ("learning, LLM benchmarking. AI/ML developer at OrgaAI.", DIM)],
            [("2024 - 2025   ", FG), ("Co-founder & co-CTO - ByTheWay, carpooling.", DIM)],
            [("2023 - 2024   ", FG), ("CTO - NetKey, NFC networking hardware.", DIM)],
            [("2023          ", FG), ("Speaker - Telefonica innovaTE.", DIM)],
            [("EDUCATION     ", FG),
             ("BSc Computer & Electronics Engineering, Universidad de Sevilla,", DIM)],
            [("              ", FG), ("2023-2027.", DIM)],
        ],
        "narrow_opts": dict(size=21),
        "narrow": [
            [("2026 - now   ", FG), ("進行中", DIM, CJK)],
            [("2025 - 2026", FG)],
            [("  Independent AI/ML research - world", DIM)],
            [("  models, continual learning, LLM", DIM)],
            [("  benchmarking. AI/ML dev at OrgaAI.", DIM)],
            [("2024 - 2025", FG)],
            [("  Co-founder & co-CTO - ByTheWay,", DIM)],
            [("  carpooling.", DIM)],
            [("2023 - 2024", FG)],
            [("  CTO - NetKey, NFC networking hardware.", DIM)],
            [("2023", FG)],
            [("  Speaker - Telefonica innovaTE.", DIM)],
            [("EDUCATION", FG)],
            [("  BSc Computer & Electronics", DIM)],
            [("  Engineering, Universidad de Sevilla,", DIM)],
            [("  2023-2027.", DIM)],
        ],
    },
    # Set in caps like the tagline. The leading is wide because the block used
    # to be cut to the height of the ASCII loop that stood beside it; nothing
    # stands there now, so the number is only what it looks like it is.
    "now": {
        "opts": dict(size=26, leading=1.936, pad=14, cursor=2),
        "wide": [
            "> ORGANISING THE AI TALKS AT THE UNIVERSIDAD DE SEVILLA",
            "> RESEARCH ON PUSHING THE TPU STATE OF THE ART",
            "> BUILDING PERSEO, THE ASSISTANT THAT LISTENS AND WATCHES",
        ],
        # On a phone the loop wraps above this block instead of sitting beside
        # it, so the height it was cut to no longer has to be held.
        "narrow": [
            "> ORGANISING THE AI TALKS AT",
            "  THE UNIVERSIDAD DE SEVILLA",
            "> RESEARCH ON PUSHING THE TPU",
            "  STATE OF THE ART",
            "> BUILDING PERSEO, THE ASSISTANT",
            "  THAT LISTENS AND WATCHES",
        ],
        "narrow_opts": dict(size=22, leading=1.3, pad=16, cursor=5),
    },
    "coords": {
        "opts": dict(size=22, leading=1.25, colors=[DIM, FG], cursor=1),
        "wide": [
            "N 42 21 36   W 71 05 31   /   MIT, CAMBRIDGE, MASSACHUSETTS",
            "> NOT THERE YET. SOON THERE.",
        ],
        "narrow": [
            "N 42 21 36   W 71 05 31",
            "MIT, CAMBRIDGE, MASSACHUSETTS",
            "> NOT THERE YET. SOON THERE.",
        ],
        "narrow_opts": dict(colors=[DIM, DIM, FG], cursor=2),
    },
}

# Eight, not eleven and not four. Each one is its own file so the README can
# wrap it in its own <a>: a name that describes a project and does not go
# anywhere is a name a reader cannot use. A fifth element changes the typeface
# the description is set in.
#
# Jetson + Gemma 3 belongs on this list on merit, but the site has no page for
# it yet and a name that leads to a 404 is worse than one that is not shown.
# Give it /projects/jetson and it goes back in as a ninth line.
PROJECTS = [
    ("wmf", "WMF BENCHMARK",
     "what a world model forgets when it learns a second task",
     "https://github.com/PersusUS/WorldModelsBenchmark"),
    # Perseo answers in the language it was taught to listen in.
    ("perseo", "PERSEO",
     "聞き、見るデスクトップアシスタント",
     "https://persus.netlify.app/projects/perseo", CJK),
    ("hybridmamba", "HYBRIDMAMBA-11",
     "31.8M parameters in 13.6 MB, in OpenAI's Parameter Golf",
     "https://persus.netlify.app/projects/hybridmamba"),
    ("multilingual", "MULTILINGUAL",
     "Chinese against Western frontier models, nine languages",
     "https://persus.netlify.app/projects/multilingual"),
    ("nightshift", "NIGHTSHIFT",
     "an autonomous queue that claims one task a night",
     "https://persus.netlify.app/projects/nightshift"),
    ("magi", "MAGI",
     "three personas answer; any one veto sinks the verdict",
     "https://persus.netlify.app/projects/magi"),
    ("traces", "TRACES",
     "15 annotated agent traces, a nine-type error taxonomy",
     "https://persus.netlify.app/projects/agentic-traces"),
    ("kotoba", "KOTOBA",
     "the whole JLPT, N5 to N1, spaced and offline, in Spanish",
     "https://persus.netlify.app/projects/kotoba"),
]

# What a screen reader and a search engine are given instead of the picture.
# Written out rather than derived: the names are not words a title-caser knows,
# and one of the lines is not in English at all.
ALT = {
    "wmf": "WMF Benchmark: what a world model forgets when it learns a second task",
    "perseo": "Perseo: a desktop assistant that listens and watches",
    "hybridmamba": "HybridMamba-11: 31.8M parameters in 13.6 MB, in OpenAI's Parameter Golf",
    "multilingual": "Multilingual: Chinese against Western frontier models, nine languages",
    "nightshift": "NightShift: an autonomous queue that claims one task a night",
    "magi": "MAGI: three personas answer, and any one veto sinks the verdict",
    "traces": "Traces: 15 annotated agent traces, a nine-type error taxonomy",
    "kotoba": "Kotoba: the whole JLPT, N5 to N1, spaced and offline, in Spanish",
}

ALL_PROJECTS = "https://persus.netlify.app/portfolio"

TITLES = ["Persus", "About", "Stack", "Work", "Projects", "Now", "Contact"]


def title_svg(word, size=13.7):
    """One dos_rebel title, its block characters drawn as outlines.

    13.7 is not arbitrary: it is the size at which every title comes out at the
    width the README already showed it at, so the page does not move and the
    browser no longer has to resample a block character to get there.
    """
    art = [line.rstrip() for line
           in pyfiglet.figlet_format(word, font="dos_rebel").split("\n")]
    while art and not art[-1]:
        art.pop()
    while art and not art[0]:
        art.pop(0)
    svg(art, "t-" + word.lower(), size=size, leading=1.0, font=MONO)


def projects_svg():
    """One file a project: the name in the bright ink, what it is in the dim.

    The name is padded to a column shared by every file, and PAD_TIGHT takes
    the ground above and below down to a few pixels, so eight images stacked in
    one paragraph read as one list rather than as eight of them.
    """
    col = max(len(name) for _, name, _, _, *_ in PROJECTS) + 2
    wide, narrow = [], []
    for _, name, desc, _, *rest in PROJECTS:
        face = rest[0] if rest else FONT
        wide.append([[(name.ljust(col), FG), (desc, DIM, face)]])
        # A description that stays on one line makes the phone variant half
        # again too wide, so there it is folded into the column a phone has.
        narrow.append([[(name, FG)]]
                      + [[("  ", DIM), (part, DIM, face)]
                         for part in fold(desc, 34)])

    for lines, suffix, leading, size in ((wide, "", 1.22, 26.7),
                                         (narrow, "-n", 1.3, 21)):
        # Drawn once to find out how wide the widest of them wants to be, then
        # again with all of them held open to it.
        widest = max(svg(block, "s-p-" + entry[0] + suffix, size=size,
                         leading=leading, pad_y=PAD_TIGHT)[0]
                     for entry, block in zip(PROJECTS, lines))
        for entry, block in zip(PROJECTS, lines):
            svg(block, "s-p-" + entry[0] + suffix, size=size, leading=leading,
                pad_y=PAD_TIGHT, min_width=widest)

    # An arrow VT323 does not carry would come out as a hole with its width
    # still spent, so the chip points the way a terminal does.
    svg(["ALL PROJECTS  ->"], "s-p-all", size=26.7, border=True, pad=14)


def readme_snippet():
    """Print the markup the project lines want, so it is pasted, not typed.

    All of them on one source line: GitHub turns a newline inside a paragraph
    into a line break, and eight line breaks put the list back where it was.
    """
    print()
    print("--- projects, for README.md (one line, no spaces between) ---")
    print("".join(
        '<a href="%s"><picture>'
        '<source media="(max-width: 600px)" srcset="assets/s-p-%s-n.svg">'
        '<img src="assets/s-p-%s.svg" alt="%s" /></picture></a>'
        % (url, slug, slug, ALT[slug])
        for slug, _, _, url, *_ in PROJECTS))
    print('<a href="%s"><img src="assets/s-p-all.svg" alt="All projects" /></a>'
          % ALL_PROJECTS)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for word in TITLES:
        title_svg(word)
    for name, block in BLOCKS.items():
        svg(block["wide"], "s-" + name, **block["opts"])
        svg(block["narrow"], "s-" + name + "-n",
            **dict(block["opts"], **block.get("narrow_opts", {})))
    projects_svg()
    readme_snippet()
