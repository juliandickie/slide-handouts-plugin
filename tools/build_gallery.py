"""Contributor script: rebuild the README gallery images, and the export guide's handout pages, from
the made-up deck and its real exports. Run from the repo root:
uv run --no-project --python 3.13 --with "pymupdf>=2.1,<3" python -I tools/build_gallery.py
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "tests")]

import pymupdf  # noqa: E402
from make_fixtures import deck_pdf  # noqa: E402
from slide_handouts import cli  # noqa: E402
from slide_handouts.layouts import GALLERY  # noqa: E402

OUT = ROOT / "assets" / "examples"
GUIDE = ROOT / "assets" / "guide"
GAP, BAND, LABEL = 24, 64, 40  # points around each page, under it for a label, and the label size


def build(deck: Path, out: Path, *options: str) -> Path:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = cli.main(["build", str(deck), *options, "--out", str(out)])
    if code:
        raise SystemExit(f"{out.name}: {json.loads(stdout.getvalue())['error']}")
    return out


def snapshot(pdfs: list, png: Path, dpi: int, labels: tuple = ()) -> None:
    """Page 1 of each PDF side by side on a grey sheet, each edged in grey so a white page shows, labels under them."""
    docs = [pymupdf.open(str(p)) for p in pdfs]
    w, h = docs[0][0].rect.width, docs[0][0].rect.height
    sheet = pymupdf.open()
    page = sheet.new_page(width=GAP + len(docs) * (w + GAP), height=h + 2 * GAP + (BAND if labels else 0))
    page.draw_rect(page.rect, color=None, fill=(0.93, 0.93, 0.93))
    rects = [pymupdf.Rect(GAP + i * (w + GAP), GAP, GAP + i * (w + GAP) + w, GAP + h) for i in range(len(docs))]
    for rect, label in zip(rects, labels):  # text first, as in render.py, or it loses its font
        width = pymupdf.get_text_length(label, fontname="helv", fontsize=LABEL)
        page.insert_text((rect.x0 + (w - width) / 2, rect.y1 + BAND * 0.75), label,
                         fontname="helv", fontsize=LABEL, color=(0.2, 0.2, 0.2))
    for rect, doc in zip(rects, docs):
        page.draw_rect(rect, color=None, fill=(1, 1, 1))
        page.show_pdf_page(rect, doc, 0)
        page.draw_rect(rect, color=(0.6, 0.6, 0.6), width=1)
    pix = page.get_pixmap(dpi=dpi * 4)  # render at 4x and average down, or the 0.6 pt dots alias into uneven or missing dots
    pix.shrink(2)
    pix.save(str(png))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    names = json.loads(GALLERY.read_text(encoding="utf-8"))["layouts"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        deck = deck_pdf(tmp / "Example deck.pdf", n=12)
        for name in names:
            n = int(name.split()[1])
            pdf = build(deck, tmp / f"example-{n:02d}.pdf", "--layout-name", name)
            snapshot([pdf], OUT / f"example-{n:02d}.png", 110)
        sizes = ("smaller", "medium", "larger")
        # Lines, not example 6's dots: a dot grid vanishes at the strip's small scale and the notes look empty.
        strip = [build(deck, tmp / f"size-{s}.pdf", "--layout-name", "example 3", "--size", s) for s in sizes]
        snapshot(strip, OUT / "sizes.png", 60, tuple(f"{s.capitalize()} slides" for s in sizes))
    GUIDE.mkdir(parents=True, exist_ok=True)
    for app in ("powerpoint", "keynote"):
        snapshot([ROOT / "tests" / "fixtures" / "real" / f"{app}-handout-3.pdf"], GUIDE / f"handout-{app}.png", 72)
    print(f"Wrote {len(names) + 1} images to {OUT} and 2 to {GUIDE}")


if __name__ == "__main__":
    main()
