import time

import pymupdf
import pytest

from make_fixtures import deck_pdf, handout_pdf
from slide_handouts import render
from slide_handouts.detect import detect, open_pdf
from slide_handouts.geometry import LayoutOptions, plan_page
from slide_handouts.render import build_handout, verify_output

O = dict(paper="a4", orientation="portrait", per_page=3, notes="beside", style="lines", spacing_mm=8, size="larger")


def build(tmp_path, n=7, src=None, **kw):
    src = src or handout_pdf(tmp_path / "h.pdf", n=n)
    doc = open_pdf(src)
    det = detect(doc)
    out = tmp_path / "out.pdf"
    return build_handout(doc, det, LayoutOptions(**{**O, **kw}), out, "Test - Slides and Notes"), out


def test_slides_are_placed_as_vectors(tmp_path):
    res, out = build(tmp_path)
    page = pymupdf.open(out)[0]
    assert res.pages == 3 and abs(res.slide_width_mm - 145) <= 0.5
    assert page.get_images() == [] and "S1" in page.get_text()


def test_typeable_box_fields(tmp_path):
    res, out = build(tmp_path, n=13, style="box")
    doc = pymupdf.open(out)
    names = [w.field_name for p in doc for w in p.widgets()]
    assert names == [f"notes_slide_{i:02d}" for i in range(1, 14)]
    assert all(w.field_flags & pymupdf.PDF_TX_FIELD_IS_MULTILINE for p in doc for w in p.widgets())
    assert doc.xref_get_key(doc.pdf_catalog(), "AcroForm/NeedAppearances") == ("bool", "true")


@pytest.mark.parametrize("style, marks", [("lines", True), ("dots", True), ("blank", False)])
def test_each_notes_style_draws_its_marks(tmp_path, style, marks):
    _, out = build(tmp_path, notes="under", per_page=2, style=style, spacing_mm=5 if style == "dots" else 8)
    page = pymupdf.open(out)[0]
    lay = plan_page(LayoutOptions(**{**O, "notes": "under", "per_page": 2, "style": style,
                                     "spacing_mm": 5 if style == "dots" else 8}), detect(open_pdf(tmp_path / "h.pdf")).aspect)
    area = lay.cells[0].notes[0]
    assert any(pymupdf.Rect(d["rect"]).intersects(area) for d in page.get_drawings()) is marks


def test_partial_last_page(tmp_path):
    res, out = build(tmp_path, n=7, notes="under")
    last = pymupdf.open(out)[-1]
    assert res.pages == 3 and last.get_text().count("Slide ") == 1 and "Slide 7" in last.get_text()
    lay = plan_page(LayoutOptions(**{**O, "notes": "under"}), detect(open_pdf(tmp_path / "h.pdf")).aspect)
    empty = [r for c in lay.cells[1:] for r in [c.slide, *c.notes]]
    assert not any(pymupdf.Rect(d["rect"]).intersects(r) for d in last.get_drawings() for r in empty)
    (tmp_path / "one").mkdir()
    one, _ = build(tmp_path / "one", n=1)
    assert one.pages == 1


def test_layout_self_check_failure_stops_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(render, "check_layout", lambda lay, o: ["slides overlap"])
    with pytest.raises(RuntimeError, match="slides overlap"):
        build(tmp_path)
    assert not (tmp_path / "out.pdf").exists()


def test_verify_output_names_a_missing_label(tmp_path):
    _, out = build(tmp_path)
    assert any("99" in p for p in verify_output(out, list(range(1, 8)) + [99], 3, box=False))


def test_low_resolution_photo_is_flagged(tmp_path):
    src = deck_pdf(tmp_path / "d.pdf", n=4, photo_on=3)
    res, _ = build(tmp_path, src=src, per_page=2, notes="under")
    assert res.low_res == [3]


@pytest.mark.parametrize("px, flagged", [(505, False), (374, True)])
def test_photo_warning_line_is_120_ppi(tmp_path, px, flagged):
    # The photo spans half of a slide placed 190 mm wide: 95 mm, so 505 px prints at 135 ppi and 374 px at 100 ppi.
    doc = pymupdf.open()
    page = doc.new_page(width=720, height=405)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, px, px // 2), False)
    pix.set_rect(pix.irect, (200, 60, 60))
    page.insert_image(pymupdf.Rect(0, 0, 360, 180), pixmap=pix)
    doc.save(str(tmp_path / "p.pdf"))
    res, _ = build(tmp_path, src=tmp_path / "p.pdf", per_page=2, notes="under", size=190.0)
    assert (res.low_res == [1]) is flagged


DOTS = dict(orientation="landscape", style="dots", spacing_mm=5, size="smaller")


def test_dot_grid_adds_little_to_the_file(tmp_path):
    src = deck_pdf(tmp_path / "d.pdf", n=60)
    (tmp_path / "blank").mkdir()
    res, dots = build(tmp_path, src=src, **DOTS)
    _, blank = build(tmp_path / "blank", src=src, **{**DOTS, "style": "blank"})
    assert (dots.stat().st_size - blank.stat().st_size) / res.pages < 5_000


def test_dots_sit_on_the_grid_to_the_end_of_each_row(tmp_path):
    _, out = build(tmp_path, src=deck_pdf(tmp_path / "d.pdf", n=3), **DOTS)
    column = plan_page(LayoutOptions(**{**O, **DOTS}), 405 / 720).column
    step, zoom = 5 * 72 / 25.4, 8
    pix = pymupdf.open(out)[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    ys = [column.y0 + step / 2 + j * step for j in range(int((column.height - step / 2) // step) + 1)]
    xs = [column.x0 + step / 2 + k * step for k in range(int((column.width - step / 2) // step) + 1)]
    for y in (ys[0], ys[-1]):
        for x in xs:
            assert pix.pixel(round(x * zoom), round(y * zoom))[0] < 235, (x, y)  # a dot here
            assert pix.pixel(round((x + step / 2) * zoom), round(y * zoom))[0] > 250, (x, y)  # white between


def test_lines_are_dotted_with_three_dots_between_grid_dots(tmp_path):
    # Julian, 2026-11-10: each ruled line is a row of dots a quarter of the spacing apart, from the left edge to the right.
    opts = dict(notes="under", per_page=2, style="lines", spacing_mm=8)
    _, out = build(tmp_path, src=deck_pdf(tmp_path / "d.pdf", n=2), **opts)
    area = plan_page(LayoutOptions(**{**O, **opts}), 405 / 720).cells[0].notes[0]
    spacing, zoom = 8 * 72 / 25.4, 8
    step = spacing / 4
    pix = pymupdf.open(out)[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    ys = [area.y0 + spacing * j for j in range(1, int(area.height // spacing) + 1)]
    xs = [area.x0 + step * k for k in range(int(area.width // step) + 1)]
    for y in (ys[0], ys[-1]):
        for x in xs[1:]:  # the first dot's left half sits on the area's edge, so check from the second
            assert pix.pixel(round(x * zoom), round(y * zoom))[0] < 235, (x, y)  # a dot here
            assert pix.pixel(round((x - step / 2) * zoom), round(y * zoom))[0] > 250, (x, y)  # white between


def test_labels_keep_their_font_when_the_slides_also_use_helvetica(tmp_path):
    # The made-up slides set "S1" in PyMuPDF's "helv" too. That name must not hide the labels' own font.
    _, out = build(tmp_path, src=deck_pdf(tmp_path / "d.pdf", n=4))
    page = pymupdf.open(out)[0]
    spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
    labels = [s for s in spans if s["text"].startswith("Slide ") or s["text"] == "1"]
    assert len(labels) == 4 and all(s["font"] == "Helvetica" for s in labels)


def test_title_and_author(tmp_path):
    _, out = build(tmp_path)
    assert pymupdf.open(out).metadata["title"] == "Test - Slides and Notes"


def test_600_slide_dot_grid_is_quick_and_small(tmp_path):
    start = time.monotonic()
    _, out = build(tmp_path, src=deck_pdf(tmp_path / "big.pdf", n=600), orientation="landscape",
                   style="dots", spacing_mm=5, size="smaller")
    assert time.monotonic() - start < 60 and out.stat().st_size < 20_000_000
