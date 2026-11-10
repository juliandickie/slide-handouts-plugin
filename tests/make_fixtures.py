"""Test fixtures: a made-up deck and synthetic PDFs. Never real decks.

Run as a script to make the made-up deck:
uv run --no-project --python 3.13 --with python-pptx --with "pymupdf>=2.1,<3" python -I tests/make_fixtures.py deck <out.pptx>
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
    """Made-up slide content: a colour band, a large "S{i}" (the only text), a circle and a square."""
    w, h = page.rect.width, page.rect.height
    page.draw_rect(pymupdf.Rect(0, 0, w, h * 0.12), color=None, fill=[c / 255 for c in COLOURS[2]])
    page.insert_text((w * 0.06, h * 0.55), f"S{i}", fontsize=h * 0.25)
    side = h * 0.28
    page.draw_circle((w * 0.6, h * 0.65), side / 2, color=None, fill=[c / 255 for c in COLOURS[i % 4]])
    page.draw_rect(pymupdf.Rect(w * 0.72, h * 0.51, w * 0.72 + side, h * 0.51 + side), color=None,
                   fill=[c / 255 for c in COLOURS[(i + 1) % 4]])


def deck_pdf(path: Path, n: int = 7, size: tuple[float, float] = (720, 405), photo_on: int | None = None) -> Path:
    """One slide per page at slide size. photo_on puts a 60 x 34 pixel picture across half of that slide."""
    doc = pymupdf.open()
    for i in range(1, n + 1):
        page = doc.new_page(width=size[0], height=size[1])
        _draw_slide(page, i)
        if i == photo_on:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 34), False)
            pix.set_rect(pix.irect, (200, 60, 60))
            w, h = size
            page.insert_image(pymupdf.Rect(w * 0.06, h * 0.3, w * 0.56, h * 0.3 + w * 0.5 * 34 / 60), pixmap=pix)
    doc.save(str(path))
    return Path(path)


def paper_deck_pdf(path: Path, n: int = 3, paper: str = "a4") -> Path:
    """One slide per page, but the deck was set to a paper size, with no frames."""
    return deck_pdf(path, n, A4 if paper == "a4" else (612, 792))


def _grid(per_page: int):
    """Frame rects on an A4 page. 3 per page copies the reference handout's geometry."""
    if per_page == 3:
        return [pymupdf.Rect(98, y, 98 + 190, y + 107) for y in (128, 367, 606)]
    cols = 1 if per_page <= 2 else 2
    rows = per_page // cols
    w = 400 if cols == 1 else 240
    h = w * 9 / 16
    return [pymupdf.Rect(50 + c * (w + 30), 80 + r * (h + 60), 50 + c * (w + 30) + w, 80 + r * (h + 60) + h)
            for r in range(rows) for c in range(cols)]


def handout_pdf(path: Path, n: int = 7, per_page: int = 3, numbers: bool = True, order: str = "rows",
                panel: bool = False, start: int = 1, skip: tuple = (), broken: str | None = None,
                jitter: bool = False) -> Path:
    """A fake exporter handout: framed slides, printed numbers below each frame."""
    path = Path(path)
    deck = pymupdf.open(deck_pdf(path.with_suffix(".deck.pdf"), n=n))
    printed = [k for k in range(start, start + n + len(skip)) if k not in skip][:n]
    if broken == "repeat":
        printed[3] = printed[2]
    if broken == "down":
        printed = [4, 5, 6, 1, 2, 3, 7][:n]
    slots = _grid(per_page)
    rows = len({round(r.y0) for r in slots})
    if order == "columns":  # fill down each column first
        slots = sorted(slots, key=lambda r: (r.x0, r.y0))
    sizes = [per_page] * (n // per_page) + ([n % per_page] if n % per_page else [])
    if broken == "counts":
        sizes = [per_page, per_page - 1] + [per_page] * 5
    out, i = pymupdf.open(), 0
    for count in sizes:
        if i >= n:
            break
        page = out.new_page(width=A4[0], height=A4[1])
        for k, frame in enumerate(slots[:min(count, n - i)]):
            if broken == "overlap" and k == 1:
                frame = pymupdf.Rect(frame.x0, slots[0].y0 + 40, frame.x1, slots[0].y0 + 40 + frame.height)
            page.show_pdf_page(frame + (1, 1, -1, -1), deck, i)
            if jitter and page.number == 1 and k == 1:  # real exports: a frame drawn 2 pt wider
                frame = frame + (0, 0, 2, 0)
            page.draw_rect(frame, color=(0, 0, 0), width=1)
            if jitter and page.number == 1 and k == 0:  # real slides: a slide-sized shape 2 pt below the frame
                page.draw_rect(frame + (0, 2, 0, 2), color=(0.8, 0.8, 0.8), width=0.5)
            if panel:
                page.draw_rect(frame + (frame.width * 0.1, frame.height * 0.1, -frame.width * 0.1, -frame.height * 0.1),
                               color=(0.5, 0.5, 0.5), width=0.5)
            if numbers:
                page.insert_text((frame.x0, frame.y1 + 12), str(printed[i]), fontsize=9)
            i += 1
    assert rows >= 1
    out.save(str(path))
    return path


def scanned_handout_pdf(path: Path, size: tuple[float, float] = A4) -> Path:
    """A handout page that is one picture, as a scan would be. Some scanner apps write the page at its pixel size."""
    source = pymupdf.open(handout_pdf(Path(path).with_suffix(".source.pdf"), n=3))
    pix = source[0].get_pixmap(dpi=100)
    out = pymupdf.open()
    out.new_page(width=size[0], height=size[1]).insert_image(pymupdf.Rect(0, 0, *size), pixmap=pix)
    out.save(str(path))
    return Path(path)


def pptx_stub(path: Path, hidden: list, order: list | None = None) -> Path:
    """A .pptx holding only the parts the hidden-slide reader opens. hidden[k-1] is slide k's flag."""
    import zipfile
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    order = order or list(range(1, len(hidden) + 1))
    ids = "".join(f'<p:sldId id="{255 + k}" r:id="rId{k}"/>' for k in order)
    rels = "".join(f'<Relationship Id="rId{k}" Type="{r}/slide" Target="slides/slide{k}.xml"/>' for k in order)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("ppt/presentation.xml", f'<p:presentation xmlns:p="{p}" xmlns:r="{r}"><p:sldIdLst>{ids}</p:sldIdLst></p:presentation>')
        z.writestr("ppt/_rels/presentation.xml.rels",
                   f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        for k, flag in enumerate(hidden, 1):
            show = ' show="0"' if flag else ""
            z.writestr(f"ppt/slides/slide{k}.xml", f'<p:sld xmlns:p="{p}"{show}/>')
    return Path(path)


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
