# Slide Handouts - contributor notes

A Claude Code plugin. The `handouts` skill runs one script through uv and reads its JSON. Read this before changing anything.

## Repo map

- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` - the manifest and the single-plugin marketplace. Their versions move together.
- `skills/handouts/SKILL.md` - the skill: the flow, the plain words for each option, and the commands.
- `scripts/handouts.py` - the entry script. It puts its own folder on `sys.path` and runs `slide_handouts.cli.main`.
- `scripts/slide_handouts/` - one module per job:
  - `geometry.py` - layout maths, pure, no PDF.
  - `layouts.py` and `gallery.json` - the option parser, saved layouts and the gallery examples.
  - `detect.py` - file kind, slide frames, printed numbers and refusals.
  - `deck.py` - hidden slides from a .pptx.
  - `convert.py` - opt-in PowerPoint and Keynote conversion.
  - `render.py` - drawing, typeable fields, the photo check and the output self-check.
  - `preview.py` - PNG pages for Claude to look at.
  - `cli.py` - subcommands, JSON output and output names.
- `guide/export-your-slides.md` and `assets/guide/` - the end-user export guide and its screenshots.
- `tools/build_gallery.py` and `assets/examples/` - the README gallery and the script that makes it.
- `tests/` - one test file per module, plus the docs, skill, entry and text rules tests. `tests/make_fixtures.py` makes the made-up deck and every synthetic PDF. `tests/fixtures/real/` holds real Keynote and PowerPoint exports of the made-up deck, described in its README.

## Run the tests

From the repo root:

```bash
uv run --no-project --python 3.13 --with "pymupdf>=2.1,<3" --with pytest pytest -p no:warnings
```

`-p no:warnings` hides PyMuPDF's SWIG deprecation warnings. The suite takes a few seconds.

Every `uv run` names `--python 3.13`. PyMuPDF 2.1 pulls in onnxruntime, which has no wheels for the newest Python, so on a fresh machine uv picks Python 3.15 and the run fails before any plugin code starts. `tests/test_skill.py` checks every run command. PyMuPDF 1.28 has no add-ons and passes the whole suite, but Julian kept 2.1 on 2026-11-10. To check a fresh machine, set `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR` to empty folders and `UV_PYTHON_PREFERENCE=only-managed`, then run the skill's command.

The two live conversion tests drive PowerPoint and Keynote, so they run only with `SLIDE_HANDOUTS_LIVE=1`, on a Mac, with a person at the screen. PowerPoint asks to grant access to each new folder (click Select, then Grant), and Keynote can wait with no visible prompt.

`tests/test_convert.py` compiles both AppleScripts with `osacompile` on a Mac. A reserved word (`before`) once broke both scripts while every text check passed.

## Rebuild the gallery

```bash
uv run --no-project --python 3.13 --with "pymupdf>=2.1,<3" python -I tools/build_gallery.py
```

It rebuilds every image in `assets/examples/` from a made-up 12-slide deck. Open each image and look at it before you commit. Each README caption must be exactly `describe()` of that example's options, and `tests/test_docs.py` checks this.

## House rules

1. **No client content.** No real deck, client name or file from anyone's work goes into tests, fixtures, examples or docs. Use the made-up deck or a synthetic fixture.
2. **Never rank layouts.** The README, the skill and the script's messages never call one layout better than another. `tests/test_skill.py` checks for ranking words.
3. **Text rules.** No em or en dashes, straight quotes only, no trademark, registered or copyright glyphs, and no typographic ligatures, in docs and in the PDFs the script writes. Labels are plain ASCII. Docs use Australian English. `tests/test_text_rules.py` checks the files.
4. **Never rasterise slides.** Place every slide with `page.show_pdf_page`.
5. **Never overwrite.** Not the source, not a file beside it, not an earlier output.
6. **Untrusted input.** Run Python with `-I`, never from the folder that holds the user's files, and take every path as an argument.
7. **Refuse, never guess.** When slide order or count cannot be trusted, stop with a plain sentence that says what to do.

## PyMuPDF quirks

- Import it as `pymupdf`, never `fitz`.
- Write a page's text before you place slides on it. Once a placed slide holds a font named `helv`, `insert_text` adds no font to the page, and the text renders in a fallback font.

## Notes styles

`--style lines` draws solid lines, 0.5 pt at 27% black. `--style dotted` draws rows of dots an eighth of the spacing apart, and `--style dots` a square dot grid, both 0.6 pt round dots at 75% black. Each dotted row is one dashed stroke with a dash period equal to the step and round caps, as Illustrator draws a dotted stroke, so a 600-slide dot grid builds in about 4 seconds. The skill asks notes style with four choices and then "solid or dotted" for lines, because AskUserQuestion shows at most four choices.

## Testing an install

- A local folder added with `/plugin marketplace add <path>` is copied whole into `~/.claude/plugins/cache`, git-ignored files included, and `${CLAUDE_PLUGIN_ROOT}` can point at the folder itself. Test the published plugin with `claude plugin install slide-handouts@loadout` instead.
- Read the test session's log in `~/.claude/projects/<folder>/` to check that Claude called `slide-handouts:handouts`. Without the plugin installed, Claude can find the repo on disk and run the script by hand, which looks the same in the chat.
- In the desktop app, `/plugin` opens Settings, Customize, Plugins, and does not run the command's arguments. Add, then Add marketplace, then Add from a repository, takes `owner/repo`.
- Users get an update only when `version` in `plugin.json` changes. Third-party marketplaces do not auto-update by default.

## Release checklist

1. Bump the version in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` together.
2. Add the version and its date to `CHANGELOG.md`.
3. Rebuild the gallery and look at every image.
4. Run the whole test suite.
5. Tag the release as `vX.Y.Z`.
6. Update the plugin's entry in the `outfit` and `ai-loadout` catalogues in lockstep: the same entry, in the same position, with each README table matching its `marketplace.json`. The entry sits after `short-io`, the last of Julian's own plugins. Run `claude plugin validate .` in each catalogue before committing.

v0.1.0 shipped on 2026-11-10: tag `v0.1.0`, listed in loadout and outfit (juliandickie/ai-loadout#1 and juliandickie/outfit#1).
