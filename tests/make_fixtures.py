"""Test fixtures: a made-up deck and synthetic PDFs. Never real decks.

Run as a script to make the made-up deck:
uv run --no-project --with python-pptx --with "pymupdf>=2.1,<3" python -I tests/make_fixtures.py deck <out.pptx>
"""
import sys
import tempfile
from pathlib import Path

import pymupdf

COLOURS = [(0x1E, 0xB5, 0xBD), (0xEF, 0xC3, 0x19), (0x05, 0x26, 0x48), (0xC8, 0x3C, 0x3C)]


def make_deck_pptx(path: Path, n: int = 13, hidden: tuple[int, ...] = (5, 9), aspect: str = "16:9") -> Path:
    """Made-up deck: slide i shows "Example i", a circle and a square. Slide 3 holds a tiny stretched picture."""
    from pptx import Presentation  # only the deck needs python-pptx
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.util import Emu, Pt

    prs = Presentation()
    prs.slide_width = Emu(12192000 if aspect == "16:9" else 9144000)
    prs.slide_height = Emu(6858000)
    w, h = prs.slide_width, prs.slide_height
    with tempfile.TemporaryDirectory() as tmp:
        picture = Path(tmp) / "low-res.png"
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 34), False)
        pix.set_rect(pymupdf.IRect(0, 0, 30, 34), (200, 60, 60))
        pix.set_rect(pymupdf.IRect(30, 0, 60, 34), (60, 60, 200))
        pix.save(str(picture))
        for i in range(1, n + 1):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            box = slide.shapes.add_textbox(int(w * 0.06), int(h * 0.08), int(w * 0.6), int(h * 0.25))
            run = box.text_frame.paragraphs[0].add_run()
            run.text = f"Example {i}"
            run.font.size = Pt(54)
            run.font.bold = True
            side = int(h * 0.3)
            for kind, left, colour in ((MSO_SHAPE.OVAL, int(w * 0.55), COLOURS[i % 4]),
                                       (MSO_SHAPE.RECTANGLE, int(w * 0.55) + side + int(w * 0.03), COLOURS[(i + 1) % 4])):
                shape = slide.shapes.add_shape(kind, left, int(h * 0.55), side, side)
                shape.fill.solid()
                shape.fill.fore_color.rgb = RGBColor(*colour)
                shape.line.fill.background()
            if i == 3:
                slide.shapes.add_picture(str(picture), int(w * 0.06), int(h * 0.4), width=int(w * 0.45))
            if i in hidden:
                slide._element.set("show", "0")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(path))
    return path


A4 = (595.28, 841.89)


def _draw_slide(page: pymupdf.Page, i: int) -> None:
    """Made-up slide content: a title band, a large "S{i}", a circle and a square."""
    w, h = page.rect.width, page.rect.height
    page.draw_rect(pymupdf.Rect(0, 0, w, h * 0.12), color=None, fill=[c / 255 for c in COLOURS[2]])
    page.insert_text((w * 0.03, h * 0.08), "Example deck", fontsize=h * 0.05, color=(1, 1, 1))
    page.insert_text((w * 0.06, h * 0.55), f"S{i}", fontsize=h * 0.25)
    side = h * 0.28
    page.draw_circle((w * 0.6, h * 0.65), side / 2, color=None, fill=[c / 255 for c in COLOURS[i % 4]])
    page.draw_rect(pymupdf.Rect(w * 0.72, h * 0.51, w * 0.72 + side, h * 0.51 + side), color=None,
                   fill=[c / 255 for c in COLOURS[(i + 1) % 4]])


def deck_pdf(path: Path, n: int = 7, size: tuple[float, float] = (720, 405)) -> Path:
    """One slide per page at slide size."""
    doc = pymupdf.open()
    for i in range(1, n + 1):
        _draw_slide(doc.new_page(width=size[0], height=size[1]), i)
    doc.save(str(path))
    return Path(path)


def paper_deck_pdf(path: Path, n: int = 3, paper: str = "a4") -> Path:
    """One slide per page, but the deck was set to a paper size, with no frames."""
    return deck_pdf(path, n, A4 if paper == "a4" else (612, 792))


def encrypted_pdf(path: Path) -> Path:
    doc = pymupdf.open(deck_pdf(Path(path).with_suffix(".plain.pdf"), n=2))
    doc.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner")
    return Path(path)


def damaged_pdf(path: Path) -> Path:
    data = deck_pdf(Path(path).with_suffix(".whole.pdf"), n=2).read_bytes()
    Path(path).write_bytes(data[:200])
    return Path(path)


def empty_pdf(path: Path) -> Path:
    """A valid PDF whose page tree is empty; PyMuPDF will not save one, so it is written by hand."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [] /Count 0 >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    Path(path).write_bytes(bytes(out))
    return Path(path)


if __name__ == "__main__":
    command, out = sys.argv[1], Path(sys.argv[2])
    if command == "deck":
        print(make_deck_pptx(out))
    else:
        sys.exit(f"unknown fixture: {command}")
