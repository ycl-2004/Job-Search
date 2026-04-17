from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib import request

import task5_resume_pipeline as resume_pipeline


ROOT_DIR = Path(__file__).resolve().parent
UPSTREAM_DIR = ROOT_DIR / "Scan-job"
GUIDE_PATH = ROOT_DIR / "README.zh-TW.md"

CommandRunner = Callable[[list[str], Path], int]
ProcessOutputMode = str


@dataclass(slots=True)
class PendingJob:
    url: str
    company: str
    title: str
    location: str
    raw_line: str


@dataclass(slots=True)
class ProcessedJob:
    report_num: str
    url: str
    company: str
    title: str
    score: str
    pdf: str
    raw_line: str


@dataclass(slots=True)
class ApplicationRecord:
    report_num: str
    date: str
    company: str
    role: str
    score: str
    status: str
    pdf: str
    report_path: str
    notes: str


@dataclass(slots=True)
class ProcessOutputArtifacts:
    mode: ProcessOutputMode
    pdf_success: bool
    generated_paths: list[Path]


@dataclass(slots=True)
class ProcessRequest:
    output_mode: ProcessOutputMode = "html"
    pending_index: int = 0


@dataclass(slots=True)
class ScanTargetRequest:
    label: str
    focus_keys: list[str]
    focus_labels: list[str]
    focus_keywords: list[str]
    location_keys: list[str]
    location_labels: list[str]
    location_keywords: list[str]
    work_mode_keys: list[str]
    work_mode_labels: list[str]
    work_mode_keywords: list[str]


@dataclass(slots=True)
class ScanTargetState:
    label: str
    focus_keys: list[str]
    focus_labels: list[str]
    location_keys: list[str]
    location_labels: list[str]
    work_mode_keys: list[str]
    work_mode_labels: list[str]
    selected_on: str


@dataclass(slots=True)
class LatestScanRunSummary:
    date: str
    time: str
    target_label: str
    focus_labels: list[str]
    location_labels: list[str]
    work_mode_labels: list[str]
    companies_scanned: int
    total_jobs_found: int
    filtered_by_title: int
    filtered_by_location: int
    filtered_by_work_mode: int
    duplicates: int
    new_offers_discovered: int
    pending_queue_rebuilt: int
    scored_scan_matches: int
    daily_log_path: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return "\n".join(self._parts)


def main(
    argv: list[str] | None = None,
    *,
    command_runner: CommandRunner | None = None,
) -> int:
    args = list(argv or [])
    runner = command_runner or _run_command
    if not args:
        return _interactive_menu(runner)

    command = args[0].strip().lower()
    remaining = args[1:]

    if command in {"help", "-h", "--help", "guide", "說明"}:
        _print_help()
        return 0
    if command in {"scan", "scan-new-jobs", "掃描"}:
        return _scan_new_jobs(remaining, runner)
    if command in {"clean", "pipeline-clean", "clean-pipeline", "清理"}:
        return _clean_pipeline(runner)
    if command in {"process", "process-top", "run-one", "處理"}:
        try:
            process_request = _parse_process_request(remaining)
        except ValueError as exc:
            print(exc)
            print("")
            print(_help_text())
            return 1
        return _process_pipeline_job_by_index(
            runner,
            pending_index=process_request.pending_index,
            output_mode=process_request.output_mode,
        )
    if command in {"pipeline", "pipeline-status", "看盤面"}:
        _print_pipeline_status()
        return 0
    if command in {"dashboard", "job-dashboard", "index", "總表"}:
        _show_dashboard()
        return 0
    if command in {"outputs", "generated", "generated-outputs", "產物"}:
        _print_generated_outputs()
        return 0
    if command in {"maintenance", "diagnostics", "maint", "維護"}:
        return _run_maintenance_command(remaining, runner)

    if command in {"status", "狀態"}:
        _print_status()
        return 0
    if command in {"paths", "path", "路徑"}:
        _print_paths()
        return 0
    if command in {"bootstrap", "setup", "安裝", "初始化"}:
        install_dependencies = "--install" in remaining
        return _bootstrap_repo(runner, install_dependencies=install_dependencies)
    if command in {"resume", "latex-resume", "resume-pdf", "履歷"}:
        return _run_resume_command(remaining)
    if command in {"doctor", "verify", "pdf"}:
        return _run_repo_script(command, remaining, runner)

    print(_help_text())
    return 1


def _repo_dir() -> Path:
    return UPSTREAM_DIR


def _data_dir() -> Path:
    return _repo_dir() / "data"


def _pipeline_path() -> Path:
    return _data_dir() / "pipeline.md"


def _scan_history_path() -> Path:
    return _data_dir() / "scan-history.tsv"


def _applications_path() -> Path:
    return _data_dir() / "applications.md"


def _reports_dir() -> Path:
    return _repo_dir() / "reports"


def _output_dir() -> Path:
    return _repo_dir() / "output"


def _jds_dir() -> Path:
    return _repo_dir() / "jds"


def _tracker_additions_dir() -> Path:
    return _repo_dir() / "batch" / "tracker-additions"


def _cv_path() -> Path:
    return _repo_dir() / "cv.md"


def _profile_config_path() -> Path:
    return _repo_dir() / "config" / "profile.yml"


def _profile_overrides_path() -> Path:
    return _repo_dir() / "modes" / "_profile.md"


def _article_digest_path() -> Path:
    return _repo_dir() / "article-digest.md"


def _dashboard_path() -> Path:
    return _data_dir() / "job-dashboard.md"


def _scan_target_state_path() -> Path:
    return _data_dir() / "scan-target-profile.json"


def _latest_scan_run_path() -> Path:
    return _data_dir() / "latest-scan-run.json"


def _help_text() -> str:
    return "\n".join(
        [
            "Task 5: Scan-job Workflow",
            "用法:",
            "  task 5 scan                    依 target profile 掃描新職缺並更新 pipeline / scan history",
            "  task 5 clean                   清理 pipeline 重複項並刷新 dashboard",
            "  task 5 process [--index N] [--output html|latex]  處理指定待辦職缺（預設第一筆）",
            "  task 5 pipeline                顯示 pending / processed / latest scan 摘要",
            "  task 5 dashboard               產生並顯示整合總表（job dashboard）",
            "  task 5 outputs                 顯示最新 report / HTML / PDF / daily scan log 與資料路徑",
            "  task 5 resume [--jd-file PATH]  生成單頁 LaTeX 履歷 PDF",
            "  task 5 maintenance             進入維護 / 診斷子選單",
            "",
            "相容的維護命令仍可直接使用:",
            "  task 5 status | paths | bootstrap [--install] | doctor | verify | pdf | resume | guide",
        ]
    )


def _interactive_menu(runner: CommandRunner) -> int:
    last_exit_code = 0
    while True:
        print("Task 5: Scan-job Workflow")
        print("=================================")
        print("1. Scan new jobs - 選擇 target profile 掃描新職缺並更新 pipeline")
        print("2. Process pipeline job - 選擇要處理哪一筆待辦職缺，再選 HTML / LaTeX outputs")
        print("3. View pipeline status - 看 pending / processed / latest scan 結果")
        print("4. View generated outputs - 看最新 reports、HTML/PDF、daily scan log、tracker 路徑")
        print("5. Maintenance / diagnostics - doctor、verify、clean、init、repo path、help")
        print("6. Show job dashboard - 看整合總表與快速連結")
        print("7. Clean pipeline - 清理重複 pending / 標準化 layout")
        print("q. Quit")
        raw_choice = _safe_input("Select an option: ")
        if raw_choice is None:
            return last_exit_code

        choice = raw_choice.strip().lower()
        if choice in {"q", "quit", "exit"}:
            return last_exit_code
        if choice == "1":
            target_request = _prompt_scan_target_request()
            if target_request is None:
                last_exit_code = 0
            else:
                last_exit_code = _scan_new_jobs(_scan_args_from_target_request(target_request), runner)
                if last_exit_code == 0:
                    _save_scan_target_state(target_request)
        elif choice == "2":
            selected_job = _prompt_pipeline_job_selection()
            if selected_job is None:
                last_exit_code = 0
            else:
                output_mode = _prompt_process_output_mode()
                if output_mode is None:
                    last_exit_code = 0
                else:
                    last_exit_code = _process_pipeline_job(selected_job, runner, output_mode=output_mode)
        elif choice == "3":
            _print_pipeline_status()
            last_exit_code = 0
        elif choice == "4":
            _print_generated_outputs()
            last_exit_code = 0
        elif choice == "5":
            last_exit_code = _interactive_maintenance_menu(runner)
        elif choice == "6":
            _show_dashboard()
            last_exit_code = 0
        elif choice == "7":
            last_exit_code = _clean_pipeline(runner)
        else:
            print(_help_text())
            last_exit_code = 1

        print("")


def _interactive_maintenance_menu(runner: CommandRunner) -> int:
    last_exit_code = 0
    while True:
        print("Maintenance / Diagnostics")
        print("---------------------------------")
        print("1. Check integration status")
        print("2. Show isolated repo path")
        print("3. Initialize / update Career-Ops")
        print("4. Run doctor")
        print("5. Run verify")
        print("6. Clean pipeline + refresh dashboard")
        print("7. Show Chinese help")
        print("b. Back")
        raw_choice = _safe_input("Select an option: ")
        if raw_choice is None:
            return last_exit_code

        choice = raw_choice.strip().lower()
        if choice in {"b", "back"}:
            return last_exit_code
        if choice == "1":
            _print_status()
            last_exit_code = 0
        elif choice == "2":
            _print_paths()
            last_exit_code = 0
        elif choice == "3":
            last_exit_code = _bootstrap_repo(runner, install_dependencies=False)
        elif choice == "4":
            last_exit_code = _run_repo_script("doctor", [], runner)
        elif choice == "5":
            last_exit_code = _run_repo_script("verify", [], runner)
        elif choice == "6":
            last_exit_code = _clean_pipeline(runner)
        elif choice == "7":
            _print_help()
            last_exit_code = 0
        else:
            print(_help_text())
            last_exit_code = 1

        print("")


def _run_maintenance_command(args: list[str], runner: CommandRunner) -> int:
    if not args:
        return _interactive_maintenance_menu(runner)

    subcommand = args[0].strip().lower()
    remaining = args[1:]
    if subcommand in {"status", "狀態"}:
        _print_status()
        return 0
    if subcommand in {"paths", "path", "路徑"}:
        _print_paths()
        return 0
    if subcommand in {"bootstrap", "setup", "安裝", "初始化"}:
        install_dependencies = "--install" in remaining
        return _bootstrap_repo(runner, install_dependencies=install_dependencies)
    if subcommand in {"clean", "pipeline-clean", "clean-pipeline", "清理"}:
        return _clean_pipeline(runner)
    if subcommand in {"doctor", "verify", "pdf"}:
        return _run_repo_script(subcommand, remaining, runner)
    if subcommand in {"help", "guide", "說明"}:
        _print_help()
        return 0

    print(_help_text())
    return 1


def _print_help() -> None:
    print(_help_text())
    print("")
    print(f"繁體中文整合說明: {GUIDE_PATH}")


def _print_paths() -> None:
    print("Career-Ops 隔離路徑")
    print(f"  整合層: {ROOT_DIR}")
    print(f"  上游 repo 預設位置: {_repo_dir()}")
    print(f"  pipeline: {_pipeline_path()}")
    print(f"  scan history: {_scan_history_path()}")
    print(f"  applications tracker: {_applications_path()}")
    print(f"  job dashboard: {_dashboard_path()}")
    print(f"  latest scan run: {_latest_scan_run_path()}")
    print(f"  daily scan logs: {_data_dir() / 'scan-runs'}")
    print(f"  reports: {_reports_dir()}")
    print(f"  output: {_output_dir()}")
    print("  原則: 與 Career-Ops 相關的 clone、設定、輸出都留在 Career_ops/ 下面。")


def _print_status() -> None:
    repo_ready = _repo_ready()
    config_paths = (
        ("repo", _repo_dir()),
        ("package.json", _repo_dir() / "package.json"),
        ("config/profile.yml", _profile_config_path()),
        ("portals.yml", _repo_dir() / "portals.yml"),
        ("cv.md", _cv_path()),
        ("article-digest.md", _article_digest_path()),
        ("modes/_profile.md", _profile_overrides_path()),
    )

    print("Career-Ops 本地整合狀態")
    print(f"  Node.js: {_tool_status('node')}")
    print(f"  npm: {_tool_status('npm')}")
    print(f"  Go: {_tool_status('go')}")
    print(f"  上游 repo: {'已就緒' if repo_ready else '尚未下載'}")
    for label, path in config_paths:
        if label == "repo":
            print(f"  {label}: {path}")
            continue
        print(f"  {label}: {'存在' if path.exists() else '缺少'} ({path})")

    if not repo_ready:
        print("")
        print("下一步建議:")
        print("  1. 先執行 `task 5 bootstrap --install` 下載 repo 並安裝依賴")
        print("  2. 再執行 `task 5 doctor` 檢查缺的初始化檔案")
        print("  3. 最後補齊 `cv.md`、`config/profile.yml`、`portals.yml`、`article-digest.md`")


def _scan_new_jobs(extra_args: list[str], runner: CommandRunner) -> int:
    catalog: dict[str, object] | None = None
    target_request: ScanTargetRequest | None = None
    if not extra_args:
        catalog = _load_targeting_catalog()
        if catalog is not None:
            target_request = _default_scan_target_request(catalog)
            extra_args = _scan_args_from_target_request(target_request)
    exit_code = _run_repo_script("scan", extra_args, runner)
    if exit_code == 0:
        if target_request is not None:
            _save_scan_target_state(target_request)
        _refresh_dashboard_file()
    return exit_code


def _clean_pipeline(runner: CommandRunner) -> int:
    exit_code = _run_repo_script("clean-pipeline", [], runner)
    if exit_code == 0:
        _refresh_dashboard_file()
    return exit_code


def _print_pipeline_status() -> None:
    if not _repo_ready():
        _print_repo_not_ready()
        return

    pending_jobs, processed_jobs = _load_pipeline_state()
    scan_target_state = _load_scan_target_state()
    latest_scan_run = _load_latest_scan_run_summary()

    print("Pipeline Summary")
    print("---------------------------------")
    print(f"Pending jobs: {len(pending_jobs)}")
    print(f"Processed jobs: {len(processed_jobs)}")
    print("")

    if scan_target_state is None:
        print("Current target profile: Not recorded yet")
        print("Focus areas: Not set")
        print("Locations: Not set")
        print("Work modes: Not set")
    else:
        print(f"Current target profile: {scan_target_state.label}")
        print(f"Focus areas: {_format_scan_target_values(scan_target_state.focus_labels)}")
        print(f"Locations: {_format_scan_target_values(scan_target_state.location_labels)}")
        print(f"Work modes: {_format_scan_target_values(scan_target_state.work_mode_labels)}")
    print("")

    print("Top pending job:")
    if pending_jobs:
        top = pending_jobs[0]
        print(f"- {top.company} — {top.title}")
        if top.location:
            print(f"  Location: {top.location}")
        print(f"  {top.url}")
    else:
        print("- None")
    print("")

    print("Most recent processed:")
    if processed_jobs:
        latest = _latest_processed_job(processed_jobs)
        print(f"- {latest.company} — {latest.title}")
        print(f"  Score: {latest.score} | PDF: {latest.pdf}")
    else:
        print("- None")
    print("")

    print("Latest scan run:")
    if latest_scan_run is None:
        print("- No scan run summary available yet")
    else:
        timestamp = latest_scan_run.date
        if latest_scan_run.time:
            timestamp = f"{timestamp} {latest_scan_run.time}"
        print(f"- Completed at: {timestamp}")
        print(f"- Target profile: {latest_scan_run.target_label or 'Unknown'}")
        print(f"- Current scan matches: {latest_scan_run.scored_scan_matches}")
        print(f"- Pending queue rebuilt: {latest_scan_run.pending_queue_rebuilt}")
        print(f"- New unique offers added to history: {latest_scan_run.new_offers_discovered}")
        if latest_scan_run.daily_log_path:
            print(f"- Daily scan log: {(_repo_dir() / latest_scan_run.daily_log_path) if not latest_scan_run.daily_log_path.startswith('/') else latest_scan_run.daily_log_path}")


def _print_generated_outputs() -> None:
    if not _repo_ready():
        _print_repo_not_ready()
        return

    latest_report = _latest_file(_reports_dir(), "*.md")
    latest_html = _latest_file(_output_dir(), "*.html")
    latest_pdf = _latest_file(_output_dir(), "*.pdf")
    latest_scan_run = _load_latest_scan_run_summary()
    latest_scan_log = None
    if latest_scan_run and latest_scan_run.daily_log_path:
        latest_scan_log = _repo_dir() / latest_scan_run.daily_log_path

    print("Generated Outputs")
    print("---------------------------------")
    print("Latest report:")
    print(f"- {latest_report if latest_report else 'None'}")
    print("")
    print("Latest tailored files:")
    print(f"- HTML: {latest_html if latest_html else 'None'}")
    print(f"- PDF: {latest_pdf if latest_pdf else 'None'}")
    print("")
    print("Tracker:")
    print(f"- {_applications_path()}")
    print("Dashboard:")
    print(f"- {_dashboard_path()}")
    print("Pipeline:")
    print(f"- {_pipeline_path()}")
    print("Scan logs:")
    print(f"- Latest daily scan log: {latest_scan_log if latest_scan_log else 'None'}")
    print(f"- Machine dedup history: {_scan_history_path()}")


def _show_dashboard() -> None:
    if not _repo_ready():
        _print_repo_not_ready()
        return

    dashboard_path = _refresh_dashboard_file()
    print(f"Job dashboard: {dashboard_path}")
    print("")
    print(dashboard_path.read_text(encoding="utf-8"))


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _load_targeting_catalog() -> dict[str, object] | None:
    if not _repo_ready():
        _print_repo_not_ready()
        return None

    script_path = _repo_dir() / "targeting-config.mjs"
    if not script_path.exists():
        print(f"缺少 targeting config helper: {script_path}")
        return None

    completed = subprocess.run(
        ["node", script_path.name],
        cwd=_repo_dir(),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        print(f"讀取 target profile 設定失敗: {message}")
        return None

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        print(f"targeting config JSON 解析失敗: {exc}")
        return None

    return payload


def _catalog_entries_by_key(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        str(entry.get("key", "")).strip(): entry
        for entry in entries
        if str(entry.get("key", "")).strip()
    }


def _scan_target_labels_for_keys(entries: list[dict[str, object]], selected_keys: list[str]) -> list[str]:
    entry_map = _catalog_entries_by_key(entries)
    labels: list[str] = []
    for key in selected_keys:
        entry = entry_map.get(key)
        labels.append(str(entry.get("label") or key).strip() if entry else key)
    return _unique_preserve_order(labels)


def _build_scan_target_state(
    request: ScanTargetRequest,
) -> ScanTargetState:
    return ScanTargetState(
        label=request.label or "Unknown target profile",
        focus_keys=list(request.focus_keys),
        focus_labels=list(request.focus_labels) or list(request.focus_keys),
        location_keys=list(request.location_keys),
        location_labels=list(request.location_labels) or list(request.location_keys),
        work_mode_keys=list(request.work_mode_keys),
        work_mode_labels=list(request.work_mode_labels) or list(request.work_mode_keys),
        selected_on=_today_iso(),
    )


def _save_scan_target_state(
    request: ScanTargetRequest,
) -> None:
    state = _build_scan_target_state(request)
    payload = {
        "label": state.label,
        "focus_keys": state.focus_keys,
        "focus_labels": state.focus_labels,
        "location_keys": state.location_keys,
        "location_labels": state.location_labels,
        "work_mode_keys": state.work_mode_keys,
        "work_mode_labels": state.work_mode_labels,
        "selected_on": state.selected_on,
    }
    state_path = _scan_target_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_scan_target_state() -> ScanTargetState | None:
    state_path = _scan_target_state_path()
    if not state_path.exists():
        return None

    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    def read_list(name: str) -> list[str]:
        values = payload.get(name, [])
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    focus_keys = read_list("focus_keys")
    location_keys = read_list("location_keys")
    work_mode_keys = read_list("work_mode_keys")
    focus_labels = read_list("focus_labels") or focus_keys
    location_labels = read_list("location_labels") or location_keys
    work_mode_labels = read_list("work_mode_labels") or work_mode_keys
    label = str(payload.get("label") or "").strip() or "Unknown target profile"
    selected_on = str(payload.get("selected_on") or "").strip()
    return ScanTargetState(
        label=label,
        focus_keys=focus_keys,
        focus_labels=focus_labels,
        location_keys=location_keys,
        location_labels=location_labels,
        work_mode_keys=work_mode_keys,
        work_mode_labels=work_mode_labels,
        selected_on=selected_on,
    )


def _format_scan_target_values(values: list[str]) -> str:
    return ", ".join(values) if values else "Not set"


def _load_latest_scan_run_summary() -> LatestScanRunSummary | None:
    summary_path = _latest_scan_run_path()
    if not summary_path.exists():
        return None

    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    def read_list(*names: str) -> list[str]:
        values = []
        for name in names:
            if name in payload:
                values = payload.get(name, [])
                break
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value).strip()]

    def read_int(*names: str) -> int:
        value = 0
        for name in names:
            if name in payload:
                value = payload.get(name, 0)
                break
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    date = str(payload.get("date") or "").strip()
    time = str(payload.get("time") or "").strip()
    if not date:
        return None

    return LatestScanRunSummary(
        date=date,
        time=time,
        target_label=str(payload.get("target_label") or payload.get("targetLabel") or "").strip(),
        focus_labels=read_list("focus_labels", "focusLabels"),
        location_labels=read_list("location_labels", "locationLabels"),
        work_mode_labels=read_list("work_mode_labels", "workModeLabels"),
        companies_scanned=read_int("companies_scanned", "companiesScanned"),
        total_jobs_found=read_int("total_jobs_found", "totalJobsFound"),
        filtered_by_title=read_int("filtered_by_title", "filteredByTitle"),
        filtered_by_location=read_int("filtered_by_location", "filteredByLocation"),
        filtered_by_work_mode=read_int("filtered_by_work_mode", "filteredByWorkMode"),
        duplicates=read_int("duplicates"),
        new_offers_discovered=read_int("new_offers_discovered", "newOffersDiscovered"),
        pending_queue_rebuilt=read_int("pending_queue_rebuilt", "pendingQueueRebuilt"),
        scored_scan_matches=read_int("scored_scan_matches", "scoredScanMatches"),
        daily_log_path=str(payload.get("daily_log_path") or payload.get("dailyLogPath") or "").strip(),
    )


def _resolve_scan_target_request(
    catalog: dict[str, object],
    *,
    label: str,
    focus_keys: list[str],
    location_keys: list[str],
    work_mode_keys: list[str],
) -> ScanTargetRequest:
    focus_entries = _catalog_entries_by_key(list(catalog.get("focus_areas", [])))
    location_entries = _catalog_entries_by_key(list(catalog.get("locations", [])))
    work_mode_entries = _catalog_entries_by_key(list(catalog.get("work_modes", [])))

    def collect_keywords(selected_keys: list[str], entry_map: dict[str, dict[str, object]]) -> list[str]:
        keywords: list[str] = []
        for key in selected_keys:
            entry = entry_map.get(key)
            if not entry:
                continue
            keywords.extend(str(keyword).strip() for keyword in list(entry.get("keywords", [])))
        return _unique_preserve_order(keywords)

    return ScanTargetRequest(
        label=label,
        focus_keys=focus_keys,
        focus_labels=_scan_target_labels_for_keys(list(catalog.get("focus_areas", [])), focus_keys),
        focus_keywords=collect_keywords(focus_keys, focus_entries),
        location_keys=location_keys,
        location_labels=_scan_target_labels_for_keys(list(catalog.get("locations", [])), location_keys),
        location_keywords=collect_keywords(location_keys, location_entries),
        work_mode_keys=work_mode_keys,
        work_mode_labels=_scan_target_labels_for_keys(list(catalog.get("work_modes", [])), work_mode_keys),
        work_mode_keywords=collect_keywords(work_mode_keys, work_mode_entries),
    )


def _default_scan_target_request(catalog: dict[str, object]) -> ScanTargetRequest:
    saved_profiles = _catalog_entries_by_key(list(catalog.get("saved_profiles", [])))
    default_key = str(catalog.get("default_saved_profile", "")).strip()
    if default_key and default_key in saved_profiles:
        saved = saved_profiles[default_key]
        return _resolve_scan_target_request(
            catalog,
            label=str(saved.get("label") or saved.get("key") or "Default target profile"),
            focus_keys=list(saved.get("focus_areas", [])),
            location_keys=list(saved.get("locations", [])),
            work_mode_keys=list(saved.get("work_modes", [])),
        )

    focus_keys = [str(entry.get("key")).strip() for entry in list(catalog.get("focus_areas", [])) if str(entry.get("key", "")).strip()]
    location_keys = [str(entry.get("key")).strip() for entry in list(catalog.get("locations", [])) if str(entry.get("key", "")).strip()]
    work_mode_keys = [str(entry.get("key")).strip() for entry in list(catalog.get("work_modes", [])) if str(entry.get("key", "")).strip()]
    return _resolve_scan_target_request(
        catalog,
        label="Default broad target profile",
        focus_keys=focus_keys,
        location_keys=location_keys,
        work_mode_keys=work_mode_keys,
    )


def _auto_generated_scan_target_request(catalog: dict[str, object]) -> ScanTargetRequest:
    focus_entries = list(catalog.get("focus_areas", []))
    location_entries = list(catalog.get("locations", []))
    work_mode_entries = list(catalog.get("work_modes", []))

    cv_text = _cv_path().read_text(encoding="utf-8") if _cv_path().exists() else ""
    combined_text = " ".join(
        [
            cv_text.lower(),
            " ".join(str(role).lower() for role in list(catalog.get("target_roles_primary", []))),
            str(catalog.get("headline", "")).lower(),
        ]
    )
    location_text = " ".join(
        [
            str(catalog.get("candidate_location", "")).lower(),
            str(catalog.get("location_flexibility", "")).lower(),
            str(catalog.get("onsite_availability", "")).lower(),
        ]
    )

    focus_keys = [
        str(entry.get("key")).strip()
        for entry in focus_entries
        if any(str(keyword).lower() in combined_text for keyword in list(entry.get("keywords", [])))
    ]
    location_keys = [
        str(entry.get("key")).strip()
        for entry in location_entries
        if any(str(keyword).lower() in location_text for keyword in list(entry.get("keywords", [])))
    ]
    work_mode_keys = [
        str(entry.get("key")).strip()
        for entry in work_mode_entries
        if any(str(keyword).lower() in location_text for keyword in list(entry.get("keywords", [])))
    ]

    default_request = _default_scan_target_request(catalog)
    if not focus_keys:
        focus_keys = default_request.focus_keys
    if not location_keys:
        location_keys = default_request.location_keys
    if not work_mode_keys:
        work_mode_keys = default_request.work_mode_keys

    return _resolve_scan_target_request(
        catalog,
        label="Auto-generated from CV + profile",
        focus_keys=_unique_preserve_order(focus_keys),
        location_keys=_unique_preserve_order(location_keys),
        work_mode_keys=_unique_preserve_order(work_mode_keys),
    )


def _prompt_select_one(
    title: str,
    entries: list[dict[str, object]],
    *,
    allow_back: bool = True,
) -> dict[str, object] | None:
    if not entries:
        return None

    while True:
        print(title)
        print("---------------------------------")
        for index, entry in enumerate(entries, start=1):
            print(f"{index}. {entry.get('label') or entry.get('key')}")
        if allow_back:
            print("b. Back")
        raw_choice = _safe_input("Select one option: ")
        if raw_choice is None:
            return None

        choice = raw_choice.strip().lower()
        if allow_back and choice in {"b", "back", "q", "quit", "exit"}:
            return None
        if choice.isdigit():
            selected_index = int(choice) - 1
            if 0 <= selected_index < len(entries):
                return entries[selected_index]
        print("Invalid selection. Please choose one of the listed options.")
        print("")


def _prompt_multi_select(
    title: str,
    entries: list[dict[str, object]],
    *,
    allow_back: bool = True,
    allow_skip: bool = False,
    default_all: bool = True,
) -> list[str] | None:
    if not entries:
        return [] if allow_skip else None

    keys = [str(entry.get("key")).strip() for entry in entries if str(entry.get("key", "")).strip()]
    labels = {str(entry.get("key")).strip(): str(entry.get("label") or entry.get("key")).strip() for entry in entries}

    while True:
        print(title)
        print("---------------------------------")
        for index, key in enumerate(keys, start=1):
            print(f"{index}. {labels[key]}")
        if allow_skip:
            print("s. Skip filter")
        if allow_back:
            print("b. Back")
        prompt = "Select numbers (comma-separated"
        if default_all:
            prompt += ", Enter = all"
        prompt += "): "
        raw_choice = _safe_input(prompt)
        if raw_choice is None:
            return None

        choice = raw_choice.strip().lower()
        if not choice and default_all:
            return keys
        if allow_skip and choice in {"s", "skip"}:
            return []
        if allow_back and choice in {"b", "back", "q", "quit", "exit"}:
            return None

        parts = [part.strip() for part in choice.split(",") if part.strip()]
        if parts and all(part.isdigit() for part in parts):
            selected: list[str] = []
            valid = True
            for part in parts:
                selected_index = int(part) - 1
                if not 0 <= selected_index < len(keys):
                    valid = False
                    break
                selected.append(keys[selected_index])
            if valid:
                return _unique_preserve_order(selected)

        print("Invalid selection. Please use comma-separated numbers from the list.")
        print("")


def _prompt_scan_target_request() -> ScanTargetRequest | None:
    catalog = _load_targeting_catalog()
    if catalog is None:
        return None

    saved_profiles = list(catalog.get("saved_profiles", []))

    while True:
        print("Choose scan target profile")
        print("---------------------------------")
        print("1. Use current default target profile")
        print("2. Auto-generate from CV + profile")
        print("3. Choose saved target profile")
        print("4. Custom focus area / location / work mode")
        print("b. Back")
        raw_choice = _safe_input("Select scan target mode: ")
        if raw_choice is None:
            return None

        choice = raw_choice.strip().lower()
        if choice in {"1", "default"}:
            return _default_scan_target_request(catalog)
        if choice in {"2", "auto", "cv", "profile"}:
            return _auto_generated_scan_target_request(catalog)
        if choice in {"3", "saved"}:
            saved = _prompt_select_one("Saved target profiles", saved_profiles)
            if saved is None:
                continue
            return _resolve_scan_target_request(
                catalog,
                label=str(saved.get("label") or saved.get("key") or "Saved target profile"),
                focus_keys=list(saved.get("focus_areas", [])),
                location_keys=list(saved.get("locations", [])),
                work_mode_keys=list(saved.get("work_modes", [])),
            )
        if choice in {"4", "custom"}:
            focus_keys = _prompt_multi_select("Choose focus areas", list(catalog.get("focus_areas", [])))
            if focus_keys is None:
                continue
            location_keys = _prompt_multi_select("Choose target locations", list(catalog.get("locations", [])))
            if location_keys is None:
                continue
            work_mode_keys = _prompt_multi_select("Choose work modes", list(catalog.get("work_modes", [])))
            if work_mode_keys is None:
                continue
            return _resolve_scan_target_request(
                catalog,
                label="Custom target profile",
                focus_keys=focus_keys,
                location_keys=location_keys,
                work_mode_keys=work_mode_keys,
            )
        if choice in {"b", "back", "q", "quit", "exit"}:
            return None

        print("Invalid selection. Please choose one of the target profile modes.")
        print("")


def _scan_args_from_target_request(request: ScanTargetRequest) -> list[str]:
    args: list[str] = []
    if request.label:
        args.extend(["--target-label", request.label])
    if request.focus_labels:
        args.extend(["--focus-labels", ",".join(request.focus_labels)])
    if request.focus_keywords:
        args.extend(["--focus-keywords", ",".join(request.focus_keywords)])
    if request.location_labels:
        args.extend(["--location-labels", ",".join(request.location_labels)])
    if request.location_keywords:
        args.extend(["--location-keywords", ",".join(request.location_keywords)])
    if request.work_mode_labels:
        args.extend(["--work-mode-labels", ",".join(request.work_mode_labels)])
    if request.work_mode_keywords:
        args.extend(["--work-mode-keywords", ",".join(request.work_mode_keywords)])
    return args


def _parse_process_request(args: list[str]) -> ProcessRequest:
    request = ProcessRequest()
    index_value: int | None = None
    output_value: str | None = None
    i = 0

    while i < len(args):
        arg = args[i].strip()
        if arg == "--output":
            if i + 1 >= len(args):
                raise ValueError("Usage: task 5 process [--index N] [--output html|latex]")
            output_value = args[i + 1].strip().lower()
            i += 2
            continue
        if arg.startswith("--output="):
            output_value = arg.split("=", 1)[1].strip().lower()
            i += 1
            continue
        if arg == "--index":
            if i + 1 >= len(args):
                raise ValueError("Usage: task 5 process [--index N] [--output html|latex]")
            try:
                index_value = int(args[i + 1].strip())
            except ValueError as exc:
                raise ValueError("Pipeline index must be a positive integer.") from exc
            i += 2
            continue
        if arg.startswith("--index="):
            try:
                index_value = int(arg.split("=", 1)[1].strip())
            except ValueError as exc:
                raise ValueError("Pipeline index must be a positive integer.") from exc
            i += 1
            continue
        raise ValueError("Usage: task 5 process [--index N] [--output html|latex]")

    if output_value is not None:
        if output_value not in {"html", "latex"}:
            raise ValueError("Output backend must be one of: html, latex")
        request.output_mode = output_value

    if index_value is not None:
        if index_value < 1:
            raise ValueError("Pipeline index must be a positive integer.")
        request.pending_index = index_value - 1

    return request


def _parse_process_output_mode(args: list[str]) -> ProcessOutputMode:
    return _parse_process_request(args).output_mode


def _prompt_pipeline_job_selection() -> PendingJob | None:
    if not _repo_ready():
        _print_repo_not_ready()
        return None

    pending_jobs, _processed_jobs = _load_pipeline_state()
    if not pending_jobs:
        print("Pipeline 沒有待處理職缺。先執行 `task 5 scan`。")
        return None

    while True:
        print("Choose pipeline job")
        print("---------------------------------")
        print("1. Auto process top pending job")
        print("2. Choose a pending job from all pending jobs")
        print("3. Filter pending jobs by keyword / location / work mode")
        print("b. Back")
        raw_choice = _safe_input("Select job source: ")
        if raw_choice is None:
            return None

        choice = raw_choice.strip().lower()
        if choice in {"1", "top", "auto"}:
            return pending_jobs[0]
        if choice in {"2", "custom", "pick"}:
            return _prompt_pending_job_choice(pending_jobs)
        if choice in {"3", "filter"}:
            return _prompt_filtered_pending_job_choice(pending_jobs)
        if choice in {"b", "back", "q", "quit", "exit"}:
            return None

        print("Invalid selection. Please choose top, custom, filter, or back.")
        print("")


def _prompt_pending_job_choice(pending_jobs: list[PendingJob], *, title: str = "Pending jobs") -> PendingJob | None:
    while True:
        print(title)
        print("---------------------------------")
        for index, job in enumerate(pending_jobs, start=1):
            suffix = f" | {job.location}" if job.location else ""
            print(f"{index}. {job.company} | {job.title}{suffix}")
        print("b. Back")
        raw_choice = _safe_input("Select pending job number: ")
        if raw_choice is None:
            return None

        choice = raw_choice.strip().lower()
        if choice in {"b", "back", "q", "quit", "exit"}:
            return None
        if choice.isdigit():
            selected_index = int(choice) - 1
            if 0 <= selected_index < len(pending_jobs):
                return pending_jobs[selected_index]

        print("Invalid job number. Please choose one of the listed pending jobs.")
        print("")


def _job_matches_catalog_keywords(job: PendingJob, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{job.company} {job.title} {job.location}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _filter_pending_jobs(
    pending_jobs: list[PendingJob],
    *,
    keyword_query: str,
    location_keywords: list[str],
    work_mode_keywords: list[str],
) -> list[PendingJob]:
    keyword_terms = [term.strip().lower() for term in re.split(r"[,\s]+", keyword_query) if term.strip()]
    filtered: list[PendingJob] = []
    for job in pending_jobs:
        haystack = f"{job.company} {job.title} {job.location}".lower()
        if keyword_terms and not all(term in haystack for term in keyword_terms):
            continue
        if not _job_matches_catalog_keywords(job, location_keywords):
            continue
        if not _job_matches_catalog_keywords(job, work_mode_keywords):
            continue
        filtered.append(job)
    return filtered


def _prompt_filtered_pending_job_choice(pending_jobs: list[PendingJob]) -> PendingJob | None:
    catalog = _load_targeting_catalog()
    if catalog is None:
        return None

    keyword_query = (_safe_input("Keyword filter for company/title/location (Enter to skip): ") or "").strip()
    location_keys = _prompt_multi_select(
        "Filter by locations",
        list(catalog.get("locations", [])),
        allow_skip=True,
        default_all=False,
    )
    if location_keys is None:
        return None
    work_mode_keys = _prompt_multi_select(
        "Filter by work modes",
        list(catalog.get("work_modes", [])),
        allow_skip=True,
        default_all=False,
    )
    if work_mode_keys is None:
        return None

    location_map = _catalog_entries_by_key(list(catalog.get("locations", [])))
    work_mode_map = _catalog_entries_by_key(list(catalog.get("work_modes", [])))
    location_keywords = _unique_preserve_order(
        [
            str(keyword).strip()
            for key in location_keys
            for keyword in list(location_map.get(key, {}).get("keywords", []))
        ]
    )
    work_mode_keywords = _unique_preserve_order(
        [
            str(keyword).strip()
            for key in work_mode_keys
            for keyword in list(work_mode_map.get(key, {}).get("keywords", []))
        ]
    )

    filtered_jobs = _filter_pending_jobs(
        pending_jobs,
        keyword_query=keyword_query,
        location_keywords=location_keywords,
        work_mode_keywords=work_mode_keywords,
    )
    if not filtered_jobs:
        print("No pending jobs matched the selected filters.")
        print("")
        return None

    return _prompt_pending_job_choice(filtered_jobs, title="Filtered pending jobs")


def _prompt_process_output_mode() -> ProcessOutputMode | None:
    while True:
        print("Choose output backend")
        print("---------------------------------")
        print("1. HTML -> PDF (current default)")
        print("2. LaTeX one-page PDF")
        print("b. Back")
        raw_choice = _safe_input("Select output backend: ")
        if raw_choice is None:
            return None

        choice = raw_choice.strip().lower()
        if choice in {"1", "html"}:
            return "html"
        if choice in {"2", "latex", "tex"}:
            return "latex"
        if choice in {"b", "back", "q", "quit", "exit"}:
            return None

        print("Invalid output backend. Please choose html or latex.")
        print("")


def _process_pipeline_job_by_index(
    runner: CommandRunner,
    *,
    pending_index: int = 0,
    output_mode: ProcessOutputMode = "html",
) -> int:
    if not _repo_ready():
        _print_repo_not_ready()
        return 1

    pending_jobs, _processed_jobs = _load_pipeline_state()
    if not pending_jobs:
        print("Pipeline 沒有待處理職缺。先執行 `task 5 scan`。")
        return 0

    if pending_index < 0 or pending_index >= len(pending_jobs):
        print(f"Pipeline index 超出範圍。目前共有 {len(pending_jobs)} 筆待辦職缺。")
        return 1

    return _process_pipeline_job(
        pending_jobs[pending_index],
        runner,
        output_mode=output_mode,
        pending_index=pending_index,
    )


def _process_top_pipeline_job(runner: CommandRunner, *, output_mode: ProcessOutputMode = "html") -> int:
    return _process_pipeline_job_by_index(runner, pending_index=0, output_mode=output_mode)


def _process_pipeline_job(
    job: PendingJob,
    runner: CommandRunner,
    *,
    output_mode: ProcessOutputMode = "html",
    pending_index: int | None = None,
) -> int:
    if pending_index == 0:
        print("Processing top pipeline job...")
    elif pending_index is None:
        print("Processing selected pipeline job...")
    else:
        print(f"Processing pipeline job #{pending_index + 1}...")
    print(f"  Output backend: {output_mode}")
    print(f"  Company: {job.company}")
    print(f"  Role: {job.title}")
    if job.location:
        print(f"  Location: {job.location}")
    print(f"  URL: {job.url}")

    try:
        posting = _load_job_posting(job)
    except Exception as exc:
        print(f"無法載入職缺內容: {exc}")
        return 1

    _jds_dir().mkdir(parents=True, exist_ok=True)
    _reports_dir().mkdir(parents=True, exist_ok=True)
    _output_dir().mkdir(parents=True, exist_ok=True)
    _tracker_additions_dir().mkdir(parents=True, exist_ok=True)

    today = _today_iso()
    report_num = _next_report_num()
    candidate_slug = _candidate_slug()
    company_slug = _slugify(job.company)
    role_slug = _slugify(job.title)

    jd_path = _jds_dir() / f"{company_slug}-{role_slug}-{today}.md"
    report_path = _reports_dir() / f"{report_num:03d}-{company_slug}-{role_slug}-{today}.md"
    html_path = _output_dir() / f"cv-{candidate_slug}-{company_slug}-{role_slug}-{today}.html"
    pdf_path = _output_dir() / f"cv-{candidate_slug}-{company_slug}-{role_slug}-{today}.pdf"

    jd_path.write_text(_render_jd_snapshot(posting), encoding="utf-8")
    evaluation = _evaluate_posting(posting)
    report_path.write_text(_render_report(posting, evaluation, report_num, pdf_path), encoding="utf-8")
    output_artifacts = _generate_process_output(
        posting=posting,
        evaluation=evaluation,
        jd_path=jd_path,
        html_path=html_path,
        pdf_path=pdf_path,
        runner=runner,
        output_mode=output_mode,
    )
    pdf_success = output_artifacts.pdf_success

    _ensure_applications_tracker()
    tsv_path = _tracker_additions_dir() / f"{report_num:03d}-{company_slug}-{role_slug}.tsv"
    tsv_path.write_text(
        "\t".join(
            [
                str(report_num),
                today,
                job.company,
                job.title,
                "Evaluated",
                f"{evaluation['overall_score']:.1f}/5",
                "✅" if pdf_success else "❌",
                f"[{report_num:03d}](reports/{report_path.name})",
                evaluation["notes"],
            ]
        ),
        encoding="utf-8",
    )

    merge_exit_code = runner(["node", "merge-tracker.mjs", "--verify"], _repo_dir())
    if merge_exit_code != 0:
        print("tracker merge 失敗，待辦狀態暫時保留。")
        return merge_exit_code

    _mark_pipeline_job_processed(
        job,
        report_num=report_num,
        score=f"{evaluation['overall_score']:.1f}/5",
        pdf_success=pdf_success,
    )
    _refresh_dashboard_file()

    print("")
    print("Processing complete.")
    print("")
    print(f"Job: {job.company} — {job.title}")
    print("")
    print("Generated:")
    print(f"- {report_path}")
    for path in output_artifacts.generated_paths:
        print(f"- {path}")
    print(f"- {_applications_path()} updated")
    print(f"- {_dashboard_path()} refreshed")
    print("")
    print("Pipeline status:")
    print("Pendientes -> Procesadas")
    return 0


def _generate_process_output(
    *,
    posting: dict[str, str],
    evaluation: dict[str, object],
    jd_path: Path,
    html_path: Path,
    pdf_path: Path,
    runner: CommandRunner,
    output_mode: ProcessOutputMode,
) -> ProcessOutputArtifacts:
    if output_mode == "latex":
        return _generate_latex_process_output(jd_path=jd_path, pdf_path=pdf_path)
    return _generate_html_process_output(
        posting=posting,
        evaluation=evaluation,
        html_path=html_path,
        pdf_path=pdf_path,
        runner=runner,
    )


def _generate_html_process_output(
    *,
    posting: dict[str, str],
    evaluation: dict[str, object],
    html_path: Path,
    pdf_path: Path,
    runner: CommandRunner,
) -> ProcessOutputArtifacts:
    html_path.write_text(_render_tailored_html(posting, evaluation), encoding="utf-8")

    pdf_command = [
        "npm",
        "run",
        "pdf",
        "--",
        str(html_path.relative_to(_repo_dir())),
        str(pdf_path.relative_to(_repo_dir())),
        f"--format={_paper_format(posting)}",
    ]
    pdf_exit_code = runner(pdf_command, _repo_dir())
    return ProcessOutputArtifacts(
        mode="html",
        pdf_success=pdf_exit_code == 0,
        generated_paths=[html_path, pdf_path],
    )


def _generate_latex_process_output(*, jd_path: Path, pdf_path: Path) -> ProcessOutputArtifacts:
    generated_paths: list[Path] = []
    tex_output_path = pdf_path.with_suffix(".tex")
    log_output_path = pdf_path.with_suffix(".log")

    try:
        result = resume_pipeline.run_resume_pipeline(ROOT_DIR, jd_path=jd_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"LaTeX output failed: {exc}")
        return ProcessOutputArtifacts(mode="latex", pdf_success=False, generated_paths=[pdf_path])

    if result.current_tex_path.exists():
        shutil.copyfile(result.current_tex_path, tex_output_path)
        generated_paths.append(tex_output_path)
    if result.log_path.exists():
        shutil.copyfile(result.log_path, log_output_path)
        generated_paths.append(log_output_path)

    if not result.success:
        print("LaTeX output failed.")
        print(f"  Reason: {result.reason}")
        print(f"  Working TeX: {result.current_tex_path}")
        print(f"  Log: {result.log_path}")
        print(f"  Pages: {result.page_count if result.page_count is not None else 'unknown'}")
        return ProcessOutputArtifacts(
            mode="latex",
            pdf_success=False,
            generated_paths=generated_paths + [pdf_path],
        )

    shutil.copyfile(result.pdf_path, pdf_path)
    return ProcessOutputArtifacts(
        mode="latex",
        pdf_success=True,
        generated_paths=generated_paths + [pdf_path],
    )


def _run_resume_command(args: list[str]) -> int:
    jd_path = _parse_resume_jd_path(args)
    try:
        result = resume_pipeline.run_resume_pipeline(ROOT_DIR, jd_path=jd_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Resume pipeline error: {exc}")
        return 1

    if result.success:
        print("Resume pipeline complete.")
        print(f"  Current JD: {result.current_jd_path}")
        print(f"  Working TeX: {result.current_tex_path}")
        print(f"  PDF: {result.pdf_path}")
        print(f"  Log: {result.log_path}")
        print(f"  Pages: {result.page_count}")
        print(f"  Fit level: {result.fit_level}")
        return 0

    print("Resume pipeline failed.")
    print(f"  Reason: {result.reason}")
    print(f"  Current JD: {result.current_jd_path}")
    print(f"  Working TeX: {result.current_tex_path}")
    print(f"  Log: {result.log_path}")
    print(f"  Pages: {result.page_count if result.page_count is not None else 'unknown'}")
    print(f"  Last fit level: {result.fit_level}")
    return 1


def _parse_resume_jd_path(args: list[str]) -> Path | None:
    if not args:
        return None
    if len(args) == 2 and args[0] == "--jd-file":
        return Path(args[1]).expanduser()
    raise ValueError("Usage: task 5 resume [--jd-file PATH]")


def _tool_status(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None:
        return "未找到"
    return f"已安裝 ({resolved})"


def _repo_ready() -> bool:
    return (_repo_dir() / "package.json").exists()


def _print_repo_not_ready() -> None:
    print(f"尚未找到 Scan-job repo: {_repo_dir()}")
    print("先執行 `task 5 bootstrap --install`，再回來跑這個命令。")


def _bootstrap_repo(runner: CommandRunner, *, install_dependencies: bool) -> int:
    if _repo_ready():
        print(f"Scan-job repo 已存在: {_repo_dir()}")
    else:
        ROOT_DIR.mkdir(parents=True, exist_ok=True)
        clone_command = ["git", "clone", "https://github.com/santifer/career-ops.git", str(_repo_dir())]
        clone_exit_code = runner(clone_command, ROOT_DIR)
        if clone_exit_code != 0:
            return clone_exit_code

    if install_dependencies:
        return runner(["npm", "install"], _repo_dir())

    print("下載完成。下一步可執行 `task 5 doctor`。")
    return 0


def _run_repo_script(script_name: str, extra_args: list[str], runner: CommandRunner) -> int:
    if not _repo_ready():
        _print_repo_not_ready()
        return 1
    command = ["npm", "run", script_name]
    if extra_args:
        command.extend(["--", *extra_args])
    return runner(command, _repo_dir())


def _run_command(command: list[str], cwd: Path) -> int:
    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


def _safe_input(prompt: str) -> str | None:
    try:
        return input(prompt)
    except (EOFError, OSError):
        return None


def _normalize_pipeline_field(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("|", " / ")).strip()


def _looks_like_pending_location(value: str) -> bool:
    lower = value.strip().lower()
    if not lower:
        return False
    return bool(
        "," in lower
        or any(
            keyword in lower
            for keyword in (
                "remote",
                "hybrid",
                "onsite",
                "on-site",
                "office",
                "canada",
                "united states",
                "usa",
                "taiwan",
                "china",
                "vancouver",
                "toronto",
                "taipei",
                "new taipei",
                "san francisco",
                "seattle",
                "austin",
                "beijing",
                "shanghai",
                "shenzhen",
            )
        )
    )


def _parse_pending_pipeline_line(raw_line: str) -> PendingJob | None:
    line = raw_line.strip()
    if not line.startswith("- [ ] "):
        return None
    payload = line[6:].strip()
    parts = [part.strip() for part in payload.split("|")]
    if len(parts) < 3:
        return None
    location = ""
    title_parts = parts[2:]
    if len(title_parts) > 1 and _looks_like_pending_location(title_parts[-1]):
        location = _normalize_pipeline_field(title_parts[-1])
        title_parts = title_parts[:-1]
    return PendingJob(
        url=parts[0],
        company=_normalize_pipeline_field(parts[1]),
        title=_normalize_pipeline_field(" | ".join(title_parts)),
        location=location,
        raw_line=raw_line,
    )


def _parse_processed_pipeline_line(raw_line: str) -> ProcessedJob | None:
    line = raw_line.strip()
    if not line.startswith("- [x] "):
        return None
    payload = line[6:].strip()
    parts = [part.strip() for part in payload.split("|")]
    if len(parts) < 6:
        return None
    return ProcessedJob(
        report_num=parts[0],
        url=parts[1],
        company=_normalize_pipeline_field(parts[2]),
        title=_normalize_pipeline_field(" | ".join(parts[3:-2])),
        score=parts[-2],
        pdf=parts[-1],
        raw_line=raw_line,
    )


def _load_pipeline_state() -> tuple[list[PendingJob], list[ProcessedJob]]:
    pending_jobs: list[PendingJob] = []
    processed_jobs: list[ProcessedJob] = []
    pipeline_path = _pipeline_path()
    if not pipeline_path.exists():
        return pending_jobs, processed_jobs

    current_section = ""
    for raw_line in pipeline_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            current_section = line.lower()
            continue
        if current_section.startswith("## pendientes") and line.startswith("- [ ] "):
            pending_entry = _parse_pending_pipeline_line(raw_line)
            if pending_entry is not None:
                pending_jobs.append(pending_entry)
        if current_section.startswith("## procesadas") and line.startswith("- [x] "):
            processed_entry = _parse_processed_pipeline_line(raw_line)
            if processed_entry is not None:
                processed_jobs.append(processed_entry)
    return pending_jobs, processed_jobs


def _latest_scan_snapshot() -> tuple[str | None, int]:
    scan_history_path = _scan_history_path()
    if not scan_history_path.exists():
        return None, 0

    latest_date: str | None = None
    counts: dict[str, int] = {}
    for line in scan_history_path.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        first_seen = parts[1].strip()
        if not first_seen:
            continue
        counts[first_seen] = counts.get(first_seen, 0) + 1
        if latest_date is None or first_seen > latest_date:
            latest_date = first_seen

    if latest_date is None:
        return None, 0
    return latest_date, counts.get(latest_date, 0)


def _latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    candidates = [path for path in directory.glob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _latest_processed_job(processed_jobs: list[ProcessedJob]) -> ProcessedJob:
    def sort_key(job: ProcessedJob) -> tuple[int, str]:
        match = re.search(r"(\d+)", job.report_num)
        numeric = int(match.group(1)) if match else -1
        return numeric, job.raw_line

    return max(processed_jobs, key=sort_key)


def _load_application_records() -> list[ApplicationRecord]:
    applications_path = _applications_path()
    if not applications_path.exists():
        return []

    records: list[ApplicationRecord] = []
    for raw_line in applications_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("| # ") or line.startswith("|---"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 9:
            continue
        report_path = _extract_markdown_link_target(parts[7]) or ""
        records.append(
            ApplicationRecord(
                report_num=parts[0],
                date=parts[1],
                company=parts[2],
                role=parts[3],
                score=parts[4],
                status=parts[5],
                pdf=parts[6],
                report_path=report_path,
                notes=parts[8],
            )
        )
    return records


def _extract_markdown_link_target(value: str) -> str | None:
    match = re.search(r"\[[^\]]+\]\(([^)]+)\)", value)
    if not match:
        return None
    return match.group(1).strip()


def _score_value(score: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", score)
    if not match:
        return None
    return float(match.group(1))


def _priority_label(score: float | None, status: str) -> str:
    lowered = status.lower()
    if lowered == "pending":
        return "Review"
    if score is None:
        return "Review"
    if score >= 3.5:
        return "High"
    if score >= 3.0:
        return "Medium"
    return "Low"


def _next_step(status: str, score: float | None) -> str:
    lowered = status.lower()
    if "applied" in lowered:
        return "Follow up in 7 days"
    if "interview" in lowered:
        return "Follow up in 2-3 days"
    if "reject" in lowered:
        return "Archive"
    if lowered == "pending":
        return "Process next"
    if score is None:
        return "Review manually"
    if score >= 3.5:
        return "Apply"
    if score >= 3.0:
        return "Consider applying"
    return "Skip or keep as benchmark"


def _follow_up_value(status: str) -> str:
    lowered = status.lower()
    if "applied" in lowered:
        return "7 days"
    if "interview" in lowered:
        return "2-3 days"
    return "None"


def _relative_dashboard_link(target: str) -> str:
    target_path = (Path(target) if not target.startswith("/") else Path(target)).as_posix()
    if target_path.startswith("../") or target_path.startswith("./"):
        return target_path
    return f"../{target_path}" if not target_path.startswith("data/") else target_path.removeprefix("data/")


def _output_variants_for_report(report_path: str) -> tuple[str | None, str | None]:
    if not report_path:
        return None, None
    report_name = Path(report_path).stem
    if "-" not in report_name:
        return None, None
    suffix = report_name.split("-", 1)[1]
    html_match = _latest_file(_output_dir(), f"*-{suffix}.html")
    pdf_match = _latest_file(_output_dir(), f"*-{suffix}.pdf")
    html_rel = html_match.relative_to(_repo_dir()).as_posix() if html_match else None
    pdf_rel = pdf_match.relative_to(_repo_dir()).as_posix() if pdf_match else None
    return html_rel, pdf_rel


def _dashboard_link(label: str, relative_path: str | None) -> str:
    if not relative_path:
        return "-"
    return f"[{label}]({_relative_dashboard_link(relative_path)})"


def _dashboard_last_updated(records: list[ApplicationRecord], latest_scan_run: LatestScanRunSummary | None) -> str:
    candidates = [record.date for record in records if record.date]
    if latest_scan_run and latest_scan_run.date:
        if latest_scan_run.time:
            candidates.append(f"{latest_scan_run.date} {latest_scan_run.time}")
        else:
            candidates.append(latest_scan_run.date)
    return max(candidates) if candidates else _today_iso()


def _dashboard_master_rows(
    pending_jobs: list[PendingJob],
    processed_jobs: list[ProcessedJob],
    records: list[ApplicationRecord],
) -> list[str]:
    lines: list[str] = []
    record_map = {(record.company, record.role): record for record in records}
    processed_map = {(job.company, job.title): job for job in processed_jobs}

    for record in sorted(records, key=lambda item: (_score_value(item.score) or 0.0), reverse=True):
        html_path, pdf_path = _output_variants_for_report(record.report_path)
        lines.append(
            "| "
            + " | ".join(
                [
                    record.company,
                    record.role,
                    record.score or "-",
                    record.status,
                    "Yes" if record.status.lower() in {"applied", "interview", "rejected"} else "No",
                    _follow_up_value(record.status),
                    record.notes or "-",
                    _dashboard_link("Report", record.report_path),
                    _dashboard_link("HTML", html_path),
                    _dashboard_link("PDF", pdf_path),
                ]
            )
            + " |"
        )

    for job in pending_jobs:
        if (job.company, job.title) in record_map or (job.company, job.title) in processed_map:
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    job.company,
                    job.title,
                    "-",
                    "Pending",
                    "No",
                    "None",
                    "Awaiting evaluation",
                    "-",
                    "-",
                    "-",
                ]
            )
            + " |"
        )

    return lines or ["| - | - | - | - | - | - | - | - | - | - |"]


def _dashboard_priority_rows(pending_jobs: list[PendingJob], records: list[ApplicationRecord]) -> list[str]:
    rows: list[tuple[float, str]] = []
    for record in records:
        score = _score_value(record.score)
        sort_key = score if score is not None else -1.0
        row = (
            "| "
            + " | ".join(
                [
                    _priority_label(score, record.status),
                    record.company,
                    record.role,
                    record.score or "-",
                    record.status,
                    _next_step(record.status, score),
                ]
            )
            + " |"
        )
        rows.append((sort_key, row))

    for job in pending_jobs:
        rows.append(
            (
                -1.0,
                "| "
                + " | ".join(
                    [
                        "Review",
                        job.company,
                        job.title,
                        "-",
                        "Pending",
                        "Process next",
                    ]
                )
                + " |",
            )
        )

    rows.sort(key=lambda item: item[0], reverse=True)
    return [row for _score, row in rows[:8]] or ["| - | - | - | - | - | - |"]


def _dashboard_tracker_rows(records: list[ApplicationRecord]) -> list[str]:
    lines = [
        "| "
        + " | ".join(
            [
                record.company,
                record.role,
                record.status,
                record.date or "-",
                _next_step(record.status, _score_value(record.score)),
            ]
        )
        + " |"
        for record in records
    ]
    return lines or ["| - | - | - | - | - |"]


def _dashboard_followup_rows(records: list[ApplicationRecord]) -> list[str]:
    lines = []
    for record in records:
        follow_up = _follow_up_value(record.status)
        if follow_up == "None":
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    record.company,
                    record.role,
                    record.status,
                    follow_up,
                    record.notes or "-",
                ]
            )
            + " |"
        )
    return lines or ["| - | - | - | - | - |"]


def _refresh_dashboard_file() -> Path:
    if not _repo_ready():
        return _dashboard_path()

    pending_jobs, processed_jobs = _load_pipeline_state()
    records = _load_application_records()
    scan_target_state = _load_scan_target_state()
    latest_scan_run = _load_latest_scan_run_summary()
    applied_count = sum(1 for record in records if record.status.lower() == "applied")
    interview_count = sum(1 for record in records if record.status.lower() == "interview")
    rejected_count = sum(1 for record in records if record.status.lower() == "rejected")
    last_updated = _dashboard_last_updated(records, latest_scan_run)

    content = "\n".join(
        [
            "# Job Application Dashboard",
            "",
            "## Summary",
            "",
            f"- Total Jobs Processed: {len(processed_jobs)}",
            f"- Pending Jobs: {len(pending_jobs)}",
            f"- Applied: {applied_count}",
            f"- Interview: {interview_count}",
            f"- Rejected: {rejected_count}",
            f"- Last Updated: {last_updated}",
            "",
            "---",
            "",
            "## Current Scan Target",
            "",
            f"- Current target profile: {scan_target_state.label if scan_target_state else 'Not recorded yet'}",
            f"- Focus areas: {_format_scan_target_values(scan_target_state.focus_labels) if scan_target_state else 'Not set'}",
            f"- Locations: {_format_scan_target_values(scan_target_state.location_labels) if scan_target_state else 'Not set'}",
            f"- Work modes: {_format_scan_target_values(scan_target_state.work_mode_labels) if scan_target_state else 'Not set'}",
            "",
            "---",
            "",
            "## Latest Scan Run",
            "",
            f"- Completed at: {f'{latest_scan_run.date} {latest_scan_run.time}'.strip() if latest_scan_run else 'Not recorded yet'}",
            f"- Latest target profile: {latest_scan_run.target_label if latest_scan_run and latest_scan_run.target_label else 'Not recorded yet'}",
            f"- Current scan matches: {latest_scan_run.scored_scan_matches if latest_scan_run else 0}",
            f"- Pending queue rebuilt: {latest_scan_run.pending_queue_rebuilt if latest_scan_run else 0}",
            f"- New unique offers added to history: {latest_scan_run.new_offers_discovered if latest_scan_run else 0}",
            f"- Daily scan log: {_dashboard_link('Open', latest_scan_run.daily_log_path if latest_scan_run and latest_scan_run.daily_log_path else None)}",
            "",
            "---",
            "",
            "## Priority Queue",
            "",
            "| Priority | Company | Role | Score | Status | Action |",
            "|----------|---------|------|-------|--------|--------|",
            *_dashboard_priority_rows(pending_jobs, records),
            "",
            "---",
            "",
            "## All Jobs",
            "",
            "| Company | Role | Score | Status | Applied | Follow-up | Notes | Report | CV | PDF |",
            "|---------|------|-------|--------|---------|-----------|-------|--------|----|-----|",
            *_dashboard_master_rows(pending_jobs, processed_jobs, records),
            "",
            "---",
            "",
            "## Application Tracker",
            "",
            "| Company | Role | Stage | Last Action | Next Step |",
            "|---------|------|-------|-------------|-----------|",
            *_dashboard_tracker_rows(records),
            "",
            "---",
            "",
            "## Follow-up Tracker",
            "",
            "| Company | Role | Status | Follow-up Date | Notes |",
            "|---------|------|--------|----------------|-------|",
            *_dashboard_followup_rows(records),
            "",
            "---",
            "",
            "## Quick Navigation",
            "",
            "- [Pipeline](pipeline.md)",
            "- [Applications](applications.md)",
            f"- Latest Scan Log: {_dashboard_link('Open', latest_scan_run.daily_log_path if latest_scan_run and latest_scan_run.daily_log_path else None)}",
            "- [Scan History](scan-history.tsv)",
            "- [Reports](../reports/)",
            "- [Outputs](../output/)",
            "",
            "---",
            "",
            "## Notes",
            "",
            "- Score >= 3.5 -> Apply",
            "- Score 3.0-3.5 -> Optional / Stretch",
            "- Score < 3.0 -> Skip or keep as benchmark",
            "- Apply -> follow up in 7 days",
            "- Interview -> follow up in 2-3 days",
            "",
        ]
    )

    dashboard_path = _dashboard_path()
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(content, encoding="utf-8")
    return dashboard_path


def _load_job_posting(job: PendingJob) -> dict[str, str]:
    if job.url.startswith("local:"):
        relative_path = job.url.removeprefix("local:")
        local_path = _repo_dir() / relative_path
        if not local_path.exists():
            raise FileNotFoundError(f"找不到本地 JD: {local_path}")
        return {
            "company": job.company,
            "title": job.title,
            "url": job.url,
            "published_at": _today_iso(),
            "location": "Unknown",
            "description_plain": local_path.read_text(encoding="utf-8"),
            "description_html": "",
        }

    ashby_match = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]+)", job.url)
    if ashby_match:
        board_slug, job_id = ashby_match.groups()
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{board_slug}?includeCompensation=true"
        payload = _fetch_json(api_url)
        for candidate in payload.get("jobs", []):
            if candidate.get("id") == job_id:
                description_plain = candidate.get("descriptionPlain") or _html_to_text(candidate.get("descriptionHtml", ""))
                return {
                    "company": job.company,
                    "title": candidate.get("title") or job.title,
                    "url": candidate.get("jobUrl") or job.url,
                    "published_at": candidate.get("publishedAt", _today_iso()),
                    "location": candidate.get("location") or ("Remote" if candidate.get("isRemote") else "Unknown"),
                    "description_plain": description_plain,
                    "description_html": candidate.get("descriptionHtml", ""),
                }
        raise ValueError("Ashby job board 已載入，但找不到對應 job id")

    raise ValueError("目前只支援 `local:` 與 Ashby job URLs 的自動處理")


def _fetch_json(url: str) -> dict[str, object]:
    req = request.Request(url, headers=_browser_like_headers(url))
    with request.urlopen(req, timeout=20) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _browser_like_headers(url: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://jobs.ashbyhq.com",
        "Referer": url,
    }


def _html_to_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(value)
    return parser.text()


def _render_jd_snapshot(posting: dict[str, str]) -> str:
    return "\n".join(
        [
            f"# {posting['company']} — {posting['title']}",
            "",
            f"**Source URL:** {posting['url']}",
            f"**Published At:** {posting['published_at']}",
            f"**Location:** {posting['location']}",
            "",
            "## Job Description",
            "",
            posting["description_plain"].strip(),
            "",
        ]
    )


def _evaluate_posting(posting: dict[str, str]) -> dict[str, object]:
    jd_text = posting["description_plain"].lower()
    candidate_text = _candidate_context_text().lower()

    match_rules = [
        {
            "label": "JavaScript / TypeScript product systems",
            "jd_terms": ("javascript", "typescript", "frontend", "dashboard"),
            "candidate_terms": ("javascript", "typescript", "react"),
            "evidence": "React and TypeScript experience across Delta Controls, CryptoPulse, YC Todo, and Future DAO.",
        },
        {
            "label": "API integrations and cross-system workflows",
            "jd_terms": ("api", "integration", "webhook", "third-party", "slack", "linear", "front"),
            "candidate_terms": ("api", "integrat", "ethers.js"),
            "evidence": "CryptoPulse integrates external APIs, and Future DAO uses Ethers.js for contract interaction.",
        },
        {
            "label": "Internal tooling / operational software",
            "jd_terms": ("internal tool", "support", "operational", "dashboard", "workflow"),
            "candidate_terms": ("operational", "workflow", "productivity", "diagnostic", "dashboard"),
            "evidence": "Delta Controls shows operational software experience; YC Todo shows tooling and interaction design ownership.",
        },
        {
            "label": "Automation and systems thinking",
            "jd_terms": ("automation", "background jobs", "ai agent", "workflow"),
            "candidate_terms": ("workflow", "real-time", "automation", "governance"),
            "evidence": "Future DAO and Delta Controls show lifecycle design and system logic, though direct production AI-agent ownership is still limited.",
        },
        {
            "label": "Reliability / debugging / real-world constraints",
            "jd_terms": ("reliability", "observability", "on-call", "debug", "quality"),
            "candidate_terms": ("real-time", "debug", "diagnostic", "stability"),
            "evidence": "Delta Controls and embedded/control projects show debugging under real-time and operational constraints.",
        },
        {
            "label": "Async communication and stakeholder translation",
            "jd_terms": ("communication", "stakeholder", "async", "support"),
            "candidate_terms": ("communication", "instruction", "collaboration"),
            "evidence": "Profile and CV emphasize communication, collaboration, and 120+ hours of structured tutoring/instruction.",
        },
    ]

    match_rows: list[dict[str, object]] = []
    score_components: list[float] = []
    gaps: list[str] = []

    for rule in match_rules:
        if not any(term in jd_text for term in rule["jd_terms"]):
            continue
        hits = sum(1 for term in rule["candidate_terms"] if term in candidate_text)
        if hits >= 2:
            strength = "Strong"
            numeric = 5.0
        elif hits == 1:
            strength = "Partial"
            numeric = 3.5
        else:
            strength = "Weak"
            numeric = 2.0
        match_rows.append(
            {
                "requirement": rule["label"],
                "evidence": rule["evidence"],
                "strength": strength,
            }
        )
        score_components.append(numeric)
        if strength != "Strong":
            gaps.append(rule["label"])

    years_match = re.search(r"(\d+)\+?\s+years", jd_text)
    level_score = 4.0
    seniority_label = "Likely junior-to-mid compatible"
    if years_match:
        required_years = int(years_match.group(1))
        if required_years >= 8:
            level_score = 1.5
            seniority_label = f"Senior stretch role ({required_years}+ years requested)"
            gaps.append("Seniority / years-of-experience requirement")
        elif required_years >= 5:
            level_score = 2.5
            seniority_label = f"Mid-to-senior stretch role ({required_years}+ years requested)"
            gaps.append("Seniority / years-of-experience requirement")

    remote_score = 5.0 if "remote" in jd_text else 3.0
    if any(word in jd_text for word in ("hybrid", "on-site", "onsite")):
        remote_score = 3.0

    match_score = sum(score_components) / len(score_components) if score_components else 3.0
    overall_score = round((match_score * 0.68) + (level_score * 0.22) + (remote_score * 0.10), 1)
    legitimacy = "High Confidence" if len(posting["description_plain"]) > 800 else "Proceed with Caution"

    notes = "High-confidence posting; strong tooling overlap but stretch because of seniority and backend depth."
    if overall_score < 3.0:
        notes = "Real posting, but current fit is limited; best used as a benchmark role."

    return {
        "archetype": "Internal Tooling / Full-Stack Engineering" if "support" in jd_text or "internal" in jd_text else "Software Engineering",
        "domain": "Operational tooling, workflows, integrations" if "support" in jd_text else "General software engineering",
        "function": "Build tooling, integrations, and user-facing operational systems",
        "seniority": seniority_label,
        "remote": "Fully remote" if remote_score >= 5 else "Location constraints worth checking",
        "team_context": "Async, globally distributed engineering organization",
        "match_rows": match_rows,
        "gaps": gaps,
        "match_score": round(match_score, 1),
        "level_score": round(level_score, 1),
        "remote_score": round(remote_score, 1),
        "overall_score": overall_score,
        "legitimacy": legitimacy,
        "keywords": _extract_keywords(posting["description_plain"]),
        "notes": notes,
    }


def _candidate_context_text() -> str:
    parts: list[str] = []
    for path in (_cv_path(), _article_digest_path(), _profile_overrides_path()):
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _extract_keywords(text: str) -> list[str]:
    canonical_terms = [
        "TypeScript",
        "JavaScript",
        "internal tooling",
        "support tooling",
        "dashboard",
        "workflow automation",
        "API integration",
        "background jobs",
        "data modeling",
        "AI agent",
        "operational workflows",
        "observability",
        "async collaboration",
        "third-party integrations",
        "Front",
        "Slack",
        "Linear",
        "Elixir",
        "production systems",
    ]
    lower_text = text.lower()
    return [term for term in canonical_terms if term.lower() in lower_text][:12]


def _render_report(
    posting: dict[str, str],
    evaluation: dict[str, object],
    report_num: int,
    pdf_path: Path,
) -> str:
    match_rows = evaluation["match_rows"]
    match_table = "\n".join(
        f"| {row['requirement']} | {row['evidence']} | {row['strength']} |"
        for row in match_rows
    ) or "| No structured match rows | Context unavailable | Needs review |"

    gap_lines = "\n".join(f"- {gap}" for gap in evaluation["gaps"]) or "- No critical gaps detected from the quick terminal pass."
    keyword_lines = "\n".join(f"- {keyword}" for keyword in evaluation["keywords"]) or "- No keywords extracted"

    return "\n".join(
        [
            f"# Evaluation: {posting['company']} — {posting['title']}",
            "",
            f"**Date:** {_today_iso()}",
            f"**Archetype:** {evaluation['archetype']}",
            f"**Score:** {evaluation['overall_score']:.1f}/5",
            f"**Legitimacy:** {evaluation['legitimacy']}",
            f"**PDF:** {pdf_path.relative_to(_repo_dir())}",
            f"**Source JD:** {posting['url']}",
            "",
            "---",
            "",
            "## A) Role Summary",
            "",
            "| Field | Assessment |",
            "|-------|------------|",
            f"| Archetype | {evaluation['archetype']} |",
            f"| Domain | {evaluation['domain']} |",
            f"| Function | {evaluation['function']} |",
            f"| Seniority | {evaluation['seniority']} |",
            f"| Remote | {evaluation['remote']} |",
            f"| Team Context | {evaluation['team_context']} |",
            f"| TL;DR | {evaluation['notes']} |",
            "",
            "## B) CV Match",
            "",
            "| JD Requirement | Evidence from profile | Match |",
            "|----------------|-----------------------|-------|",
            match_table,
            "",
            "## C) Level and Strategy",
            "",
            f"- Match score: {evaluation['match_score']:.1f}/5",
            f"- Level fit score: {evaluation['level_score']:.1f}/5",
            f"- Remote / logistics score: {evaluation['remote_score']:.1f}/5",
            f"- Strategy: {evaluation['notes']}",
            "",
            "## D) Compensation and Demand",
            "",
            "- Use external salary sources during live review when compensation is critical.",
            "- This terminal-first pass focuses on workflow continuity and first-pass prioritization.",
            "- For deeper negotiation context, cross-check current market sources before applying.",
            "",
            "## E) Personalization Plan",
            "",
            "| # | Section | Current state | Change proposed | Why |",
            "|---|---------|---------------|-----------------|-----|",
            "| 1 | Summary | Broad software / full-stack narrative | Emphasize tooling, integrations, and operational workflows | Better mirrors this JD |",
            "| 2 | Work Experience | Delta Controls already leads the CV | Keep it first and stress operational tooling and diagnostics | Strongest adjacent proof point |",
            "| 3 | Projects | Multiple strong projects | Prioritize CryptoPulse, YC Todo, and Future DAO | Best mix of tooling, UI, and system logic |",
            "",
            "## F) Interview Plan",
            "",
            "- Lead with Delta Controls for operational tooling and real-world debugging.",
            "- Use CryptoPulse to demonstrate integrations and dashboard-style product work.",
            "- Use YC Todo for UI ownership and platform-specific problem solving.",
            "- Be ready to address the seniority gap directly and honestly.",
            "",
            "## G) Posting Legitimacy",
            "",
            f"- Published at: {posting['published_at']}",
            f"- URL: {posting['url']}",
            f"- Assessment: {evaluation['legitimacy']}",
            "- Signals: specific responsibilities, active live posting, and detailed operational scope.",
            "",
            "---",
            "",
            "## Keywords extracted",
            "",
            keyword_lines,
            "",
        ]
    )


def _render_tailored_html(posting: dict[str, str], evaluation: dict[str, object]) -> str:
    cv = _parse_cv_markdown()
    competencies = evaluation["keywords"][:8]
    work_entries = cv["work"]
    project_entries = sorted(
        cv["projects"],
        key=lambda entry: _entry_relevance_score(entry, posting["description_plain"]),
        reverse=True,
    )[:3]

    summary = (
        f"Entry-level Software Engineer and Full-Stack Developer with hands-on experience building "
        f"tooling, integrations, and production-like systems across web, desktop, industrial, and blockchain environments. "
        f"For {posting['company']}'s {posting['title']} role, the strongest overlap is in TypeScript, API integration, "
        f"dashboard-style interfaces, operational workflows, and product-minded implementation."
    )

    competency_tags = "".join(f"<span>{escape(keyword)}</span>" for keyword in competencies)
    work_html = "".join(_render_entry_block(entry) for entry in work_entries)
    project_html = "".join(_render_entry_block(entry) for entry in project_entries)
    skills_html = escape(cv["skills"]).replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(cv['name'])} — Tailored CV</title>
  <style>
    body {{
      font-family: Arial, Helvetica, sans-serif;
      color: #1f2937;
      margin: 0;
      padding: 0;
      background: #ffffff;
      font-size: 11px;
      line-height: 1.45;
    }}
    .page {{
      max-width: 8.5in;
      margin: 0 auto;
    }}
    h1, h2 {{
      margin: 0;
      padding: 0;
    }}
    .header {{
      margin-bottom: 18px;
    }}
    .header h1 {{
      font-size: 26px;
      line-height: 1.1;
      margin-bottom: 6px;
    }}
    .subline {{
      color: #4b5563;
      font-size: 10px;
    }}
    .section {{
      margin-bottom: 16px;
    }}
    .section h2 {{
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      border-bottom: 1px solid #d1d5db;
      padding-bottom: 4px;
      margin-bottom: 8px;
    }}
    .tags span {{
      display: inline-block;
      border: 1px solid #cbd5e1;
      border-radius: 3px;
      padding: 3px 7px;
      margin: 0 6px 6px 0;
      font-size: 10px;
    }}
    .entry {{
      margin-bottom: 12px;
    }}
    .entry-header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-weight: bold;
    }}
    .entry-role {{
      font-weight: 600;
      margin: 2px 0 5px 0;
    }}
    ul {{
      margin: 6px 0 0 18px;
      padding: 0;
    }}
    li {{
      margin-bottom: 4px;
    }}
    a {{
      color: #1f2937;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="header">
      <h1>{escape(cv['name'])}</h1>
      <div class="subline">{escape(cv['contact'])}</div>
    </section>

    <section class="section">
      <h2>Professional Summary</h2>
      <p>{escape(summary)}</p>
    </section>

    <section class="section">
      <h2>Core Competencies</h2>
      <div class="tags">{competency_tags}</div>
    </section>

    <section class="section">
      <h2>Work Experience</h2>
      {work_html}
    </section>

    <section class="section">
      <h2>Selected Projects</h2>
      {project_html}
    </section>

    <section class="section">
      <h2>Education</h2>
      {_render_entry_block(cv['education'])}
    </section>

    <section class="section">
      <h2>Skills</h2>
      <p>{skills_html}</p>
    </section>
  </div>
</body>
</html>
"""


def _parse_cv_markdown() -> dict[str, object]:
    cv_text = _cv_path().read_text(encoding="utf-8")
    lines = cv_text.splitlines()

    name_line = next((line for line in lines if line.startswith("# ")), "# Candidate")
    raw_name = name_line.removeprefix("# ").strip()
    name = raw_name.split("--")[-1].strip() if "--" in raw_name else raw_name

    header_lines: list[str] = []
    for line in lines[1:]:
        if line.startswith("## "):
            break
        if line.strip():
            header_lines.append(re.sub(r"^\*\*(.+?):\*\*\s*", "", line).strip())
    contact = " | ".join(header_lines)

    summary = _section_body(cv_text, "Professional Summary").strip().split("\n")[0].strip()
    work_section = _section_body(cv_text, "Work Experience")
    projects_section = _section_body(cv_text, "Projects")
    education_section = _section_body(cv_text, "Education")
    skills_section = _section_body(cv_text, "Skills").strip()

    return {
        "name": name,
        "contact": contact,
        "summary": summary,
        "work": _parse_markdown_entries(work_section),
        "projects": _parse_markdown_entries(projects_section),
        "education": _parse_markdown_entries(education_section)[0],
        "skills": skills_section,
    }


def _section_body(markdown: str, title: str) -> str:
    match = re.search(
        rf"^## {re.escape(title)}\n(?P<body>.*?)(?=^## |\Z)",
        markdown,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group("body").strip() if match else ""


def _parse_markdown_entries(section_body: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    if not section_body.strip():
        return entries

    for match in re.finditer(
        r"^### (?P<title>[^\n]+)\n(?P<body>.*?)(?=^### |\Z)",
        section_body,
        flags=re.MULTILINE | re.DOTALL,
    ):
        title = match.group("title").strip()
        body_lines = [line.rstrip() for line in match.group("body").splitlines()]
        role = ""
        period = ""
        details: list[str] = []
        bullets: list[str] = []

        for raw_line in body_lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("**") and line.endswith("**") and not role:
                role = line.strip("*")
                continue
            if line.startswith("- "):
                bullets.append(line[2:].strip())
                continue
            if not period and not line.startswith("**"):
                period = line
                continue
            if line.startswith("**"):
                details.append(line.strip("*"))
            else:
                details.append(line)

        entries.append(
            {
                "title": title,
                "role": role,
                "period": period,
                "details": details,
                "bullets": bullets,
            }
        )
    return entries


def _render_entry_block(entry: dict[str, object]) -> str:
    detail_lines = "".join(f"<div>{escape(detail)}</div>" for detail in entry["details"])
    bullet_lines = "".join(f"<li>{escape(bullet)}</li>" for bullet in entry["bullets"])
    return (
        '<div class="entry">'
        f'<div class="entry-header"><div>{escape(entry["title"])}</div><div>{escape(entry["period"])}</div></div>'
        f'<div class="entry-role">{escape(entry["role"])}</div>'
        f"{detail_lines}"
        f"<ul>{bullet_lines}</ul>"
        "</div>"
    )


def _entry_relevance_score(entry: dict[str, object], jd_text: str) -> int:
    haystack = " ".join(
        [
            str(entry.get("title", "")),
            str(entry.get("role", "")),
            " ".join(entry.get("details", [])),
            " ".join(entry.get("bullets", [])),
        ]
    ).lower()
    score = 0
    for keyword in _extract_keywords(jd_text):
        if keyword.lower() in haystack:
            score += 1
    return score


def _paper_format(posting: dict[str, str]) -> str:
    location = posting["location"].lower()
    if any(keyword in location for keyword in ("canada", "united states", "us", "remote")):
        return "letter"
    return "a4"


def _candidate_slug() -> str:
    cv_text = _cv_path().read_text(encoding="utf-8")
    name_line = next((line for line in cv_text.splitlines() if line.startswith("# ")), "# candidate")
    raw_name = name_line.removeprefix("# ").split("--")[-1].strip()
    return _slugify(raw_name)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def _today_iso() -> str:
    return date.today().isoformat()


def _next_report_num() -> int:
    highest = 0
    for report_path in _reports_dir().glob("*.md"):
        match = re.match(r"(\d+)-", report_path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _ensure_applications_tracker() -> None:
    applications_path = _applications_path()
    applications_path.parent.mkdir(parents=True, exist_ok=True)
    if applications_path.exists():
        return
    applications_path.write_text(
        "\n".join(
            [
                "# Applications Tracker",
                "",
                "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |",
                "|---|------|---------|------|-------|--------|-----|--------|-------|",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _mark_pipeline_job_processed(
    job: PendingJob,
    *,
    report_num: int,
    score: str,
    pdf_success: bool,
) -> None:
    pipeline_path = _pipeline_path()
    if not pipeline_path.exists():
        return

    lines = pipeline_path.read_text(encoding="utf-8").splitlines()
    updated_lines: list[str] = []
    moved = False
    processed_inserted = False
    safe_company = _normalize_pipeline_field(job.company)
    safe_title = _normalize_pipeline_field(job.title)

    for line in lines:
        if not moved and line == job.raw_line:
            moved = True
            continue
        updated_lines.append(line)
        if line.strip().lower() == "## procesadas":
            updated_lines.append(
                f"- [x] #{report_num:03d} | {job.url} | {safe_company} | {safe_title} | {score} | PDF {'✅' if pdf_success else '❌'}"
            )
            processed_inserted = True

    if moved and not processed_inserted:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append("## Procesadas")
        updated_lines.append(
            f"- [x] #{report_num:03d} | {job.url} | {safe_company} | {safe_title} | {score} | PDF {'✅' if pdf_success else '❌'}"
        )

    pipeline_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
