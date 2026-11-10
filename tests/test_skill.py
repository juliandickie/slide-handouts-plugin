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
    uv_flags = {"--no-project", "--with", "--directory", "--version"}
    assert set(re.findall(r"(--[a-z][a-z-]+)", text)) - uv_flags <= known


def test_description_names_the_job_and_trigger_phrases():
    head = SKILL.read_text().split("---")[1]
    for phrase in ("slide handouts", "slides per page", "note-taking lines", "dot grid",
                   "fillable notes", "PowerPoint handout PDF"):
        assert phrase in head


def test_no_ranking_words():
    for path in (SKILL, SKILL.parents[2] / "README.md"):
        if path.exists():
            assert not re.search(r"\b(recommend\w*|best|ideal|preferred|most popular)\b", path.read_text(), re.I), path
