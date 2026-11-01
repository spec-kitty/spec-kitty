---
work_package_id: WP07
title: Release verifies the service pins
dependencies:
- WP06
requirement_refs:
- FR-014
- FR-015
- NFR-001
- SC-004
planning_base_branch: issue-6915-events-service-cutover
merge_target_branch: issue-6915-events-service-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6915-events-service-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6915-events-service-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T028
- T029
- T030
phase: Phase 4 - Remove and release
history:
- at: '2026-11-01T08:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/release.yml
create_intent:
- tests/ci/test_release_service_pins.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/release.yml
- RELEASE_CHECKLIST.md
- tests/ci/test_release_service_pins.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`), then load `spec-kitty charter context --action implement`. Read `research/code-grounding.md` for the facts this WP relies on.

## Branch Strategy

- Planning/base branch: `issue-6915-events-service-cutover`; final merge target: `issue-6915-events-service-cutover`.
- Topology `single_branch`: no lane worktree. `lanes.json` holds one repo-root lane; work in the repository root checkout.
- Start with: `spec-kitty agent action implement WP07 --agent <name> --mission events-service-cutover-01M6B0AE`.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>` and `Refs #6915`. No model identifier in commits.

## Objective

Gap 11: a core release fetches and checks the service pins next to the packs check, and proves the built wheel holds the pins and no service binary. `RELEASE_CHECKLIST.md` names the steps. Requirements: FR-014, FR-015, NFR-001. Keep the hunks minimal: PR #6949 also edits these two files (C-003).

## Subtasks

### T028 — Red tests

`tests/ci/test_release_service_pins.py` (check for an existing release-workflow test first: `grep -rln "release.yml" tests/ci tests/release`; extend it if one fits):
- `release.yml` has a step running `scripts/sync_services.py --service all` (fetch) and, after it, one running `scripts/sync_services.py --service all --check`, both before the build step and next to the packs `--check` step (assert ordering by step index).
- A wheel-content step asserts `specify_cli/_pins/read-service.source.yaml` is in the wheel and no member matches `mission-status-api-*`, `*.jar`, `*.exe`, `command-cli-*`.
- `RELEASE_CHECKLIST.md` names `spec-kitty service vendor --check` and `make sync-services ARGS=--check`.
Commit red.

### T029 — `release.yml`

- Around the packs `--check` step (`~:186-187`; `sync_packs.py --pack all` fetch at `~:129`): add "Fetch the pinned service assets" (`PYTHONPATH=src uv run --frozen --no-sync python scripts/sync_services.py --service all`) and "Verify the fetched service assets equal their pins (fail-closed on drift)" (`... --check`). The fetch downloads the host native build (~95 MB) — acceptable once per release; say so in a comment. A mismatch exits 1 before build.
- In the wheel content checks (`~:198-270`), add the pins-in/no-binary assertion (Python `zipfile` over `dist/*.whl`, same style as the existing checks).

### T030 — Checklist

Add, before the build section and next to `spec-kitty charter pack vendor --check` (`~:59-61`): `spec-kitty service vendor --service read-service --check` (online, against the release's SHA256SUMS) and `make sync-services` then `make sync-services ARGS=--check`; one sentence: the wheel ships pins only, never a binary (ADR `2026-10-29-1` D-4).

## Validation

```bash
uv run --frozen pytest tests/ci/test_release_service_pins.py tests/cross_cutting/packaging/ -q
actionlint .github/workflows/release.yml   # if available
uv build --wheel -o /tmp/whl && python -c "import zipfile,glob;n=zipfile.ZipFile(glob.glob('/tmp/whl/*.whl')[0]).namelist();print([x for x in n if '_pins' in x])"
```

## Definition of Done
- Release refuses on a digest mismatch before build; wheel proven pure.
