"""Command line for Slide Handouts. Every subcommand prints exactly one JSON object."""
import argparse
import json
import os
import re
import sys
import traceback
from pathlib import Path

from . import layouts
from .convert import convert
from .deck import apply_deck
from .detect import RefusedError, detect, open_pdf, shape_name
from .geometry import LayoutOptions, describe
from .layouts import LayoutError, add_layout_arguments, list_layouts, resolve, save_layout, delete_layout
from .preview import render_pages
from .render import build_handout

LAYOUT_KEYS = ("paper", "orientation", "per_page", "notes", "style", "spacing", "size")


class UsageError(Exception):
    """A command-line mistake, reported as JSON instead of argparse's usage text."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="handouts.py", description="Make printable slide handouts with room for notes.")
    subs = parser.add_subparsers(dest="command", required=True)

    def source_options(p):
        p.add_argument("--deck", help="the original .pptx, .ppt or .key file, for real slide numbers")
        p.add_argument("--order", choices=["rows", "columns"], default="rows")
        p.add_argument("--one-per-page", action="store_true", help="read each page as one slide")

    p = subs.add_parser("detect", help="report what a PDF holds: deck or handout, slides per page, slide count")
    p.add_argument("src")
    source_options(p)
    p = subs.add_parser("convert", help="turn a .pptx, .ppt or .key file into a PDF in a temporary folder")
    p.add_argument("src")
    p = subs.add_parser("build", help="write one handout and check it")
    p.add_argument("src")
    add_layout_arguments(p)
    source_options(p)
    p.add_argument("--layout-name", help="a saved layout or gallery example; options given beside it win")
    p.add_argument("--out", help="a file name, or an existing folder")
    p = subs.add_parser("layouts", help="list, save or delete saved layouts")
    actions = p.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    save = actions.add_parser("save")
    save.add_argument("name")
    add_layout_arguments(save)
    save.add_argument("--usual", action="store_true")
    actions.add_parser("delete").add_argument("name")
    p = subs.add_parser("preview", help="render pages as PNG images")
    p.add_argument("pdf")
    p.add_argument("--pages", default="1,last")
    p.add_argument("--mark-order", action="store_true", help="number the slides on the image in the order they will be read")
    p.add_argument("--order", choices=["rows", "columns"], default="rows")
    p.add_argument("--one-per-page", action="store_true")
    p.add_argument("--out-dir")
    return parser


def safe_name(text: str) -> str:
    """Letters, digits, spaces, hyphens, underscores, parentheses, full stops and commas only."""
    text = text.replace("&", " and ").replace("/", "-").replace("\\", "-")
    text = "".join(c for c in text if c.isalnum() or c in " -_().,")
    return re.sub(r" +", " ", text).strip(" .")


def _free(path: Path) -> Path:
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_v{n}{path.suffix}")
        n += 1
    return candidate


def output_path(source: Path, opts: LayoutOptions, layout_name: str | None, out: Path | None) -> Path:
    stem = safe_name(Path(source).stem) or "slides"
    if layout_name:
        name = f"{stem}_{safe_name(layout_name)}.pdf"
    else:
        size = opts.size if isinstance(opts.size, str) else f"{opts.size:.0f}mm"
        name = f"{stem}_{opts.per_page}-per-page_{opts.orientation}_{opts.style}-{opts.notes}_{size}.pdf"
    if out is None:
        target = Path(source).parent / name
    elif Path(out).is_dir():
        target = Path(out) / name
    else:
        target = Path(out)
    return _free(target)


def _typed(args: argparse.Namespace) -> list:
    argv = []
    for key in LAYOUT_KEYS:
        value = getattr(args, key, None)
        if value is not None:
            argv += [f"--{key.replace('_', '-')}", f"{value:g}" if isinstance(value, float) else str(value)]
    return argv


def _detect(args, src: Path):
    det = detect(open_pdf(src), args.order, args.one_per_page)
    return apply_deck(det, Path(args.deck)) if args.deck else det


def cmd_detect(args) -> dict:
    det = _detect(args, Path(args.src))
    return {"kind": det.kind, "per_page": det.per_page, "slide_count": len(det.slides), "shape": shape_name(det.aspect),
            "numbers_from": det.numbers_from, "skipped": det.skipped, "notes": det.notes}


def cmd_convert(args) -> dict:
    pdf, app = convert(Path(args.src))
    return {"pdf": str(pdf), "app": app, "deck": str(Path(args.src).resolve())}


def cmd_build(args) -> dict:
    src = Path(args.src)
    opts = resolve(_typed(args), args.layout_name, layouts.STORE)
    origin = Path(args.deck) if args.deck else src
    out = output_path(origin, opts, args.layout_name, Path(args.out) if args.out else None)
    if not os.access(out.parent, os.W_OK):
        raise RefusedError(f"Could not write to {out.parent}. Name another place with --out.")
    det = _detect(args, src)
    result = build_handout(open_pdf(src), det, opts, out, f"{origin.stem} - Slides and Notes")
    return {"file": str(out), "pages": result.pages, "slide_width_mm": round(result.slide_width_mm, 1),
            "layout": describe(opts), "warnings": result.warnings, "low_res_slides": result.low_res, "notes": det.notes}


def cmd_layouts(args) -> dict:
    if args.action == "list":
        return list_layouts(layouts.STORE)
    if args.action == "save":
        save_layout(args.name, _typed(args), args.usual, layouts.STORE)
        return {"saved": args.name, "usual": args.usual}
    delete_layout(args.name, layouts.STORE)
    return {"deleted": args.name}


def cmd_preview(args) -> dict:
    mark = detect(open_pdf(Path(args.pdf)), args.order, args.one_per_page) if args.mark_order else None
    images = render_pages(Path(args.pdf), args.pages.split(","), Path(args.out_dir) if args.out_dir else None, mark)
    return {"images": [str(p) for p in images]}


COMMANDS = {"detect": cmd_detect, "convert": cmd_convert, "build": cmd_build, "layouts": cmd_layouts, "preview": cmd_preview}


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        payload, code = {"ok": True, **COMMANDS[args.command](args)}, 0
    except (RefusedError, LayoutError, UsageError, RuntimeError) as err:
        payload, code = {"ok": False, "error": str(err)}, 1
    except Exception as err:  # never a bare traceback on stdout; the skill reads JSON
        traceback.print_exc(file=sys.stderr)
        payload, code = {"ok": False, "error": f"Something went wrong: {err}"}, 1
    print(json.dumps(payload, indent=2))
    return code
