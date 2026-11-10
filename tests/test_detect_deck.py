import json
from pathlib import Path

import pytest

from make_fixtures import damaged_pdf, deck_pdf, empty_pdf, encrypted_pdf, paper_deck_pdf
from slide_handouts.detect import RefusedError, detect, open_pdf, shape_name

REAL = Path(__file__).parent / "fixtures" / "real"
EXPECTED = json.loads((REAL / "expected.json").read_text())


def test_deck_gives_one_slide_per_page(tmp_path):
    d = detect(open_pdf(deck_pdf(tmp_path / "d.pdf", n=7)))
    assert (d.kind, d.per_page, d.numbers_from) == ("deck", 1, "page order")
    assert [s.number for s in d.slides] == list(range(1, 8))
    assert shape_name(d.aspect) == "16:9"


def test_4_3_deck_is_named(tmp_path):
    assert shape_name(detect(open_pdf(deck_pdf(tmp_path / "d.pdf", size=(720, 540)))).aspect) == "4:3"


def test_paper_size_page_without_frames_is_refused(tmp_path):
    with pytest.raises(RefusedError, match="--one-per-page"):
        detect(open_pdf(paper_deck_pdf(tmp_path / "p.pdf")))


def test_one_per_page_flag_skips_the_page_size_test(tmp_path):
    d = detect(open_pdf(paper_deck_pdf(tmp_path / "p.pdf", n=3)), one_per_page=True)
    assert (d.kind, len(d.slides)) == ("deck", 3)


def test_refuses_encrypted_and_damaged(tmp_path):
    with pytest.raises(RefusedError, match="password"):
        open_pdf(encrypted_pdf(tmp_path / "e.pdf"))
    with pytest.raises(RefusedError, match="could not be opened"):
        open_pdf(damaged_pdf(tmp_path / "x.pdf"))


def test_empty_pdf_is_refused(tmp_path):
    with pytest.raises(RefusedError, match="no pages"):
        open_pdf(empty_pdf(tmp_path / "empty.pdf"))


@pytest.mark.parametrize("name", [n for n, e in EXPECTED.items() if e.get("kind") == "deck"])
def test_real_deck_exports(name):
    d = detect(open_pdf(REAL / name))
    assert len(d.slides) == EXPECTED[name]["count"]
    assert [s.number for s in d.slides] == EXPECTED[name]["numbers"]
