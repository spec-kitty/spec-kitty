---
work_package_id: WP01
title: '#4921 brief chokepoint + shared guard_destructive_overwrite primitive'
dependencies: []
requirement_refs:
- FR-003
- FR-005
- NFR-003
- C-001
- C-004
planning_base_branch: issue-4931-ownership-boundary-overwrite-hardening
merge_target_branch: issue-4931-ownership-boundary-overwrite-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-4931-ownership-boundary-overwrite-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4931-ownership-boundary-overwrite-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ownership-boundary-overwrite-hardening-01M35ER3
base_commit: 638e27d2fe4885511dc2b5597d8b65ff42292310
created_at: '2026-09-22T21:39:12.345505+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- at: '2026-09-22T21:15:00Z'
  actor: claude
  note: Work package authored (tasks phase).
agent_profile: python-pedro
authoritative_surface: src/specify_cli/asset_preservation/
create_intent:
- tests/specify_cli/asset_preservation/test_guard_destructive_overwrite.py
- tests/specify_cli/test_mission_brief_overwrite_chokepoint.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/asset_preservation/guard.py
- src/specify_cli/asset_preservation/__init__.py
- src/specify_cli/mission_brief.py
- src/specify_cli/cli/commands/intake.py
- tests/specify_cli/asset_preservation/test_guard_destructive_overwrite.py
- tests/specify_cli/test_mission_brief_overwrite_chokepoint.py
- tests/specify_cli/cli/commands/test_intake.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile:
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro` + `spec-kitty charter context --action implement --mission ownership-boundary-overwrite-hardening-01M35ER3 --json`). Apply the resolved initialization, boundaries, directives, and tactics, then state which you applied. Force `PYTHONPATH=$(pwd)/src` for every pytest call, and use `.venv/bin/python -m pytest` (never a bare `uv run`, which re-syncs and destroys the hand-built `.venv`).

## Objective

Introduce ONE shared overwrite-preservation primitive `guard_destructive_overwrite`, co-located with the landed `guard_destructive_removal` in `src/specify_cli/asset_preservation/`, and use it to push the mission-brief overwrite invariant OUT of the duplicated `intake.py` CLI gates and INTO the `write_mission_brief` chokepoint (typed `BriefExistsError`). This retires the #4910 bug class one layer down (#4921) and gives WP02 the primitive it consumes.

Read first: `../spec.md` (FR-003, US3), `../plan.md` (Design → the shared overwrite primitive truth table), `../traces/design-decisions.md` (D1, D4). Study the authority you are extending: `src/specify_cli/asset_preservation/guard.py` (`guard_destructive_removal`, `OwnershipVerdict`) and `provers.py` (`OwnershipProof`, `OwnershipProver`).

## Governing invariant (charter §463-479)

Never destroy user-authored bytes without proven authorization. For an OVERWRITE the decision, when the destination holds bytes not proven package-owned:

| dest | replacement_substantive | authorized | verdict |
|---|---|---|---|
| absent | False | — | refuse (never fabricate empty) |
| absent | True | — | proceed |
| exists (user) | False | any | refuse/preserve (never truncate to empty, even under --force) |
| exists (user) | True | False | refuse/preserve (unauthorized) |
| exists (user) | True | True | proceed (optionally archive first) |
| exists (proven package-owned via prover) | True | any | proceed |

The guard stays PURE (no I/O beyond an optional archive), mirroring `guard_destructive_removal`; the caller decides how to surface a `refuse`.

## Subtasks

### T001 — Add `guard_destructive_overwrite` + `OverwriteVerdict`
In `asset_preservation/guard.py`, add `OverwriteVerdict` (frozen dataclass: `proceed: bool`, `reason: str`, `diagnostic: str`, `backup_path: Path | None`) and `guard_destructive_overwrite(dest, project_path, *, replacement_substantive: bool, authorized: bool, prover: OwnershipProver | None = None, backup_parent: Path | None = None) -> OverwriteVerdict` implementing the truth table above. When proceeding over existing user bytes and `backup_parent` is set, archive first (reuse `backup.archive_into`, as the removal guard does). Export both from `asset_preservation/__init__.py` (add to `__all__`). Keep cyclomatic complexity ≤15.

### T002 — Add typed `BriefExistsError` [P]
Add a typed error the brief writer raises when a complete brief is present and overwrite is not authorized. Put it in `mission_brief.py` (brief-local; it carries the operator-facing `--force` message text as a class attribute/arg so both CLI sites reuse one string — Sonar S1192). Export it in `mission_brief.__all__`.

### T003 — RED-first #4921 regression (write FIRST, watch it fail) — prove the DESTROYER, not a missing kwarg
Create `tests/specify_cli/test_mission_brief_overwrite_chokepoint.py`, `@pytest.mark.regression`, docstring-pin `#4921`. **The RED must reproduce the DESTRUCTION at the writer layer, NOT a `TypeError` from the new kwarg** (which proves nothing about #4921). So:
- **RED-on-base arm**: write a hand-authored brief, then call `write_mission_brief` AGAIN using the BASE signature (no `overwrite` kwarg) with different content; assert the original bytes were replaced. This is RED-on-base — it witnesses the unconditional-overwrite destroyer. (After the fix, this same call must refuse; keep it as the behavioral pin, adapting to the post-fix default `overwrite=False`.)
- **Brief-only (sidecar-absent) arm — the #4910 regression**: create ONLY `.kittify/mission-brief.md` (no `brief-source.yaml`), call `write_mission_brief(..., overwrite=False)`; assert it RAISES `BriefExistsError` and the original brief bytes are intact (the XOR must NOT unlink-then-rewrite it). This proves the refusal is keyed on existence and evaluated before the XOR.
- **GREEN-side arms**: `overwrite=True` replaces; orphan-sidecar (sidecar present, brief ABSENT) still recovers.

### T004 — Route `write_mission_brief` through the guard — existence-alone, BEFORE the XOR
Add `overwrite: bool = False` to `write_mission_brief` (`mission_brief.py:42`). Place the refusal **BEFORE** the XOR partial-state cleanup (`:73-75`): if `brief_path.exists()` (existence ALONE — do NOT require the sidecar; a brief-only file is the #4910 unknown-provenance case and must refuse) and not `overwrite`, call `guard_destructive_overwrite(brief_path, repo_root, replacement_substantive=True, authorized=overwrite)` and on `proceed=False` raise `BriefExistsError`. Only then run the XOR cleanup (unchanged) and `write_brief_atomic`. Placing it AFTER the XOR would let a brief-only file be unlinked then rewritten (re-introducing #4910) — do not. When `brief_path` is absent (orphan-sidecar), no refusal fires and recovery proceeds as today. Do not change provenance-header/sidecar logic.

### T005 — Thread `overwrite` through the real chokepoint + delegate the gates
The single write chokepoint is `_commit_brief` (`intake.py:114-137`, calls `write_mission_brief`, currently has NO `force` param), and the `--auto` path routes through `_write_brief_from_candidate`. Thread `overwrite=force` down to `write_mission_brief` from BOTH. Then replace the two duplicated `if brief_path.exists() and not force:` gates (`:155-157`, `:296-298`) with catching `BriefExistsError` from the writer → print the existing `--force` message and `raise typer.Exit(1)`. Net: the invariant lives in the chokepoint; the adapter only translates the error. Confirm `--auto`, identity, and stdin-guard paths do not regress.

### T006 — Unit tests
In `tests/specify_cli/asset_preservation/test_guard_destructive_overwrite.py` cover every truth-table row (absent/exists × substantive × authorized × package-owned-prover), including the archive-on-proceed path. Update `tests/specify_cli/cli/commands/test_intake.py` so BOTH the `--force` overwrite control and the refuse-without-force path (including the brief-only/sidecar-absent case) pass through the new delegation.

## Definition of Done

- T003 was RED on the base branch and is GREEN at the final commit (record both in review).
- All truth-table rows unit-tested; `--force` overwrite + orphan-sidecar recovery controls green (NFR-002).
- `ruff check`, `ruff format --check`, `mypy --strict` clean on touched files; complexity ≤15; no new `# noqa`/`# type: ignore`.
- Targeted tests: `tests/specify_cli/asset_preservation/ tests/specify_cli/test_mission_brief*.py tests/specify_cli/cli/commands/test_intake*.py tests/cli/test_mission_brief.py` — record commands + pass/fail counts.

## Reviewer guidance

Verify the invariant is genuinely at the chokepoint (a direct `write_mission_brief(overwrite=False)` call refuses even with NO CLICK through intake). **Critically: verify the brief-only (sidecar-ABSENT) case refuses and preserves bytes, and that the refusal is BEFORE the XOR cleanup** — a fix that only refuses on a "complete" brief, or that runs after the XOR, silently re-introduces #4910 (the RED-first T003 must have failed on base for this exact reason, not for a missing kwarg). Verify the orphan-sidecar (brief-absent) recovery path is untouched. Verify the guard is pure (no filesystem write except the optional archive). Reject if the two intake gates were merely deduplicated without moving the invariant down, or if `_commit_brief`/`_write_brief_from_candidate` were not threaded.
