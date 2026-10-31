---
work_package_id: WP06
title: Release workflow and checklist
dependencies:
- WP03
- WP04
requirement_refs:
- FR-009
- FR-012
- NFR-004
- C-006
planning_base_branch: companion-services-wheel
merge_target_branch: companion-services-wheel
branch_strategy: Planning artifacts for this mission were generated on companion-services-wheel. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into companion-services-wheel unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
- T021
- T022
phase: Phase 4 - Release
history:
- at: '2026-10-31T14:15:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/release.yml
create_intent:
- tests/release/test_release_companion_wheels.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/release.yml
- RELEASE_CHECKLIST.md
- tests/release/test_release_companion_wheels.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP06 – Release workflow and checklist

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter
**before parsing the rest of this prompt**, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If the profile cannot be loaded, run `spec-kitty agent profile list` and select the best match for
`task_type: implement` on `authoritative_surface: .github/workflows/release.yml`.

---

## Branch Strategy

- Planning base and final merge target: `companion-services-wheel`.
- Topology `single_branch`: no lane worktree. Work in the repository root checkout on `companion-services-wheel`.
- Start with `spec-kitty agent action implement WP06 --agent claude --mission companion-services-wheel-01M694B1`.


## Objective

Ship the companion from core's release workflow (FR-009) and gate a release on pinned services (FR-012).

## Context

- `.github/workflows/release.yml`: jobs `nightly-gate` → `build-release` → `publish-pypi` → `verify-pypi-installability`. Packs check at the step
  "Verify the fetched packs equal their pins (fail-closed on drift)". "Verify wheel contents" assumes exactly one wheel in `dist/` — keep companion wheels out of `dist/`.
- Research R-4: call `scripts/sync_services.py` directly, **not** the `sync-services` composite action (the "wire it now" ratchet in `tests/ci/test_sync_services.py` must keep its meaning).
- Existing shape tests: `tests/release/test_release_ci_ownership.py`, `tests/architectural/_workflow_jobs.py`, `tests/ci/test_fork_guard.py`. Run them.

## Subtasks

### T019 — Red tests (`tests/release/test_release_companion_wheels.py`, fast, YAML only)

1. `build-release` has a step running `scripts/sync_services.py --service all` and then one running `--check`, both after the packs check and before "Build distributions".
2. Job `build-companion-wheels`: `needs: build-release`, runs `scripts/build_services_wheel.py --out dist-services` and `--verify dist-services`, `twine check dist-services/*`, uploads artifact `companion-distributions`; never writes to `dist/`.
3. Job `publish-companion-pypi`: `needs: build-companion-wheels`, `environment.name == "pypi-services"`, `permissions.id-token == "write"`, uses the same pinned `pypa/gh-action-pypi-publish` SHA as `publish-pypi` with `packages-dir: dist-services/`.
4. `publish-pypi.needs` includes `publish-companion-pypi` and its `if:` requires that job's success.
5. No job uses `./.github/actions/sync-services`.

### T020 — sync steps

After the packs check: `PYTHONPATH=src uv run --frozen --no-sync python scripts/sync_services.py --service all` (fetch + verify the host's pinned assets) and then
`... --check` (prove the cache equals the pins). With no pin both print `no service pinned` and exit 0.

### T021 — Companion jobs

Mirror `build-release`'s `if:` guard style (`!cancelled() && needs.build-release.result == 'success'`). Steps: checkout `RELEASE_REF`, setup-python 3.12, setup-uv (same pinned SHA),
`uv sync --frozen --no-install-project`? Use the same "Install tooling" pattern as build-release minus tests, then build, verify, twine check, `sha256sum dist-services/* > SHA256SUMS-services.txt`, upload.
`publish-companion-pypi`: download artifact into `.`, publish. Update `publish-pypi` needs/if.

### T022 — RELEASE_CHECKLIST.md

- Release-Line Sanity: the `spec-kitty-services` Trusted Publisher and the `pypi-services` environment exist.
- Version planning: bump three places (root version, `packages/spec-kitty-services/pyproject.toml`, the `services` extra pin); `validate_release.py` checks it.
- Code Quality / RC Hygiene: `make sync-services` and `scripts/sync_services.py --check` are green; `scripts/build_services_wheel.py --verify` is green.
- Step 7 (monitor): companion build → companion publish → CLI publish order.
- Post-release: `pip install "spec-kitty-cli[services]==X"` installs `spec-kitty-services==X`.

## Validation

`uv run --frozen pytest tests/release/ tests/ci/test_sync_services.py tests/ci/test_fork_guard.py -q`; a YAML parse of release.yml.

## Commit discipline

- The red test is its own commit **before** the implementation commit (charter ATDD-First, C-011).
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`. No AI model identifier.
