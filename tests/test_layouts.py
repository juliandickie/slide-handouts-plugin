import json
from collections import defaultdict

import pytest

from slide_handouts.layouts import (GALLERY, LayoutError, delete_layout, list_layouts, load_store, resolve,
                                    save_layout)

FULL = ["--paper", "a4", "--orientation", "portrait", "--per-page", "3", "--notes", "beside",
        "--style", "lines", "--size", "larger"]


def test_typed_values_override_saved_ones(tmp_path):
    store = tmp_path / "layouts.json"
    save_layout("wide", FULL + ["--spacing", "6"], usual=False, store=store)
    o = resolve(["--spacing", "7"], "wide", store)
    assert o.spacing_mm == 7 and o.per_page == 3


def test_hand_edited_bad_value_is_refused_by_name(tmp_path):
    store = tmp_path / "layouts.json"
    store.write_text(json.dumps({"usual": None, "layouts": {"mine": FULL + ["--spacing", "0"]}}))
    with pytest.raises(LayoutError, match=r"mine.*4 to 12"):
        resolve([], "mine", store)


def test_damaged_file_is_reported_and_never_overwritten(tmp_path):
    store = tmp_path / "layouts.json"
    store.write_text("{not json")
    with pytest.raises(LayoutError, match="layouts.json"):
        save_layout("x", FULL, usual=False, store=store)
    assert store.read_text() == "{not json"


def test_missing_file_reads_as_empty(tmp_path):
    assert load_store(tmp_path / "none.json") == {"usual": None, "layouts": {}}


def test_usual_is_marked_and_listed(tmp_path):
    store = tmp_path / "layouts.json"
    save_layout("mine", FULL, usual=True, store=store)
    listed = list_layouts(store)
    assert listed["usual"] == "mine"
    assert any(entry["name"] == "mine" and not entry["gallery"] for entry in listed["layouts"])


def test_gallery_names_cannot_be_saved_over_or_deleted(tmp_path):
    with pytest.raises(LayoutError):
        save_layout("example 6", FULL, usual=False, store=tmp_path / "l.json")
    with pytest.raises(LayoutError):
        delete_layout("example 6", store=tmp_path / "l.json")


def test_gallery_example_loads_like_a_saved_layout(tmp_path):
    o = resolve([], "example 6", tmp_path / "l.json")
    assert (o.orientation, o.style, o.spacing_mm, o.size) == ("landscape", "dots", 5, "smaller")


def test_gallery_covers_every_option_value(tmp_path):
    seen = defaultdict(set)
    for name in json.loads(GALLERY.read_text())["layouts"]:
        o = resolve([], name, tmp_path / "l.json")
        for field in ("paper", "orientation", "per_page", "notes", "style"):
            seen[field].add(getattr(o, field))
        seen["size"].add(o.size if isinstance(o.size, str) else "mm")
        seen["spacing"].add(o.spacing_mm)
    assert seen["per_page"] == {1, 2, 3, 4, 6} and seen["notes"] == {"beside", "under", "both"}
    assert seen["style"] == {"lines", "dots", "blank", "box"} and {5, 6, 7, 8} <= seen["spacing"]
    assert seen["size"] == {"smaller", "medium", "larger", "mm"} and len(seen["paper"]) == 2


def test_missing_options_are_listed(tmp_path):
    with pytest.raises(LayoutError, match="orientation.*per-page.*notes.*style.*size"):
        resolve(["--paper", "a4"], None, tmp_path / "l.json")


def test_spacing_fallbacks_follow_the_style(tmp_path):
    dots = [a if a != "lines" else "dots" for a in FULL]
    assert resolve(dots, None, tmp_path / "l.json").spacing_mm == 5
    assert resolve(FULL, None, tmp_path / "l.json").spacing_mm == 8
