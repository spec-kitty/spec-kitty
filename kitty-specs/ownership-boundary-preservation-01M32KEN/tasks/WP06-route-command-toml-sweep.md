---
work_package_id: WP06
title: Route legacy command TOML sweep (m_0_10_2)
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
base_commit: dfefb858e7cdead0241bd1d95298de86530c0a48
created_at: '2026-09-22T06:33:45.810809+00:00'
subtasks:
- T017
- T018
phase: Phase 2 - Route destructive sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/m_0_10_2_update_slash_commands.py
create_intent:
- tests/specify_cli/upgrade/migrations/test_m_0_10_2_update_slash_commands.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_0_10_2_update_slash_commands.py
- tests/specify_cli/upgrade/migrations/test_m_0_10_2_update_slash_commands.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Route legacy command TOML sweep (m_0_10_2)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **Marker is `<!-- -->` only.** The command version marker is `<!-- spec-kitty-command-version:`
  (HTML comment) even inside `.toml` prompt bodies — there is NO `# …` command marker. Use only the
  `<!-- -->` marker in `CanonicalContentProver`; since it can sit past a 15-line head in `.toml`,
  order the `AnyProver` **manifest-first** (command-skills), marker as fallback.
- **Owned-delete is a GREEN-on-base anchor**; the user-toml-survives test is the RED-on-base repro.
- **Guard performs the delete.** T018 replaces the `:153` `unlink` with a `guard_destructive_removal`
  call; no raw literal remains at the site (contract C1.0/C3).

## Objectives & Success Criteria

Route the `commands/*.toml` sweep through `AnyProver([ManifestProver(command-skills),
CanonicalContentProver(# marker)])` — prove via the command-skills manifest first, `#`-syntax
version marker as fallback.

- A user-authored `.kittify/commands/custom.toml` (no manifest entry, no marker) SURVIVES + a
  diagnostic.
- A genuinely-owned `.toml` (manifest entry with matching hash, or a marker-bearing file) is STILL
  removed.
- **Success**: tests RED on base `32cfc272ee`, GREEN on this WP's final commit.

## Context & Constraints

- **Requirement refs**: FR-010, NFR-001, NFR-006.
- **The site** (verified on base): `m_0_10_2_update_slash_commands.py:153`
  `toml_file.unlink()` (inside `apply()` at `:80`).
- **The proof**: prefer the command-skills manifest predicate first — the `.toml` version marker may
  sit PAST a 15-line head window, so a manifest hit is the reliable ownership signal; the `#`-syntax
  `CanonicalContentProver` is the fallback (research post-plan finding).
- **Design**: [data-model.md](../data-model.md) census row 4;
  [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md) C1 (prover
  composition) + C4 US4.

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T017 – Red-first: user toml survives + owned toml removed

- **Purpose**: Pin BOTH directions BEFORE the fix.
- **Steps**:
  1. In `test_m_0_10_2_update_slash_commands.py`, seed a user `.kittify/commands/custom.toml` with
     no command-skills manifest entry and no version marker; run the migration; assert it SURVIVES +
     a diagnostic.
  2. ADD an owned-delete test: a `.toml` that either has a command-skills manifest entry whose
     `content_hash` matches, OR carries the `# spec-kitty-command-version:` marker ⇒ it is removed.
  3. Confirm RED on base, GREEN after T018.
- **Files**: `tests/specify_cli/upgrade/migrations/test_m_0_10_2_update_slash_commands.py`.

### Subtask T018 – Route `:153` via `AnyProver`

- **Purpose**: Ownership-gate the sweep with a manifest-first, marker-fallback prover.
- **Steps**:
  1. Route the `toml_file.unlink()` at `:153` through
     `guard_destructive_removal(toml_file, project_path,
     prover=AnyProver([ManifestProver(<command-skills>), CanonicalContentProver(marker_syntaxes=["# …"])]))`.
  2. Delete only on `verdict.owned`; append the diagnostic on preservation.
  3. Add an in-code ownership-proof rationale comment noting the manifest-first ordering and the
     head-window caveat (NFR-006).
- **Files**: `src/specify_cli/upgrade/migrations/m_0_10_2_update_slash_commands.py`.
- **Notes**: the file has a `# noqa: C901` on `apply()` already — do not widen suppressions; if the
  routing pushes complexity, extract a small helper rather than relaxing the check.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/upgrade/migrations/test_m_0_10_2_update_slash_commands.py -q
uv run --frozen mypy --strict src/specify_cli/upgrade/migrations/m_0_10_2_update_slash_commands.py
```

- Record RED-on-base → GREEN-on-fix in the PR.

## Risks & Mitigations

- **Marker past the head window** — mitigated by the manifest-first `AnyProver` ordering.
- **Complexity creep on `apply()`** — extract a helper; do not widen the existing `# noqa: C901`.

## Review Guidance

- Confirm the user toml survives AND an owned toml is removed.
- Confirm the manifest-first ordering and the in-code rationale.
- Confirm no new suppression was added.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
