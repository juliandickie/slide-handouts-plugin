import json
import string
import sys
from pathlib import Path

import pymupdf
import pytest

from make_fixtures import deck_pdf, handout_pdf, paper_deck_pdf, pptx_stub
from slide_handouts import layouts
from slide_handouts.cli import main, output_path, safe_name
from slide_handouts.detect import detect, open_pdf
from slide_handouts.layouts import resolve
from slide_handouts.preview import render_pages

ALLOWED = set(string.ascii_letters + string.digits + " -_().,")
FULL = ["--paper", "a4", "--orientation", "portrait", "--per-page", "3", "--notes", "beside",
        "--style", "lines", "--size", "larger"]


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    return code, json.loads(capsys.readouterr().out)


def test_output_name_drive_safe(tmp_path):
    assert safe_name("Q&A: Week #2") == "Q and A Week 2"
    assert safe_name("Mum's usual / big") == "Mums usual - big"
    p = output_path(tmp_path / "Q&A: Week #2.pdf", resolve(FULL, None, tmp_path / "l.json"), None, None)
    assert set(p.name) <= ALLOWED and p.name == "Q and A Week 2_3-per-page_portrait_lines-beside_larger.pdf"


def test_output_never_overwrites(tmp_path):
    o = resolve(FULL, None, tmp_path / "l.json")
    first = output_path(tmp_path / "talk.pdf", o, "mine", None)
    first.write_bytes(b"x")
    second = output_path(tmp_path / "talk.pdf", o, "mine", None)
    assert (first.name, second.name) == ("talk_mine.pdf", "talk_mine_v2.pdf")


def test_out_folder_gets_default_name(tmp_path):
    (tmp_path / "elsewhere").mkdir()
    p = output_path(tmp_path / "talk.pdf", resolve(FULL, None, tmp_path / "l.json"), "mine", tmp_path / "elsewhere")
    assert p == tmp_path / "elsewhere" / "talk_mine.pdf"


@pytest.mark.skipif(sys.platform == "win32", reason="chmod does not lock a folder on Windows")
def test_unwritable_folder_reports(tmp_path, capsys):
    src = handout_pdf(tmp_path / "h.pdf")
    tmp_path.chmod(0o500)
    try:
        code, out = run(capsys, "build", src, *FULL)
    finally:
        tmp_path.chmod(0o700)
    assert code == 1 and str(tmp_path) in out["error"] and "--out" in out["error"]


def test_build_end_to_end(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(layouts, "STORE", tmp_path / "l.json")
    code, out = run(capsys, "build", handout_pdf(tmp_path / "h.pdf"), *FULL)
    assert code == 0 and out["ok"] and out["pages"] == 3 and Path(out["file"]).parent == tmp_path


def test_deck_flag_names_and_places_the_output(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(layouts, "STORE", tmp_path / "l.json")
    (tmp_path / "tmp").mkdir()
    (tmp_path / "talks").mkdir()
    pdf = deck_pdf(tmp_path / "tmp" / "talk.pdf", n=2)
    deck = pptx_stub(tmp_path / "talks" / "talk.pptx", hidden=[False, True, False])
    code, out = run(capsys, "build", pdf, *FULL, "--deck", deck)
    assert code == 0 and Path(out["file"]).parent == tmp_path / "talks"
    assert "Slide 3" in pymupdf.open(out["file"])[0].get_text()


def test_refusal_is_json_with_exit_1(tmp_path, capsys):
    code, out = run(capsys, "detect", paper_deck_pdf(tmp_path / "p.pdf"))
    assert code == 1 and out["ok"] is False and "--one-per-page" in out["error"]


def test_bad_option_is_json_too(tmp_path, capsys):
    code, out = run(capsys, "build", handout_pdf(tmp_path / "h.pdf"), *FULL, "--spacing", "40")
    assert code == 1 and "4 to 12" in out["error"]


def test_detect_reports_the_shape(tmp_path, capsys):
    code, out = run(capsys, "detect", deck_pdf(tmp_path / "d.pdf", n=7))
    assert (out["kind"], out["slide_count"], out["shape"]) == ("deck", 7, "16:9")


def test_layouts_list_includes_the_gallery(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(layouts, "STORE", tmp_path / "l.json")
    code, out = run(capsys, "layouts", "list")
    assert code == 0 and any(entry["name"] == "example 6" and entry["gallery"] for entry in out["layouts"])


def test_preview_renders_first_and_last_and_marks_order(tmp_path):
    src = handout_pdf(tmp_path / "h.pdf", n=7)
    imgs = render_pages(src, ["1", "last"], tmp_path / "png", mark=detect(open_pdf(src)))
    assert len(imgs) == 2 and all(p.exists() and p.suffix == ".png" for p in imgs)
