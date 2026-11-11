---
work_package_id: WP01
title: Live-site probe
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- NFR-004
- SC-002
planning_base_branch: issue-6938-docsite-canary
merge_target_branch: issue-6938-docsite-canary
branch_strategy: Planning artifacts for this mission were generated on issue-6938-docsite-canary. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6938-docsite-canary unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Probe
history:
- at: '2026-11-11T06:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/site_live_probe.py
- tests/docs/test_site_live_probe.py
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/site_live_probe.py
- tests/docs/test_site_live_probe.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Live-site probe

## ⚡ Do This First: Load Agent Profile

Load the assigned profile with the `/spk-charter-profile-load` skill (`implementer-ivan`) before reading anything else.

## Objective

Add `scripts/docs/site_live_probe.py`: it derives a small, deterministic sample of the ADR 2026-10-31-1 D-13 URL classes from the committed ledgers and checks each over HTTP against a base URL, one report line per URL, exit 1 on any mismatch, exit 2 when the sample cannot be derived. It is the logic the canary (WP02) and the post-cutover smoketest (#2361) run.

## Context & Constraints

- Spec: `kitty-specs/docsite-canary-01M74KM6/spec.md` (FR-001..FR-003, NFR-001, NFR-002, NFR-004); research R-5; data model "Probe".
- Reuse the canonical readers: `scripts.docs.moves_ledger.load_baseline`, `load_moves`, `collapse`; `scripts.docs._dockitty_contract.redirect_stub_target` (the one stub predicate). Never re-implement them. Standard library plus PyYAML through `moves_ledger`; runnable as `PYTHONPATH=.:src python3 -m scripts.docs.site_live_probe`.
- ATDD: the tests (T001, T002) are committed RED before the module.
- No YAML-shape tests (#7484): every test exercises behaviour.

## Subtasks

### T001 — Red-first tests: derivation

- Against the committed ledgers: one probe per class (`own-page-key`, `moved-chain-key`, `live-index`, `readme-key`, `directory`, `root`, `llms`, `retired`); the own-page key's target is its own directory route; the chain key's first move target is itself moved and its probe target equals the committed map value; the live index has no map key; the retired path is in neither the baseline nor the map; the derivation is deterministic.
- Against synthetic ledgers in `tmp_path`: a missing class refuses with a message naming it.

### T002 — Red-first tests: assertion branches

A fixture site in `tmp_path` served by `http.server.ThreadingHTTPServer` on `127.0.0.1:0`. Cover: all pass (exit 0); wrong status; a page that is a stub; a stub with the wrong target; a stub whose target 404s; a stub whose target is itself a stub; a non-stub where a stub is expected; the retired path serving 200; a 3xx not followed; a refused connection; retry succeeds after a transient failure (injected fetch); retries exhausted; CLI exit codes and one line per URL.

### T003 — Sample derivation

`derive_sample(baseline, moves, redirect_map) -> list[Probe]`, deterministic (first in sorted order per class), `SampleError` when a class is missing.

### T004 — HTTP check, retries, report, CLI

- `fetch` does not follow redirects, uses a timeout, returns status and body; a network error is a failed attempt.
- `check(probe, fetch)` returns an `Outcome`; `run(probes, fetch, attempts, delay, sleep)` retries each failing probe up to `attempts` with `delay` seconds between.
- CLI: `base_url`, `--attempts` (1..6, default 5), `--delay` (default 10), `--timeout` (1..30, default 15), ledger path overrides.

### T005 — Local probe of a real build

Build `site/dist` (`make docs-site`, PlantUML via `make docs-site-plantuml`) and run the probe against `python3 -m http.server -d site/dist`; record the result in the WP's activity.

## Definition of Done

- Tests green; the module at 90 %+ line coverage; ruff, `ruff format --check --force-exclude`, `mypy --strict` clean.
- The probe passes against a local build of `site/dist`.

## Reviewer guidance

Check red-first order, that every assertion branch has a test that fails when the branch is broken, and that no ledger logic is duplicated.

## Implementation command

```bash
spec-kitty agent action implement WP01 --agent claude --mission docsite-canary-01M74KM6
```
