# LaTeX One-Page Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local `task 5 resume` workflow that renders the fixed LaTeX template into a single current working `.tex`, compiles a single current PDF, reads page count from the LaTeX log, and retries with progressively tighter fitting rules until it reaches one page or fails cleanly.

**Architecture:** Keep the implementation inside the `Job Searching` integration layer and leave `Scan-job` as the factual data source plus output directory. Use a small Python pipeline module for data loading, LaTeX rendering, compilation, page-count parsing, and fitting decisions, then expose it through `Job Searching/cli.py`.

**Tech Stack:** Python 3.14, local `latexmk`/`pdfLaTeX`, pytest, existing Task 5 CLI integration.

---

### Task 1: Add the implementation scaffolding and path rules

**Files:**
- Modify: `/Users/yichenlin/Desktop/Daily_Task/task5_loader.py`
- Modify: `/Users/yichenlin/Desktop/Daily_Task/Job Searching/.gitignore`
- Create: `/Users/yichenlin/Desktop/Daily_Task/Job Searching/latex-template/main.tex`

- [ ] **Step 1: Ensure Task 5 sibling modules are importable**

Update `task5_loader.py` so it inserts the Task 5 root directory into `sys.path` before loading `cli.py`.

- [ ] **Step 2: Mark generated resume artifacts as ignored**

Add ignore entries for:
- `latex-work/`
- `current-jd.md`

- [ ] **Step 3: Create the tokenized LaTeX template**

Add `latex-template/main.tex` with:
- the same layout and visual structure as the current resume;
- replacement tokens for summary, sections, and fit-related spacing.

### Task 2: Build the resume pipeline module

**Files:**
- Create: `/Users/yichenlin/Desktop/Daily_Task/Job Searching/task5_resume_pipeline.py`
- Test: `/Users/yichenlin/Desktop/Daily_Task/tests/test_task5_resume_pipeline.py`

- [ ] **Step 1: Write unit tests for page-count parsing and fitting orchestration**

Cover:
- parsing `Output written on ... (N page...)`;
- retrying when compile result reports more than one page;
- preserving the last rendered `current.tex`.

- [ ] **Step 2: Implement resume data loading**

Read:
- `Scan-job/cv.md`
- `current-jd.md` or an explicit JD file

Parse:
- header/contact info
- summary
- work entries
- project entries
- engineering/design-team entry
- skills groups
- education entry

- [ ] **Step 3: Implement structured fitting rules**

Represent fit levels for:
- summary shortening
- bullet shortening
- low-priority bullet trimming
- whole-block deletion
- layout compaction

- [ ] **Step 4: Implement template rendering**

Render the tokenized template into `latex-work/current.tex` with safe LaTeX escaping.

- [ ] **Step 5: Implement compilation and log parsing**

Compile with `latexmk -pdf -jobname=main -outdir=Scan-job/output latex-work/current.tex` and parse page count from `Scan-job/output/main.log`.

### Task 3: Expose the workflow in the Task 5 CLI

**Files:**
- Modify: `/Users/yichenlin/Desktop/Daily_Task/Job Searching/cli.py`
- Test: `/Users/yichenlin/Desktop/Daily_Task/tests/test_career_ops_cli.py`

- [ ] **Step 1: Add `resume` as a Task 5 command**

Support:
- `task 5 resume`
- `task 5 resume --jd-file <path>`

- [ ] **Step 2: Print clear success/failure output**

On success, show:
- current JD path
- generated `current.tex`
- generated PDF path
- page count
- fit level used

On failure, show:
- latest log path
- failure reason

- [ ] **Step 3: Add CLI regression tests**

Verify:
- CLI routes to the new pipeline;
- `--jd-file` is respected;
- pipeline failures return non-zero status.

### Task 4: Run verification and document current limitations

**Files:**
- Modify if needed: `/Users/yichenlin/Desktop/Daily_Task/Job Searching/docs/superpowers/specs/2026-04-16-latex-one-page-resume-design.md`

- [ ] **Step 1: Run targeted pytest coverage**

Run:
- `./.venv/bin/python -m pytest tests/test_task5_resume_pipeline.py tests/test_career_ops_cli.py -v`

- [ ] **Step 2: Run a real local compile smoke test**

Run:
- `task 5 resume --jd-file <sample-jd-path>`

Expected:
- `latex-work/current.tex` exists
- `Scan-job/output/main.pdf` exists
- page count is reported

- [ ] **Step 3: Record any remaining gaps**

If the first version still uses heuristic tailoring rather than full semantic rewriting, note that clearly in the final summary.
