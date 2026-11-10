import json
import re
from pathlib import Path

from slide_handouts.geometry import describe
from slide_handouts.layouts import resolve

ROOT = Path(__file__).parents[1]


def test_readme_shows_every_gallery_example_with_its_caption(tmp_path):
    readme = (ROOT / "README.md").read_text()
    for name in json.loads((ROOT / "scripts/slide_handouts/gallery.json").read_text())["layouts"]:
        n = int(name.split()[1])
        image = f"assets/examples/example-{n:02d}.png"
        assert (ROOT / image).exists() and image in readme
        assert describe(resolve([], name, tmp_path / "l.json")) in readme


def test_size_strip_exists_and_is_shown():
    assert (ROOT / "assets/examples/sizes.png").exists()
    assert "assets/examples/sizes.png" in (ROOT / "README.md").read_text()


def test_guide_images_exist_and_readme_links_the_guide():
    guide = ROOT / "guide/export-your-slides.md"
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", guide.read_text())
    assert images and all((guide.parent / image).resolve().exists() for image in images)
    assert "guide/export-your-slides.md" in (ROOT / "README.md").read_text()


def test_changelog_has_the_current_version():
    version = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]
    assert f"## {version}" in (ROOT / "CHANGELOG.md").read_text()
