import json
import subprocess
import sys
from pathlib import Path

ENTRY = Path(__file__).parents[1] / "scripts" / "handouts.py"


def test_entry_ignores_planted_module_in_cwd(tmp_path):
    (tmp_path / "json.py").write_text("raise SystemExit('planted json imported')")
    r = subprocess.run([sys.executable, "-I", str(ENTRY), "--help"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for sub in ("detect", "convert", "build", "layouts", "preview"):
        assert sub in r.stdout


def test_manifests_agree():
    root = ENTRY.parents[1] / ".claude-plugin"
    plugin = json.loads((root / "plugin.json").read_text())
    entry = json.loads((root / "marketplace.json").read_text())["plugins"][0]
    assert plugin["name"] == entry["name"] == "slide-handouts"
    assert plugin["version"] == entry["version"]
    assert plugin["description"] == entry["description"]
