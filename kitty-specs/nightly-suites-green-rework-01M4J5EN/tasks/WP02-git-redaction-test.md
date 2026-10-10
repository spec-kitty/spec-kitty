---
work_package_id: WP02
title: Git-source credential-redaction test realignment (#5987)
dependencies: []
requirement_refs:
- FR-004
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-rework-01M4J5EN
base_commit: 2c60855a0be252c7de22d8487021babaeff67353
created_at: '2026-10-10T06:17:02.047474+00:00'
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Test realignment
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/charter_packs/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/specify_cli/charter_packs/test_sources_security.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Git-source redaction test realignment (#5987)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer, claude) before continuing.

## Objectives & Success Criteria

`test_git_source_redacts_injected_oauth_token_from_stderr` (nightly `interpreter-3.13-shard-5`, #5987) is RED because it monkeypatches `GitSource._run_git`, but the fresh-dir clone path runs through the kernel owner `clone_repository` (`src/specify_cli/charter_packs/sources/git_source.py:270`), not `_run_git`. So the test hits **real git**, and modern git strips credentials from the "Authentication failed" line → nothing to redact → `oauth2:<redacted>@` absent. The redaction code (`_redact_git_tokens`, applied at :274) is correct.

Done when: the test drives token-bearing stderr through the **real clone seam** and asserts both `token not in error_text` AND `oauth2:<redacted>@ in error_text`, on one shared fixture (FR-004).

## Context & Constraints

- **C-002**: fix the TEST to exercise the real production seam; do not weaken the assertion or the security property.
- Non-vacuity: pair the absence assertion (raw token never leaks) with a positive control (token present in git stderr → redacted marker appears) built from one shared fixture.

## Subtasks

- **T006** — Red-first: show the test is currently red because `_run_git` is patched but `_clone` calls `clone_repository`. Confirm via the current failure (`oauth2:<redacted>@` not in error_text; stderr shows a real-git auth failure with no token).
- **T007** — Monkeypatch the actual clone seam (`specify_cli.charter_packs.sources.git_source.clone_repository`, or the kernel owner it calls) to return a non-zero result whose stderr carries the injected `oauth2:<token>@…` URL. Keep the `_inject_token` assertions (token URL-encoded, raw token never in argv).
- **T008** — Assert `result.ok is False`, `token not in error_text`, `"oauth2:<redacted>@" in error_text`. Add a same-fixture positive/negative pair so the probe proves it can see the token when present.

## Branch Strategy
Planning base / merge target: `fix/nightly-suites-green-rework`. Lane from `lanes.json`.

## Validation
```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/specify_cli/charter_packs/test_sources_security.py
```

## Definition of Done
Test green through the real clone seam; non-vacuity control present; `ruff` clean. Activity Log notes the seam change.

## Reviewer Guidance (opus)
Confirm the test now exercises `clone_repository` (the production path), not only `_run_git`; verify the positive control proves non-vacuity; confirm the security property (no raw token) is unchanged.
