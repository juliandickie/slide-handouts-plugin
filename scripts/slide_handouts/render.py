"""Draw the handout: slides as vectors, labels, notes marks or typeable boxes, then check the saved file."""
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .detect import Detection
from .geometry import MARGIN, MM, LayoutOptions, check_layout, plan_page

BORDER = (0.70, 0.70, 0.70)
LINE = (0.73, 0.73, 0.73)
LABEL = (0.43, 0.43, 0.43)          # #6E6E6E, 4.5 to 1 on white
LABEL_COLOUR_INT = 0x6E6E6E
FIELD_TEXT = (0.13, 0.13, 0.13)
LOW_PPI = 150
LABEL_RE = re.compile(r"^Slide (-?\d+)$")


@dataclass
class BuildResult:
    pages: int
    slide_width_mm: float
    warnings: list
    low_res: list


def _label(page: pymupdf.Page, slide: pymupdf.Rect, number: int) -> None:
    text = f"Slide {number}"
    width = pymupdf.get_text_length(text, fontname="helv", fontsize=7.5)
    page.insert_text((slide.x1 - width, slide.y0 - 3.5), text, fontsize=7.5, fontname="helv", color=LABEL)


def _box(page: pymupdf.Page, rect: pymupdf.Rect, number: int, digits: int) -> None:
    page.draw_rect(rect, color=BORDER, width=0.6, radius=0.03)
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = f"notes_slide_{number:0{digits}d}"
    widget.field_label = f"Notes for slide {number}"
    widget.field_flags = pymupdf.PDF_TX_FIELD_IS_MULTILINE
    widget.rect = rect + (5, 5, -5, -5)
    widget.text_font, widget.text_fontsize, widget.text_color = "Helv", 9, FIELD_TEXT
    widget.border_width, widget.border_color, widget.fill_color = 0, None, None
    widget.field_value = ""
    page.add_widget(widget)


def _marks(page: pymupdf.Page, areas: list, style: str, spacing: float) -> None:
    """All of a page's lines or dots in one shape, so big decks stay quick and small."""
    if style not in ("lines", "dots") or not areas:
        return
    shape = page.new_shape()
    for a in areas:
        if style == "lines":
            y = a.y0 + spacing
            while y <= a.y1 + 0.01:
                shape.draw_line((a.x0, y), (a.x1, y))
                y += spacing
        else:
            y = a.y0 + spacing / 2
            while y <= a.y1:
                x = a.x0 + spacing / 2
                while x <= a.x1:
                    shape.draw_circle((x, y), 0.3)
                    x += spacing
                y += spacing
    if style == "lines":
        shape.finish(color=LINE, width=0.5)
    else:
        shape.finish(color=None, fill=LINE, width=0)
    shape.commit()


def _low_res(src: pymupdf.Document, slide, placed: pymupdf.Rect, cache: dict) -> bool:
    if slide.page not in cache:
        cache[slide.page] = src[slide.page].get_image_info()
    scale = placed.width / slide.clip.width
    for info in cache[slide.page]:
        bbox = pymupdf.Rect(info["bbox"])
        if bbox.width <= 0 or not bbox.intersects(slide.clip):
            continue
        if info["width"] / (bbox.width * scale / 72) < LOW_PPI:
            return True
    return False


def build_handout(src: pymupdf.Document, det: Detection, opts: LayoutOptions, out: Path, title: str) -> BuildResult:
    layout = plan_page(opts, det.aspect)
    problems = check_layout(layout, opts)
    if problems:
        raise RuntimeError("The layout failed its self-check, so nothing was written: " + "; ".join(problems))
    labels = [s.number for s in det.slides]
    digits = len(str(max(labels)))
    spacing = opts.spacing_mm * MM
    box = opts.style == "box"
    doc, cache, low_res = pymupdf.open(), {}, []
    for start in range(0, len(det.slides), opts.per_page):
        page = doc.new_page(width=layout.width, height=layout.height)
        areas = [layout.column] if layout.column is not None else []
        for cell, slide in zip(layout.cells, det.slides[start:start + opts.per_page]):
            page.show_pdf_page(cell.slide, src, slide.page, clip=slide.clip)
            page.draw_rect(cell.slide, color=BORDER, width=0.5)
            _label(page, cell.slide, slide.number)
            if box:
                _box(page, cell.notes[0], slide.number, digits)
            else:
                areas += cell.notes
            if _low_res(src, slide, cell.slide, cache):
                low_res.append(slide.number)
        _marks(page, areas, opts.style, spacing)
        number = str(page.number + 1)
        width = pymupdf.get_text_length(number, fontname="helv", fontsize=8)
        page.insert_text((layout.width - MARGIN - width, layout.height - MARGIN / 2 + 3), number,
                         fontsize=8, fontname="helv", color=LABEL)
    if box:
        doc.need_appearances(True)
    doc.set_metadata({"title": title, "author": (src.metadata or {}).get("author") or ""})
    doc.save(str(out), garbage=3, deflate=True)
    pages = doc.page_count
    doc.close()
    problems = verify_output(Path(out), labels, opts.per_page, box)
    if problems:
        raise RuntimeError(f"The finished handout {Path(out).name} failed its check: " + "; ".join(problems))
    return BuildResult(pages, layout.slide_width_mm, layout.warnings, low_res)


def verify_output(path: Path, labels: list, per_page: int, box: bool) -> list:
    problems = []
    doc = pymupdf.open(str(path))
    want = -(-len(labels) // per_page)
    if doc.page_count != want:
        problems.append(f"it has {doc.page_count} pages instead of {want}")
    found = []
    for page in doc:
        hits = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    match = LABEL_RE.match(span["text"].strip())
                    if match and abs(span["size"] - 7.5) < 0.1 and span["color"] == LABEL_COLOUR_INT:
                        hits.append((round(span["bbox"][3]), span["bbox"][0], int(match.group(1))))
        found += [n for _, _, n in sorted(hits)]
    if found != labels:
        missing = [n for n in labels if n not in found]
        extra = [n for n in found if n not in labels]
        problems.append(f"the slide labels do not match (missing {missing}, unexpected {extra}, or out of order)")
    if box:
        widgets = [w for page in doc for w in page.widgets()]
        names = [w.field_name for w in widgets]
        if len(widgets) != len(labels):
            problems.append(f"it has {len(widgets)} typeable boxes for {len(labels)} slides")
        if len(set(names)) != len(names):
            problems.append("two typeable boxes share a name")
        if not all(w.field_flags & pymupdf.PDF_TX_FIELD_IS_MULTILINE for w in widgets):
            problems.append("a typeable box is not multiline")
    doc.close()
    return problems
