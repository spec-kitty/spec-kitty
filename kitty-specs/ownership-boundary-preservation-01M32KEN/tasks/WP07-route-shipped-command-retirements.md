---
work_package_id: WP07
title: Route shipped command/skill retirements (clarify/release/profile-context)
dependencies:
- WP01
requirement_refs:
- C-001
- FR-010
- NFR-001
- NFR-006
planning_base_branch: fix/ownership-boundary-preservation
merge_target_branch: fix/ownership-boundary-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/ownership-boundary-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ownership-boundary-preservation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ownership-boundary-preservation-01M32KEN
base_commit: 1bfd6d2d54c67b06f5f74617b14dc23808ab8f83
created_at: '2026-09-22T06:34:28.645347+00:00'
subtasks:
- T019
- T020
- T021
phase: Phase 2 - Route destructive sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent:
- tests/specify_cli/upgrade/migrations/test_m_2_0_11_remove_clarify_command.py
- tests/specify_cli/upgrade/migrations/test_m_2_1_2_remove_release_skill.py
- tests/specify_cli/upgrade/migrations/test_m_2_2_0_profile_context_deployment.py
- tests/specify_cli/upgrade/migrations/test_m_3_2_0rc43_retire_profile_context_command.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_2_0_11_remove_clarify_command.py
- src/specify_cli/upgrade/migrations/m_2_1_2_remove_release_skill.py
- src/specify_cli/upgrade/migrations/m_2_2_0_profile_context_deployment.py
- src/specify_cli/upgrade/migrations/m_3_2_0rc43_retire_profile_context_command.py
- tests/specify_cli/upgrade/migrations/test_m_2_0_11_remove_clarify_command.py
- tests/specify_cli/upgrade/migrations/test_m_2_1_2_remove_release_skill.py
- tests/specify_cli/upgrade/migrations/test_m_2_2_0_profile_context_deployment.py
- tests/specify_cli/upgrade/migrations/test_m_3_2_0rc43_retire_profile_context_command.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Route shipped command/skill retirements (clarify/release/profile-context)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **Marker is `<!-- -->` only** — drop any `# …` syntax. **T021 is MANDATORY**: verify each shipped
  target actually carries the `<!-- spec-kitty-command-version:` marker; if a site's target does not,
  reclassify that site to `ManifestProver`. The three command sites (`m_2_0_11`, `m_2_2_0`,
  `m_3_2_0rc43`) carry the marker; `m_2_1_2` release is a SKILL → `ManifestProver` (already correct).
- **Owned-delete halves are GREEN-on-base anchors**; the preserve halves are the RED-on-base repros.
- **Guard performs the delete.** T020 replaces each site's raw `unlink`/`rmtree` with a
  `guard_destructive_removal(...)` call; no raw literal remains at any site (contract C1.0/C3).

## Objectives & Success Criteria

Route four shipped-asset retirement migrations through their provers so a user-authored file that
collides by name but is unprovable SURVIVES, while a genuinely-owned target is still removed.

- `m_2_0_11_remove_clarify_command.py:52` — `CanonicalContentProver` (BOTH marker syntaxes; the
  broad `spec-kitty.clarify*` match is exactly the charter-warned pattern).
- `m_2_1_2_remove_release_skill.py:55` — `ManifestProver` (managed skills; `.claude/skills/release`).
- `m_2_2_0_profile_context_deployment.py:61` — `CanonicalContentProver` (`<!-- -->` marker).
- `m_3_2_0rc43_retire_profile_context_command.py:48` — `CanonicalContentProver`.
- **Success**: per-site preserve + owned-delete tests RED on base `32cfc272ee`, GREEN on this WP's
  final commit.

## Context & Constraints

- **Requirement refs**: FR-010, NFR-001, NFR-006, C-001.
- **The sites** (verified on base): `m_2_0_11:52` `target.unlink()`; `m_2_1_2:55`
  `shutil.rmtree(skill_dir)`; `m_2_2_0:61` `dest.unlink()`; `m_3_2_0rc43:48` `dest.unlink()`.
- **Marker verification (T021)**: `CanonicalContentProver` over-preserves a genuinely-owned target
  if the target carries no marker. CONFIRM each canonical target actually carries
  `spec-kitty-command-version:` in a scanned syntax; if not, reclassify that site to
  `ManifestProver` (command-skills) or a last-shipped-hash `canonical_bytes`.
- **Design**: [data-model.md](../data-model.md) census rows 5–8; [spec.md](../spec.md) US4;
  [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md) C4 US4;
  [research.md](../research.md) post-plan finding (retired-command canonical sites may over-preserve).

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T019 – Red-first per site: unprovable collisions survive

- **Purpose**: Pin the preserve direction for all four sites BEFORE the fix.
- **Steps**:
  1. Create any missing test file (all four are in `create_intent`).
  2. Per site, seed a user-authored file that collides by name with the retired asset but is
     unprovable (no manifest entry / no marker / bytes differ): a clarify command, the release
     skill dir, and the two `spec-kitty.profile-context.md` files.
  3. Assert each SURVIVES (in place or recoverable backup) + a diagnostic.
  4. Confirm RED on base, GREEN after T020/T021.
- **Files**: the four `test_m_*.py` files above.

### Subtask T020 – Route each site to its prover

- **Purpose**: Ownership-gate each delete.
- **Steps**:
  1. `m_2_0_11:52` → `CanonicalContentProver(marker_syntaxes=["<!-- … -->", "# …"])`.
  2. `m_2_1_2:55` → `ManifestProver(<managed skills>)` (route the `rmtree(skill_dir)`; archive to an
     external `backup_parent` since a directory is removed).
  3. `m_2_2_0:61` → `CanonicalContentProver(marker_syntaxes=["<!-- … -->"])`.
  4. `m_3_2_0rc43:48` → `CanonicalContentProver`.
  5. Delete only on `verdict.owned`; append the diagnostic on preservation.
- **Files**: the four migration modules above.

### Subtask T021 – Marker verification, owned-delete tests, and rationale

- **Purpose**: Prevent over-preservation and prove non-vacuity.
- **Steps**:
  1. For each canonical site, VERIFY the shipped target file carries the version marker in a scanned
     syntax; if a target has no marker, RECLASSIFY that site to `ManifestProver` (command-skills) or
     supply `canonical_bytes` (last-shipped hash). Record the classification decision.
  2. ADD an owned-delete direction test per site: a marker-bearing/canonical-matching (or
     manifest-owned) target IS removed + entry pruned where applicable.
  3. Add a one-line in-code ownership-proof rationale comment at each routed site (NFR-006).
- **Files**: the four migration modules + their test files.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/upgrade/migrations/test_m_2_0_11_remove_clarify_command.py \
  tests/specify_cli/upgrade/migrations/test_m_2_1_2_remove_release_skill.py \
  tests/specify_cli/upgrade/migrations/test_m_2_2_0_profile_context_deployment.py \
  tests/specify_cli/upgrade/migrations/test_m_3_2_0rc43_retire_profile_context_command.py -q
uv run --frozen mypy --strict \
  src/specify_cli/upgrade/migrations/m_2_0_11_remove_clarify_command.py \
  src/specify_cli/upgrade/migrations/m_2_1_2_remove_release_skill.py \
  src/specify_cli/upgrade/migrations/m_2_2_0_profile_context_deployment.py \
  src/specify_cli/upgrade/migrations/m_3_2_0rc43_retire_profile_context_command.py
```

- Record RED-on-base → GREEN-on-fix per site in the PR.

## Risks & Mitigations

- **Over-preservation** (canonical site with no marker) — mitigated by T021 verification /
  reclassification; do not assume a marker exists.
- **Directory removal** (`m_2_1_2`) — external `backup_parent` for the archive.
- **Broad name match** (`spec-kitty.clarify*`) — the guard's content proof, not the glob, decides.

## Review Guidance

- Confirm each site has BOTH a preserve and an owned-delete test.
- Confirm the marker verification / reclassification decision is recorded per site.
- Confirm in-code rationale comments and clean `mypy --strict`.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
