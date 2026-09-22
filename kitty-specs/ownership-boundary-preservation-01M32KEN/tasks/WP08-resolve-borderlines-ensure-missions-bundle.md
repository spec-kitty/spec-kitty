---
work_package_id: WP08
title: 'Resolve borderlines: ensure-missions recopy (B3) + charter-activation bundle (B4)'
dependencies:
- WP01
requirement_refs:
- FR-010
- NFR-001
- NFR-006
planning_base_branch: fix/ownership-boundary-preservation
merge_target_branch: fix/ownership-boundary-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/ownership-boundary-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ownership-boundary-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ownership-boundary-preservation-01M32KEN
base_commit: 43c2265946324c2f443c19360c3896f35635ccfa
created_at: '2026-09-22T06:35:11.751601+00:00'
subtasks:
- T022
- T023
phase: Phase 2 - Route destructive sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- tests/specify_cli/upgrade/migrations/test_m_0_6_7_ensure_missions.py
- tests/specify_cli/upgrade/migrations/test_m_unify_charter_activation_finalize.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_0_6_7_ensure_missions.py
- src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py
- tests/specify_cli/upgrade/migrations/test_m_0_6_7_ensure_missions.py
- tests/specify_cli/upgrade/migrations/test_m_unify_charter_activation_finalize.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Resolve borderlines: ensure-missions recopy (B3) + charter-activation bundle (B4)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **B4 (`m_unify:439`) evidence points to ROUTE, not allowlist.** In the `charter_already_present`
  branch (`:425-430`) the code relocates activation keys but does NOT re-fold the legacy bundle into
  the pre-existing `charter.yaml` before unlinking it, so a divergent bundle is lost. Expect T023 to
  resolve to **route** (fold-then-delete / canonical check). If the implementer still concludes
  allowlist, the divergence probe test MUST be COMMITTED (a test proving no divergent content is
  reachable, exercising the charter-already-present branch) — never a prose-only rationale.
- **Guard performs the delete.** Route B3/B4 by replacing raw literals with `guard_destructive_removal`
  calls (B3's archive-then-recopy is already correct); no raw literal remains at the site (C1.0/C3).

## Objectives & Success Criteria

Resolve the two borderline destructive sites by red-first probe — route iff a test proves
user-content loss is possible; else allowlist with a documented rationale (no borderline is
silently dropped).

- **B3 `m_0_6_7:119`** — archive-then-recopy: a user/untracked member co-located in an incomplete
  `REQUIRED_MISSION` dir is ARCHIVED to an external `backup_parent`, THEN the legitimate
  `rmtree`+`copytree` proceeds. (In-place preserve is structurally impossible:
  `copytree(dirs_exist_ok=False)` needs the dest absent.)
- **B4 `m_unify:439`** — probe whether the compiled bundle can diverge from `charter.yaml`; route
  with a fold-then-delete/canonical check if it can, else allowlist as a compiled-only artifact
  with an in-code + gate-allowlist rationale.
- **Success**: B3 test RED on base `32cfc272ee` → GREEN; B4 resolved with either a passing preserve
  test (routed) or a documented allowlist entry (coordinated with WP09).

## Context & Constraints

- **Requirement refs**: FR-010, NFR-001, NFR-006.
- **The sites** (verified on base): `m_0_6_7_ensure_missions.py:119`
  `shutil.rmtree(dest_mission)` immediately followed by `:120` `shutil.copytree(src_mission,
  dest_mission)`; `m_unify_charter_activation_finalize.py:439` `path.unlink()` (compiled bundle,
  inside `apply()` at `:403`).
- **B3 rule**: red-first asserts the user member lands in the backup (in-place preserve is
  impossible here); the guard preserves only untracked/user members, then the legitimate recopy
  proceeds (plan Coordination Points note).
- **B4 rule**: the compiled `governance/directives/metadata/references.yaml` bundle — if it can
  diverge from `charter.yaml` (a content-loss path), route; if provably compiled-only, allowlist.
- **Design**: [research.md](../research.md) Decision 5 (B3, B4); [data-model.md](../data-model.md)
  borderline table B3/B4; [plan.md](../plan.md) Coordination Points.

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T022 – B3 `m_0_6_7`: archive-then-recopy

- **Purpose**: Preserve a user member without breaking the legitimate mission recopy.
- **Steps**:
  1. Red-first in `test_m_0_6_7_ensure_missions.py`: seed an incomplete `REQUIRED_MISSION` dir that
     also contains a user/untracked member; run the migration; assert the user member ends up in an
     external backup (`backup_parent`) AND the mission is recopied (the legitimate `rmtree`+
     `copytree` still runs).
  2. At `:119`, before the `rmtree(dest_mission)`, archive any user/untracked member OUT to
     `backup_parent` (outside `dest_mission`) via the guard; then the existing `rmtree` +
     `copytree(dirs_exist_ok=False)` proceeds unchanged.
  3. Add an in-code rationale comment: package-owned mission members are recopied; user/untracked
     members are archived first (charter L472). NFR-006.
  4. Confirm RED on base, GREEN on the final commit.
- **Files**: `src/specify_cli/upgrade/migrations/m_0_6_7_ensure_missions.py`,
  `tests/specify_cli/upgrade/migrations/test_m_0_6_7_ensure_missions.py`.
- **Notes**: leave the `:130`/`:155` `copytree` calls (no pre-existing dest) untouched; only the
  `:119` rmtree-before-recopy path needs the archive.

### Subtask T023 – B4 `m_unify`: probe bundle divergence → route or allowlist

- **Purpose**: Objectively decide whether the compiled-bundle unlink can lose content.
- **Steps**:
  1. Probe: can the compiled `references.yaml` bundle at `:439` diverge from `charter.yaml` (i.e.
     hold content not reconstructable from source)? Write a probe test that attempts to lose
     divergent bundle content through the real entry point.
  2. **If yes** (content-loss possible): route the `:439` unlink through the guard with a
     fold-then-delete / `CanonicalContentProver` check; add a preserve test + in-code rationale.
  3. **If provably compiled-only**: leave the unlink but add an in-code rationale comment (why no
     user content can be there) AND record it for WP09's frozen allowlist (coordinate — WP09 owns
     the allowlist file).
  4. Document the decision either way (NFR-006); do not silently drop the borderline.
- **Files**: `src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py`,
  `tests/specify_cli/upgrade/migrations/test_m_unify_charter_activation_finalize.py`.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/upgrade/migrations/test_m_0_6_7_ensure_missions.py \
  tests/specify_cli/upgrade/migrations/test_m_unify_charter_activation_finalize.py -q
uv run --frozen mypy --strict \
  src/specify_cli/upgrade/migrations/m_0_6_7_ensure_missions.py \
  src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py
```

- Record RED-on-base → GREEN-on-fix (B3) and the B4 route-or-allowlist decision in the PR.

## Risks & Mitigations

- **B3 recopy regression** — the archive must happen BEFORE `rmtree`, to a parent outside
  `dest_mission`; the legitimate recopy must still run.
- **B4 misclassification** — decide by probe, not assumption; if allowlisting, the rationale must
  state why no user content can be at the bundle path, and WP09 must carry the entry.
- **Cross-WP coupling** — a B4 allowlist entry lands in WP09's file; coordinate so the gate stays
  green.

## Review Guidance

- Confirm B3's user member lands in the backup AND the mission is recopied.
- Confirm B4's decision is evidence-based and documented (routed with a test, or allowlisted with a
  rationale carried in WP09).
- Confirm in-code rationale comments and clean `mypy --strict`.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
