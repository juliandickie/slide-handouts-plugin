import itertools

import pymupdf
import pytest

from slide_handouts.geometry import LayoutOptions, check_layout, describe, plan_page

R = 105 / 188  # aspect of the reference handout's clip: frame 190 x 107 pt, less 1 pt each side


def opts(**kw):
    base = dict(paper="a4", orientation="portrait", per_page=3, notes="beside",
                style="lines", spacing_mm=8, size="larger")
    return LayoutOptions(**{**base, **kw})


def test_larger_beside_portrait_matches_delivered_stack():
    assert abs(plan_page(opts(), R).slide_width_mm - 145) <= 0.5


def test_larger_beside_landscape_matches_delivered_landscape():
    assert abs(plan_page(opts(orientation="landscape"), R).slide_width_mm - 108.6) <= 0.5


def test_larger_under_two_per_page_matches_delivered_two():
    assert abs(plan_page(opts(per_page=2, notes="under"), R).slide_width_mm - 190) <= 0.5


def test_exact_width_used_when_it_fits():
    assert plan_page(opts(notes="both", size=108.0), R).slide_width_mm == pytest.approx(108)


def test_exact_width_too_wide_falls_back_with_warning():
    lay = plan_page(opts(size=170.0), R)
    assert abs(lay.slide_width_mm - 145) <= 0.5 and any("170" in w for w in lay.warnings)


def test_presets_scale_from_larger():
    big = plan_page(opts(), R).slide_width_mm
    assert plan_page(opts(size="medium"), R).slide_width_mm == pytest.approx(0.85 * big)
    assert plan_page(opts(size="smaller"), R).slide_width_mm == pytest.approx(0.70 * big)


def test_small_slides_warn_but_still_plan():
    lay = plan_page(opts(per_page=6, size="smaller"), 9 / 16)
    assert lay.slide_width_mm < 70 and any("hard to read" in w for w in lay.warnings)


def test_box_with_both_is_refused():
    with pytest.raises(ValueError, match="beside or under"):
        plan_page(opts(style="box", notes="both"), R)


def test_single_column_beside_shares_one_notes_column():
    lay = plan_page(opts(), R)
    assert lay.column is not None and all(c.notes == [] for c in lay.cells)


def test_box_beside_is_as_tall_as_its_slide():
    for c in plan_page(opts(style="box"), R).cells:
        assert c.notes[0].height == pytest.approx(c.slide.height)


def test_cells_fill_rows_first():
    cells = plan_page(opts(per_page=4, notes="under", orientation="landscape"), 9 / 16).cells
    keys = [(round(c.slide.y0), c.slide.x0) for c in cells]
    assert keys == sorted(keys)


def test_check_layout_catches_an_overlap():
    lay = plan_page(opts(per_page=2, notes="under"), R)
    lay.cells[1].slide = pymupdf.Rect(lay.cells[0].slide)
    assert any("overlap" in p for p in check_layout(lay, opts(per_page=2, notes="under")))


def test_every_combination_passes_its_checks():
    failures = []
    for paper, orient, per, notes, style, size, aspect in itertools.product(
            ("a4", "letter"), ("portrait", "landscape"), (1, 2, 3, 4, 6), ("beside", "under", "both"),
            ("lines", "dots", "blank", "box"), ("smaller", "medium", "larger"), (9 / 16, 3 / 4)):
        if style == "box" and notes == "both":
            continue
        o = LayoutOptions(paper, orient, per, notes, style, 5 if style == "dots" else 8, size)
        problems = check_layout(plan_page(o, aspect), o)
        if problems:
            failures.append((o, aspect, problems))
    assert failures == []


def test_describe_uses_plain_neutral_words():
    o = opts(orientation="landscape", style="dots", spacing_mm=5, size="smaller")
    assert describe(o) == "A4 landscape, 3 slides per page, dots beside each slide (5 mm apart), smaller slides"
