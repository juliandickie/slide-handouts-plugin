"""Command line for Slide Handouts. Every subcommand prints one JSON object."""
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="handouts.py", description="Make printable slide handouts with room for notes.")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("detect", help="report what a PDF holds: deck or handout, slides per page, slide count")
    subs.add_parser("convert", help="turn a .pptx, .ppt or .key file into a PDF in a temporary folder")
    subs.add_parser("build", help="write one handout and check it")
    subs.add_parser("layouts", help="list, save or delete saved layouts")
    subs.add_parser("preview", help="render pages as PNG images")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
