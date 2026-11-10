"""Render pages as PNG images for Claude to look at, optionally with the slide order marked."""
import tempfile
from pathlib import Path

import pymupdf

from .detect import Detection, RefusedError, open_pdf

MARK = (0.8, 0.1, 0.1)


def render_pages(pdf: Path, pages: list, out_dir: Path | None = None, mark: Detection | None = None, dpi: int = 100) -> list:
    pdf = Path(pdf)
    doc = open_pdf(pdf)
    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="slide-handouts-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    images = []
    for token in pages:
        token = str(token).strip()
        number = doc.page_count if token == "last" else int(token) if token.isdigit() else 0
        if not 1 <= number <= doc.page_count:
            raise RefusedError(f"Page {token} is not in {pdf.name}, which has {doc.page_count} pages.")
        page = doc[number - 1]
        if mark is not None:  # draw on a copy, so the source is never changed
            copy = pymupdf.open()
            copy.insert_pdf(doc, from_page=number - 1, to_page=number - 1)
            page = copy[0]
            for slide in (s for s in mark.slides if s.page == number - 1):
                centre = slide.clip.tl + (slide.clip.br - slide.clip.tl) * 0.5
                page.draw_circle(centre, 20, color=MARK, fill=(1, 1, 1), width=2)
                text = str(slide.number)
                width = pymupdf.get_text_length(text, fontname="helv", fontsize=24)
                page.insert_text((centre.x - width / 2, centre.y + 8.5), text, fontsize=24, fontname="helv", color=MARK)
        path = out_dir / f"{pdf.stem}-page-{number}.png"
        page.get_pixmap(dpi=dpi).save(str(path))
        images.append(path)
    return images
