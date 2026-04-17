from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess


DEFAULT_PRONOUNS = "(he/him)"
TEX_BIN_FALLBACK_DIRS: tuple[Path, ...] = (Path("/Library/TeX/texbin"),)


@dataclass(slots=True)
class SkillGroup:
    label: str
    values: list[str]


@dataclass(slots=True)
class ResumeEntry:
    title: str
    context: str
    role: str
    period: str
    bullets: list[str]
    links: list[tuple[str, str]]


@dataclass(slots=True)
class EducationEntry:
    school: str
    location: str
    degree: str
    graduation: str
    honors: str


@dataclass(slots=True)
class ResumeDocument:
    name: str
    pronouns: str
    phone: str
    email: str
    linkedin_url: str
    linkedin_label: str
    summary: str
    skills: list[SkillGroup]
    education: EducationEntry
    work_entries: list[ResumeEntry]
    project_entries: list[ResumeEntry]
    design_team_entry: ResumeEntry | None
    research_entry: ResumeEntry | None


@dataclass(frozen=True, slots=True)
class FitConfig:
    summary_sentences: int
    skill_group_limit: int
    skill_items_limit: int
    project_limit: int
    project_bullet_limit: int
    work_bullet_limit: int
    design_bullet_limit: int
    research_bullet_limit: int
    include_design_team: bool
    include_research: bool
    compact_text: bool
    itemsep: str
    topsep: str
    section_top_spacing: str
    section_bottom_spacing: str
    blockspace: str
    body_font_command: str


@dataclass(slots=True)
class LatexCompileResult:
    success: bool
    page_count: int | None
    log_path: Path
    pdf_path: Path
    reason: str | None = None


@dataclass(slots=True)
class ResumePipelineResult:
    success: bool
    page_count: int | None
    fit_level: int
    current_jd_path: Path
    current_tex_path: Path
    pdf_path: Path
    log_path: Path
    reason: str | None = None


FIT_CONFIGS: list[FitConfig] = [
    FitConfig(
        summary_sentences=3,
        skill_group_limit=5,
        skill_items_limit=6,
        project_limit=3,
        project_bullet_limit=3,
        work_bullet_limit=3,
        design_bullet_limit=3,
        research_bullet_limit=3,
        include_design_team=True,
        include_research=True,
        compact_text=False,
        itemsep="2pt",
        topsep="3pt",
        section_top_spacing="10pt",
        section_bottom_spacing="5pt",
        blockspace="8pt",
        body_font_command="",
    ),
    FitConfig(
        summary_sentences=2,
        skill_group_limit=5,
        skill_items_limit=6,
        project_limit=3,
        project_bullet_limit=3,
        work_bullet_limit=3,
        design_bullet_limit=3,
        research_bullet_limit=3,
        include_design_team=True,
        include_research=True,
        compact_text=False,
        itemsep="2pt",
        topsep="3pt",
        section_top_spacing="10pt",
        section_bottom_spacing="5pt",
        blockspace="8pt",
        body_font_command="",
    ),
    FitConfig(
        summary_sentences=2,
        skill_group_limit=5,
        skill_items_limit=5,
        project_limit=3,
        project_bullet_limit=3,
        work_bullet_limit=3,
        design_bullet_limit=3,
        research_bullet_limit=2,
        include_design_team=True,
        include_research=True,
        compact_text=True,
        itemsep="2pt",
        topsep="2pt",
        section_top_spacing="9pt",
        section_bottom_spacing="4pt",
        blockspace="7pt",
        body_font_command="",
    ),
    FitConfig(
        summary_sentences=2,
        skill_group_limit=4,
        skill_items_limit=5,
        project_limit=3,
        project_bullet_limit=2,
        work_bullet_limit=3,
        design_bullet_limit=2,
        research_bullet_limit=2,
        include_design_team=True,
        include_research=True,
        compact_text=True,
        itemsep="1pt",
        topsep="2pt",
        section_top_spacing="8pt",
        section_bottom_spacing="4pt",
        blockspace="6pt",
        body_font_command="",
    ),
    FitConfig(
        summary_sentences=2,
        skill_group_limit=4,
        skill_items_limit=4,
        project_limit=2,
        project_bullet_limit=2,
        work_bullet_limit=3,
        design_bullet_limit=2,
        research_bullet_limit=0,
        include_design_team=True,
        include_research=False,
        compact_text=True,
        itemsep="1pt",
        topsep="2pt",
        section_top_spacing="8pt",
        section_bottom_spacing="3pt",
        blockspace="5pt",
        body_font_command="",
    ),
    FitConfig(
        summary_sentences=2,
        skill_group_limit=4,
        skill_items_limit=4,
        project_limit=2,
        project_bullet_limit=2,
        work_bullet_limit=3,
        design_bullet_limit=0,
        research_bullet_limit=0,
        include_design_team=False,
        include_research=False,
        compact_text=True,
        itemsep="1pt",
        topsep="1pt",
        section_top_spacing="7pt",
        section_bottom_spacing="3pt",
        blockspace="4pt",
        body_font_command="\\fontsize{9.6}{11.2}\\selectfont",
    ),
]


def run_resume_pipeline(
    root_dir: Path,
    *,
    jd_path: Path | None = None,
    compile_latex_fn=None,
) -> ResumePipelineResult:
    template_path = root_dir / "latex-template" / "main.tex"
    current_jd_path = root_dir / "current-jd.md"
    current_tex_path = root_dir / "latex-work" / "current.tex"
    output_dir = root_dir / "Scan-job" / "output"
    pdf_path = output_dir / "main.pdf"
    log_path = output_dir / "main.log"
    cv_path = root_dir / "Scan-job" / "cv.md"

    if not template_path.exists():
        raise FileNotFoundError(f"LaTeX template not found: {template_path}")
    if not cv_path.exists():
        raise FileNotFoundError(f"CV source not found: {cv_path}")

    current_tex_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_jd_path = jd_path.resolve() if jd_path is not None else current_jd_path
    if not source_jd_path.exists():
        raise FileNotFoundError(f"Job description file not found: {source_jd_path}")

    jd_text = source_jd_path.read_text(encoding="utf-8").strip()
    current_jd_path.write_text(jd_text + "\n", encoding="utf-8")
    document = _build_resume_document(cv_path, jd_text)
    template = template_path.read_text(encoding="utf-8")

    compile_runner = compile_latex_fn or _compile_latex
    last_result: LatexCompileResult | None = None

    for fit_level, fit_config in enumerate(FIT_CONFIGS):
        rendered = _render_latex_document(template, document, jd_text, fit_config)
        current_tex_path.write_text(rendered, encoding="utf-8")

        compile_result = compile_runner(root_dir, current_tex_path, output_dir)
        last_result = compile_result
        if not compile_result.success:
            return ResumePipelineResult(
                success=False,
                page_count=compile_result.page_count,
                fit_level=fit_level,
                current_jd_path=current_jd_path,
                current_tex_path=current_tex_path,
                pdf_path=compile_result.pdf_path,
                log_path=compile_result.log_path,
                reason=compile_result.reason or "LaTeX compilation failed.",
            )
        if compile_result.page_count == 1:
            return ResumePipelineResult(
                success=True,
                page_count=1,
                fit_level=fit_level,
                current_jd_path=current_jd_path,
                current_tex_path=current_tex_path,
                pdf_path=compile_result.pdf_path,
                log_path=compile_result.log_path,
                reason=None,
            )

    return ResumePipelineResult(
        success=False,
        page_count=last_result.page_count if last_result is not None else None,
        fit_level=len(FIT_CONFIGS) - 1,
        current_jd_path=current_jd_path,
        current_tex_path=current_tex_path,
        pdf_path=pdf_path,
        log_path=log_path,
        reason="Unable to fit the resume into one page within the allowed fitting levels.",
    )


def parse_page_count_from_log(log_text: str) -> int | None:
    match = re.search(r"Output written on .*\((\d+) page", log_text)
    if match is None:
        return None
    return int(match.group(1))


def _resolve_tex_binary(binary_name: str, *, search_dirs: tuple[Path, ...] = TEX_BIN_FALLBACK_DIRS) -> Path:
    resolved = shutil.which(binary_name)
    if resolved is not None:
        return Path(resolved)

    for search_dir in search_dirs:
        candidate = search_dir / binary_name
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"Unable to find '{binary_name}'. Checked PATH and fallback directories: "
        + ", ".join(str(path) for path in search_dirs)
    )


def _build_latex_env(latexmk_path: Path, *, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    path_parts = [str(latexmk_path.parent)]
    current_path = env.get("PATH", "")
    if current_path:
        path_parts.append(current_path)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


def _compile_latex(root_dir: Path, current_tex_path: Path, output_dir: Path) -> LatexCompileResult:
    relative_tex = current_tex_path.relative_to(root_dir)
    relative_output = output_dir.relative_to(root_dir)
    log_path = output_dir / "main.log"
    pdf_path = output_dir / "main.pdf"

    try:
        latexmk_path = _resolve_tex_binary("latexmk")
    except FileNotFoundError as exc:
        return LatexCompileResult(
            success=False,
            page_count=None,
            log_path=log_path,
            pdf_path=pdf_path,
            reason=str(exc),
        )

    command = [
        str(latexmk_path),
        "-pdf",
        "-jobname=main",
        f"-outdir={relative_output.as_posix()}",
        relative_tex.as_posix(),
    ]
    completed = subprocess.run(
        command,
        cwd=root_dir,
        check=False,
        capture_output=True,
        text=True,
        env=_build_latex_env(latexmk_path),
    )

    log_text = ""
    if log_path.exists():
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
    else:
        log_text = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    page_count = parse_page_count_from_log(log_text)
    reason = None if completed.returncode == 0 else (completed.stderr.strip() or "latexmk failed.")
    return LatexCompileResult(
        success=completed.returncode == 0,
        page_count=page_count,
        log_path=log_path,
        pdf_path=pdf_path,
        reason=reason,
    )


def _build_resume_document(cv_path: Path, jd_text: str) -> ResumeDocument:
    cv_text = cv_path.read_text(encoding="utf-8")
    header = _parse_header(cv_text)
    summary = _build_summary(_section_body(cv_text, "Professional Summary"), jd_text)
    work_entries = _parse_markdown_entries(_section_body(cv_text, "Work Experience"))
    project_entries = _parse_markdown_entries(_section_body(cv_text, "Projects"))
    engineering_entries = _parse_markdown_entries(_section_body(cv_text, "Engineering Experience"))
    education_entries = _parse_markdown_entries(_section_body(cv_text, "Education"))
    if not education_entries:
        raise ValueError("Education section is required in cv.md")

    design_team_entry = engineering_entries[0] if engineering_entries else None
    research_entry = _default_research_entry()
    skills = _parse_skill_groups(_section_body(cv_text, "Skills"))

    return ResumeDocument(
        name=header["name"],
        pronouns=DEFAULT_PRONOUNS,
        phone=header.get("phone", ""),
        email=header.get("email", ""),
        linkedin_url=header.get("linkedin_url", "https://www.linkedin.com/"),
        linkedin_label=header.get("linkedin_label", "LinkedIn"),
        summary=summary,
        skills=skills,
        education=_build_education_entry(education_entries[0]),
        work_entries=work_entries,
        project_entries=project_entries,
        design_team_entry=design_team_entry,
        research_entry=research_entry,
    )


def _parse_header(cv_text: str) -> dict[str, str]:
    lines = cv_text.splitlines()
    name_line = next((line for line in lines if line.startswith("# ")), "# Candidate")
    raw_name = name_line.removeprefix("# ").strip()
    name = raw_name.split("--")[-1].strip() if "--" in raw_name else raw_name
    header: dict[str, str] = {"name": name}
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            break
        match = re.match(r"\*\*(.+?):\*\*\s*(.+)", stripped)
        if match is None:
            continue
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        if key == "phone":
            header["phone"] = value
        elif key == "email":
            header["email"] = value
        elif key == "linkedin":
            header["linkedin_url"] = value
            header["linkedin_label"] = "LinkedIn"
    return header


def _section_body(markdown: str, title: str) -> str:
    match = re.search(
        rf"^## {re.escape(title)}\n(?P<body>.*?)(?=^## |\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group("body").strip() if match else ""


def _parse_markdown_entries(section_body: str) -> list[ResumeEntry]:
    entries: list[ResumeEntry] = []
    if not section_body.strip():
        return entries

    for match in re.finditer(
        r"^### (?P<title>[^\n]+)\n(?P<body>.*?)(?=^### |\Z)",
        section_body,
        flags=re.MULTILINE | re.DOTALL,
    ):
        heading = match.group("title").strip()
        title, context = _split_heading(heading)
        body_lines = [line.rstrip() for line in match.group("body").splitlines()]
        role = ""
        period = ""
        bullets: list[str] = []
        links: list[tuple[str, str]] = []

        for raw_line in body_lines:
            line = raw_line.strip()
            if not line:
                continue
            link_match = re.match(r"\*\*(.+?):\*\*\s*(https?://\S+)", line)
            if link_match is not None:
                links.append((link_match.group(1).strip(), link_match.group(2).strip()))
                continue
            if line.startswith("**") and line.endswith("**") and not role:
                role = line.strip("*").strip()
                continue
            if line.startswith("- "):
                bullets.append(line[2:].strip())
                continue
            if not period:
                period = line

        entries.append(
            ResumeEntry(
                title=title,
                context=context,
                role=role,
                period=period,
                bullets=bullets,
                links=links,
            )
        )

    return entries


def _split_heading(heading: str) -> tuple[str, str]:
    if " -- " not in heading:
        return heading.strip(), ""
    left, right = heading.split(" -- ", 1)
    return left.strip(), right.strip()


def _parse_skill_groups(section_body: str) -> list[SkillGroup]:
    groups: list[SkillGroup] = []
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        match = re.match(r"- \*\*(.+?):\*\*\s*(.+)", line)
        if match is None:
            continue
        values = [value.strip() for value in match.group(2).split(",") if value.strip()]
        groups.append(SkillGroup(label=match.group(1).strip(), values=values))
    return groups


def _build_education_entry(entry: ResumeEntry) -> EducationEntry:
    honors = entry.bullets[0] if entry.bullets else ""
    degree = entry.role or entry.context or "Education"
    location = entry.context if entry.role else ""
    return EducationEntry(
        school=entry.title,
        location=location,
        degree=degree,
        graduation=entry.period,
        honors=honors,
    )


def _default_research_entry() -> ResumeEntry:
    return ResumeEntry(
        title="Independent Web3 & AI Content Researcher",
        context="Self-Managed",
        role="",
        period="January 2025 -- Present",
        bullets=[
            "Research and write beginner-focused content on Web3 concepts, security awareness, and blockchain tools.",
            "Explore AI productivity and development tools, documenting features, use cases, and workflow takeaways.",
            "Publish recurring technical summaries and short-form educational posts on \\href{https://x.com/yc04bq}{\\textbf{X}} for online audiences.",
        ],
        links=[],
    )


def _build_summary(summary_body: str, jd_text: str) -> str:
    base_sentences = _split_sentences(summary_body)
    summary_sentences = base_sentences[:2] if base_sentences else [
        "Entry-level Software Engineer with hands-on product, systems, and full-stack development experience."
    ]
    keywords = _extract_keywords(jd_text)
    if keywords:
        summary_sentences.append(f"Strongest overlap for this role: {', '.join(keywords[:3])}.")
    return " ".join(summary_sentences)


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _extract_keywords(text: str) -> list[str]:
    canonical_terms = [
        "TypeScript",
        "JavaScript",
        "Python",
        "React",
        "dashboard",
        "API integration",
        "internal tooling",
        "workflow automation",
        "operational workflows",
        "cross-functional collaboration",
        "production systems",
        "observability",
        "data modeling",
        "background jobs",
        "AI",
        "Web3",
        "BLE",
        "Android",
    ]
    lower_text = text.lower()
    return [term for term in canonical_terms if term.lower() in lower_text][:8]


def _entry_relevance_score(entry: ResumeEntry, keywords: list[str]) -> int:
    haystack = " ".join([entry.title, entry.context, entry.role, *entry.bullets]).lower()
    return sum(1 for keyword in keywords if keyword.lower() in haystack)


def _render_latex_document(template: str, document: ResumeDocument, jd_text: str, fit_config: FitConfig) -> str:
    keywords = _extract_keywords(jd_text)
    summary = _fit_summary(document.summary, fit_config)
    skills = _select_skills(document.skills, jd_text, fit_config)
    work_entries = [_fit_entry(entry, fit_config.work_bullet_limit, fit_config.compact_text) for entry in document.work_entries]
    project_entries = _select_projects(document.project_entries, keywords, fit_config)
    design_team_entry = (
        _fit_entry(document.design_team_entry, fit_config.design_bullet_limit, fit_config.compact_text)
        if document.design_team_entry is not None and fit_config.include_design_team and fit_config.design_bullet_limit > 0
        else None
    )
    research_entry = (
        _fit_entry(document.research_entry, fit_config.research_bullet_limit, fit_config.compact_text)
        if document.research_entry is not None and fit_config.include_research and fit_config.research_bullet_limit > 0
        else None
    )

    replacements = {
        "<<ITEMSEP>>": fit_config.itemsep,
        "<<TOPSEP>>": fit_config.topsep,
        "<<SECTION_TOP_SPACING>>": fit_config.section_top_spacing,
        "<<SECTION_BOTTOM_SPACING>>": fit_config.section_bottom_spacing,
        "<<BLOCKSPACE>>": fit_config.blockspace,
        "<<BODY_FONT_COMMAND>>": fit_config.body_font_command,
        "<<HEADER_NAME>>": _latex_escape(document.name),
        "<<HEADER_PRONOUNS>>": _latex_escape(document.pronouns),
        "<<HEADER_PHONE>>": _latex_escape(document.phone),
        "<<HEADER_EMAIL>>": _latex_escape(document.email),
        "<<HEADER_LINKEDIN_URL>>": document.linkedin_url,
        "<<HEADER_LINKEDIN_LABEL>>": _latex_escape(document.linkedin_label),
        "<<SUMMARY_SECTION>>": _render_summary_section(summary),
        "<<SKILLS_SECTION>>": _render_skills_section(skills),
        "<<EDUCATION_SECTION>>": _render_education_section(document.education),
        "<<WORK_SECTION>>": _render_work_section(work_entries),
        "<<PROJECTS_SECTION>>": _render_projects_section(project_entries),
        "<<DESIGN_TEAM_SECTION>>": _render_design_team_section(design_team_entry),
        "<<RESEARCH_SECTION>>": _render_research_section(research_entry),
    }

    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


def _fit_summary(summary: str, fit_config: FitConfig) -> str:
    sentences = _split_sentences(summary)
    if fit_config.summary_sentences > 0:
        sentences = sentences[:fit_config.summary_sentences]
    text = " ".join(sentences)
    return _compact_text(text) if fit_config.compact_text else text


def _select_skills(skill_groups: list[SkillGroup], jd_text: str, fit_config: FitConfig) -> list[SkillGroup]:
    keywords = _extract_keywords(jd_text)
    scored_groups = []
    for index, group in enumerate(skill_groups):
        haystack = " ".join([group.label, *group.values]).lower()
        score = sum(1 for keyword in keywords if keyword.lower() in haystack)
        scored_groups.append((score, -index, group))

    scored_groups.sort(reverse=True)
    selected = [group for _score, _index, group in scored_groups[: fit_config.skill_group_limit]]
    selected.sort(key=lambda group: next(i for i, original in enumerate(skill_groups) if original.label == group.label))

    fitted: list[SkillGroup] = []
    for group in selected:
        values = group.values[: fit_config.skill_items_limit]
        if fit_config.compact_text:
            values = [_compact_skill_value(value) for value in values]
        fitted.append(SkillGroup(label=group.label, values=values))
    return fitted


def _select_projects(project_entries: list[ResumeEntry], keywords: list[str], fit_config: FitConfig) -> list[ResumeEntry]:
    ranked = sorted(project_entries, key=lambda entry: _entry_relevance_score(entry, keywords), reverse=True)
    selected = ranked[: fit_config.project_limit]
    return [_fit_entry(entry, fit_config.project_bullet_limit, fit_config.compact_text) for entry in selected]


def _fit_entry(entry: ResumeEntry, bullet_limit: int, compact_text: bool) -> ResumeEntry:
    bullets = entry.bullets[:bullet_limit] if bullet_limit > 0 else []
    if compact_text:
        bullets = [_compact_text(bullet) for bullet in bullets]
    return ResumeEntry(
        title=entry.title,
        context=entry.context,
        role=entry.role,
        period=entry.period,
        bullets=bullets,
        links=entry.links,
    )


def _compact_skill_value(value: str) -> str:
    replacements = {
        "responsive UI implementation": "responsive UI",
        "UX-focused interaction design": "interaction design",
        "application state handling": "state handling",
        "hardware-software integration": "hw-sw integration",
    }
    compacted = replacements.get(value, value)
    return compacted


def _compact_text(text: str) -> str:
    replacements = {
        "Built and maintained": "Built",
        "Designed and implemented": "Built",
        "Implemented and maintained": "Implemented",
        "real-time": "real-time",
        "production-oriented": "production",
        "cross-platform": "cross-platform",
        "frontend-native": "frontend-native",
        "state synchronization": "state sync",
        "support stable": "stabilize",
        "improved application": "improved",
        "Designed and tested": "Tested",
        "Designed and implemented custom": "Built",
    }
    compacted = text
    for old, new in replacements.items():
        compacted = compacted.replace(old, new)

    for delimiter in ("; ", ", and ", ", ", " to ", " for "):
        if len(compacted.split()) > 18 and delimiter in compacted:
            first_part = compacted.split(delimiter, 1)[0].strip()
            if len(first_part.split()) >= 8:
                compacted = first_part
                break

    compacted = re.sub(r"\s+", " ", compacted).strip()
    return compacted


def _latex_escape(text: str) -> str:
    replacements = {
        "\\": "\\textbackslash{}",
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
    }
    escaped = text
    for old, new in replacements.items():
        escaped = escaped.replace(old, new)
    return escaped


def _render_summary_section(summary: str) -> str:
    return "\n".join(
        [
            "\\section*{PROFESSIONAL SUMMARY}",
            _latex_escape(summary),
            "",
        ]
    )


def _render_skills_section(skill_groups: list[SkillGroup]) -> str:
    lines = ["\\section*{SKILLS}", "\\begin{itemize}"]
    for group in skill_groups:
        values = ", ".join(f"\\textbf{{{_latex_escape(value)}}}" for value in group.values)
        lines.append(f"    \\item \\textbf{{{_latex_escape(group.label)}:}} {values}")
    lines.append("\\end{itemize}")
    lines.append("")
    return "\n".join(lines)


def _render_education_section(education: EducationEntry) -> str:
    school_text = education.school
    if education.location:
        school_text = f"{school_text}, {education.location}"
    return "\n".join(
        [
            "\\section*{EDUCATION}",
            f"\\resumeheading{{\\textbf{{{_latex_escape(school_text)}}}}}{{\\textbf{{{_latex_escape(education.graduation)}}}}}",
            "\\begin{tabularx}{\\textwidth}{@{}Xr@{}}",
            f"\\textbf{{{_latex_escape(education.degree)}}} & \\textbf{{{_latex_escape(education.honors)}}}\\\\",
            "\\end{tabularx}",
            "",
        ]
    )


def _render_work_section(entries: list[ResumeEntry]) -> str:
    lines = ["\\section*{PROFESSIONAL WORK EXPERIENCE}", ""]
    for index, entry in enumerate(entries):
        title_line = _entry_heading_line(entry)
        lines.append(f"\\entryline{{{title_line}}}{{{_latex_escape(entry.period)}}}")
        lines.extend(_render_bullets(entry.bullets))
        if index != len(entries) - 1:
            lines.append("\\blockspace")
            lines.append("")
    lines.append("")
    return "\n".join(lines)


def _render_projects_section(entries: list[ResumeEntry]) -> str:
    if not entries:
        return ""
    lines = ["\\section*{TECHNICAL PROJECTS}", ""]
    for index, entry in enumerate(entries):
        title = _project_title_text(entry)
        lines.append(f"\\projectline{{{title}}}{{\\textbf{{Self-Managed}}}}{{{_latex_escape(entry.period)}}}")
        lines.extend(_render_bullets(entry.bullets))
        if index != len(entries) - 1:
            lines.append("\\blockspace")
            lines.append("")
    lines.append("")
    return "\n".join(lines)


def _render_design_team_section(entry: ResumeEntry | None) -> str:
    if entry is None:
        return ""
    lines = ["\\section*{ENGINEERING DESIGN TEAM}", ""]
    lines.append(f"\\entryline{{{_entry_heading_line(entry)}}}{{{_latex_escape(entry.period)}}}")
    lines.extend(_render_bullets(entry.bullets))
    lines.append("")
    return "\n".join(lines)


def _render_research_section(entry: ResumeEntry | None) -> str:
    if entry is None:
        return ""
    lines = ["\\section*{TECHNICAL CONTENT \\& RESEARCH}", ""]
    title = _latex_safe_project_title(entry)
    lines.append(f"\\projectline{{{title}}}{{\\textbf{{{_latex_escape(entry.context)}}}}}{{{_latex_escape(entry.period)}}}")
    lines.extend(_render_bullets(entry.bullets, escape=False))
    lines.append("")
    return "\n".join(lines)


def _entry_heading_line(entry: ResumeEntry) -> str:
    company = f"\\textbf{{{_latex_escape(entry.title)}}}"
    if entry.role:
        parts = [_latex_escape(entry.role), company]
        if entry.context:
            parts.append(_latex_escape(entry.context))
        return ", ".join(parts)
    if entry.context:
        return ", ".join([_latex_escape(entry.context), company])
    return company


def _project_title_text(entry: ResumeEntry) -> str:
    if not entry.links:
        return _latex_escape(entry.title)
    label, url = entry.links[0]
    _ = label
    return f"\\href{{{url}}}{{{_latex_escape(entry.title)}}}"


def _latex_safe_project_title(entry: ResumeEntry) -> str:
    if "\\href{" in entry.title:
        return entry.title
    return _latex_escape(entry.title)


def _render_bullets(bullets: list[str], *, escape: bool = True) -> list[str]:
    if not bullets:
        return []
    lines = ["\\begin{itemize}"]
    for bullet in bullets:
        text = _latex_escape(bullet) if escape else bullet
        lines.append(f"    \\item {text}")
    lines.append("\\end{itemize}")
    return lines
