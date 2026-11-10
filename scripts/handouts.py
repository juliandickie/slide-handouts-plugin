"""Slide Handouts command line. Run it as:
uv run --no-project --with "pymupdf>=2.1,<3" python -I scripts/handouts.py <subcommand> ...
"""
import sys
from pathlib import Path

# -I leaves the script's folder off sys.path; this folder is the plugin's own, never the user's.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from slide_handouts.cli import main  # noqa: E402

raise SystemExit(main())
