import json
from pathlib import Path

import pytest

from make_fixtures import handout_pdf, scanned_handout_pdf
from slide_handouts.detect import RefusedError, detect, open_pdf

REAL = Path(__file__).parent / "fixtures" / "real"
EXPECTED = json.loads((REAL / "expected.json").read_text())


def labels_and_text(doc, d):
    return [(s.number, doc[s.page].get_textbox(s.clip).split()[0]) for s in d.slides]


def test_reference_geometry_with_printed_numbers(tmp_path):
    doc = open_pdf(handout_pdf(tmp_path / "h.pdf", n=7))
    d = detect(doc)
    assert (d.kind, d.per_page, d.numbers_from) == ("handout", 3, "printed")
    assert labels_and_text(doc, d) == [(i, f"S{i}") for i in range(1, 8)]


def test_numbers_may_start_anywhere_and_skip(tmp_path):
    d = detect(open_pdf(handout_pdf(tmp_path / "h.pdf", n=6, start=0, skip=(4,))))
    assert [s.number for s in d.slides] == [0, 1, 2, 3, 5, 6]
    assert d.skipped == [4] and any("4" in n for n in d.notes)


@pytest.mark.parametrize("broken, message", [("repeat", "repeat or go down"), ("down", "repeat or go down"),
                                             ("counts", "frame counts"), ("overlap", "overlap")])
def test_broken_handouts_are_refused(tmp_path, broken, message):
    with pytest.raises(RefusedError, match=message):
        detect(open_pdf(handout_pdf(tmp_path / "h.pdf", n=7, broken=broken)))


def test_frames_a_little_off_size_or_doubled_are_tolerated(tmp_path):
    doc = open_pdf(handout_pdf(tmp_path / "h.pdf", n=9, jitter=True))
    d = detect(doc)
    assert (d.per_page, [s.number for s in d.slides]) == (3, list(range(1, 10)))
    assert d.slides[3].clip.y0 == pytest.approx(128 + 1)  # the frame wins over the shape 2 pt below it


def test_panel_inside_each_slide_is_not_a_frame(tmp_path):
    d = detect(open_pdf(handout_pdf(tmp_path / "h.pdf", n=7, panel=True)))
    assert (d.per_page, len(d.slides)) == (3, 7)


def test_unnumbered_handout_reads_rows_or_columns(tmp_path):
    doc = open_pdf(handout_pdf(tmp_path / "h.pdf", n=7, per_page=6, numbers=False, order="columns"))
    d = detect(doc, order="columns")
    assert d.numbers_from == "reading order"
    assert [t for _, t in labels_and_text(doc, d)] == [f"S{i}" for i in range(1, 8)]
    assert [t for _, t in labels_and_text(doc, detect(doc))] != [f"S{i}" for i in range(1, 8)]


def test_refuses_scanned_handout(tmp_path):
    with pytest.raises(RefusedError, match="export"):
        detect(open_pdf(scanned_handout_pdf(tmp_path / "s.pdf")))


@pytest.mark.parametrize("size", [(1240, 1754), (598, 845)])
def test_refuses_a_scan_whose_page_is_not_a_paper_size(tmp_path, size):
    # Final review I1: A4 at 150 dpi pixel size, and a page just outside the A4 tolerance, were read as decks.
    with pytest.raises(RefusedError, match="--one-per-page"):
        detect(open_pdf(scanned_handout_pdf(tmp_path / "s.pdf", size=size)))


@pytest.mark.parametrize("name", [n for n, e in EXPECTED.items() if e.get("kind") != "deck"])
def test_real_handout_exports(name):
    want = EXPECTED[name]
    if want.get("refused"):
        with pytest.raises(RefusedError):
            detect(open_pdf(REAL / name))
        return
    d = detect(open_pdf(REAL / name), order=want.get("order", "rows"))
    assert (d.per_page, len(d.slides), d.numbers_from) == (want["per_page"], want["count"], want["numbers_from"])
    assert [s.number for s in d.slides] == want["numbers"]
