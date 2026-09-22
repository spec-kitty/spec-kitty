---
work_package_id: WP05
title: Preserve scripts in python-only migration (m_0_10_0 + B2)
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
base_commit: d30c95d5631f7160c700f75f8ccdebcf3eac6f5f
created_at: '2026-09-22T06:31:25.740618+00:00'
subtasks:
- T015
- T016
phase: Phase 2 - Route destructive sites
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py
create_intent:
- tests/specify_cli/upgrade/migrations/test_m_0_10_0_python_only.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py
- tests/specify_cli/upgrade/migrations/test_m_0_10_0_python_only.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Preserve scripts in python-only migration (m_0_10_0 + B2)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ Binding post-tasks corrections (supersede any conflicting text below)

- **`:229` is REQUIRED-route, not allowlist.** `_cleanup_worktree_bash_scripts` (`:229`) deletes
  user `.worktrees/*/.kittify/scripts/bash/*.sh` — same user-content hazard class as `:175`. Route it
  preserve-all like `:175`/`:187`; **never** allowlist it as "package-internal/teardown". Add a
  red-first seed at `.worktrees/<wt>/.kittify/scripts/bash/custom.sh` asserting it survives. Resolve
  this WITHIN WP05 (do not defer to WP09).
- **Add a positive non-neuter assertion.** Assert a NON-script step of `m_0_10_0` still runs, so the
  "removed N" → "preserved M" expectation rewrite cannot silently turn the migration into a no-op.
- **Guard performs the delete.** T016 replaces the `:175`/`:187`/`:250`/`:229` literals with
  `guard_destructive_removal(...)` calls (`CanonicalContentProver` → `None` → preserve-all); no raw
  literal remains at the site (contract C1.0/C3).

## Objectives & Success Criteria

Route the python-only migration's script sweeps through `CanonicalContentProver`, which returns
`None` for scripts (no marker, no shipped canonical) ⇒ **preserve-all**. Rewrite the migration's
expectations from "removed N" to "preserved M unprovable script(s) + warning".

- A user `.kittify/scripts/bash/custom.sh` and a `powershell/custom.ps1` SURVIVE the migration + a
  warning names them.
- The migration no longer deletes scripts by glob; its expectation strings/counters read
  "preserved M unprovable script(s)".
- B2 `scripts/tasks/` (`:250`) follows the same preserve-all rule.
- **Success**: tests RED on base `32cfc272ee`, GREEN on this WP's final commit; the migration's
  non-script behavior is unchanged.

## Context & Constraints

- **Requirement refs**: FR-010, NFR-001, NFR-006.
- **The sites** (verified on base, `m_0_10_0_python_only.py`): `:175` `script.unlink()` (bash
  `*.sh`); `:187` `ps_script.unlink()` (powershell `*.ps1`); `:250` `shutil.rmtree(tasks_dir)` (B2).
  Note there is also a `:229` unlink — classify it during implementation (if it is a script sweep,
  it follows the same preserve-all rule; if package-internal, allowlist with rationale via WP09).
- **Why preserve-all (charter-mandated)**: scripts carry no version marker (markers are markdown/
  `#`-comment for command files, never injected into scripts) and the package no longer ships a
  canonical to byte-match (the migration exists *because* it went python-only). No content signal
  ⇒ `CanonicalContentProver.prove()` returns `None` ⇒ preserve + warn (charter L472). "owned-delete"
  is N/A here — there is no ownership signal.
- **Do NOT allowlist the script deletes** — the current code deletes *custom* scripts, so "no
  signal" is not a safe rationale (research Decision 6).
- **Design**: [research.md](../research.md) Decision 6 + B2; [data-model.md](../data-model.md)
  census rows 2–3 + B2; [contracts/ownership-guard-contract.md](../contracts/ownership-guard-contract.md)
  C4 US4 (script clause).

## Branch Strategy

- **Strategy**: shared-lane
- **Planning base branch**: fix/ownership-boundary-preservation
- **Merge target branch**: fix/ownership-boundary-preservation

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T015 – Red-first: user scripts survive + rewrite expectations

- **Purpose**: Pin preserve-all BEFORE the fix.
- **Steps**:
  1. In `test_m_0_10_0_python_only.py`, seed `.kittify/scripts/bash/custom.sh` and
     `.kittify/scripts/powershell/custom.ps1` with distinctive bytes; run the migration; assert BOTH
     survive and a warning names them.
  2. Rewrite the migration's result expectations in the tests from "Total scripts removed: N" to
     "preserved M unprovable script(s)" (+ warning). Update any assertion counting deletions.
  3. B2: seed a user member under `.kittify/scripts/tasks/`; assert it survives.
  4. Confirm RED on base, GREEN after T016.
- **Files**: `tests/specify_cli/upgrade/migrations/test_m_0_10_0_python_only.py`.
- **Notes**: `.ps1` fixtures must work on a non-Windows CI host (no execution — byte survival only).

### Subtask T016 – Route the sweeps ⇒ preserve-all

- **Purpose**: Replace the glob deletes with the guard returning preserve-all.
- **Steps**:
  1. Route `:175`, `:187`, and B2 `:250` (and `:229` if it is a script sweep) through
     `guard_destructive_removal(path, project_path, prover=CanonicalContentProver(<no canonical;
     script has no marker>))`. Every script proves `None` ⇒ preserved in place (parent survives).
  2. Emit a warning per preserved script (or an aggregate "preserved M unprovable script(s)").
  3. Add an in-code comment documenting WHY preserve-all is charter-mandated (no ownership signal
     exists for scripts; L472) — NFR-006.
- **Files**: `src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py`.
- **Notes**: the retired package scripts are inert and simply linger; an operator may remove them
  manually. Keep the migration's non-script steps untouched.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/upgrade/migrations/test_m_0_10_0_python_only.py -q
uv run --frozen mypy --strict src/specify_cli/upgrade/migrations/m_0_10_0_python_only.py
```

- Record RED-on-base → GREEN-on-fix in the PR; note the expectation rewrite explicitly.

## Risks & Mitigations

- **Expectation rewrite regresses non-script behavior** — scope the changes to the script sweeps
  only; keep the migration's other steps and their assertions intact.
- **`:229` classification** — decide route (script sweep) vs. allowlist (package-internal) during
  implementation and coordinate with WP09's census.
- **Dishonest allowlisting** — do NOT allowlist the script deletes; they delete custom content.

## Review Guidance

- Confirm both `.sh` and `.ps1` user scripts survive and the expectations were rewritten.
- Confirm the preserve-all rationale is documented in code.
- Confirm no script is deleted by glob any more; non-script steps unchanged.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

- {{TIMESTAMP}} – system – Prompt created.
