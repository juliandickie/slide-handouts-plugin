import re
from pathlib import Path

from slide_handouts.cli import build_parser

SKILL = Path(__file__).parents[1] / "skills" / "handouts" / "SKILL.md"


def test_skill_uses_only_real_subcommands_and_flags():
    text = SKILL.read_text()
    parser = build_parser()
    subs = parser._subparsers._group_actions[0].choices
    used = set(re.findall(r"handouts\.py\"? (\w+)", text))
    assert used and used <= set(subs)
    known = set()
    for sub in subs.values():
        known |= {f for a in sub._actions for f in a.option_strings}
        for action in sub._actions:  # layouts has its own subcommands
            if isinstance(action, type(parser._subparsers._group_actions[0])):
                for nested in action.choices.values():
                    known |= {f for a in nested._actions for f in a.option_strings}
    uv_flags = {"--no-project", "--with", "--directory", "--version", "--python"}
    assert set(re.findall(r"(--[a-z][a-z-]+)", text)) - uv_flags <= known


def test_every_run_command_names_python_3_13():
    # PyMuPDF 2.1 needs onnxruntime, which has no wheels for the newest Python, so a fresh machine
    # fails unless uv is told which Python to use (final review C1; Julian kept 2.1, 2026-11-10).
    root = SKILL.parents[2]
    files = [SKILL, root / "CLAUDE.md", root / "scripts" / "handouts.py",
             root / "tools" / "build_gallery.py", root / "tests" / "make_fixtures.py"]
    commands = [line for f in files for line in f.read_text().splitlines() if "uv run" in line and "pymupdf" in line]
    assert len(commands) >= 6
    assert all("--python 3.13" in line for line in commands), [c for c in commands if "--python 3.13" not in c]


def test_description_names_the_job_and_trigger_phrases():
    head = SKILL.read_text().split("---")[1]
    for phrase in ("slide handouts", "slides per page", "note-taking lines", "dot grid",
                   "fillable notes", "PowerPoint handout PDF"):
        assert phrase in head


def test_no_ranking_words():
    for path in (SKILL, SKILL.parents[2] / "README.md"):
        if path.exists():
            assert not re.search(r"\b(recommend\w*|best|ideal|preferred|most popular)\b", path.read_text(), re.I), path


def test_skill_asks_each_option_on_its_own_and_never_drops_a_choice():
    # Install test, 2026-11-10: notes position and style merged into one 4-choice question hid blank space,
    # the typeable box and "beside and under". AskUserQuestion shows at most four choices.
    text = SKILL.read_text()
    assert "Ask each option as its own question" in text and "Never leave a choice out" in text
    assert '"1", "2", "3" and "4 or 6"' in text and "solid or dotted" in text


def test_skill_leaves_the_naming_to_the_script():
    # Install test: Claude chose its own --out names, which skipped the script's safe names and _v2 rule.
    assert "Leave out `--out` unless the person names a folder or a file name" in SKILL.read_text()


def test_skill_saves_a_gallery_example_as_usual_under_a_new_name():
    # Install test: "make example 6 my usual" hit the gallery refusal before Claude asked for a name.
    text = SKILL.read_text()
    assert "To make a gallery example the usual, ask for a name of their own" in text


def test_skill_flags_are_on_the_commands_that_take_them():
    # Final review minor 11: --deck went to "every later command", but preview and layouts save reject it.
    text = SKILL.read_text()
    assert "pass `--deck <original file>` to `detect` and `build`" in text
    assert "and pass it to `build` too" in text and '"${CLAUDE_PLUGIN_ROOT}/scripts/handouts.py" convert' not in text
