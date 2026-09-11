"""Render every README text block as a PNG that sits on GitHub's own ground.

GitHub applies its own chrome to code fences, tables and links, so every block
that must stay monochrome is rasterised here instead: white text on #0d1117,
the exact colour of the dark-theme canvas, so the blocks blend into the page
with no visible seam. Photos in .build/src are levelled onto the same ground.

Run from the repo root: python .build/render.py
"""

import glob
import os

import matplotlib
import pyfiglet
from PIL import Image, ImageDraw, ImageFont

SCALE = 2
OUT = "assets"
SRC = ".build/src"
MONO = glob.glob(os.path.join(
    os.path.dirname(matplotlib.__file__),
    "mpl-data", "fonts", "ttf", "DejaVuSansMono.ttf"))[0]
VT323 = ".build/VT323-Regular.ttf"

GROUND = (13, 17, 23)          # #0d1117 - GitHub dark canvas
FG = (255, 255, 255)
DIM = (145, 152, 160)


def text_image(lines, font_path, size, pad=24, line_gap=1.0, colors=None):
    font = ImageFont.truetype(font_path, size * SCALE)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * line_gap)
    p = pad * SCALE
    w = int(max(probe.textlength(line, font=font) for line in lines)) + 2 * p
    h = lh * len(lines) + 2 * p
    img = Image.new("RGB", (w, h), GROUND)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((p, p + i * lh), line, font=font,
               fill=FG if colors is None else colors[i])
    return img


def save(img, name):
    path = os.path.join(OUT, name + ".png")
    img.save(path)
    print("%-30s %dx%d css px" % (path, img.width // SCALE, img.height // SCALE))


def ascii_title(word, name, size=13):
    art = pyfiglet.figlet_format(word, font="dos_rebel").split("\n")
    while art and not art[-1].strip():
        art.pop()
    while art and not art[0].strip():
        art.pop(0)
    save(text_image(art, MONO, size, pad=14), "t-" + name)


def vt(lines, name=None, size=26, **kw):
    img = text_image(lines, VT323, size, line_gap=0.78, **kw)
    if name:
        save(img, name)
    return img


def onto_ground(img):
    """Map a white-on-black photo so its black becomes the GitHub ground."""
    g = img.convert("L")
    return Image.merge("RGB", [
        g.point(lambda v, c=c: int(c + v * (255 - c) / 255)) for c in GROUND])


def photo(name, level_from=0):
    """Level a source photo's background to black, then onto the ground."""
    im = Image.open(os.path.join(SRC, name)).convert("L")
    if level_from:
        span = 255 - level_from
        im = im.point(lambda v: max(0, min(255, int((v - level_from) * 255 / span))))
    return onto_ground(im)


PROJECTS = [
    ("WMF BENCHMARK", "How world models forget - under review"),
    ("PERSEO", "Assistant that listens and watches - Tauri 2, Rust"),
    ("HYBRIDMAMBA-11", "31.8M params in 13.6 MB - OpenAI Parameter Golf"),
    ("JETSON ORIN", "Running an LLM in orbit - thesis proposal"),
    ("MULTILINGUAL BENCH", "Chinese vs. Western models, nine languages"),
    ("KOTOBA", "The entire JLPT, spaced - 20,785 cards"),
    ("NIGHTSHIFT", "A queue that ships code while I sleep - 27 done"),
    ("MAGI", "Three personas answer, one veto sinks the verdict"),
    ("REASONING TRACES", "15 traces, 142 steps, 9-type error taxonomy"),
    ("CLASSTRANSCRIBER", "Lectures into speaker-separated notes, local"),
    ("NETKEY", "NFC networking startup where I was CTO"),
]


ART_WIDTH = 500      # css px the glitch photo occupies inside the projects block


def projects_block():
    """Glitch photo large on the left, the project list smaller on the right."""
    text = vt([t.ljust(21) + d for t, d in PROJECTS], size=21)
    art = photo("03-glitch-hands.jpg")
    width = ART_WIDTH * SCALE
    art = art.resize((width, round(art.height * width / art.width)), Image.LANCZOS)
    gap = 32 * SCALE
    height = max(art.height, text.height)
    out = Image.new("RGB", (art.width + gap + text.width, height), GROUND)
    out.paste(art, (0, (height - art.height) // 2))
    out.paste(text, (art.width + gap, (height - text.height) // 2))
    save(out, "b-projects")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)

    for word in ["Persus", "About", "Stack", "Work", "Projects", "Now", "Contact"]:
        ascii_title(word, word.lower())

    vt([
        "JESUS PEREZ BAZAROT - 21 - SEVILLE",
        "I WORK ON THE PARTS OF AI THAT BREAK.",
        "MODELS THAT FORGET. MODELS TOO LARGE. BENCHMARKS THAT LIE.",
        "IF A RESULT CAN'T BE REPRODUCED BIT FOR BIT, I DON'T TRUST IT YET.",
    ], "b-tagline", size=30, colors=[FG, FG, DIM, DIM])

    vt([
        "AI/ML RESEARCH   /   CONTINUAL LEARNING   /   "
        "BENCHMARKS & EVALUATION   /   EDGE & LOCAL-FIRST",
    ], "b-tags", size=24, colors=[DIM])

    vt([
        "Born and raised near Seville, final year of Computer Engineering at the",
        "UNIVERSIDAD DE SEVILLA, with the third year spent at the BEIJING INSTITUTE",
        "OF TECHNOLOGY. I work on the parts of AI that break: models that forget what",
        "they learned, models too large for the hardware they need to run on,",
        "benchmarks that quietly measure the wrong thing.",
        "",
        "Most of what I know I learned by building something, watching it fail in an",
        "interesting way, and rebuilding it. Along the way I have spoken at TELEFONICA,",
        "competed in NASA SPACEAPPS, been CTO of a small startup, and co-founded",
        "another. Martial arts, three or four times a week, taught me the part no",
        "project teaches: how to keep showing up after losing.",
        "",
        "My current research asks a narrow question - when a world model learns a",
        "second task, what exactly does its transition model forget, and how do we",
        "measure that honestly? Seven debugging sessions turned up twenty-one bugs,",
        "one of which, a collapsed VAE posterior, invalidated an entire round of",
        "results. Rewriting the paper from scratch was less painful than publishing",
        "something I knew was wrong.",
        "",
        "Aiming for a master's in AI at MIT, and long term for work where machine",
        "learning is pointed at something worth conserving - marine ecology, for a start.",
    ], "b-about")

    vt([
        "LANGUAGES        Python / TypeScript / Java / C / C++ / Rust / SQL / Assembly",
        "DEEP LEARNING    PyTorch / CUDA / Triton / torch.compile / BF16 / quantisation / DDP",
        "AI / ML          Transformers / state space models / RAG / speech pipelines",
        "                 diarisation / benchmarking / agents & multi-agent systems",
        "BACKEND & DATA   FastAPI / React / Supabase / PostgreSQL / pgvector / Docker",
        "                 Neo4j / WebSockets",
        "SPOKEN           Spanish (native) / English (C1, Trinity 2020) / Chinese (conversational)",
    ], "b-stack")

    vt([
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
    ], "b-work",
        colors=[FG, DIM, FG, FG, DIM, FG, FG, DIM, FG, FG, DIM, FG, FG, DIM])

    vt([
        "EDUCATION      BSc Computer Engineering - Universidad de Sevilla - 2023-2027",
        "               Erasmus exchange - Beijing Institute of Technology - 2025-2026",
    ], "b-education", colors=[FG, DIM])

    projects_block()

    vt([
        "> finishing the WMF benchmark write-up and the forgetting metrics behind it",
        "> compressing state space models until they fit where they shouldn't",
        "> Perseo, still, after three years",
    ], "b-now")

    vt(["N 37 23 21   W 5 59 04   /   SEVILLE, SPAIN"], "b-coords",
       size=24, colors=[DIM])

    # Photos share the same ground. The poster's own background sits at level 44.
    save(photo("01-hands.png"), "p-hands")
    save(photo("02-creative-ecstasy.jpg", level_from=44), "p-angel")
