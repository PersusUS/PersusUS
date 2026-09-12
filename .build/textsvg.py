"""Typeset the README's body copy as SVG set in VT323.

GitHub renders README markdown in its own font and strips every stylesheet, so
plain text cannot be given a typeface. An <img> pointing at an SVG can: the text
stays vector text rather than a rasterised PNG, and the glyph outlines travel
inside the file, so nothing has to be fetched at render time.

Each glyph is emitted as a <path> taken from the VT323 outlines. Paths render
identically everywhere, including inside GitHub's image proxy, where an
@font-face would be at the mercy of the sandbox.

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
# VT323 carries no CJK. DotGothic16 does, and is drawn on a dot grid the way a
# screen font is, so the kanji in the margin read as something the same machine
# put there. `.build/subset-cjk.py` cuts the 2 MB upstream release down to the
# six characters wanted here. DotGothic16 is under the SIL Open Font License,
# which travels with it in DotGothic16-OFL.txt.
CJK = ".build/DotGothic16-subset.ttf"
OUT = "assets"

GROUND = "#0d1117"      # GitHub dark canvas
FG = "#e6edf3"          # GitHub's own body ink
DIM = "#8b949e"
RULE = "#30363d"        # GitHub's own border grey
RADIUS = 18             # px the bordered blocks are rounded by
PAD = 16                # px of ground around the text
NOTE_GAP = 48           # px between a line and the note set out to its right

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
        return self.hmtx[name][0] * self.scale

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
        notes=None, note_size=24, scan=False, cursor=None):
    """Render lines of text to assets/<name>.svg, reusing each glyph outline.

    A line is either a string, which takes its colour from `colors`, or a list
    of (text, colour) runs - (text, colour, face) to change typeface mid-line -
    which is how a name and its description share one baseline in two inks.

    `scan` sends a soft band down the block for as long as the page is open,
    the way a phosphor screen is refreshed. `cursor` parks a blinking block at
    the end of the line it names, which is what a terminal does when it waits.

    Pass `animate` a mode per line - "type" to have it typed a character at a
    time behind a cursor, "wipe" to have it swept in - and the block plays
    itself out on load. `delay` holds the whole sequence back, which is how a
    block in a second file falls in behind the one above it.

    `notes` sets (line, text) pairs in the margin the short lines leave on the
    right, in the second face. The line may be fractional, which sets the note
    between two of them. They fade up once the block has finished playing.
    """
    faces = {}

    def face(path):
        if path not in faces:
            faces[path] = Typesetter(path, size)
        return faces[path]

    t = face(font)
    flat = [_plain(line) for line in lines]
    drawn = [_runs(line, FG if colors is None else colors[i], font)
             for i, line in enumerate(lines)]
    line_h = size * leading
    w = max(sum(face(f).width(text) for text, _, f in runs)
            for runs in drawn) + 2 * pad
    h = line_h * len(lines) + 2 * pad

    if cursor is not None:
        # Leave the cursor somewhere to sit, or it lands on the right edge.
        w = max(w, t.width(flat[cursor]) + t.advance("M") * 1.4 + 2 * pad)

    if notes:
        # The margin has to be there before a note can be set in it: widen the
        # block until the line a note shares a baseline with clears it by NOTE_GAP.
        tn0 = Typesetter(CJK, note_size)
        w = max([w] + [t.width(flat[round(i)]) + NOTE_GAP + tn0.width(text)
                       + 2 * pad for i, text in notes])

    # Each distinct glyph is defined once and placed with <use>; VT323 repeats
    # enough that this is roughly a tenth of the size of one path per glyph.
    used = sorted({(f, ch) for runs in drawn for text, _, f in runs
                   for ch in text if ch != " " and face(f).path(ch)})
    ids = {key: "g%d" % i for i, key in enumerate(used)}
    defs = "".join('<path id="%s" d="%s"/>' % (ids[(f, ch)], face(f).path(ch))
                   for f, ch in used)

    if notes:
        tn = tn0
        marks = sorted({ch for _, text in notes for ch in text if tn.path(ch)})
        nids = {ch: "j%d" % i for i, ch in enumerate(marks)}
        defs += "".join('<path id="%s" d="%s"/>' % (nids[ch], tn.path(ch))
                        for ch in marks)

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" '
             'xmlns:xlink="http://www.w3.org/1999/xlink" width="%d" height="%d" '
             'viewBox="0 0 %d %d" role="img">'
             % (round(w), round(h), round(w), round(h)),
             '<rect width="100%%" height="100%%" fill="%s"/>' % GROUND,
             '<defs>%s</defs>' % defs]

    if border:
        parts.append('<rect x="0.5" y="0.5" width="%.1f" height="%.1f" rx="%d" '
                     'fill="none" stroke="%s"/>'
                     % (round(w) - 1, round(h) - 1, RADIUS, RULE))

    for i, runs in enumerate(drawn):
        # Baseline: the ascender sits just under the top padding.
        baseline = pad + line_h * i + size * 0.78
        x = pad
        for text, fill, f in runs:
            tf = face(f)
            parts.append('<g fill="%s" transform="translate(0 %.2f) '
                         'scale(%.5f %.5f)">'
                         % (fill, baseline, tf.scale, -tf.scale))
            for ch in text:
                if ch != " " and (f, ch) in ids:
                    parts.append('<use xlink:href="#%s" x="%.1f"/>'
                                 % (ids[(f, ch)], x / tf.scale))
                x += tf.advance(ch)
            parts.append("</g>")

    if animate:
        parts.extend(_animation(flat, animate, t, size, line_h, pad,
                                round(w), round(h), delay))

    if cursor is not None:
        # A block left waiting at the end of a line, blinking on the same
        # cycle as the one that types the tagline out.
        baseline = pad + line_h * cursor + size * 0.78
        parts.append('<style>@keyframes bk{50%%{opacity:0}}'
                     '.cr{animation:bk %.2fs step-end infinite}'
                     '@media (prefers-reduced-motion:reduce){.cr{animation:none}}'
                     '</style>' % BLINK)
        parts.append('<rect class="cr" x="%.1f" y="%.1f" width="%.1f" '
                     'height="%.1f" fill="%s"/>'
                     % (pad + t.width(flat[cursor]) + t.advance("M") * 0.3,
                        baseline - size * 0.74, t.advance("M"), size * 0.8, FG))

    if scan:
        # A band of light crossing the block for as long as the page is open,
        # slow enough to be felt rather than watched, and at the opacity of a
        # reflection, so nothing under it becomes harder to read.
        band = round(size * 4)
        parts.append('<defs><linearGradient id="sc" x1="0" y1="0" x2="0" y2="1">'
                     '<stop offset="0" stop-color="%s" stop-opacity="0"/>'
                     '<stop offset=".5" stop-color="%s" stop-opacity=".05"/>'
                     '<stop offset="1" stop-color="%s" stop-opacity="0"/>'
                     '</linearGradient></defs>' % (FG, FG, FG))
        parts.append('<style>@keyframes sw{from{transform:translateY(%dpx)}'
                     'to{transform:translateY(%dpx)}}'
                     '.sw{animation:sw %.1fs linear infinite}'
                     '@media (prefers-reduced-motion:reduce){.sw{display:none}}'
                     '</style>' % (-band, round(h), max(6.0, h / 26.0)))
        parts.append('<rect class="sw" x="0" y="0" width="100%%" height="%d" '
                     'fill="url(#sc)"/>' % band)

    if notes:
        # Painted after the covers, so a cover parked to the right of the line
        # it has just uncovered cannot sit on top of the margin.
        if animate:
            parts.append("<style>@keyframes fade{to{opacity:1}}"
                         ".nt{opacity:0;animation:fade .6s %.3fs forwards}"
                         "@media (prefers-reduced-motion:reduce)"
                         "{.nt{opacity:1;animation:none}}</style>"
                         % (delay + _runtime(flat, animate)))
        for i, text in notes:
            baseline = pad + line_h * i + size * 0.78
            x = (w - pad - tn.width(text)) / tn.scale
            parts.append('<g class="nt" fill="%s" transform="translate(0 %.2f) '
                         'scale(%.5f %.5f)">'
                         % (FG, baseline, tn.scale, -tn.scale))
            for ch in text:
                if ch in nids:
                    parts.append('<use xlink:href="#%s" x="%.1f"/>' % (nids[ch], x))
                x += tn.advance(ch) / tn.scale
            parts.append("</g>")

    parts.append("</svg>")

    path = os.path.join(OUT, name + ".svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    print("%-26s %dx%d  %d KB" % (path, round(w), round(h),
                                  os.path.getsize(path) // 1024))


def _animation(lines, modes, t, size, line_h, pad, w, h, delay):
    """Cover every line, then slide the covers off in turn.

    Revealing by sliding an opaque rectangle the colour of the ground, rather
    than by clipping, buys the widest support there is: the only things put in
    motion are `transform` and `opacity`. A typed line steps its cover off one
    character at a time - VT323 is monospaced, so a step is exactly a glyph -
    with a block cursor riding the edge; a swept line is uncovered in one go.
    """
    adv = t.advance("M")
    css = [".cv{fill:%s}.cu{fill:%s}" % (GROUND, FG),
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
        y0 = 0 if i == 0 else pad + line_h * i
        y1 = h if i == len(lines) - 1 else pad + line_h * (i + 1)
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
            baseline = pad + line_h * i + size * 0.78
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

def _runtime(lines, modes):
    """How long a block takes to play itself out, in seconds."""
    return LEAD + sum(len(line) * (CHAR if mode == "type" else SWEEP) + PAUSE
                      for line, mode in zip(lines, modes) if line)


# The two lines that say who he is are typed; the two that qualify it are
# swept in behind them, which keeps the whole opening under three seconds
# instead of the five it would take to type all 147 characters.
TAGLINE = [
    "JESUS PEREZ BAZAROT - 21 - SEVILLE",
    "I WORK ON THE PARTS OF AI THAT BREAK.",
    "I MEAN TO MOVE THE WORLD, AND I AM STARTING WITH AI.",
    "SEARCHING FOR SAFE AGI.",
]
TAGLINE_MODES = ["type", "type", "wipe", "wipe"]

BLOCKS = {
    # The Instrumentality Project, in the margin the two short lines leave,
    # on the first line's own baseline and in the bright ink.
    "tagline": (dict(size=30, leading=1.15, colors=[FG, FG, DIM, DIM],
                     animate=TAGLINE_MODES,
                     notes=[(0, "人類補完計画")], note_size=26), TAGLINE),
    # Tags is a second file, so it cannot share a clock with the block above
    # it - it can only be held back by what that block is known to take. A
    # sweep tolerates the few milliseconds the two images load apart; a typed
    # line, locked to the character, would not.
    "tags": (dict(size=22, colors=[DIM], animate=["wipe"],
                  delay=_runtime(TAGLINE, TAGLINE_MODES) - LEAD), [
        "AI/ML RESEARCH  /  CONTINUAL LEARNING  /  BENCHMARKS  /  EDGE",
    ]),
    "about": (dict(size=22, leading=1.25, scan=True), [
        "Fourth-year Computer & Electronics Engineering at the UNIVERSIDAD DE",
        "SEVILLA, back from a year of Data Science & AI at the BEIJING INSTITUTE",
        "OF TECHNOLOGY.",
        "",
        "I learn by building, breaking and rebuilding. Long term: a master's in AI",
        "at MIT, pointed at something worth conserving.",
    ]),
    # Label in the bright ink, what it holds in the dim one, on one baseline.
    "stack": (dict(size=21, leading=1.3, scan=True), [
        [("LANGUAGES        ", FG), ("Python / C / C++ / Assembly", DIM)],
        [("DEEP LEARNING    ", FG), ("PyTorch / CUDA / Triton / quantisation", DIM)],
        [("AI / ML          ", FG),
         ("Transformers / state space models / RAG / benchmarking / agents", DIM)],
        [("BACKEND & DATA   ", FG),
         ("FastAPI / React / PostgreSQL / pgvector / Docker / Neo4j", DIM)],
        [("SPOKEN           ", FG), ("Spanish / English / Chinese", DIM)],
    ]),
    "work": (dict(size=21, leading=1.3, scan=True), [
        [("2026 - now    ", FG), ("進行中", FG, CJK)],
        [("2025 - 2026   ", FG),
         ("Independent AI/ML research - world models, continual", DIM)],
        [("              ", FG),
         ("learning, LLM benchmarking. AI/ML developer at OrgaAI.", DIM)],
        [("2024 - 2025   ", FG), ("Co-founder & co-CTO - ByTheWay. Closed.", DIM)],
        [("2023 - 2024   ", FG), ("CTO - NetKey, NFC hardware. Closed.", DIM)],
        [("2023          ", FG), ("Speaker - Telefonica innovaTE.", DIM)],
        [("EDUCATION     ", FG),
         ("BSc Computer & Electronics Engineering, Universidad", DIM)],
        [("              ", FG), ("de Sevilla, 2023-2027.", DIM)],
    ]),
    # Set in caps like the tagline, and sized so the block comes out 179 high
    # -- the height of the loop it sits beside -- at its own scale, so the
    # README shows it 1:1 and the glyphs are never resampled by the browser.
    "now": (dict(size=26, leading=1.936, pad=14, cursor=2), [
        "> ORGANISING THE AI TALKS AT THE UNIVERSIDAD DE SEVILLA",
        "> RESEARCH ON PUSHING THE TPU STATE OF THE ART",
        "> BUILDING PERSEO, THE ASSISTANT THAT LISTENS AND WATCHES",
    ]),
    "coords": (dict(size=22, leading=1.25, colors=[DIM, FG], cursor=1), [
        "N 42 21 36   W 71 05 31   /   MIT, CAMBRIDGE, MASSACHUSETTS",
        "> NOT THERE YET. SOON THERE.",
    ]),
}

PROJECTS = [
    ("WMF BENCHMARK", "what a world model forgets when it learns a second task"),
    ("PERSEO", "a desktop assistant that listens and watches"),
    ("HYBRIDMAMBA-11", "31.8M parameters in 13.6 MB, in OpenAI's Parameter Golf"),
    ("JETSON + GEMMA 3", "a model run where it does not fit - final-year project"),
    ("MULTILINGUAL", "Chinese against Western frontier models, nine languages"),
    ("NIGHTSHIFT", "an autonomous queue that claims one task a night"),
    ("KOTOBA", "the whole JLPT, N5 to N1, spaced and offline, in Spanish"),
    ("MAGI", "three personas answer; any one veto sinks the verdict"),
    ("TRACES", "15 annotated agent traces, a nine-type error taxonomy"),
    ("CLASSTRANSCRIBER", "lectures into speaker-separated notes, all local"),
    ("NETKEY", "NFC networking startup where I was CTO"),
]

TITLES = ["Persus", "About", "Stack", "Work", "Projects", "Now", "Contact"]


def title_svg(word, size=16):
    """One dos_rebel title, its block characters drawn as outlines."""
    art = [line.rstrip() for line
           in pyfiglet.figlet_format(word, font="dos_rebel").split("\n")]
    while art and not art[-1]:
        art.pop()
    while art and not art[0]:
        art.pop(0)
    svg(art, "t-" + word.lower(), size=size, leading=1.0, font=MONO)


def projects_svg():
    """One line a project: the name in the bright ink, what it is in the dim."""
    col = max(len(name) for name, _ in PROJECTS) + 2
    svg([[(name.ljust(col), FG), (desc, DIM)] for name, desc in PROJECTS],
        "s-projects", size=21, leading=1.45, scan=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for word in TITLES:
        title_svg(word)
    for name, (opts, lines) in BLOCKS.items():
        svg(lines, "s-" + name, **opts)
    projects_svg()
