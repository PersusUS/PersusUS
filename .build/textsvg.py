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
OUT = "assets"

GROUND = "#0d1117"      # GitHub dark canvas
FG = "#e6edf3"          # GitHub's own body ink
DIM = "#8b949e"
RULE = "#30363d"        # GitHub's own border grey
RADIUS = 18             # px the bordered blocks are rounded by
PAD = 16                # px of ground around the text
PROMPT = "PS> "         # the shell prompt the Now block is set behind


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
        pad=PAD, border=False):
    """Render lines of text to assets/<name>.svg, reusing each glyph outline.

    A line is either a string or, where one line needs two inks - a shell
    prompt in grey ahead of the command in white - a list of (text, colour)
    runs that are set one after another on the same baseline.
    """
    t = Typesetter(font, size)
    line_h = size * leading
    rows = [line if isinstance(line, list) else
            [(line, FG if colors is None else colors[i])]
            for i, line in enumerate(lines)]
    w = max(sum(t.width(text) for text, _ in row) for row in rows) + 2 * pad
    h = line_h * len(lines) + 2 * pad

    # Each distinct glyph is defined once and placed with <use>; VT323 repeats
    # enough that this is roughly a tenth of the size of one path per glyph.
    used = sorted({ch for row in rows for text, _ in row for ch in text
                   if ch != " " and t.path(ch)})
    ids = {ch: "g%d" % i for i, ch in enumerate(used)}
    defs = "".join('<path id="%s" d="%s"/>' % (ids[ch], t.path(ch)) for ch in used)

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

    for i, row in enumerate(rows):
        # Baseline: the ascender sits just under the top padding.
        baseline = pad + line_h * i + size * 0.78
        x = pad / t.scale
        for text, fill in row:
            parts.append('<g fill="%s" transform="translate(0 %.2f) scale(%.5f %.5f)">'
                         % (fill, baseline, t.scale, -t.scale))
            for ch in text:
                if ch != " " and ch in ids:
                    parts.append('<use xlink:href="#%s" x="%.1f"/>' % (ids[ch], x))
                x += t.advance(ch) / t.scale
            parts.append("</g>")
    parts.append("</svg>")

    path = os.path.join(OUT, name + ".svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    print("%-26s %dx%d  %d KB" % (path, round(w), round(h),
                                  os.path.getsize(path) // 1024))


BLOCKS = {
    "tagline": (dict(size=30, leading=1.15, colors=[FG, FG, DIM, DIM]), [
        "JESUS PEREZ BAZAROT - 21 - SEVILLE",
        "I WORK ON THE PARTS OF AI THAT BREAK.",
        "MODELS THAT FORGET. MODELS TOO LARGE. BENCHMARKS THAT LIE.",
        "IF A RESULT CAN'T BE REPRODUCED BIT FOR BIT, I DON'T TRUST IT YET.",
    ]),
    "tags": (dict(size=22, colors=[DIM]), [
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
    # Now is the one block written as a session rather than as prose: three
    # PowerShell commands, the prompt in grey and the command in white, which
    # is the same terminal the titles and the loop are already set in.
    "now": (dict(size=26, leading=1.97, pad=30), [
        [(PROMPT, DIM),
         ('START-TALKSERIES -TOPIC AI -AT "UNIVERSIDAD DE SEVILLA"', FG)],
        [(PROMPT, DIM),
         ("INVOKE-RESEARCH -TARGET TPU -GOAL STATE-OF-THE-ART", FG)],
        [(PROMPT, DIM),
         ("BUILD-PERSEO -CAPABILITY LISTEN,WATCH", FG)],
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
