# Scan-job Agent Notes

This folder is now maintained as a local, terminal-first support directory for
Task 5 in `Job Searching/cli.py`.

Use these rules when working here:

- Treat the Task 5 menu workflow as the primary entry point. The `.mjs` files in
  this folder are support utilities, not a separate product surface.
- Keep user-specific data in `cv.md`, `config/profile.yml`, `modes/_profile.md`,
  `article-digest.md`, `portals.yml`, `interview-prep/`, and `data/`.
- Keep shared logic in the checked-in scripts, templates, and dashboard.
- Do not reintroduce cloud-only slash commands, community repo scaffolding, or
  duplicate docs unless the user explicitly asks for them.
- Never submit an application on the user's behalf.

Start with:

- `README.zh-TW.md` or `README.md` for orientation
- `DATA_CONTRACT.md` for file ownership
- `docs/SCRIPTS.md` for utility commands
