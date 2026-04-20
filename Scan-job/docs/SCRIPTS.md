# Scripts Reference

Task 5 in the main project is the preferred user-facing workflow. These scripts
are the support tools behind it.

## Everyday Commands

| Command | Purpose |
|---------|---------|
| `npm run doctor` | Validate local prerequisites |
| `npm run scan` | Run the raw portal scanner |
| `npm run pdf -- input.html output.pdf` | Render an HTML CV to PDF |
| `npm run verify` | Check tracker integrity |
| `npm run clean-pipeline` | Rebuild and normalize pending queue layout |
| `npm run normalize` | Normalize tracker statuses |
| `npm run dedup` | Remove duplicate tracker rows |
| `npm run merge` | Merge batch tracker additions |

## Notes

### `doctor`

Checks Node, dependencies, Playwright Chromium, required personal files, fonts,
and ensures `data/`, `output/`, and `reports/` exist.

### `scan`

Runs the zero-token portal scanner. Task 5 already wraps this in a menu, target
profile picker, and status logging.

### `pdf`

Converts a generated HTML resume into a print-ready PDF. This is the current
HTML output path used by Task 5.

### `verify`, `clean-pipeline`, `normalize`, `dedup`, `merge`

These are maintenance commands for tracker and pipeline hygiene. You usually
only need them when something looks inconsistent.

There are no longer any built-in upstream sync or cloud-agent maintenance
commands in this folder. The remaining scripts are only for the local project.
