#!/usr/bin/env node

import { existsSync, readFileSync } from 'fs';
import yaml from 'js-yaml';

const parseYaml = yaml.load;
const PROFILE_PATH = 'config/profile.yml';

function normalizeSpacing(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function normalizeKeywordList(values) {
  return (Array.isArray(values) ? values : [])
    .map(value => normalizeSpacing(value))
    .filter(Boolean);
}

function normalizeCatalogEntry(entry) {
  return {
    key: normalizeSpacing(entry?.key),
    label: normalizeSpacing(entry?.label || entry?.key),
    keywords: normalizeKeywordList(entry?.keywords),
  };
}

function normalizeSavedProfile(entry) {
  return {
    key: normalizeSpacing(entry?.key),
    label: normalizeSpacing(entry?.label || entry?.key),
    focus_areas: normalizeKeywordList(entry?.focus_areas),
    locations: normalizeKeywordList(entry?.locations),
    work_modes: normalizeKeywordList(entry?.work_modes),
  };
}

if (!existsSync(PROFILE_PATH)) {
  console.error(`Missing ${PROFILE_PATH}`);
  process.exit(1);
}

const profile = parseYaml(readFileSync(PROFILE_PATH, 'utf-8')) || {};
const targeting = profile.targeting || {};

const payload = {
  default_saved_profile: normalizeSpacing(targeting.default_saved_profile),
  focus_areas: (targeting.focus_areas || []).map(normalizeCatalogEntry).filter(entry => entry.key),
  locations: (targeting.locations || []).map(normalizeCatalogEntry).filter(entry => entry.key),
  work_modes: (targeting.work_modes || []).map(normalizeCatalogEntry).filter(entry => entry.key),
  saved_profiles: (targeting.saved_profiles || []).map(normalizeSavedProfile).filter(entry => entry.key),
  target_roles_primary: normalizeKeywordList(profile?.target_roles?.primary),
  candidate_location: normalizeSpacing(profile?.candidate?.location),
  location_flexibility: normalizeSpacing(profile?.compensation?.location_flexibility),
  onsite_availability: normalizeSpacing(profile?.location?.onsite_availability),
  headline: normalizeSpacing(profile?.narrative?.headline),
};

process.stdout.write(JSON.stringify(payload));
