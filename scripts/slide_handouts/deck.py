"""Hidden slides, read from a .pptx with the standard library, so labels keep the presenter's slide numbers."""
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from .detect import Detection, RefusedError

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_PART = 20_000_000  # bytes: a slide list or slide part bigger than this is not a real deck part


def _read(z: zipfile.ZipFile, name: str) -> bytes:
    if z.getinfo(name).file_size > MAX_PART:
        raise ValueError(f"{name} is too large")
    return z.read(name)


def read_hidden(pptx: Path) -> list | None:
    """Hidden flags in slide-list order, or None when the file cannot be read this way."""
    try:
        with zipfile.ZipFile(pptx) as z:
            pres = ET.fromstring(_read(z, "ppt/presentation.xml"))
            rels = ET.fromstring(_read(z, "ppt/_rels/presentation.xml.rels"))
            targets = {rel.get("Id"): rel.get("Target") for rel in rels.iter(f"{REL}Relationship")}
            slide_list = pres.find(f"{P}sldIdLst")
            if slide_list is None:
                return None
            hidden = []
            for sid in slide_list.findall(f"{P}sldId"):
                target = targets[sid.get(f"{R}id")]
                part = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("ppt", target))
                hidden.append(ET.fromstring(_read(z, part)).get("show") == "0")
            return hidden
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError, ValueError, TypeError):
        return None


def deck_labels(page_count: int, hidden: list | None, deck_name: str) -> tuple[list, str, list, list]:
    """Labels for a deck PDF exported from this deck: labels, numbers_from, skipped, notes."""
    if hidden is None:
        return (list(range(1, page_count + 1)), "page order", [],
                [f"Could not read hidden slides from {deck_name}, so slides are numbered in page order. "
                 "Hidden slides, if the deck had any, are not counted."])
    visible = [i for i, h in enumerate(hidden, 1) if not h]
    hidden_numbers = [i for i, h in enumerate(hidden, 1) if h]
    if page_count == len(visible):
        notes = [f"Slides {', '.join(map(str, hidden_numbers))} are hidden in the deck and left out."] if hidden_numbers else []
        return visible, "deck file", hidden_numbers, notes
    if page_count == len(hidden):
        notes = ["The export included the deck's hidden slides."] if hidden_numbers else []
        return list(range(1, page_count + 1)), "deck file", [], notes
    raise RefusedError(f"The PDF has {page_count} pages, but {deck_name} has {len(hidden)} slides with "
                       f"{len(hidden_numbers)} hidden. The labels cannot be trusted, so nothing was built.")


def apply_deck(det: Detection, deck: Path) -> Detection:
    """Relabel a deck PDF with the original file's slide numbers. A handout keeps its printed numbers."""
    if det.kind != "deck":
        return det
    deck = Path(deck)
    hidden = read_hidden(deck) if deck.suffix.lower() == ".pptx" else None
    labels, source, skipped, notes = deck_labels(len(det.slides), hidden, deck.name)
    slides = [replace(s, number=n) for s, n in zip(det.slides, labels)]
    return replace(det, slides=slides, numbers_from=source, skipped=skipped, notes=det.notes + notes)
