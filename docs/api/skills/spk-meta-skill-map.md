---
title: "spk-meta-skill-map"
description: "Reference for the spk-meta-skill-map skill: discovering the spk-* skill hierarchy, naming convention, and legacy aliases."
doc_status: active
updated: '2026-07-21'
related:
  - docs/api/skills/index.md
---

# spk-meta-skill-map

## What it does

Helps you discover the Spec Kitty 3.2.0 `spk-*` skill hierarchy: the naming
convention, the family taxonomy, and which skill applies to a given intent.
It resolves against a full inventory (`references/spk-skill-map.md`) that
lists every `spk-*` skill by family plus the legacy `spec-kitty-*` aliases
that still exist alongside them.

## When to reach for it

Use this skill when you (or your agent) aren't sure which skill covers a
task, when you want to understand how `spk-*` names are organized, or when
you need to map a legacy `spec-kitty-*` skill name to its current `spk-*`
equivalent.

## Naming convention

Skills follow `spk-<family>-<action-or-topic>`. Families: `spk-start-*`
(onboarding), `spk-mission-*` (authoring mission artifacts), `spk-run-*`
(runtime advancement/orchestration), `spk-gate-*` (accept/merge/review/
retrospective), `spk-admin-*` (setup/config/upgrade),
`spk-team-*` (auth/sync/tracker/connectors), `spk-doctrine-*`
(charter/glossary/SPDD/profiles/bulk-edit), `spk-integrate-*` (external
APIs/CI), and `spk-meta-*` (skill discovery and authoring, this skill's own
family).

## Invocation

There is no CLI flag syntax — it is invoked by trigger phrase inside your
agent harness, e.g. asking what skills exist, how skill names are organized,
or which skill fits a request.

## Rule it applies

When more than one skill matches, it picks the narrowest matching skill,
starting from the earliest lifecycle family in order: start, mission, run,
gate, admin/team, doctrine, integrate, meta.

## See also

`spk-meta-skill-authoring` covers the flip side: writing new `spk-*` skills
under this same convention.
