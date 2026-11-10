"""Layout maths for handout pages. Pure: returns rectangles, draws nothing."""
from dataclasses import dataclass

import pymupdf

MM = 72 / 25.4
PAPER = {"a4": (595.28, 841.89), "letter": (612.0, 792.0)}  # portrait width, height in pt
MARGIN = 10 * MM
GAP = 5 * MM            # minimum gap between cells (Julian raised it from 4 mm, 2026-11-10)
BESIDE_GAP = 5 * MM     # slide edge to notes beside it
BESIDE_MIN = 40 * MM    # narrowest notes beside a slide
UNDER_GAP = 4 * MM      # slide bottom to notes under it
CAP = 5.4               # Helvetica cap height at 7.5 pt
LABEL_LIFT = 3.5        # label baseline above the slide's top
LABEL_CLEAR = 2.0       # clear space between a label's letters and the cell above
PRESETS = {"smaller": 0.70, "medium": 0.85, "larger": 1.0}
SMALL_WARN_MM = 70
SMALLEST_MM = 20
TOL = 0.01


@dataclass(frozen=True)
class LayoutOptions:
    paper: str          # "a4" | "letter"
    orientation: str    # "portrait" | "landscape"
    per_page: int       # 1, 2, 3, 4 or 6
    notes: str          # "beside" | "under" | "both"
    style: str          # "lines" | "dots" | "blank" | "box"
    spacing_mm: float   # 4 to 12, already resolved from the fallbacks
    size: str | float   # "smaller" | "medium" | "larger" | exact slide width in mm


@dataclass
class Cell:
    slide: pymupdf.Rect
    notes: list          # beside or under: 1 rect; both: [beside, under]; [] with a shared column
    label: pymupdf.Rect  # visible letters of "Slide 999"


@dataclass
class PageLayout:
    width: float
    height: float
    cells: list
    column: pymupdf.Rect | None
    slide_width_mm: float
    warnings: list


def under_min(opts: LayoutOptions) -> float:
    return 2 * opts.spacing_mm * MM if opts.style in ("lines", "dotted", "dots") else 16 * MM


def _larger(opts, cols, rows, w, h, aspect):
    col_w = (w - (cols - 1) * GAP) / cols
    row_h = (h - (rows - 1) * GAP) / rows
    if opts.notes == "beside":
        width = min(col_w - BESIDE_GAP - BESIDE_MIN, row_h / aspect)
    elif opts.notes == "under":
        width = min(col_w, (row_h - UNDER_GAP - under_min(opts)) / aspect)
    else:
        width = min(col_w - BESIDE_GAP - BESIDE_MIN, (row_h - UNDER_GAP - under_min(opts)) / aspect)
    return width, col_w, row_h


def plan_page(opts: LayoutOptions, aspect: float) -> PageLayout:
    if opts.style == "box" and opts.notes == "both":
        raise ValueError("A typeable box works with notes beside or under each slide, not both.")
    pw, ph = PAPER[opts.paper]
    if opts.orientation == "landscape":
        pw, ph = ph, pw
    w, h = pw - 2 * MARGIN, ph - 2 * MARGIN
    best = None
    for cols in range(1, opts.per_page + 1):
        if opts.per_page % cols:
            continue
        rows = opts.per_page // cols
        larger, col_w, row_h = _larger(opts, cols, rows, w, h, aspect)
        if best is None or larger > best[0] + TOL:  # ties keep the grid with fewer columns
            best = (larger, cols, rows, col_w, row_h)
    larger, cols, rows, col_w, row_h = best
    if larger < SMALLEST_MM * MM:
        raise ValueError(f"This layout does not fit: slides would be under {SMALLEST_MM} mm wide.")

    warnings = []
    if isinstance(opts.size, str):
        sw = larger * PRESETS[opts.size]
    elif opts.size * MM > larger + TOL:
        sw = larger
        warnings.append(f"A slide width of {opts.size:g} mm does not fit this layout, so slides are {larger / MM:.0f} mm wide.")
    else:
        sw = opts.size * MM
    sh = sw * aspect
    if sw / MM < SMALL_WARN_MM:
        warnings.append(f"Slides are {sw / MM:.0f} mm wide. Small text may be hard to read.")

    cell_h = sh if opts.notes == "beside" else row_h
    gap_v = max(GAP, (h - rows * cell_h) / (rows - 1)) if rows > 1 else GAP
    shared = cols == 1 and opts.notes == "beside" and opts.style != "box"
    label_w = pymupdf.get_text_length("Slide 999", fontname="helv", fontsize=7.5)
    cells = []
    for r in range(rows):
        top = MARGIN + r * (cell_h + gap_v)
        for c in range(cols):
            left = MARGIN + c * (col_w + GAP)
            slide = pymupdf.Rect(left, top, left + sw, top + sh)
            notes = []
            if not shared and opts.notes in ("beside", "both"):
                notes.append(pymupdf.Rect(slide.x1 + BESIDE_GAP, top, left + col_w, top + sh))
            if opts.notes in ("under", "both"):
                notes.append(pymupdf.Rect(left, slide.y1 + UNDER_GAP, left + col_w, top + cell_h))
            base = slide.y0 - LABEL_LIFT
            cells.append(Cell(slide, notes, pymupdf.Rect(slide.x1 - label_w, base - CAP, slide.x1, base)))
    column = pymupdf.Rect(MARGIN + sw + BESIDE_GAP, MARGIN, pw - MARGIN, ph - MARGIN) if shared else None
    return PageLayout(pw, ph, cells, column, sw / MM, warnings)


def check_layout(layout: PageLayout, opts: LayoutOptions) -> list[str]:
    problems = []
    page = pymupdf.Rect(0, 0, layout.width, layout.height)
    content = page + (MARGIN - TOL, MARGIN - TOL, TOL - MARGIN, TOL - MARGIN)
    items = []
    for i, cell in enumerate(layout.cells, 1):
        items += [(f"slide {i}", cell.slide)] + [(f"notes {i}", n) for n in cell.notes] + [(f"label {i}", cell.label)]
    if layout.column is not None:
        items.append(("notes column", layout.column))
    for name, rect in items:
        if not (page if name.startswith("label") else content).contains(rect):
            problems.append(f"{name} runs off the page or into the margin")
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            inter = pymupdf.Rect(items[a][1]) & items[b][1]
            if not inter.is_empty and inter.get_area() > TOL:
                problems.append(f"{items[a][0]} and {items[b][0]} overlap")
    rows = {}
    for cell in layout.cells:
        rows.setdefault(round(cell.slide.y0, 1), []).append(cell)
    tops = sorted(rows)
    for upper, lower in zip(tops, tops[1:]):
        bottom = max(max([c.slide.y1] + [n.y1 for n in c.notes]) for c in rows[upper])
        if min(c.slide.y0 for c in rows[lower]) - bottom < GAP - TOL:
            problems.append(f"rows are closer than {GAP / MM:g} mm")
        if min(c.label.y0 for c in rows[lower]) - bottom < LABEL_CLEAR - TOL:
            problems.append("a label sits too close to the cell above it")
    for i, cell in enumerate(layout.cells, 1):
        if opts.notes in ("beside", "both") and layout.column is None and cell.notes[0].width < BESIDE_MIN - TOL:
            problems.append(f"notes beside slide {i} are under 40 mm wide")
        if opts.notes in ("under", "both") and cell.notes[-1].height < under_min(opts) - TOL:
            problems.append(f"notes under slide {i} are too short")
    if layout.column is not None and layout.column.width < BESIDE_MIN - TOL:
        problems.append("the notes column is under 40 mm wide")
    keys = [(round(c.slide.y0, 1), c.slide.x0) for c in layout.cells]
    if keys != sorted(keys):
        problems.append("cells are not in reading order")
    return problems


def describe(opts: LayoutOptions) -> str:
    style = {"lines": "lines", "dotted": "dotted lines", "dots": "dots", "blank": "blank space", "box": "a typeable box"}[opts.style]
    where = {"beside": "beside each slide", "under": "under each slide", "both": "beside and under each slide"}[opts.notes]
    spacing = f" ({opts.spacing_mm:g} mm apart)" if opts.style in ("lines", "dotted", "dots") else ""
    size = f"{opts.size} slides" if isinstance(opts.size, str) else f"slides {opts.size:g} mm wide"
    per = "1 slide per page" if opts.per_page == 1 else f"{opts.per_page} slides per page"
    return f"{'A4' if opts.paper == 'a4' else 'Letter'} {opts.orientation}, {per}, {style} {where}{spacing}, {size}"
