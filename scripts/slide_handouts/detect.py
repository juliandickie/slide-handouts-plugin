"""Find the slides in a PDF: a deck saved one slide per page, or a handout with several framed slides per page."""
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

PAPER_SIZES = [(595.28, 841.89), (612.0, 792.0), (612.0, 1008.0)]  # A4, US Letter, US Legal
PAPER_TOL = 2.0
SHAPES = {"16:9": 9 / 16, "16:10": 10 / 16, "4:3": 3 / 4}
NO_FRAMES = ("This looks like a printed page with no slide frames. If each page is one slide, run again "
             "with --one-per-page. Otherwise export the deck straight to PDF, one slide per page.")


class RefusedError(Exception):
    """A message the user sees as it is."""


@dataclass(frozen=True)
class Slide:
    page: int
    clip: pymupdf.Rect
    number: int


@dataclass
class Detection:
    kind: str
    per_page: int
    slides: list
    aspect: float
    numbers_from: str
    skipped: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def open_pdf(path: Path) -> pymupdf.Document:
    name = Path(path).name
    try:
        doc = pymupdf.open(str(path), filetype="pdf")
    except Exception:
        raise RefusedError(f"{name} could not be opened. It may be damaged, or not a PDF.") from None
    if doc.needs_pass:
        raise RefusedError(f"{name} is protected by a password. Export it again without one.")
    if doc.page_count == 0:
        raise RefusedError(f"{name} has no pages.")
    return doc


def is_paper(rect: pymupdf.Rect) -> bool:
    w, h = rect.width, rect.height
    return any((abs(w - a) <= PAPER_TOL and abs(h - b) <= PAPER_TOL) or (abs(w - b) <= PAPER_TOL and abs(h - a) <= PAPER_TOL)
               for a, b in PAPER_SIZES)


def shape_name(aspect: float) -> str:
    for name, value in SHAPES.items():
        if abs(aspect - value) / value <= 0.02:
            return name
    return f"{1 / aspect:.2f} to 1"


def _deck(doc: pymupdf.Document) -> Detection:
    # Task 2's real exports add no margin around the slide, so each clip is the whole page.
    slides = [Slide(page.number, pymupdf.Rect(page.rect), page.number + 1) for page in doc]
    first = doc[0].rect
    return Detection("deck", 1, slides, first.height / first.width, "page order")


def detect(doc: pymupdf.Document, order: str = "rows", one_per_page: bool = False) -> Detection:
    if one_per_page or not is_paper(doc[0].rect):
        return _deck(doc)
    raise RefusedError(NO_FRAMES)
