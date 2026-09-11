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
# VT323 carries no CJK, and the Noto Serif SC that Windows ships is 21 MB for
# the six characters wanted here, so `.build/subset-cjk.py` cuts it down to
# just those - a Mincho serif, which is the shape Evangelion's own titles are
# cut in. Noto is under the SIL Open Font License, which travels with it in
# NotoSerifSC-OFL.txt.
CJK = ".build/NotoSerifSC-subset.ttf"
OUT = "assets"

GROUND = "#0d1117"      # GitHub dark canvas
FG = "#e6edf3"          # GitHub's own body ink
DIM = "#8b949e"
RULE = "#30363d"        # GitHub's own border grey
RADIUS = 18             # px the bordered blocks are rounded by
PAD = 16                # px of ground around the text

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


def svg(lines, name, size=20, leading=1.0, colors=None, font=FONT,
        pad=PAD, border=False, animate=None, delay=0.0,
        notes=None, note_size=24):
    """Render lines of text to assets/<name>.svg, reusing each glyph outline.

    Pass `animate` a mode per line - "type" to have it typed a character at a
    time behind a cursor, "wipe" to have it swept in - and the block plays
    itself out on load. `delay` holds the whole sequence back, which is how a
    block in a second file falls in behind the one above it.

    `notes` sets (line, text) pairs in the margin the short lines leave on the
    right, in the second face. The line may be fractional, which sets the note
    between two of them. They fade up once the block has finished playing.
    """
    t = Typesetter(font, size)
    line_h = size * leading
    w = max(t.width(line) for line in lines) + 2 * pad
    h = line_h * len(lines) + 2 * pad

    # Each distinct glyph is defined once and placed with <use>; VT323 repeats
    # enough that this is roughly a tenth of the size of one path per glyph.
    used = sorted({ch for line in lines for ch in line if ch != " " and t.path(ch)})
    ids = {ch: "g%d" % i for i, ch in enumerate(used)}
    defs = "".join('<path id="%s" d="%s"/>' % (ids[ch], t.path(ch)) for ch in used)

    if notes:
        tn = Typesetter(CJK, note_size)
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

    for i, line in enumerate(lines):
        fill = FG if colors is None else colors[i]
        # Baseline: the ascender sits just under the top padding.
        baseline = pad + line_h * i + size * 0.78
        parts.append('<g fill="%s" transform="translate(0 %.2f) scale(%.5f %.5f)">'
                     % (fill, baseline, t.scale, -t.scale))
        x = pad / t.scale
        for ch in line:
            if ch != " " and ch in ids:
                parts.append('<use xlink:href="#%s" x="%.1f"/>' % (ids[ch], x))
            x += t.advance(ch) / t.scale
        parts.append("</g>")

    if animate:
        parts.extend(_animation(lines, animate, t, size, line_h, pad,
                                round(w), round(h), delay))

    if notes:
        # Painted after the covers, so a cover parked to the right of the line
        # it has just uncovered cannot sit on top of the margin.
        if animate:
            parts.append("<style>@keyframes fade{to{opacity:1}}"
                         ".nt{opacity:0;animation:fade .6s %.3fs forwards}"
                         "@media (prefers-reduced-motion:reduce)"
                         "{.nt{opacity:1;animation:none}}</style>"
                         % (delay + _runtime(lines, animate)))
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


# The two lines that say who he is are typed; the three that qualify it are
# swept in behind them, which keeps the whole opening under four seconds
# instead of the seven it would take to type all 283 characters.
TAGLINE = [
    "JESUS PEREZ BAZAROT - 21 - SEVILLE",
    "I WORK ON THE PARTS OF AI THAT BREAK.",
    "MODELS THAT FORGET. MODELS TOO LARGE. BENCHMARKS THAT LIE.",
    "SEARCHING FOR SAFE AGI.",
]
TAGLINE_MODES = ["type", "type", "wipe", "wipe"]

BLOCKS = {
    # The Instrumentality Project, in the margin the two short lines leave,
    # on the first line's own baseline and in the bright ink.
    "tagline": (dict(size=30, leading=1.15, colors=[FG, FG, DIM, DIM],
                     animate=TAGLINE_MODES,
                     notes=[(0, "人類補完計画")]), TAGLINE),
    # Tags is a second file, so it cannot share a clock with the block above
    # it - it can only be held back by what that block is known to take. A
    # sweep tolerates the few milliseconds the two images load apart; a typed
    # line, locked to the character, would not.
    "tags": (dict(size=22, colors=[DIM], animate=["wipe"],
                  delay=_runtime(TAGLINE, TAGLINE_MODES) - LEAD), [
        "AI/ML RESEARCH  /  CONTINUAL LEARNING  /  "
        "BENCHMARKS & EVALUATION  /  EDGE & LOCAL-FIRST",
    ]),
    "about": (dict(size=22, leading=1.25), [
        "Fourth-year Computer Engineering at the UNIVERSIDAD DE SEVILLA, back in",
        "Seville since July 2026 after spending third year at the BEIJING INSTITUTE",
        "OF TECHNOLOGY. I work on the parts of AI that break: models that forget",
        "what they learned, models too large for the hardware they need to run on,",
        "benchmarks that quietly measure the wrong thing.",
        "",
        "Most of what I know I learned by building something, watching it fail in an",
        "interesting way, and rebuilding it. My benchmark work took seven debugging",
        "sessions and turned up thirty problems; the worst of them, a collapsed VAE",
        "posterior with 0 of 32 latent dimensions active, meant the transition model",
        "had never seen the environment at all and invalidated 225 runs. Rewriting",
        "from scratch was less painful than publishing something I knew was wrong.",
        "",
        "Long term: a master's in AI, and work where machine learning is pointed at",
        "something worth conserving - marine ecology, for a start.",
    ]),
    "stack": (dict(size=21, leading=1.2), [
        "LANGUAGES        Python / TypeScript / Java / C / C++ / Rust / SQL / Assembly",
        "DEEP LEARNING    PyTorch / CUDA / Triton / torch.compile / BF16 / quantisation / DDP",
        "AI / ML          Transformers / state space models / RAG / speech pipelines",
        "                 diarisation / benchmarking / agents & multi-agent systems",
        "BACKEND & DATA   FastAPI / React / Supabase / PostgreSQL / pgvector / Docker",
        "                 Neo4j / WebSockets",
        "HARDWARE         RTX 4050 local / RunPod for anything that does not fit",
        "SPOKEN           Spanish (native) / English (C1, Trinity 2020) / Chinese",
    ]),
    "work": (dict(size=21, leading=1.2), [
        "2025 - now     INDEPENDENT AI/ML RESEARCH",
        "               World models, continual learning, LLM benchmarking",
        "",
        "               AI/ML DEVELOPER - OrgaAI",
        "               Conversational AI, audio & transcription (under NDA)",
        "",
        "2024 - 2025    CO-FOUNDER & CO-CTO - ByTheWay",
        "               Carpooling venture, closed",
        "",
        "2023 - 2024    CHIEF TECHNOLOGY OFFICER - NetKey",
        "               NFC networking hardware, closed",
        "",
        "2023           TECHNOLOGY SPEAKER - Telefonica innovaTE",
        "               NB-IoT & sustainability track",
        "",
        "EDUCATION      BSc Computer Engineering - Universidad de Sevilla - 2023-2027",
        "               Erasmus - Beijing Institute of Technology - to July 2026",
    ]),
    # Set in caps like the tagline, and sized so the block comes out 179 high
    # -- the height of the loop it sits beside -- at its own scale, so the
    # README shows it 1:1 and the glyphs are never resampled by the browser.
    "now": (dict(size=26, leading=1.936, pad=14), [
        "> ORGANISING THE AI TALKS AT THE UNIVERSIDAD DE SEVILLA",
        "> RESEARCH ON PUSHING THE TPU STATE OF THE ART",
        "> BUILDING PERSEO, THE ASSISTANT THAT LISTENS AND WATCHES",
    ]),
    "coords": (dict(size=22, leading=1.25, colors=[DIM, FG]), [
        "N 42 21 36   W 71 05 31   /   MIT, CAMBRIDGE, MASSACHUSETTS",
        "> NOT THERE YET. SOON THERE.",
    ]),
}

PROJECTS = [
    ("WMF BENCHMARK", "what a world model forgets when it learns a second task."),
    ("", "375 cells, 75 reference pairs, five methods, zero NaN steps. The"),
    ("", "distance axis does not order forgetting (rank correlation +0.00), and"),
    ("", "almost all of it happens in the encoder, where the standard metrics do"),
    ("", "not look: finetuning loses task-A reconstruction by a factor of 811"),
    ("", "while its fidelity score reports an improvement. Submitted to"),
    ("", "CL4FMAgents @ NeurIPS 2026; notification 29 Sep."),
    ("", ""),
    ("PERSEO", "a desktop assistant that listens and watches. Tauri 2, React 19,"),
    ("", "Gemini Live over WebSocket, a clap detector with voice confirmation,"),
    ("", "a ChromaDB RAG over my own notes. Built April-June 2026 in Beijing,"),
    ("", "then audited: the core sat outside git, the RAG had zero embeddings,"),
    ("", "and the Rust-Python bridge went from 7.5 s to 0.30 s a call."),
    ("", ""),
    ("HYBRIDMAMBA-11", "31.8M parameters in 13.6 MB, the first state-space entry"),
    ("", "in OpenAI's Parameter Golf. Closed: the H100 credits ran out."),
    ("", ""),
    ("TFG - JETSON ORIN NANO + GEMMA 3", "three pillars on running a model where"),
    ("", "it does not fit: optimisation, evaluation, deployment. Proposal stage."),
    ("", ""),
    ("MULTILINGUAL BENCHMARK", "Chinese against Western frontier models across"),
    ("", "nine languages and four task categories. Blocked on API credits."),
    ("", ""),
    ("NIGHTSHIFT", "an autonomous queue that claims one task a night, runs it"),
    ("", "unsupervised, and leaves a Telegram report by morning. Hourly, 00:00"),
    ("", "to 06:00, in production since August 2026."),
    ("", ""),
    ("KOTOBA", "the whole JLPT, N5 to N1, spaced and offline, in Spanish."),
    ("", ""),
    ("MAGI", "three personas answer at once and any one veto sinks the verdict."),
    ("", ""),
    ("AGENTIC REASONING TRACES", "15 annotated traces, 142 steps, a nine-type"),
    ("", "error taxonomy, three of them wrong on purpose. Human review pending."),
    ("", ""),
    ("CLASSTRANSCRIBER", "lectures into speaker-separated notes, diarisation and"),
    ("", "Whisper, all running locally."),
    ("", ""),
    ("NETKEY", "NFC networking startup where I was CTO."),
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
    """Project names in the bright ink, their descriptions in the dim one."""
    lines, colors = [], []
    for title, desc in PROJECTS:
        if title:
            lines.append(title + ("  " + desc if desc else ""))
            colors.append(FG)
        else:
            lines.append(("  " + desc) if desc else "")
            colors.append(DIM)
    svg(lines, "s-projects", size=21, leading=1.2, colors=colors)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for word in TITLES:
        title_svg(word)
    for name, (opts, lines) in BLOCKS.items():
        svg(lines, "s-" + name, **opts)
    projects_svg()
