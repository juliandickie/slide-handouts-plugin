import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pymupdf
import pytest

from slide_handouts import convert as convert_module
from slide_handouts.convert import convert, find_converters, sweep_old_temp
from slide_handouts.detect import RefusedError

REAL = Path(__file__).parent / "fixtures" / "real"


def test_sweep_removes_only_old_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    old, new, other = (tmp_path / n for n in ("slide-handouts-old", "slide-handouts-new", "keep-me"))
    for d in (old, new, other):
        d.mkdir()
    os.utime(old, (time.time() - 2 * 86400,) * 2)
    os.utime(other, (time.time() - 2 * 86400,) * 2)
    sweep_old_temp()
    assert not old.exists() and new.exists() and other.exists()


def test_no_converter_says_how_to_export(monkeypatch, tmp_path):
    monkeypatch.setattr(convert_module, "find_converters", lambda: [])
    deck = tmp_path / "talk.pptx"
    deck.write_bytes(b"x")
    with pytest.raises(RefusedError, match="export a PDF"):
        convert(deck)


@pytest.mark.skipif(sys.platform != "darwin", reason="Apple Events are macOS only")
def test_permission_refusal_names_the_setting(monkeypatch, tmp_path):
    monkeypatch.setattr(convert_module, "find_converters", lambda: ["PowerPoint"])
    refusal = subprocess.CompletedProcess([], 1, "", "execution error: Not authorized to send Apple events to Microsoft PowerPoint. (-1743)")
    monkeypatch.setattr(convert_module.subprocess, "run", lambda *a, **k: refusal)
    deck = tmp_path / "talk.pptx"
    deck.write_bytes(b"x")
    with pytest.raises(RefusedError, match="Privacy and Security, Automation"):
        convert(deck)


def test_windows_script_goes_in_the_private_work_folder(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(convert_module.sys, "platform", "win32")
    monkeypatch.setattr(convert_module.subprocess, "run", lambda cmd, **k: commands.append(cmd))
    work, decks = tmp_path / "work", tmp_path / "decks"
    work.mkdir()
    decks.mkdir()
    convert_module._run("PowerPoint", decks / "talk.pptx", decks / "talk (landing).pdf", work)
    script = Path(commands[0][commands[0].index("-File") + 1])
    assert script.parent == work and not any(p.suffix == ".ps1" for p in decks.iterdir())


def _fake_app(writes: bytes | None, timeout: bool = False):
    def run(app, src, landing, work):
        if writes is not None:
            landing.write_bytes(writes)
        if timeout:
            raise subprocess.TimeoutExpired("osascript", 300)
        return subprocess.CompletedProcess([], 0, "", "")
    return run


def test_saved_beside_the_deck_then_moved_away(tmp_path, monkeypatch):
    monkeypatch.setattr(convert_module, "find_converters", lambda: ["PowerPoint"])
    monkeypatch.setattr(convert_module, "_run", _fake_app(b"%PDF-1.4 converted"))
    deck = tmp_path / "talk.pptx"
    deck.write_bytes(b"x")
    (tmp_path / "talk.pdf").write_bytes(b"keep me")
    pdf, app = convert(deck)
    assert pdf.read_bytes() == b"%PDF-1.4 converted" and pdf.parent != tmp_path and pdf.name == "talk.pdf"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["talk.pdf", "talk.pptx"]
    assert (tmp_path / "talk.pdf").read_bytes() == b"keep me"


def test_a_timeout_leaves_nothing_beside_the_deck(tmp_path, monkeypatch):
    monkeypatch.setattr(convert_module, "find_converters", lambda: ["Keynote"])
    monkeypatch.setattr(convert_module, "_run", _fake_app(b"partial", timeout=True))
    deck = tmp_path / "talk.pptx"
    deck.write_bytes(b"x")
    with pytest.raises(RefusedError, match="Grant File Access"):
        convert(deck)
    assert [p.name for p in tmp_path.iterdir()] == ["talk.pptx"]


@pytest.mark.skipif(os.environ.get("SLIDE_HANDOUTS_LIVE") != "1",
                    reason="drives PowerPoint or Keynote; a new folder needs a person to grant file access")
@pytest.mark.parametrize("app", find_converters() or [pytest.param(None, marks=pytest.mark.skip(reason="no converter here"))])
def test_converts_without_touching_a_pdf_beside_the_deck(app, monkeypatch):
    # Run with SLIDE_HANDOUTS_LIVE=1 while someone can click Select in the app's Grant File Access window.
    # A folder in the repo, not pytest's tmp_path: sandboxed PowerPoint and Keynote cannot reach the system temp folder.
    folder = Path(__file__).parent / "out" / f"convert-{app}"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    monkeypatch.setattr(convert_module, "find_converters", lambda: [app])
    deck = folder / "example-deck.pptx"
    shutil.copy(REAL / "example-deck.pptx", deck)
    (folder / "example-deck.pdf").write_bytes(b"keep me")
    pdf, used = convert(deck)
    assert used == app and pdf.parent != folder and pdf.name == "example-deck.pdf"
    assert (folder / "example-deck.pdf").read_bytes() == b"keep me"
    assert sorted(p.name for p in folder.iterdir()) == ["example-deck.pdf", "example-deck.pptx"]
    assert pymupdf.open(pdf).page_count in (11, 13)
