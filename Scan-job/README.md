# Scan-job

[English](README.md) | [繁體中文](README.zh-TW.md)

This directory now acts as the local support layer for the Task 5 workflow in
`Job Searching/cli.py`.

Instead of treating `Scan-job` like a standalone cloud-agent product, treat it
as the place that holds:

- scan and maintenance scripts
- shared templates and mode files
- pipeline/tracker data
- generated reports and CV outputs
- optional dashboard code

## What Still Matters

Current local workflow:

1. Configure `cv.md`, `config/profile.yml`, and `portals.yml`
2. Use Task 5 in the main project to scan jobs, inspect the pipeline, and
   process a selected job
3. Let this folder store the generated `reports/`, `output/`, `jds/`, and
   `data/` artifacts
4. Use the utility scripts here only when you need setup checks or maintenance

## Quick Start

```bash
cd "Job Searching/Scan-job"
npm install
npx playwright install chromium
npm run doctor
```

Required personal files:

- `cv.md`
- `config/profile.yml`
- `portals.yml`

Optional but useful:

- `article-digest.md`
- `modes/_profile.md`
- `interview-prep/story-bank.md`

## Main Commands

These are the local utilities behind the workflow:

| Command | Purpose |
|---------|---------|
| `npm run doctor` | Check local prerequisites |
| `npm run scan` | Run the raw portal scanner |
| `npm run pdf -- input.html output.pdf` | Render HTML CV to PDF |
| `npm run verify` | Validate tracker consistency |
| `npm run clean-pipeline` | Rebuild and normalize pipeline layout |
| `npm run normalize` | Normalize tracker statuses |
| `npm run dedup` | Deduplicate tracker rows |
| `npm run merge` | Merge batch tracker additions |

See `docs/SCRIPTS.md` for details.

## Folder Layout

```text
Scan-job/
├── cv.md
├── article-digest.md
├── config/
├── interview-prep/
├── data/
├── reports/
├── output/
├── jds/
├── templates/
├── fonts/
├── dashboard/
├── modes/_profile.md
└── *.mjs
```

## Keep vs Customize

- Keep your personal facts and target preferences in `cv.md`,
  `config/profile.yml`, `article-digest.md`, `portals.yml`, `interview-prep/*`,
  and `data/*`
- Keep shared system logic in scripts, templates, and dashboard
- Use `modes/_profile.md` only for your own framing or tailoring notes

See:

- `DATA_CONTRACT.md`
- `docs/CUSTOMIZATION.md`
- `docs/SCRIPTS.md`
