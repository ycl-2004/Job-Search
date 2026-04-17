# LaTeX One-Page Resume Generation Design

Date: 2026-04-16
Project root: `/Users/yichenlin/Desktop/Daily_Task/Job Searching`
Related repo: `/Users/yichenlin/Desktop/Daily_Task/Job Searching/Scan-job`

## Goal

Build a local resume-generation workflow that:

- uses the current LaTeX resume layout as the fixed visual template;
- rewrites the resume content for the latest job description only;
- overwrites the same working `.tex` file and the same output PDF each run;
- compiles locally with `pdfLaTeX` via `latexmk`;
- guarantees the final PDF is exactly one page whenever possible;
- keeps the final content length and information density close to the current resume, instead of over-compressing into a visibly sparse page.

This design intentionally does not create a long-lived per-job archive of `.tex` and `.pdf` outputs. The system is optimized for "generate the current application version now" rather than maintaining a historical build artifact for every application.

## Confirmed Decisions

### Compiler and toolchain

- Use `pdfLaTeX` as the initial and primary engine.
- Use local `latexmk` to drive compilation.
- Do not use `ThatLatexLib`.
- Do not add `XeLaTeX` fallback in the first version.

### File retention strategy

- Keep the current `main.tex`-style layout as the template source.
- Maintain only one generated working `.tex` file for the latest application.
- Maintain only one generated output PDF for the latest application.
- Overwrite the previous generated working file and PDF on each new run.

### Content fitting strategy

Use a combined `1 + 3` strategy:

- generate an initial version using a content-length budget close to the current resume;
- compile the real PDF;
- if the result exceeds one page, run an automatic fitting loop using progressive content and layout compression until it reaches one page or hits an explicit stop condition.

### Section preservation priority

Content preservation priority is fixed as:

1. `Professional Work Experience`
2. `Technical Projects`
3. `Engineering Design Team`
4. `Technical Content & Research`

This priority controls both bullet trimming and whole-block deletion.

### Allowed fitting adjustments

When content exceeds one page, the system may:

- shorten summary text;
- shorten bullets;
- remove lower-priority bullets;
- remove lower-priority entire items or blocks;
- slightly reduce layout spacing;
- slightly reduce item spacing;
- slightly reduce vertical block spacing;
- slightly reduce font size.

It must not radically redesign the layout.

## Source Template

The current LaTeX resume file is the authoritative visual template. Its structure and look should be treated as the base layout contract:

- one-page A4 resume;
- current margins, section titles, colors, and typographic tone;
- current top-level section ordering;
- current resume-style tabular heading and bullet formatting.

The system should preserve the template's visual identity and only change content and narrowly allowed fitting parameters.

## Proposed File Structure

The design separates three concepts:

- stable template source;
- current generated working file;
- current generated output artifact.

Suggested structure:

```text
/Users/yichenlin/Desktop/Daily_Task/Job Searching/
  docs/
    superpowers/
      specs/
        2026-04-16-latex-one-page-resume-design.md
  latex-template/
    main.tex
  latex-work/
    current.tex
  current-jd.md
  Scan-job/
    cv.md
    output/
      main.pdf
      main.log
```

### File responsibilities

- `latex-template/main.tex`
  - stable template source;
  - manually maintained;
  - not overwritten during generation.

- `latex-work/current.tex`
  - generated working file for the current application;
  - overwritten every run.

- `current-jd.md`
  - normalized current job description for the active application;
  - overwritten every run.

- `Scan-job/output/main.pdf`
  - final PDF artifact for the current application;
  - overwritten every run.

- `Scan-job/output/main.log`
  - latest compilation log;
  - overwritten every run.

## Inputs

The workflow consumes three categories of input.

### 1. Current job description

Supported sources should be:

- pasted raw text;
- local markdown or text file;
- URL fetched and normalized elsewhere before generation.

The normalized result is written to `current-jd.md`.

### 2. Resume fact source

Primary fact source remains:

- `/Users/yichenlin/Desktop/Daily_Task/Job Searching/Scan-job/cv.md`

Optional supporting facts may also come from:

- `article-digest.md`
- `modes/_profile.md`
- existing structured profile/config files inside `Scan-job/`

These sources provide factual material only. The generator may rephrase, reorder, compress, or omit content, but must not invent facts.

### 3. Layout template

The fixed LaTeX template provides:

- document class and page setup;
- section order;
- layout macros;
- visual styling;
- fixed baseline typography and spacing.

## Outputs

The workflow produces only the current version of the application package:

- `latex-work/current.tex`
- `Scan-job/output/main.pdf`
- `Scan-job/output/main.log`
- `current-jd.md`

There is no per-job output archive in this first version.

## Fixed vs Variable Content

### Fixed

The following are fixed by design:

- overall visual template identity;
- top-level section ordering;
- `pdfLaTeX` compilation route;
- one-page output target;
- section preservation priority;
- overwrite-in-place artifact strategy.

### Variable

The following are intentionally variable:

- professional summary wording;
- bullet wording;
- bullet count per item;
- selected projects;
- order of project entries;
- inclusion or exclusion of lower-priority blocks;
- low-level spacing settings used only during fitting;
- slight font-size reduction during last-resort fitting.

## Initial Content Budget

The first generated version should aim to match the current resume's density, not the shortest possible version.

Recommended starting budget:

- Summary: `2-3` sentences.
- `Professional Work Experience`: `2-3` bullets per role.
- `Technical Projects`: `2-3` selected projects, each with `2-3` bullets.
- `Engineering Design Team`: `1` entry with `2-3` bullets.
- `Technical Content & Research`: `1` entry with about `2` bullets.
- `Skills`: mostly fixed, only reordered or lightly tuned.
- `Education`: mostly fixed.

This budget is a starting point only. The real acceptance gate is still final PDF page count.

## End-to-End Workflow

### Step 1. Normalize current JD

- Read the incoming job description.
- Convert it into a normalized text representation.
- Save it to `current-jd.md`.

### Step 2. Generate structured resume content

- Read factual source material from `Scan-job/cv.md` and optional supporting files.
- Extract the strongest matching facts for the current JD.
- Produce structured content for:
  - header;
  - summary;
  - skills;
  - education;
  - work experience;
  - projects;
  - design team;
  - research.

At this stage the output should be structured data, not raw LaTeX text.

### Step 3. Render the working LaTeX file

- Read the stable template source.
- Fill it using the generated structured content.
- Write the result to `latex-work/current.tex`.

This file is fully overwritten on every run.

### Step 4. Compile the PDF

Compile with:

```bash
latexmk -pdf -jobname=main -outdir=Scan-job/output latex-work/current.tex
```

This ensures:

- generated PDF is always `Scan-job/output/main.pdf`;
- generated log is always `Scan-job/output/main.log`.

### Step 5. Check page count

Read page count from the compiler log line that looks like:

```text
Output written on Scan-job/output/main.pdf (1 page, ...)
```

This is the preferred page-count source in version one because:

- it comes directly from the successful compilation result;
- it does not require extra OS-specific PDF tooling;
- it is stable for the current `pdfLaTeX` workflow.

### Step 6. If over one page, enter fitting loop

If the page count is greater than `1`, regenerate `current.tex` with a higher compression level and compile again.

The fitting loop repeats until one of these conditions is met:

- page count becomes exactly `1`;
- the system reaches the maximum allowed compression level;
- compilation fails.

### Step 7. Finalize

If the output becomes one page:

- keep the final `current.tex`;
- keep the final `main.pdf`;
- return success.

If fitting fails:

- preserve the latest `current.tex` and `main.log`;
- return a failure message that explicitly says the content could not be fitted into one page within the allowed constraints.

## Fitting Loop Design

The fitting loop is the core of the system.

### Important rule

Do not patch the previous generated `.tex` in place with ad hoc text edits.

Instead:

- maintain a structured representation of the resume content;
- maintain a fitting level state;
- regenerate the full `current.tex` from structured data on each loop iteration.

This keeps the workflow deterministic and easier to debug.

### Fitting levels

Suggested progression:

#### Level 0. Baseline budgeted content

- near-current length;
- no fitting pressure applied beyond the initial budget.

#### Level 1. Summary compression

- shorten summary wording;
- keep the same meaning;
- reduce rhetorical filler first.

#### Level 2. Bullet compression

- shorten all bullets without deleting structure;
- remove redundant adjectives and explanatory padding;
- keep role-specific facts and useful keywords.

#### Level 3. Low-priority bullet trimming

Delete lower-value bullets starting from the lowest-priority section:

1. `Technical Content & Research`
2. `Engineering Design Team`
3. `Technical Projects`
4. `Professional Work Experience`

#### Level 4. Whole-block deletion

If bullet trimming is not enough, remove entire low-priority entries or blocks:

1. remove the full `Research` block;
2. remove the weakest project;
3. consider removing the `Design Team` block;
4. avoid deleting `Professional Work Experience` unless absolutely necessary in a later version.

#### Level 5. Layout compaction

Only after exhausting content-side fitting:

- reduce section spacing slightly;
- reduce list `itemsep` slightly;
- reduce `\blockspace` slightly;
- reduce font size slightly from the `10pt` baseline.

## Deletion and Compression Rules

### Compression rule

Always prefer:

- shorter wording over deleting substance;
- deleting low-value bullets over deleting high-value bullets;
- deleting lower-priority sections before higher-priority sections.

### Whole-block deletion rule

Whole-block deletion is explicitly allowed, but only in this order:

1. `Technical Content & Research`
2. weakest project inside `Technical Projects`
3. `Engineering Design Team`

`Professional Work Experience` is the last line of defense and should be preserved as long as possible.

## Quality Guardrails

The workflow must enforce these constraints:

- Do not produce a visibly sparse page that is much shorter than the current baseline resume.
- Do not delete high-priority sections before lower-priority ones.
- Do not replace concrete bullets with vague AI-style filler.
- Do not invent facts, tools, achievements, metrics, or experiences.
- Keep the final one-page output as informative as possible within the template.

## Script Responsibilities

The implementation should be split into clear modules.

### 1. Orchestrator script

Responsibilities:

- read the current JD;
- trigger content generation;
- call template rendering;
- call LaTeX compilation;
- inspect page count;
- drive the fitting loop;
- return final result paths and status.

This is the script that the Task 5 CLI should call.

### 2. Resume content generator

Responsibilities:

- read factual resume sources;
- rank source content against the JD;
- create structured resume data;
- respect section priorities and initial budgets.

### 3. Template renderer

Responsibilities:

- read the stable template;
- inject structured content safely into LaTeX;
- write `latex-work/current.tex`.

### 4. Fitting policy module

Responsibilities:

- represent fitting levels;
- decide what changes at each level;
- encode deletion order, compression order, and layout fallback order.

### 5. Compilation wrapper

Responsibilities:

- run `latexmk`;
- store outputs in the fixed output paths;
- return success/failure and log path.

### 6. Page-count parser

Responsibilities:

- read `Scan-job/output/main.log`;
- parse the `Output written on ... (N page...)` line;
- return the detected page count.

## Suggested CLI Behavior

The Task 5 workflow should expose a dedicated command for this flow, for example:

```bash
task 5 resume
```

Possible arguments later:

```bash
task 5 resume --jd-file current-jd.md
task 5 resume --jd-url <url>
task 5 resume --strict-one-page
```

Version one can keep this simpler and start from a single entry path.

## Failure Cases

### Compilation failure

- stop immediately;
- show the log location;
- do not continue fitting blindly.

### Fitting failure

- stop after the last allowed fitting level;
- report that the current content could not fit into one page under the allowed constraints.

### Missing source data

- fail early if required resume source files are missing;
- do not generate placeholder content.

## Out of Scope for Version One

- multi-template support;
- multiple simultaneous saved application variants;
- `XeLaTeX` fallback;
- automated per-job archive naming;
- visual PDF diffing;
- external PDF page-count dependencies.

## Recommended Next Step

After this design is approved, implementation planning should define:

- exact file paths and names to create;
- structured content schema for the renderer;
- fitting-level state representation;
- the Task 5 CLI command surface for the new workflow;
- verification steps using a real JD and the current template.
