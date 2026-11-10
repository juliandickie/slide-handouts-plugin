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
    if not doc.is_pdf:  # MuPDF opens a picture even when told it is a PDF
        raise RefusedError(f"{name} is not a PDF. Export the slides to PDF and try again.")
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


EXPORT_ADVICE = "Export the deck straight to PDF, one slide per page, which always works."
EDGE_TOL = 1.5    # pt: the same rectangle drawn twice, or a frame drawn 1 pt smaller
SIZE_TOL = 3.0    # pt: real exports draw the odd frame up to 2 pt off size
NEAR_TOL = 4.0    # pt: a slide-sized shape this close to a frame is a copy of it, not another slide
NUMBER_REACH = 20  # pt: how far from a frame a printed slide number may sit


def _same(a: pymupdf.Rect, b: pymupdf.Rect) -> bool:
    return all(abs(x - y) <= EDGE_TOL for x, y in zip(a, b))


def _candidates(page: pymupdf.Page) -> list:
    """Slide-shaped rectangles drawn on the page, outermost only."""
    found = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "re":
                rect = pymupdf.Rect(item[1])
            elif item[0] == "qu" and item[1].is_rectangular:
                rect = item[1].rect
            else:
                continue
            if rect.height <= 0 or rect.width < 0.15 * page.rect.width:
                continue
            if rect.get_area() > 0.9 * page.rect.get_area():  # a page background or border box
                continue
            if 1.2 <= rect.width / rect.height <= 1.9 and not any(_same(rect, f) for f in found):
                found.append(rect)
    return [r for r in found if not any(o is not r and o.get_area() > r.get_area() and
                                        o.contains(r + (EDGE_TOL, EDGE_TOL, -EDGE_TOL, -EDGE_TOL)) for o in found)]


def _frames(doc: pymupdf.Document) -> list | None:
    """Per page, the frames of the size found on the most pages (ties go to the larger size)."""
    per_page = [_candidates(page) for page in doc]
    sizes = []
    for pno, rects in enumerate(per_page):
        for r in rects:
            for size in sizes:
                if abs(size[0] - r.width) <= SIZE_TOL and abs(size[1] - r.height) <= SIZE_TOL:
                    size[2].add(pno)
                    break
            else:
                sizes.append((r.width, r.height, {pno}))
    if not sizes:
        return None
    w, h, _ = max(sizes, key=lambda s: (len(s[2]), s[0] * s[1]))
    kept = [[r for r in rects if abs(r.width - w) <= SIZE_TOL and abs(r.height - h) <= SIZE_TOL] for rects in per_page]

    def pages_with_position(r):
        return sum(any(abs(o.x0 - r.x0) <= EDGE_TOL and abs(o.y0 - r.y0) <= EDGE_TOL for o in rects) for rects in kept)

    merged = []
    for rects in kept:  # near copies of one frame become the copy whose position recurs on the most pages
        groups = []
        for r in rects:
            for g in groups:
                if all(abs(a - b) <= NEAR_TOL for a, b in zip(r, g[0])):
                    g.append(r)
                    break
            else:
                groups.append([r])
        merged.append([max(g, key=pages_with_position) for g in groups])
    return merged


def _printed_number(frame: pymupdf.Rect, words: list, frames: list):
    best = None
    for w in words:
        if not w[4].isdigit():
            continue
        box = pymupdf.Rect(w[:4])
        if any(box.intersects(f) for f in frames):
            continue
        middle = (box.y0 + box.y1) / 2
        if 0 <= box.y0 - frame.y1 <= NUMBER_REACH and frame.x0 - NUMBER_REACH <= box.x0 and box.x1 <= frame.x1 + NUMBER_REACH:
            distance = box.y0 - frame.y1
        elif frame.y0 <= middle <= frame.y1 and (0 <= box.x0 - frame.x1 <= NUMBER_REACH or 0 <= frame.x0 - box.x1 <= NUMBER_REACH):
            distance = min(abs(box.x0 - frame.x1), abs(frame.x0 - box.x1))
        else:
            continue
        if best is None or distance < best[0]:
            best = (distance, int(w[4]))
    return None if best is None else best[1]


def _reading_order(frames: list, order: str) -> list:
    across, down = ("x0", "y0") if order == "rows" else ("y0", "x0")
    ordered, groups = sorted(frames, key=lambda r: getattr(r, down)), []
    for r in ordered:  # a new row (or column) starts more than half a frame further down (or across)
        half = (r.height if order == "rows" else r.width) / 2
        if groups and getattr(r, down) - getattr(groups[-1][0], down) <= half:
            groups[-1].append(r)
        else:
            groups.append([r])
    return [r for g in groups for r in sorted(g, key=lambda r: getattr(r, across))]


def _handout(doc: pymupdf.Document, frames: list, order: str) -> Detection:
    first = doc[0].rect
    if any(abs(p.rect.width - first.width) > PAPER_TOL or abs(p.rect.height - first.height) > PAPER_TOL for p in doc):
        raise RefusedError(f"The pages have mixed page sizes, so this cannot be read as one handout. {EXPORT_ADVICE}")
    per = len(frames[0])
    for pno, page_frames in enumerate(frames):
        last = pno == len(frames) - 1
        if (not last and len(page_frames) != per) or not 1 <= len(page_frames) <= per:
            raise RefusedError(f"The slide frame counts vary between pages, so the slide order cannot be trusted. {EXPORT_ADVICE}")
        for a in range(len(page_frames)):
            for b in range(a + 1, len(page_frames)):
                inter = pymupdf.Rect(page_frames[a]) & page_frames[b]
                if not inter.is_empty and inter.get_area() > 1:
                    raise RefusedError(f"Slide frames overlap on page {pno + 1}, so the slides cannot be separated. {EXPORT_ADVICE}")
    numbered = []
    for pno, page_frames in enumerate(frames):
        words = doc[pno].get_text("words")
        numbered.append([(_printed_number(f, words, page_frames), f) for f in page_frames])
    flat = [n for page in numbered for n, _ in page]
    notes, skipped = [], []
    if all(n is not None for n in flat):
        source, slides, previous = "printed", [], None
        for pno, page in enumerate(numbered):
            page = sorted(page, key=lambda pair: pair[0])
            values = [n for n, _ in page]
            if len(set(values)) != len(values) or (previous is not None and values[0] <= previous):
                raise RefusedError(f"The printed slide numbers repeat or go down, so the slide order cannot be trusted. {EXPORT_ADVICE}")
            previous = values[-1]
            slides += [Slide(pno, f + (1, 1, -1, -1), n) for n, f in page]
        present = set(flat)
        skipped = [k for k in range(min(flat), max(flat) + 1) if k not in present]
        if skipped:
            notes.append(f"Slides {', '.join(map(str, skipped))} are not in the handout, probably because they were hidden.")
    elif all(n is None for n in flat):
        source, slides = "reading order", []
        for pno, page_frames in enumerate(frames):
            slides += [Slide(pno, f + (1, 1, -1, -1), len(slides) + k + 1) for k, f in enumerate(_reading_order(page_frames, order))]
        notes.append("The handout has no printed slide numbers, so slides are numbered in reading order. "
                     "Hidden slides, if the deck had any, are not counted.")
    else:
        raise RefusedError(f"Only some slides have printed numbers, so the slide order cannot be trusted. {EXPORT_ADVICE}")
    clip = slides[0].clip
    return Detection("handout", per, slides, clip.height / clip.width, source, skipped, notes)


def detect(doc: pymupdf.Document, order: str = "rows", one_per_page: bool = False) -> Detection:
    if any(page.rotation for page in doc):  # show_pdf_page ignores a source page's rotation
        raise RefusedError(f"Some pages are turned inside the PDF, so the slides cannot be placed reliably. {EXPORT_ADVICE}")
    if one_per_page:
        return _deck(doc)
    frames = _frames(doc)
    if is_paper(doc[0].rect):
        if not frames or not frames[0]:
            raise RefusedError(NO_FRAMES)
        return _handout(doc, frames, order)
    # Any other page size is a deck, unless every page but the last holds 2 or more frames:
    # Keynote's handout export uses 1024 x 768 pt pages, not paper.
    if frames and len(frames[0]) >= 2 and all(len(f) >= 2 for f in frames[:-1]):
        return _handout(doc, frames, order)
    if doc[0].rect.width / doc[0].rect.height < 1.2:  # narrower than any slide: a scan or a printed page
        raise RefusedError(NO_FRAMES)
    return _deck(doc)
