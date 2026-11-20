# StitchRow

An offline-first knitting row tracker for PDF patterns. Import a pattern PDF, choose the size, and follow one row at a time with the expected stitch count. Progress is saved on the device.

## Use it

- Open `StitchRow-offline.html` in a browser — everything is in that one file and no server is needed.
- For installation as a web app, deploy the four-file site in `StitchRow-pwa.zip` (or this repo with `index.html` at the root) to any static HTTPS host.
- The optional local server version: `python3 app.py`, then open `http://127.0.0.1:8124`.

## What it tracks

- Current row, section, tags (knit, purl, increase, decrease, special), instruction, and expected stitch count.
- "Row complete" button, clickable row tiles, undo, jump to row, reset, progress persistence.
- Swedish written-row patterns (e.g. Sophie Hood, Monday Sweater Junior): size selection, repeat expansion, stitch-count milestones.
- English round patterns (e.g. Step By Step Sweater): letter sizes, round repeats, stitch counts.
- Chart-only patterns: extracts the chart image from the PDF and highlights the active chart row.

## Files

- `index.html` — self-contained offline app and GitHub Pages site root.
- `server.html` — server-based UI used by `app.py`.
- `StitchRow-offline.html` — single-file offline app.
- `app.py` — local server with `/api/parse` and `/api/sizes`.
- `pattern-extract/parse_pattern.py` — PDF-to-rows parser used by the server.
- `bundle/` — browser PDF engine, JS parser and the offline build script.
- `manifest.webmanifest`, `sw.js`, icons — PWA files.
- `StitchRow-pwa.zip` — ready-to-deploy static site bundle.

## Rebuild the single file

```
cd bundle
python3 build_offline.py
```

## Known limits

- Chart patterns are followed visually; the app does not translate chart symbols into text.
- Instructions are translated from recurring Swedish knitting phrases; unusual wording may remain in Swedish.
