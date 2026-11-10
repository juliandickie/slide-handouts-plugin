"""Layout options: the command-line flags, saved layouts and the gallery examples.

A saved layout is stored as its list of command-line options, so saved and typed values go through one parser.
"""
import argparse
import json
import os
import tempfile
from pathlib import Path

from .geometry import LayoutOptions, describe

STORE = Path.home() / ".config" / "slide-handouts" / "layouts.json"
GALLERY = Path(__file__).with_name("gallery.json")
REQUIRED = ("paper", "orientation", "per_page", "notes", "style", "size")


class LayoutError(Exception):
    """A message the user sees as it is."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise LayoutError(message)


def _spacing(text):
    try:
        value = float(text)
    except ValueError:
        value = -1
    if not 4 <= value <= 12:
        raise argparse.ArgumentTypeError("spacing must be 4 to 12 mm")
    return value


def _size(text):
    if text in ("smaller", "medium", "larger"):
        return text
    try:
        value = float(text)
    except ValueError:
        value = -1
    if not 20 <= value <= 300:
        raise argparse.ArgumentTypeError("size must be smaller, medium, larger or a slide width from 20 to 300 mm")
    return value


def add_layout_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--paper", choices=["a4", "letter"])
    parser.add_argument("--orientation", choices=["portrait", "landscape"])
    parser.add_argument("--per-page", type=int, choices=[1, 2, 3, 4, 6])
    parser.add_argument("--notes", choices=["beside", "under", "both"])
    parser.add_argument("--style", choices=["lines", "dotted", "dots", "blank", "box"])
    parser.add_argument("--spacing", type=_spacing, help="4 to 12 mm")
    parser.add_argument("--size", type=_size, help="smaller, medium, larger or a slide width in mm")


def _parse(argv: list[str]) -> argparse.Namespace:
    parser = _Parser(add_help=False, prog="layout")
    add_layout_arguments(parser)
    return parser.parse_args(argv)


def _gallery() -> dict:
    return json.loads(GALLERY.read_text(encoding="utf-8"))["layouts"]


def load_store(store: Path = STORE) -> dict:
    if not store.exists():
        return {"usual": None, "layouts": {}}
    try:
        data = json.loads(store.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("layouts", {}), dict):
            raise ValueError("unexpected contents")
    except (OSError, ValueError) as err:
        raise LayoutError(f"The saved layouts file {store} could not be read ({err}). "
                          "It was not changed. Fix it, or move it aside to start again.") from None
    return {"usual": data.get("usual"), "layouts": data.get("layouts", {})}


def _layout_argv(name: str, store: Path) -> list[str]:
    gallery = _gallery()
    if name in gallery:
        return gallery[name]
    layouts = load_store(store)["layouts"]
    if name not in layouts:
        raise LayoutError(f"There is no saved layout called '{name}'.")
    argv = layouts[name]
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise LayoutError(f"saved layout '{name}' is damaged in {store}")
    return argv


def resolve(typed: list[str], name: str | None, store: Path = STORE) -> LayoutOptions:
    saved = []
    if name:
        saved = _layout_argv(name, store)
        try:
            _parse(saved)
        except LayoutError as err:
            raise LayoutError(f"saved layout '{name}': {err}") from None
    ns = _parse(saved + list(typed))  # one pass, so a typed value comes last and wins
    missing = [key.replace("_", "-") for key in REQUIRED if getattr(ns, key) is None]
    if missing:
        raise LayoutError("Missing layout options: " + ", ".join(missing) + ".")
    if ns.style == "box" and ns.notes == "both":
        raise LayoutError("A typeable box works with notes beside or under each slide, not both.")
    spacing = ns.spacing if ns.spacing is not None else (5.0 if ns.style == "dots" else 8.0)
    return LayoutOptions(ns.paper, ns.orientation, ns.per_page, ns.notes, ns.style, spacing, ns.size)


def to_argv(opts: LayoutOptions) -> list[str]:
    size = opts.size if isinstance(opts.size, str) else f"{opts.size:g}"
    return ["--paper", opts.paper, "--orientation", opts.orientation, "--per-page", str(opts.per_page),
            "--notes", opts.notes, "--style", opts.style, "--spacing", f"{opts.spacing_mm:g}", "--size", size]


def _write(store: Path, data: dict) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=store.parent, prefix="layouts-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    os.replace(tmp, store)


def save_layout(name: str, argv: list[str], usual: bool, store: Path = STORE) -> None:
    if not name.strip():
        raise LayoutError("A saved layout needs a name.")
    if name in _gallery():
        raise LayoutError(f"'{name}' is a gallery example and cannot be saved over. Choose another name.")
    complete = to_argv(resolve(argv, None, store))  # refuses an incomplete or invalid layout before writing
    data = load_store(store)                         # refuses a damaged file, so it is never overwritten
    data["layouts"][name] = complete
    if usual:
        data["usual"] = name
    _write(store, data)


def delete_layout(name: str, store: Path = STORE) -> None:
    if name in _gallery():
        raise LayoutError(f"'{name}' is a gallery example and cannot be deleted.")
    data = load_store(store)
    if name not in data["layouts"]:
        raise LayoutError(f"There is no saved layout called '{name}'.")
    del data["layouts"][name]
    if data["usual"] == name:
        data["usual"] = None
    _write(store, data)


def list_layouts(store: Path = STORE) -> dict:
    data = load_store(store)
    entries = []
    for gallery, source in ((True, _gallery()), (False, data["layouts"])):
        for name, argv in source.items():
            try:
                description = describe(resolve(argv, None, store))
            except LayoutError as err:
                description = f"cannot be used: {err}"
            entries.append({"name": name, "options": argv, "description": description, "gallery": gallery})
    return {"usual": data["usual"], "layouts": entries}
