from pathlib import Path

import pytest

from make_fixtures import pptx_stub
from slide_handouts.deck import apply_deck, deck_labels, read_hidden
from slide_handouts.detect import RefusedError, detect, open_pdf

REAL = Path(__file__).parent / "fixtures" / "real"
HIDDEN = [i in (5, 9) for i in range(1, 14)]


def test_reads_hidden_flags_in_slide_list_order(tmp_path):
    p = pptx_stub(tmp_path / "d.pptx", hidden=[False, True, False], order=[3, 1, 2])
    assert read_hidden(p) == [False, False, True]   # slide3.xml, slide1.xml, slide2.xml


def test_visible_count_uses_deck_numbers():
    labels, src, skipped, notes = deck_labels(11, HIDDEN, "talk.pptx")
    assert labels == [1, 2, 3, 4, 6, 7, 8, 10, 11, 12, 13] and src == "deck file" and skipped == [5, 9]


def test_total_count_numbers_every_page():
    labels, _, skipped, notes = deck_labels(13, HIDDEN, "talk.pptx")
    assert labels == list(range(1, 14)) and skipped == [] and any("hidden" in n for n in notes)


def test_any_other_count_stops():
    with pytest.raises(RefusedError, match="cannot be trusted"):
        deck_labels(12, HIDDEN, "talk.pptx")


def test_unreadable_deck_falls_back_with_a_note(tmp_path):
    bad = tmp_path / "x.pptx"
    bad.write_bytes(b"not a zip")
    assert read_hidden(bad) is None
    labels, src, _, notes = deck_labels(5, None, "x.pptx")
    assert labels == [1, 2, 3, 4, 5] and src == "page order" and any("x.pptx" in n for n in notes)


def test_real_keynote_exports_map_to_the_example_deck():
    for pdf, want in (("keynote-slides.pdf", [1, 2, 3, 4, 6, 7, 8, 10, 11, 12, 13]),
                      ("keynote-slides-with-skipped.pdf", list(range(1, 14)))):
        if not (REAL / pdf).exists():
            pytest.skip(f"{pdf} not available, see tests/fixtures/real/README.md")
        d = apply_deck(detect(open_pdf(REAL / pdf)), REAL / "example-deck.pptx")
        assert [s.number for s in d.slides] == want
