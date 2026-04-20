# Customization Guide

This project is easiest to maintain when each kind of customization has one
clear home.

## 1. CV Facts: `cv.md`

Put the source facts of your resume here:

- summary
- experience
- projects
- education
- skills

Treat `cv.md` as the factual source. Tailoring should pull from here, not from
scattered docs.

## 2. Candidate Identity + Targets: `config/profile.yml`

Use `profile.yml` for structured preferences and reusable targeting:

- candidate identity
- target roles
- compensation expectations
- location policy
- scan targeting lists

The `targeting` section now powers Task 5 choices for:

- focus areas
- target locations
- work modes
- saved scan profiles

If you want to add a new location or focus area later, add it here instead of
hardcoding it in scripts.

## 3. Framing and Narrative: `modes/_profile.md`

Use `_profile.md` for the softer layer:

- how your work should be framed
- role-specific mapping of projects to job families
- negotiation angles
- narrative emphasis for tailoring

Rule: put personal framing here, not in shared scripts or templates.

## 4. Scanner Configuration: `portals.yml`

Use `portals.yml` to control where and how the scanner looks:

- `tracked_companies`
- `search_queries`
- `title_filter.positive`
- `title_filter.negative`

This is where company coverage and title matching should change.

## 5. Evidence Library: `article-digest.md`

Use `article-digest.md` for extra proof points you want the system to reuse:

- shipped projects
- articles
- metrics
- awards
- speaking / teaching / community proof

## 6. Interview Stories: `interview-prep/story-bank.md`

If you want to keep reusable STAR stories, store them here. Treat it as personal
working material, not as system logic.

## 7. CV Output Design: `templates/cv-template.html`

If you want to change the HTML/PDF visual design, edit the template here.

Common edits:

- fonts
- colors
- spacing
- section layout

## 8. Canonical States: `templates/states.yml`

Only change this if you really want to rename or add tracker states. If you do,
also review `normalize-statuses.mjs`.
