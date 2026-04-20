#!/usr/bin/env node

/**
 * scan.mjs — Zero-token portal scanner
 *
 * Fetches Greenhouse, Ashby, and Lever APIs directly, applies title
 * filters from portals.yml, rebuilds the pending pipeline based on the
 * latest scan, appends newly discovered offers to scan-history.tsv,
 * and writes daily per-run scan summaries for human review.
 *
 * Zero Claude API tokens — pure HTTP + JSON.
 *
 * Usage:
 *   node scan.mjs                  # scan all enabled companies
 *   node scan.mjs --dry-run        # preview without writing files
 *   node scan.mjs --company Cohere # scan a single company
 */

import { readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync } from 'fs';
import yaml from 'js-yaml';
const parseYaml = yaml.load;

// ── Config ──────────────────────────────────────────────────────────

const PORTALS_PATH = 'portals.yml';
const SCAN_HISTORY_PATH = 'data/scan-history.tsv';
const PIPELINE_PATH = 'data/pipeline.md';
const APPLICATIONS_PATH = 'data/applications.md';
const SCAN_RUNS_DIR = 'data/scan-runs';
const LATEST_SCAN_RUN_PATH = 'data/latest-scan-run.json';

// Ensure required directories exist (fresh setup)
mkdirSync('data', { recursive: true });
mkdirSync(SCAN_RUNS_DIR, { recursive: true });

const CONCURRENCY = 10;
const FETCH_TIMEOUT_MS = 10_000;

function parseCsvList(value) {
  return String(value || '')
    .split(',')
    .map(item => normalizeSpacing(item))
    .filter(Boolean);
}

function collectArgValues(args, flag) {
  const values = [];
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === flag) {
      if (i + 1 < args.length) {
        values.push(...parseCsvList(args[i + 1]));
        i += 1;
      }
      continue;
    }
    if (arg.startsWith(`${flag}=`)) {
      values.push(...parseCsvList(arg.split('=', 1)[1] || arg.slice(flag.length + 1)));
    }
  }
  return values;
}

function readSingleArg(args, flag) {
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === flag) {
      return i + 1 < args.length ? args[i + 1] : '';
    }
    if (arg.startsWith(`${flag}=`)) {
      return arg.slice(flag.length + 1);
    }
  }
  return '';
}

function markdownList(values, fallback) {
  return values.length > 0 ? values.join(', ') : fallback;
}

// ── API detection ───────────────────────────────────────────────────

function detectApi(company) {
  // Greenhouse: explicit api field
  if (company.api && company.api.includes('greenhouse')) {
    return { type: 'greenhouse', url: company.api };
  }

  const url = company.careers_url || '';

  // Ashby
  const ashbyMatch = url.match(/jobs\.ashbyhq\.com\/([^/?#]+)/);
  if (ashbyMatch) {
    return {
      type: 'ashby',
      url: `https://api.ashbyhq.com/posting-api/job-board/${ashbyMatch[1]}?includeCompensation=true`,
    };
  }

  // Lever
  const leverMatch = url.match(/jobs\.lever\.co\/([^/?#]+)/);
  if (leverMatch) {
    return {
      type: 'lever',
      url: `https://api.lever.co/v0/postings/${leverMatch[1]}`,
    };
  }

  // Greenhouse EU boards
  const ghEuMatch = url.match(/job-boards(?:\.eu)?\.greenhouse\.io\/([^/?#]+)/);
  if (ghEuMatch && !company.api) {
    return {
      type: 'greenhouse',
      url: `https://boards-api.greenhouse.io/v1/boards/${ghEuMatch[1]}/jobs`,
    };
  }

  return null;
}

// ── API parsers ─────────────────────────────────────────────────────

function parseGreenhouse(json, companyName) {
  const jobs = json.jobs || [];
  return jobs.map(j => ({
    title: j.title || '',
    url: j.absolute_url || '',
    company: companyName,
    location: j.location?.name || '',
  }));
}

function parseAshby(json, companyName) {
  const jobs = json.jobs || [];
  return jobs.map(j => ({
    title: j.title || '',
    url: j.jobUrl || '',
    company: companyName,
    location: j.location || '',
  }));
}

function parseLever(json, companyName) {
  if (!Array.isArray(json)) return [];
  return json.map(j => ({
    title: j.text || '',
    url: j.hostedUrl || '',
    company: companyName,
    location: j.categories?.location || '',
  }));
}

const PARSERS = { greenhouse: parseGreenhouse, ashby: parseAshby, lever: parseLever };

// ── Fetch with timeout ──────────────────────────────────────────────

async function fetchJson(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

// ── Title filter ────────────────────────────────────────────────────

function buildTitleFilter(titleFilter, positiveOverride = []) {
  const positiveSource = positiveOverride.length > 0 ? positiveOverride : (titleFilter?.positive || []);
  const positive = positiveSource.map(k => k.toLowerCase());
  const negative = (titleFilter?.negative || []).map(k => k.toLowerCase());

  return (title) => {
    const lower = title.toLowerCase();
    const hasPositive = positive.length === 0 || positive.some(k => lower.includes(k));
    const hasNegative = negative.some(k => lower.includes(k));
    return hasPositive && !hasNegative;
  };
}

function normalizeSpacing(value) {
  return value.replace(/\s+/g, ' ').trim();
}

function sanitizeField(value) {
  return normalizeSpacing(value).replace(/\s*\|\s*/g, ' / ');
}

function looksLikeLocation(value) {
  const lower = normalizeSpacing(value).toLowerCase();
  if (!lower) return false;
  return (
    lower.includes(',') ||
    [
      'remote',
      'hybrid',
      'onsite',
      'on-site',
      'office',
      'canada',
      'united states',
      'usa',
      'taiwan',
      'china',
      'vancouver',
      'toronto',
      'taipei',
      'new taipei',
      'san francisco',
      'seattle',
      'austin',
      'beijing',
      'shanghai',
      'shenzhen',
    ].some(keyword => lower.includes(keyword))
  );
}

function parsePendingCheckboxLine(rawLine) {
  const line = rawLine.trim();
  if (!line.startsWith('- [ ] ')) return null;
  const payload = line.slice(6).trim();
  const parts = payload.split('|').map(part => part.trim());
  if (parts.length < 3) return null;
  let location = '';
  let titleParts = parts.slice(2);
  if (titleParts.length > 1 && looksLikeLocation(titleParts.at(-1) || '')) {
    location = sanitizeField(titleParts.at(-1) || '');
    titleParts = titleParts.slice(0, -1);
  }
  return {
    url: normalizeSpacing(parts[0]),
    company: sanitizeField(parts[1]),
    title: sanitizeField(titleParts.join(' | ')),
    location,
  };
}

function parseProcessedCheckboxLine(rawLine) {
  const line = rawLine.trim();
  if (!line.startsWith('- [x] ')) return null;
  const payload = line.slice(6).trim();
  const parts = payload.split('|').map(part => part.trim());
  if (parts.length < 6) return null;
  return {
    url: normalizeSpacing(parts[1]),
    company: sanitizeField(parts[2]),
    title: sanitizeField(parts.slice(3, -2).join(' | ')),
  };
}

function normalizeRoleKey(company, role) {
  const normalizedCompany = sanitizeField(company).toLowerCase();
  const normalizedRole = sanitizeField(role).toLowerCase();
  return `${normalizedCompany}::${normalizedRole}`;
}

function matchesKeywords(text, keywords) {
  if (!keywords || keywords.length === 0) return true;
  const lower = normalizeSpacing(text || '').toLowerCase();
  return keywords.some(keyword => lower.includes(normalizeSpacing(keyword).toLowerCase()));
}

function countKeywordMatches(text, keywords) {
  const lower = normalizeSpacing(text || '').toLowerCase();
  if (!lower) return 0;

  const matches = new Set();
  for (const keyword of keywords || []) {
    const normalizedKeyword = normalizeSpacing(String(keyword || '')).toLowerCase();
    if (normalizedKeyword && lower.includes(normalizedKeyword)) {
      matches.add(normalizedKeyword);
    }
  }
  return matches.size;
}

function remotePriorityFromJob(job) {
  const lower = normalizeSpacing(`${job.location || ''} ${job.title || ''}`).toLowerCase();
  if (!lower) {
    return { bucket: 'unspecified', priority: 1 };
  }

  if (/\b(on[\s-]?site|in[\s-]?office|office[-\s]?based)\b/.test(lower)) {
    return { bucket: 'onsite', priority: 0 };
  }
  if (/\b(hybrid)\b/.test(lower)) {
    return { bucket: 'hybrid', priority: 2 };
  }
  if (/\b(remote|distributed|work from home|wfh|fully remote|100% remote)\b/.test(lower)) {
    if (/\b(global|anywhere|worldwide|work from anywhere)\b/.test(lower)) {
      return { bucket: 'remote-global', priority: 5 };
    }
    if (/\b(emea|europe|eu|uk|canada|north america|na|apac|latam)\b/.test(lower)) {
      return { bucket: 'remote-regional', priority: 4 };
    }
    return { bucket: 'remote', priority: 3 };
  }

  return { bucket: 'unspecified', priority: 1 };
}

function scoreOffer(job, titleFilter) {
  const keywordHits = countKeywordMatches(job.title, titleFilter?.positive || []);
  const seniorityHits = countKeywordMatches(job.title, titleFilter?.seniority_boost || []);
  const remote = remotePriorityFromJob(job);
  const priorityScore = remote.priority * 100 + keywordHits * 10 + seniorityHits * 3;

  return {
    ...job,
    keywordHits,
    seniorityHits,
    remoteBucket: remote.bucket,
    remotePriority: remote.priority,
    priorityScore,
  };
}

function compareOffers(a, b) {
  return (
    b.priorityScore - a.priorityScore ||
    b.remotePriority - a.remotePriority ||
    b.keywordHits - a.keywordHits ||
    b.seniorityHits - a.seniorityHits ||
    a.company.localeCompare(b.company) ||
    a.title.localeCompare(b.title) ||
    a.url.localeCompare(b.url)
  );
}

function formatPendingLine(entry) {
  const base = `- [ ] ${normalizeSpacing(entry.url)} | ${sanitizeField(entry.company)} | ${sanitizeField(entry.title)}`;
  if (entry.location) {
    return `${base} | ${sanitizeField(entry.location)}`;
  }
  return base;
}

function loadPipelineState() {
  const state = {
    pendingEntries: [],
    processedLines: [],
    processedUrls: new Set(),
    processedRoleKeys: new Set(),
  };

  if (!existsSync(PIPELINE_PATH)) {
    return state;
  }

  let section = '';
  const lines = readFileSync(PIPELINE_PATH, 'utf-8').split('\n');
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (line.startsWith('## ')) {
      section = line.toLowerCase();
      continue;
    }
    if (!line) continue;

    if (section.startsWith('## pendientes')) {
      const pendingEntry = parsePendingCheckboxLine(rawLine);
      if (pendingEntry) {
        state.pendingEntries.push(pendingEntry);
      }
      continue;
    }

    if (section.startsWith('## procesadas')) {
      state.processedLines.push(rawLine.trimEnd());
      const processedEntry = parseProcessedCheckboxLine(rawLine);
      if (processedEntry) {
        state.processedUrls.add(processedEntry.url);
        state.processedRoleKeys.add(normalizeRoleKey(processedEntry.company, processedEntry.title));
      }
    }
  }

  return state;
}

// ── Dedup ───────────────────────────────────────────────────────────

function loadHistoricalUrls() {
  const seen = new Set();

  // scan-history.tsv
  if (existsSync(SCAN_HISTORY_PATH)) {
    const lines = readFileSync(SCAN_HISTORY_PATH, 'utf-8').split('\n');
    for (const line of lines.slice(1)) { // skip header
      const url = line.split('\t')[0];
      if (url) seen.add(url);
    }
  }

  // pipeline.md — extract URLs from checkbox lines so pending jobs do not look
  // brand-new when we rebuild the queue.
  if (existsSync(PIPELINE_PATH)) {
    const text = readFileSync(PIPELINE_PATH, 'utf-8');
    for (const match of text.matchAll(/- \[[ x]\] (https?:\/\/\S+)/g)) {
      seen.add(match[1]);
    }
  }

  // applications.md — extract URLs from report links and any inline URLs
  if (existsSync(APPLICATIONS_PATH)) {
    const text = readFileSync(APPLICATIONS_PATH, 'utf-8');
    for (const match of text.matchAll(/https?:\/\/[^\s|)]+/g)) {
      seen.add(match[0]);
    }
  }

  return seen;
}

function loadTrackedUrls(pipelineState) {
  const tracked = new Set(pipelineState.processedUrls);

  if (existsSync(APPLICATIONS_PATH)) {
    const text = readFileSync(APPLICATIONS_PATH, 'utf-8');
    for (const match of text.matchAll(/https?:\/\/[^\s|)]+/g)) {
      tracked.add(match[0]);
    }
  }

  return tracked;
}

function loadTrackedCompanyRoles(pipelineState) {
  const tracked = new Set(pipelineState.processedRoleKeys);

  if (existsSync(APPLICATIONS_PATH)) {
    const text = readFileSync(APPLICATIONS_PATH, 'utf-8');
    // Parse markdown table rows: | # | Date | Company | Role | ...
    for (const match of text.matchAll(/\|[^|]+\|[^|]+\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|/g)) {
      if (normalizeSpacing(match[1]).toLowerCase() === 'company') continue;
      tracked.add(normalizeRoleKey(match[1], match[2]));
    }
  }

  return tracked;
}

// ── Pipeline writer ─────────────────────────────────────────────────

function rewritePipeline({ manualPendingEntries, scannedOffers, processedLines }) {
  const pendingLines = [
    ...manualPendingEntries.map(formatPendingLine),
    ...scannedOffers.map(formatPendingLine),
  ];
  const content = [
    '## Pendientes',
    '',
    ...pendingLines,
    '',
    '## Procesadas',
    '',
    ...processedLines,
    '',
  ].join('\n');

  writeFileSync(PIPELINE_PATH, content, 'utf-8');
}

function appendToScanHistory(offers, date) {
  // Ensure file + header exist
  if (!existsSync(SCAN_HISTORY_PATH)) {
    writeFileSync(SCAN_HISTORY_PATH, 'url\tfirst_seen\tportal\ttitle\tcompany\tstatus\n', 'utf-8');
  }

  const lines = offers.map(o =>
    `${o.url}\t${date}\t${o.source}\t${o.title}\t${o.company}\tadded`
  ).join('\n') + '\n';

  appendFileSync(SCAN_HISTORY_PATH, lines, 'utf-8');
}

function scanRunLogPath(date) {
  return `${SCAN_RUNS_DIR}/${date}.md`;
}

function appendDailyScanRun(summary) {
  const logPath = scanRunLogPath(summary.date);
  if (!existsSync(logPath)) {
    writeFileSync(logPath, `# Scan Runs — ${summary.date}\n\n`, 'utf-8');
  }

  const lines = [
    `## ${summary.time || 'Latest run'} — ${summary.target_label || 'Unnamed target profile'}`,
    '',
    `- Focus areas: ${markdownList(summary.focus_labels, 'Not set')}`,
    `- Locations: ${markdownList(summary.location_labels, 'Not set')}`,
    `- Work modes: ${markdownList(summary.work_mode_labels, 'Not set')}`,
    '',
    '### Matches',
    '',
    ...(summary.matches.length > 0
      ? summary.matches.map(match => `- ${match.company} | ${match.title} | ${match.location || 'N/A'} | score ${match.priorityScore}`)
      : ['- None']),
    '',
    '### Totals',
    '',
    `- Companies scanned: ${summary.companies_scanned}`,
    `- Total jobs found: ${summary.total_jobs_found}`,
    `- Filtered by title: ${summary.filtered_by_title}`,
    `- Filtered by location: ${summary.filtered_by_location}`,
    `- Filtered by work mode: ${summary.filtered_by_work_mode}`,
    `- Duplicates skipped: ${summary.duplicates}`,
    `- New unique offers added to history: ${summary.new_offers_discovered}`,
    `- Current scan matches: ${summary.scored_scan_matches}`,
    `- Pending queue rebuilt: ${summary.pending_queue_rebuilt}`,
    '',
    '### Errors',
    '',
    ...(summary.errors.length > 0
      ? summary.errors.map(error => `- ${error.company}: ${error.error}`)
      : ['- None']),
    '',
    '---',
    '',
  ];

  appendFileSync(logPath, lines.join('\n'), 'utf-8');
  return logPath;
}

function writeLatestScanRunSummary(summary) {
  writeFileSync(LATEST_SCAN_RUN_PATH, `${JSON.stringify(summary, null, 2)}\n`, 'utf-8');
}

// ── Parallel fetch with concurrency limit ───────────────────────────

async function parallelFetch(tasks, limit) {
  const results = [];
  let i = 0;

  async function next() {
    while (i < tasks.length) {
      const task = tasks[i++];
      results.push(await task());
    }
  }

  const workers = Array.from({ length: Math.min(limit, tasks.length) }, () => next());
  await Promise.all(workers);
  return results;
}

// ── Main ────────────────────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const companyFlag = args.indexOf('--company');
  const filterCompany = companyFlag !== -1 ? args[companyFlag + 1]?.toLowerCase() : null;
  const runtimeTargeting = {
    focusKeywords: collectArgValues(args, '--focus-keywords'),
    focusLabels: collectArgValues(args, '--focus-labels'),
    locationKeywords: collectArgValues(args, '--location-keywords'),
    locationLabels: collectArgValues(args, '--location-labels'),
    workModeKeywords: collectArgValues(args, '--work-mode-keywords'),
    workModeLabels: collectArgValues(args, '--work-mode-labels'),
    targetLabel: normalizeSpacing(readSingleArg(args, '--target-label')),
  };

  // 1. Read portals.yml
  if (!existsSync(PORTALS_PATH)) {
    console.error('Error: portals.yml not found. Run onboarding first.');
    process.exit(1);
  }

  const config = parseYaml(readFileSync(PORTALS_PATH, 'utf-8'));
  const companies = config.tracked_companies || [];
  const effectivePositiveKeywords = runtimeTargeting.focusKeywords.length > 0
    ? runtimeTargeting.focusKeywords
    : (config.title_filter?.positive || []);
  const titleFilter = buildTitleFilter(config.title_filter, effectivePositiveKeywords);

  // 2. Filter to enabled companies with detectable APIs
  const targets = companies
    .filter(c => c.enabled !== false)
    .filter(c => !filterCompany || c.name.toLowerCase().includes(filterCompany))
    .map(c => ({ ...c, _api: detectApi(c) }))
    .filter(c => c._api !== null);

  const skippedCount = companies.filter(c => c.enabled !== false).length - targets.length;

  console.log(`Scanning ${targets.length} companies via API (${skippedCount} skipped — no API detected)`);
  if (dryRun) console.log('(dry run — no files will be written)\n');

  // 3. Load pipeline + dedup sets
  const pipelineState = loadPipelineState();
  const historicalUrls = loadHistoricalUrls();
  const trackedUrls = loadTrackedUrls(pipelineState);
  const trackedCompanyRoles = loadTrackedCompanyRoles(pipelineState);
  const manualPendingEntries = pipelineState.pendingEntries.filter(entry => !/^https?:\/\//i.test(entry.url));
  const scannedUrlsThisRun = new Set();
  const scannedRoleKeysThisRun = new Set();

  // 4. Fetch all APIs
  const date = new Date().toISOString().slice(0, 10);
  let totalFound = 0;
  let totalFiltered = 0;
  let totalLocationFiltered = 0;
  let totalWorkModeFiltered = 0;
  let totalDupes = 0;
  let totalNewToHistory = 0;
  const historyAdds = [];
  const scoredOffers = [];
  const errors = [];

  const tasks = targets.map(company => async () => {
    const { type, url } = company._api;
    try {
      const json = await fetchJson(url);
      const jobs = PARSERS[type](json, company.name);
      totalFound += jobs.length;

      for (const job of jobs) {
        if (!titleFilter(job.title)) {
          totalFiltered++;
          continue;
        }
        if (!matchesKeywords(job.location, runtimeTargeting.locationKeywords)) {
          totalLocationFiltered++;
          continue;
        }
        if (!matchesKeywords(`${job.location || ''} ${job.title || ''}`, runtimeTargeting.workModeKeywords)) {
          totalWorkModeFiltered++;
          continue;
        }
        const key = normalizeRoleKey(job.company, job.title);
        if (trackedUrls.has(job.url)) {
          totalDupes++;
          continue;
        }
        if (trackedCompanyRoles.has(key)) {
          totalDupes++;
          continue;
        }
        if (scannedUrlsThisRun.has(job.url) || scannedRoleKeysThisRun.has(key)) {
          totalDupes++;
          continue;
        }

        scannedUrlsThisRun.add(job.url);
        scannedRoleKeysThisRun.add(key);

        const scoredJob = scoreOffer(
          { ...job, source: `${type}-api` },
          {
            ...config.title_filter,
            positive: effectivePositiveKeywords,
          },
        );
        scoredOffers.push(scoredJob);

        if (!historicalUrls.has(job.url)) {
          historicalUrls.add(job.url);
          totalNewToHistory++;
          historyAdds.push(scoredJob);
        }
      }
    } catch (err) {
      errors.push({ company: company.name, error: err.message });
    }
  });

  await parallelFetch(tasks, CONCURRENCY);
  scoredOffers.sort(compareOffers);

  // 5. Write results
  if (!dryRun) {
    rewritePipeline({
      manualPendingEntries,
      scannedOffers: scoredOffers,
      processedLines: pipelineState.processedLines,
    });
  }
  if (!dryRun && historyAdds.length > 0) {
    appendToScanHistory(historyAdds, date);
  }

  const completedAt = new Date();
  const time = completedAt.toLocaleTimeString('en-GB', { hour12: false });
  const summary = {
    date,
    time,
    target_label: runtimeTargeting.targetLabel || 'Ad hoc scan',
    focus_labels: runtimeTargeting.focusLabels.length > 0 ? runtimeTargeting.focusLabels : runtimeTargeting.focusKeywords,
    location_labels: runtimeTargeting.locationLabels.length > 0 ? runtimeTargeting.locationLabels : runtimeTargeting.locationKeywords,
    work_mode_labels: runtimeTargeting.workModeLabels.length > 0 ? runtimeTargeting.workModeLabels : runtimeTargeting.workModeKeywords,
    focus_keywords: runtimeTargeting.focusKeywords,
    location_keywords: runtimeTargeting.locationKeywords,
    work_mode_keywords: runtimeTargeting.workModeKeywords,
    companies_scanned: targets.length,
    total_jobs_found: totalFound,
    filtered_by_title: totalFiltered,
    filtered_by_location: totalLocationFiltered,
    filtered_by_work_mode: totalWorkModeFiltered,
    duplicates: totalDupes,
    new_offers_discovered: totalNewToHistory,
    pending_queue_rebuilt: manualPendingEntries.length + scoredOffers.length,
    scored_scan_matches: scoredOffers.length,
    matches: scoredOffers.map(offer => ({
      company: offer.company,
      title: offer.title,
      location: offer.location || '',
      priorityScore: offer.priorityScore,
      url: offer.url,
    })),
    errors,
    daily_log_path: scanRunLogPath(date),
  };

  if (!dryRun) {
    appendDailyScanRun(summary);
    writeLatestScanRunSummary(summary);
  }

  // 6. Print summary
  console.log(`\n${'━'.repeat(45)}`);
  console.log(`Portal Scan — ${date}`);
  console.log(`${'━'.repeat(45)}`);
  if (runtimeTargeting.targetLabel) {
    console.log(`Target profile:        ${runtimeTargeting.targetLabel}`);
  }
  console.log(`Companies scanned:     ${targets.length}`);
  console.log(`Total jobs found:      ${totalFound}`);
  console.log(`Filtered by title:     ${totalFiltered} removed`);
  console.log(`Filtered by location:  ${totalLocationFiltered} removed`);
  console.log(`Filtered by work mode: ${totalWorkModeFiltered} removed`);
  console.log(`Duplicates:            ${totalDupes} skipped`);
  console.log(`New offers discovered: ${totalNewToHistory}`);
  console.log(`Pending queue rebuilt: ${manualPendingEntries.length + scoredOffers.length}`);
  console.log(`Scored scan matches:   ${scoredOffers.length}`);

  if (errors.length > 0) {
    console.log(`\nErrors (${errors.length}):`);
    for (const e of errors) {
      console.log(`  ✗ ${e.company}: ${e.error}`);
    }
  }

  if (scoredOffers.length > 0) {
    console.log('\nPending order after scoring:');
    for (const o of scoredOffers) {
      console.log(`  + ${o.company} | ${o.title} | ${o.location || 'N/A'} | score ${o.priorityScore}`);
    }
  }

  if (dryRun) {
    console.log('\n(dry run — run without --dry-run to save results)');
  } else {
    console.log(`\nResults saved to ${PIPELINE_PATH}, ${summary.daily_log_path}, and ${LATEST_SCAN_RUN_PATH}`);
    console.log(`Machine dedup history kept in ${SCAN_HISTORY_PATH}`);
  }

  console.log('\n→ Use Task 5 in the main terminal workflow to process a pending job.');
  console.log('→ Open Task 5 status or outputs if you want to review the latest scan summary.');
}

main().catch(err => {
  console.error('Fatal:', err.message);
  process.exit(1);
});
