#!/usr/bin/env node
/**
 * clean-pipeline.mjs — Normalize and deduplicate data/pipeline.md
 *
 * Run:
 *   node clean-pipeline.mjs
 *   node clean-pipeline.mjs --dry-run
 */

import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';

const PIPELINE_PATH = 'data/pipeline.md';
const APPLICATIONS_PATH = 'data/applications.md';
const DRY_RUN = process.argv.includes('--dry-run');

mkdirSync('data', { recursive: true });

function normalizeSpacing(value) {
  return value.replace(/\s+/g, ' ').trim();
}

function sanitizeField(value) {
  return normalizeSpacing(value).replace(/\s*\|\s*/g, ' / ');
}

function normalizeKey(company, title) {
  return `${sanitizeField(company).toLowerCase()}::${sanitizeField(title).toLowerCase()}`;
}

function parsePendingLine(rawLine) {
  const line = rawLine.trim();
  if (!line.startsWith('- [ ] ')) return null;
  const payload = line.slice(6).trim();
  const firstSep = payload.indexOf('|');
  const secondSep = payload.indexOf('|', firstSep + 1);
  if (firstSep === -1 || secondSep === -1) return null;
  return {
    url: normalizeSpacing(payload.slice(0, firstSep)),
    company: sanitizeField(payload.slice(firstSep + 1, secondSep)),
    title: sanitizeField(payload.slice(secondSep + 1)),
  };
}

function parseProcessedLine(rawLine) {
  const line = rawLine.trim();
  if (!line.startsWith('- [x] ')) return null;
  const payload = line.slice(6).trim();
  const parts = payload.split('|').map(part => part.trim());
  if (parts.length < 6) return null;
  return {
    reportNum: normalizeSpacing(parts[0]),
    url: normalizeSpacing(parts[1]),
    company: sanitizeField(parts[2]),
    title: sanitizeField(parts.slice(3, -2).join(' | ')),
    score: normalizeSpacing(parts.at(-2) || ''),
    pdf: normalizeSpacing(parts.at(-1) || ''),
  };
}

function formatPending(entry) {
  return `- [ ] ${entry.url} | ${entry.company} | ${entry.title}`;
}

function formatProcessed(entry) {
  return `- [x] ${entry.reportNum} | ${entry.url} | ${entry.company} | ${entry.title} | ${entry.score} | ${entry.pdf}`;
}

function loadTrackedKeys() {
  const trackedKeys = new Set();
  if (!existsSync(APPLICATIONS_PATH)) return trackedKeys;
  for (const rawLine of readFileSync(APPLICATIONS_PATH, 'utf-8').split('\n')) {
    const line = rawLine.trim();
    if (!line.startsWith('|') || line.startsWith('| #') || line.startsWith('|---')) continue;
    const parts = line.trim().slice(1, -1).split('|').map(part => part.trim());
    if (parts.length < 4) continue;
    trackedKeys.add(normalizeKey(parts[2], parts[3]));
  }
  return trackedKeys;
}

function loadPipeline() {
  if (!existsSync(PIPELINE_PATH)) {
    return { pending: [], processed: [], invalidPending: 0, invalidProcessed: 0 };
  }

  const pending = [];
  const processed = [];
  let invalidPending = 0;
  let invalidProcessed = 0;
  let section = '';

  for (const rawLine of readFileSync(PIPELINE_PATH, 'utf-8').split('\n')) {
    const line = rawLine.trim();
    if (line.startsWith('## ')) {
      section = line.toLowerCase();
      continue;
    }
    if (!line) continue;
    if (section.startsWith('## pendientes')) {
      const entry = parsePendingLine(rawLine);
      if (entry) pending.push(entry);
      else invalidPending++;
      continue;
    }
    if (section.startsWith('## procesadas')) {
      const entry = parseProcessedLine(rawLine);
      if (entry) processed.push(entry);
      else invalidProcessed++;
    }
  }

  return { pending, processed, invalidPending, invalidProcessed };
}

function buildCleanPipeline() {
  const trackedKeys = loadTrackedKeys();
  const { pending, processed, invalidPending, invalidProcessed } = loadPipeline();

  const seenProcessedReportNums = new Set();
  const seenProcessedUrls = new Set();
  const processedKeys = new Set();
  const cleanedProcessed = [];
  let removedProcessed = 0;

  for (const entry of processed) {
    if (seenProcessedReportNums.has(entry.reportNum) || seenProcessedUrls.has(entry.url)) {
      removedProcessed++;
      continue;
    }
    seenProcessedReportNums.add(entry.reportNum);
    seenProcessedUrls.add(entry.url);
    processedKeys.add(normalizeKey(entry.company, entry.title));
    cleanedProcessed.push(entry);
  }

  const seenPendingUrls = new Set();
  const seenPendingKeys = new Set();
  const cleanedPending = [];
  let removedPendingUrlDupes = 0;
  let removedPendingRoleDupes = 0;
  let removedTracked = 0;
  let removedProcessedOverlap = 0;

  for (const entry of pending) {
    const key = normalizeKey(entry.company, entry.title);
    if (seenPendingUrls.has(entry.url)) {
      removedPendingUrlDupes++;
      continue;
    }
    if (seenPendingKeys.has(key)) {
      removedPendingRoleDupes++;
      continue;
    }
    if (trackedKeys.has(key)) {
      removedTracked++;
      continue;
    }
    if (processedKeys.has(key) || seenProcessedUrls.has(entry.url)) {
      removedProcessedOverlap++;
      continue;
    }
    seenPendingUrls.add(entry.url);
    seenPendingKeys.add(key);
    cleanedPending.push(entry);
  }

  const content = [
    '## Pendientes',
    '',
    ...cleanedPending.map(formatPending),
    '',
    '## Procesadas',
    '',
    ...cleanedProcessed.map(formatProcessed),
    '',
  ].join('\n');

  return {
    content,
    stats: {
      pendingBefore: pending.length,
      pendingAfter: cleanedPending.length,
      processedBefore: processed.length,
      processedAfter: cleanedProcessed.length,
      invalidPending,
      invalidProcessed,
      removedPendingUrlDupes,
      removedPendingRoleDupes,
      removedTracked,
      removedProcessedOverlap,
      removedProcessed,
    },
  };
}

function main() {
  const { content, stats } = buildCleanPipeline();
  const previous = existsSync(PIPELINE_PATH) ? readFileSync(PIPELINE_PATH, 'utf-8') : '';
  const changed = previous !== content;

  console.log('Pipeline Clean Summary');
  console.log('---------------------------------');
  console.log(`Pending: ${stats.pendingBefore} -> ${stats.pendingAfter}`);
  console.log(`Processed: ${stats.processedBefore} -> ${stats.processedAfter}`);
  console.log(`Removed pending URL dupes: ${stats.removedPendingUrlDupes}`);
  console.log(`Removed pending role dupes: ${stats.removedPendingRoleDupes}`);
  console.log(`Removed pending already tracked: ${stats.removedTracked}`);
  console.log(`Removed pending already processed: ${stats.removedProcessedOverlap}`);
  console.log(`Removed processed dupes: ${stats.removedProcessed}`);
  console.log(`Invalid pending rows skipped: ${stats.invalidPending}`);
  console.log(`Invalid processed rows skipped: ${stats.invalidProcessed}`);

  if (!changed) {
    console.log('\nPipeline already clean.');
    return 0;
  }

  if (DRY_RUN) {
    console.log('\nDry run only — no files written.');
    return 0;
  }

  if (existsSync(PIPELINE_PATH)) {
    copyFileSync(PIPELINE_PATH, `${PIPELINE_PATH}.bak`);
  }
  writeFileSync(PIPELINE_PATH, content, 'utf-8');
  console.log(`\nUpdated ${PIPELINE_PATH}`);
  console.log(`Backup written to ${PIPELINE_PATH}.bak`);
  return 0;
}

process.exit(main());
