# Data Contract

This directory separates personal working data from reusable system logic.

## User Layer

These files are your facts, preferences, or generated work. Cleanup and script
changes should avoid rewriting them unless the user explicitly asks.

| File | Purpose |
|------|---------|
| `cv.md` | Source CV facts in markdown |
| `config/profile.yml` | Candidate identity, targeting, compensation, locations |
| `modes/_profile.md` | Personalized framing and archetype notes |
| `article-digest.md` | Proof points and portfolio evidence |
| `portals.yml` | Scanner targets and title filters |
| `interview-prep/*` | Personal interview notes and story bank |
| `data/applications.md` | Canonical tracker |
| `data/pipeline.md` | Pending job queue |
| `data/scan-runs/*` | Daily human-readable scan logs |
| `data/latest-scan-run.json` | Latest scan summary for menu/status UI |
| `data/scan-history.tsv` | Dedup history used by the scanner |
| `reports/*` | Generated evaluation reports |
| `output/*` | Generated HTML/PDF outputs |
| `jds/*` | Saved job descriptions |

## System Layer

These files are shared logic and support assets for the local workflow.

| File | Purpose |
|------|---------|
| `*.mjs` | Utility scripts |
| `templates/*` | HTML template, state list, example portal config |
| `fonts/*` | Self-hosted fonts for PDF rendering |
| `batch/tracker-additions/*` | Tracker merge staging area |
| `dashboard/*` | Optional Go dashboard |
| `README*.md` | Local orientation docs |
| `docs/*` | Focused maintenance/customization docs |
| `AGENTS.md` | Local agent notes |
| `DATA_CONTRACT.md` | This file |

## Rule of Thumb

- Personalization goes in the user layer
- Shared workflow logic goes in the system layer
- If a change would overwrite the user's facts or generated work, stop and ask
