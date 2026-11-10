from pathlib import Path

# En and em dashes, curly quotes, trademark, registered and copyright glyphs, typographic ligatures.
# Spelled as code points so this file holds none of them itself.
BANNED = "".join(map(chr, [0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2122, 0xAE, 0xA9,
                           *range(0xFB00, 0xFB07)]))
PATTERNS = ["README.md", "CHANGELOG.md", "CLAUDE.md", "skills/**/*.md", ".claude-plugin/*.json",
            "scripts/**/*.py", "scripts/**/*.json", "tools/*.py"]


def test_no_banned_characters():
    root = Path(__file__).parents[1]
    hits = [f"{p.relative_to(root)}:{n}" for pat in PATTERNS for p in root.glob(pat)
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if any(c in line for c in BANNED)]
    assert hits == []
