# Real exports of the made-up deck

These PDFs were exported on 2026-11-10 from `example-deck.pptx`, a made-up 13-slide 16:9 deck with slides 5 and 9 hidden. It was made by `tests/make_fixtures.py`. Nothing here comes from a real presentation. The tests read the expected results from `expected.json`.

**Apps:** Keynote 15.3.1 and PowerPoint for Mac 16.114.4, on macOS.

**How they were made:** Keynote's slide PDFs and its handout came from AppleScript `export`. PowerPoint's slide PDF came from AppleScript `save as PDF`. PowerPoint's handouts came from File, Print, Layout, then the PDF button, because its scripted PDF save ignores the handout settings.

## keynote-slides.pdf

**Page size:** 960 x 540 pt, one slide per page, no margin.

**Hidden slides:** left out, so 11 pages.

**Numbers:** none printed.

## keynote-slides-with-skipped.pdf

**Page size:** 960 x 540 pt, one slide per page, no margin.

**Hidden slides:** included, so 13 pages.

**Numbers:** none printed.

## powerpoint-slides.pdf

**Page size:** 960 x 540 pt, one slide per page, no margin.

**Hidden slides:** left out, so 11 pages.

**Numbers:** none printed.

## keynote-handout-3.pdf

**Page size:** 1024 x 768 pt. This is not a paper size, so the page size alone cannot tell this handout from a deck.

**Layout:** 3 slides per page down the left, 4 pages, the last holding 2.

**Frames:** 295 x 166 pt at x 43.2 pt and y 43.2, 276.4 and 509.6 pt, drawn with "borders" on.

**Numbers:** printed level with the top of each frame, about 4 pt to its right. Keynote numbers the visible slides 1 to 11, so the printed numbers are positions in the handout, not deck numbers. Deck slides 5 and 9 leave no gap.

**Order:** rows, top to bottom.

## powerpoint-handout-2.pdf

**Page size:** A4 portrait (595.3 x 841.9 pt).

**Layout:** 2 slides per page, 6 pages, the last holding 1.

**Frames:** 480 x 270 pt at x 58 pt and y 120 and 451 pt.

**Numbers:** printed about 3 pt below each frame's bottom-left corner. They are deck numbers, so 5 and 9 are missing.

**Other text:** the date at the top right and the page number at the bottom right.

**Order:** rows.

## powerpoint-handout-3.pdf

**Page size:** A4 portrait.

**Layout:** 3 slides per page down the left, with ruled lines on the right, 4 pages, the last holding 2.

**Frames:** about 234 x 132 pt at x 52 pt and y 134, 355 and 575 pt. Sizes vary by up to 1 pt.

**Numbers:** printed about 3 pt below each frame's bottom-left corner, as deck numbers with 5 and 9 missing.

**Other text:** the date at the top right and the page number at the bottom right.

**Order:** rows.

## powerpoint-handout-3-noframe.pdf

**Settings:** as `powerpoint-handout-3.pdf`, with "Frame slides" off.

**Frames:** no border is drawn, but each slide's background is still a 234 x 132 pt rectangle at the same place, so the slides can still be found.

**Numbers and order:** as `powerpoint-handout-3.pdf`.

## powerpoint-handout-4.pdf

**Page size:** A4 portrait.

**Layout:** 4 slides per page in a 2 x 2 grid, 3 pages, the last holding 3.

**Frames:** about 234 x 132 pt at x 52 and 309 pt and y 189 and 520 pt.

**Numbers:** below each frame's bottom-left corner, as deck numbers.

**Order:** rows (left to right, then down).

## powerpoint-handout-6.pdf

**Page size:** A4 portrait.

**Layout:** 6 slides per page in 2 columns and 3 rows, 2 pages, the last holding 5.

**Frames:** about 234 x 132 pt at x 52 and 309 pt and y 134, 355 and 575 pt.

**Numbers:** below each frame's bottom-left corner, as deck numbers.

**Order:** rows. PowerPoint for Mac's Print dialog offers no column order for handouts.

## Not available

**keynote-handout-2, -4 and -6:** Keynote's scripted export has no slides-per-page setting and always made 3 per page. The Print dialog can make the others, but saving from it needs a person, because a Save-panel utility on this Mac covers the panel's buttons. Keynote's frame and number style is covered by `keynote-handout-3.pdf`.

**powerpoint-handout-6-vertical:** PowerPoint for Mac 16.114 has no handout order setting. Column order is covered by the synthetic fixtures.

**A frameless PowerPoint handout:** turning "Frame slides" off still leaves the slide background rectangle (see above). A scanned handout is the frameless case, and it is synthetic.
