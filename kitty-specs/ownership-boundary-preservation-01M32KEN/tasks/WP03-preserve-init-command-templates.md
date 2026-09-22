---
work_package_id: WP03
title: Preserve user command-templates in init (#4861)
dependencies:
- WP01
requirement_refs:
- C-006
- FR-005
- NFR-001
- NFR-006
planning_base_branch: fix/ownership-boundary-preservation
merge_target_branch: fix/ownership-boundary-preservation
branch_strategy: Planning artifacts for this mission were generated on fix/ownership-boundary-preservation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ownership-boundary-preservation unless the human explicitly redirects the landing branch.
subtasks:
- T011
- T012
phase: Phase 2 - Route destructive sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/init.py
create_intent:
- tests/init/test_init_command_templates_preservation.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/init.py
- tests/init/test_init_command_templates_preservation.py
- tests/cli/test_init_backup_then_proceed.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Preserve user command-templates in init (#4861)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **Guard performs the delete.** T012 replaces the `init.py:1568` `rmtree` with a
  `guard_destructive_removal(cleanup_dir, project_path, prover=ManagedPathProver(...), is_tree=True)`
  call per cleanup name — the guard preserves `command-templates` and removes `templates`/`.scratch`;
  no raw `rmtree` literal remains at the site (contract C1.0/C3).
- **Case B (config.yaml PRESENT) is a GREEN-on-base wiring/invariant guard, NOT a RED repro.** Init's
  unconditional `raise typer.Exit(0)` at `init.py:900-928` makes the `:1564` cleanup unreachable when
  config.yaml exists, so the file survives trivially on base. **Case A (config.yaml ABSENT)** carries
  the RED-on-base evidence (it falls through to `:1564`). Label the two accordingly; do not claim
  Case B is red-on-base.

## Objectives & Success Criteria

Route the single `init.py` cleanup `rmtree` (in the 3-name loop
`("templates", "command-templates", ".scratch")`) through `ManagedPathProver` so a user-authored
`.kittify/command-templates/` is preserved while genuinely regenerable scratch is still deleted —
closing #4861 (P0) and epic #4792.

- A seeded `.kittify/command-templates/custom.md` (known bytes) SURVIVES a real `init` run — with
  `config.yaml` ABSENT **and** PRESENT — either in place or in `.kittify/.backup-<ts>/`, and `init`
  exits 0 with a diagnostic naming the preserved path.
- A project that never seeded `.kittify/command-templates/` still ends with NO
  `.kittify/command-templates/`; `templates`/`.scratch` (regenerable this run) are still removed.
- **Success**: new tests RED on base `32cfc272ee`, GREEN on this WP's final commit;
  `test_init_minimal_integration.py:551` no-seed deletion case stays green (C-006, do NOT edit it).

## Context & Constraints

- **Requirement refs**: FR-005, NFR-001, NFR-006, C-006.
- **The site**: `src/specify_cli/cli/commands/init.py` lines 1564-1568 —
  `for cleanup_name in ("templates", "command-templates", ".scratch"): … shutil.rmtree(cleanup_dir)`.
  It is **ONE** `rmtree` literal in a 3-name loop. **Route it, do NOT allowlist** — allowlisting a
  target op would defeat the gate's positive-routing non-vacuity (WP09).
- **The proof**: `ManagedPathProver` returns owned for `templates`/`.scratch` (package-managed
  regenerable this run) and `None` for `command-templates` (operator-authorable LEGACY resolver
  tier ⇒ never owned-by-name ⇒ preserve).
- **Design**: [data-model.md](../data-model.md) census row 1; [spec.md](../spec.md) US2 (all three
  scenarios); [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md) C4
  US2.
- **Note**: per-path preservation (preserve `command-templates` while deleting `templates` at the
  single literal) is proven by THESE behavioural tests, not the WP09 gate (the gate is
  module-coarse).

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T011 – Red-first: command-templates preservation (config absent AND present)

- **Purpose**: Pin US2's three scenarios BEFORE the fix.
- **Steps**:
  1. NEW `tests/init/test_init_command_templates_preservation.py`. Seed
     `.kittify/command-templates/custom.md` with known bytes.
  2. **Case A — config.yaml ABSENT**: run the real `init` CLI; assert the bytes survive (in place or
     in `.kittify/.backup-<ts>/`), `init` exits 0, and a diagnostic names the preserved path.
  3. **Case B — config.yaml PRESENT**: same seed + a `.kittify/config.yaml`; assert the custom
     template is likewise preserved (proves the fix is not gated on config.yaml-absence).
  4. **Never-seeded**: a project that never authored `.kittify/command-templates/` still ends with
     NO `.kittify/command-templates/` and `templates`/`.scratch` this run created are still removed.
  5. If `tests/cli/test_init_backup_then_proceed.py` needs a companion assertion for the
     backup-then-proceed path, add it there. Do NOT edit `test_init_minimal_integration.py`.
  6. Confirm RED on base, GREEN after T012.
- **Files**: `tests/init/test_init_command_templates_preservation.py`,
  `tests/cli/test_init_backup_then_proceed.py`.

### Subtask T012 – Route the cleanup `rmtree` via `ManagedPathProver`

- **Purpose**: Preserve the operator LEGACY tier while still cleaning regenerable scratch.
- **Steps**:
  1. In the `for cleanup_name in ("templates", "command-templates", ".scratch")` loop, replace the
     raw `shutil.rmtree(cleanup_dir)` with `guard_destructive_removal(cleanup_dir, project_path,
     prover=ManagedPathProver(<regenerable contract>))`.
  2. Configure the prover so `templates`/`.scratch` (and `.resolved-*`/`.merged-*` scratch this run
     created) prove owned, and `.kittify/command-templates/` proves `None`.
  3. On `verdict.owned` ⇒ the existing `rmtree`; on unprovable ⇒ preserve/archive + append the
     diagnostic to init's output; keep `init` exit 0.
  4. Add a one-line in-code ownership-proof rationale comment (NFR-006).
- **Files**: `src/specify_cli/cli/commands/init.py`.
- **Notes**: keep the existing permission-denied `try/except` branches intact; do not add code to
  `specify_cli/__init__.py` (C-004).

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/init/test_init_command_templates_preservation.py \
  tests/cli/test_init_backup_then_proceed.py \
  tests/init/test_init_minimal_integration.py -q
uv run --frozen mypy --strict src/specify_cli/cli/commands/init.py
```

- Use the real `init` CLI entry point (not a reconstructed path) per canonical-sources doctrine.
- Record RED-on-base → GREEN-on-fix in the PR.

## Risks & Mitigations

- **One literal, per-name behavior** — the `ManagedPathProver` contract must classify the three
  names correctly; behavioural tests (not the gate) prove the per-path split.
- **config.yaml path divergence** — US2 scenario 2 explicitly exercises the present path.
- **Regressing legitimate cleanup** — `test_init_minimal_integration.py` no-seed case must stay
  green (do not edit it).

## Review Guidance

- Confirm both config.yaml states are exercised and both preserve.
- Confirm the never-seeded project still ends with no `command-templates/` and scratch is removed.
- Confirm the site is ROUTED (not allowlisted) and carries an in-code rationale.
- Confirm `mypy --strict` clean and no `__init__.py` edits.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
