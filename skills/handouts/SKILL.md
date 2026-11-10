---
name: handouts
description: Make printable slide handouts with room for notes, from a PowerPoint handout PDF, a slide deck PDF, or a PowerPoint, Keynote or Google Slides file. Use for slide handouts, printable slides with notes, bigger slides, a different number of slides per page, note-taking lines, a dot grid, blank space, fillable notes boxes, and saving a usual handout layout.
argument-hint: "<file> [layout in plain words, a saved layout name or a gallery example]"
---

# Slide handouts

Turn slides into a printable handout with space for notes beside or under each slide. Each person picks their own layout. Never say one layout is better than another.

## Run the script

Run every command like this, with absolute paths for every file:

```
uv run --directory "${CLAUDE_PLUGIN_ROOT}" --no-project --with "pymupdf>=2.1,<3" python -I "${CLAUDE_PLUGIN_ROOT}/scripts/handouts.py" <subcommand> ...
```

Each command prints one JSON object. When `ok` is false, tell the person the `error` sentence as it is.

The export guide is at https://github.com/juliandickie/slide-handouts-plugin/blob/main/guide/export-your-slides.md and the layout gallery is in the README at https://github.com/juliandickie/slide-handouts-plugin#gallery.

## The flow

1. Find the file the person means. If more than one file fits, ask which one.
2. Run `uv --version`. If uv is missing, give one command and stop:
   - Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - Then ask the person to restart Claude Code.
3. If the file is a slide app file (.pptx, .ppt, .key, or a Google Slides deck), get a PDF first.
   - By default, give the export steps for their app and wait for the PDF:
     - PowerPoint on a Mac: File, Export, File Format PDF, Export.
     - PowerPoint on Windows: File, Export, Create PDF/XPS, Publish.
     - Keynote: File, Export To, PDF, with "Include skipped slides", "Include presenter notes" and "Include each stage of builds" unticked, then Save (Next in older versions).
     - Google Slides: File, Download, PDF document.
     - Link the export guide for screenshots.
   - Only if the person asks you to convert it, offer automatic conversion. Say first that it needs permission for Claude to control PowerPoint or Keynote, and that the app may ask them to allow access to the folder. Then run `"${CLAUDE_PLUGIN_ROOT}/scripts/handouts.py" convert <file>`. Tell them which app converted it, and when it was Keynote, that fonts can shift. Google Slides has no automatic conversion.
   - Either way, pass `--deck <original file>` to every later command, so hidden slides keep their real numbers.
4. Run `handouts.py" detect <pdf>` and say what it found in one or two sentences: the slide count and slides per page.
   - If the error mentions `--one-per-page`, ask "Is each page one slide?" If yes, run detect again with `--one-per-page`.
   - If `numbers_from` is "reading order", run `handouts.py" preview <pdf> --pages 1 --mark-order`, open the image for the person (`open <png>` on a Mac, `start "" <png>` on Windows), and ask "Do the numbers follow the slide order?" If not, use `--order columns` from then on.
   - Pass on every sentence in `notes`.
5. Settle the layout.
   - Use what the person already said: a saved layout name, a gallery example such as "example 6", or options in plain words.
   - If they said nothing and `handouts.py" layouts list` shows a usual layout, offer it first, described in plain words.
   - Ask only about options that are still open, in as few AskUserQuestion questions as possible, in this order: paper, orientation, slides per page, notes position, notes style, spacing (lines and dots only), slide size. List the choices in that fixed order and never rank them.
   - A typeable box works beside or under each slide, not both. If they ask for both, ask which side.
6. Build each handout with `handouts.py" build <pdf> <options> [--deck <file>] [--layout-name NAME] [--out PATH]`. The build checks its own output and stops loudly on a failure. Then run `handouts.py" preview <handout> --pages 1,last` and look at both images before you report.
7. Report each file as a link, with its page count, slide width and the `layout` sentence. Pass on every warning and note. For each slide in `low_res_slides`, say its photos may print soft, and that a fresh export from the original deck may be sharper.
8. If the layout was new, ask once whether to save it, under what name, and whether to make it the usual. Save it with `handouts.py" layouts save NAME <options> [--usual]`.

## Plain words to options

- A4 or US Letter: `--paper a4` or `--paper letter`
- upright or sideways pages: `--orientation portrait` or `--orientation landscape`
- "3 to a page": `--per-page 3` (1, 2, 3, 4 or 6)
- notes to the side, below, or both: `--notes beside`, `--notes under`, `--notes both`
- dotted lines, a dot grid, empty space, a box to type into: `--style lines`, `--style dots`, `--style blank`, `--style box`
- narrow, medium or wide spacing: `--spacing 6`, `--spacing 7`, `--spacing 8` (any value from 4 to 12 mm)
- bigger slides, in between, more room to write: `--size larger`, `--size medium`, `--size smaller`, or an exact width such as `--size 120`
- "example 6": `--layout-name "example 6"`, and any options given beside it change that example

## When a file is refused

Tell the person the error sentence, then link the export guide. Exporting the deck straight to PDF, one slide per page, always works. Do not retry with guessed options.
