This repository contains utilities used to extract and group map strongpoints and a data file of map objectives used by the HLL Map Switcher Discord bot scaffold.

Keep guidance short and actionable for automated coding agents. Focus on the concrete patterns and files in this repo.

Key files to read first
- `temp/run_ocr.py` — runs OCR (easyocr) against per-map point images in `temp/assets/points/` and writes `temp/ocr_results.json`.
- `temp/group_columns.py` — groups OCR detections into 5 columns per map and writes `temp/strongpoints_grouped.json`.
- `temp/download_points.py` — convenience script that downloads the map point images from an external GH repo to `temp/assets/points/`.
- `data/map-objectives.json` — canonical mapping of map keys to objective sets (used by the bot). Update this file only when confident about naming and counts.

High-level architecture and intent
- This workspace is a small data-processing scaffold (no long-running server). The primary flow is:
  1. ensure `temp/assets/points/` contains map point images (run `temp/download_points.py` or add images manually)
  2. run `temp/run_ocr.py` to produce `temp/ocr_results.json`
  3. run `temp/group_columns.py` to produce `temp/strongpoints_grouped.json`
  4. manually verify and edit `data/map-objectives.json` (or source-of-truth) if labels need correction

Developer conventions and patterns
- Filenames: map keys are lower/underscored (example: `carentan_warfare`) and map image prefixes are short (example: `Carentan`). The mapping is defined inside the `temp/*` scripts; prefer to update the mapping there if you add new maps.
- OCR pipeline: easyocr is used with `gpu=False`. Scripts are simple one-off utilities; they write JSON into `temp/` for manual inspection.
- Text normalization: OCR outputs are upper-cased in `run_ocr.py` and `group_columns.py` expects uppercase tokens. When editing `data/map-objectives.json`, use uppercase option names to match existing conventions.
- Data authoritative source: treat `data/map-objectives.json` as the canonical objectives list for the bot. Keep the `map` keys aligned with the keys used in OCR results (the keys in `temp/ocr_results.json` and `temp/strongpoints_grouped.json`).

Integration and external dependencies
- easyocr is required for OCR. If you run `temp/run_ocr.py` locally, install it in your Python environment: `pip install easyocr` (plus its backends like torch). The scripts assume CPU-only (gpu=False).
- `temp/download_points.py` downloads images from `mattwright324/maps-let-loose` GitHub raw URLs. If those assets change, update `map_prefixes` in the script.

Testing and debugging tips
- Quick sanity check: run `python temp/run_ocr.py` then `python temp/group_columns.py` and inspect `temp/strongpoints_grouped.json` in an editor.
- If OCR misses or mangles labels, inspect the corresponding image at `temp/assets/points/{PREFIX}_SP_NoMap.png` and consider manual correction. The OCR outputs include `conf` per detection.
- When changing `data/map-objectives.json`, open `temp/strongpoints_grouped.json` to see how OCR grouped similar labels — use those as examples to align naming.

Examples to reference
- Map OCR + grouping flow: `temp/run_ocr.py` -> `temp/ocr_results.json` -> `temp/group_columns.py` -> `temp/strongpoints_grouped.json`.
- Map objectives canonical file: `data/map-objectives.json` (example entries: `omahabeach_warfare`, `elalamein_warfare`).

What to avoid
- Do not rename map keys in `data/map-objectives.json` without updating the mapping used by the OCR scripts — keys must match across files.
- Avoid mass-formatting changes elsewhere in the repo; these scripts are small and style-preserving edits are preferred.

If you need clarification
- Ask for the preferred canonical map key naming and whether `data/map-objectives.json` should be the single source of truth for the bot data. Include an example map key and a desired option name when asking.

Update process
- For small data fixes (typos): edit `data/map-objectives.json` directly, keep option strings uppercase, and commit.
- For adding maps: add entries to the `map_prefixes` dictionaries in the `temp/*` scripts and add the new map entry to `data/map-objectives.json`.

End of file.
