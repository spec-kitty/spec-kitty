---
work_package_id: WP03
title: Pin the six walkers on the predicate and record the user-facing change
dependencies:
- WP01
requirement_refs:
- FR-008
- SC-003
- NFR-002
- NFR-003
- C-001
planning_base_branch: issue-6758-kitty-specs-walkers-mission-predicate
merge_target_branch: issue-6758-kitty-specs-walkers-mission-predicate
branch_strategy: Planning artifacts for this mission were generated on issue-6758-kitty-specs-walkers-mission-predicate. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6758-kitty-specs-walkers-mission-predicate unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
phase: Phase 3 - One authority, enforced, and the record
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/architectural/test_mission_resolver_walker_gate.py
- src/specify_cli/cli/commands/doctor.py
- docs/api/cli-commands.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Pin the six walkers on the predicate and record the user-facing change

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Objectives & Success Criteria

1. `tests/architectural/test_mission_resolver_walker_gate.py` carries a shrink-only ledger of the six
   walkers and fails if any of them stops calling `is_selectable_mission_dir`.
2. The raw-walk allowlist shrinks: `src/specify_cli/cli/commands/_identity_audit.py` no longer enumerates
   `kitty-specs/` itself, and each remaining allowlisted walker states how it decides residue.
3. `doctor topology`'s help text says residue is not listed and points at `doctor identity`; the generated
   CLI reference is regenerated and fresh.
4. `docs/changelog/CHANGELOG.md` has one `[Unreleased]` → `### Fixed` entry with the issue reference, the
   before/after and under 1,200 characters.
5. The architectural gate, the changelog style check and ruff all pass on the touched files.

## Context & Constraints

- Mission spec FR-008, SC-003, NFR-002, NFR-003, C-001; plan IC-03.
- WP01 and WP02 must be approved first: the ledger can only pass once all six walkers route through the
  predicate, and `_identity_audit.py` can only leave the allowlist once it uses the shared walk.
- **Do not** touch `src/specify_cli/audit/engine.py` (#6757 owns it) or the predicate's rules (C-002).
- The gate file's docstring explains its two existing mechanisms (`_WALKER_INVENTORY`,
  `_GUARDED_SEAMS`) and the detector's blind spots; follow that style rather than inventing a new one.

## Branch Strategy

- **Strategy**: feature branch, single-branch mission topology.
- **Planning base branch**: `issue-6758-kitty-specs-walkers-mission-predicate`
- **Merge target branch**: `issue-6758-kitty-specs-walkers-mission-predicate`

## Subtasks & Detailed Guidance

### Subtask T012 – Predicate ledger, AST check and planted-walker case

- **Files**: `tests/architectural/test_mission_resolver_walker_gate.py`.
- **Steps**:
  1. Add `_PREDICATE_ROUTED_WALKERS: dict[tuple[str, str], str]` with the six pairs (module path,
     function name) and one sentence each on why that walk is read-side:
     - `("src/specify_cli/cli/commands/_identity_audit.py", "_collect_topology_rows")`
     - `("src/specify_cli/cli/commands/_coordination_doctor.py", "_resolve_mission_dirs")`
     - `("src/specify_cli/cli/commands/_review_cycle_reconcile_doctor.py", "_mission_dirs_for")`
     - `("src/specify_cli/cli/commands/materialize.py", "_mission_dirs_to_process")`
     - `("src/specify_cli/charter_activate.py", "_collect_inflight_missions")`
     - `("src/specify_cli/release/changelog.py", "build_changelog_block")`
     The docstring must say the ledger is shrink-only: it may gain a walker, never lose one.
  2. Add a helper `_calls_predicate(module: str, function: str) -> bool` that parses the module with
     `ast`, **raises** (or returns a third state) if the function name is not found — a renamed walker must
     fail loudly, not pass vacuously — and returns whether any `Call` in the function's body resolves to
     `is_selectable_mission_dir` (bare `Name` or `Attribute` `.attr`).
  3. Add `test_named_walkers_route_through_the_selectable_predicate` parametrized over the ledger.
  4. Add `test_predicate_ledger_checker_detects_a_missing_call` that writes a temporary module in
     `tmp_path` with two functions (one calling the predicate, one not) and asserts the helper reports
     `True` for the first, `False` for the second, and raises for an unknown function name. This is the
     non-vacuity proof required by the architectural-gate-non-vacuity tactic.
- **Validation**: `uv run pytest tests/architectural/test_mission_resolver_walker_gate.py -q`.

### Subtask T013 – Shrink the raw-walk allowlist

- **Files**: `tests/architectural/test_mission_resolver_walker_gate.py`.
- **Steps**:
  1. Remove `"src/specify_cli/cli/commands/_identity_audit.py"` from `_LEGACY_WALKER_ALLOWLIST` and
     replace the existing explanatory comment with one covering the new state: `doctor topology` now walks
     through `mission_resolver.iter_kitty_specs_children` + `is_selectable_mission_dir`, so it needs no
     entry.
  2. For each of the five remaining allowlisted modules in the ledger, add a short comment (or extend the
     existing one) recording that the walk filters through `is_selectable_mission_dir` with one
     `TrackedMissionPaths` memo, so a reader sees the decision next to the exemption.
  3. Confirm the gate still passes with the entry removed (if it fails, the shared-walk change in WP01 is
     incomplete — report rather than re-adding the entry).

### Subtask T014 – `doctor topology` help text and the regenerated CLI reference

- **Files**: `src/specify_cli/cli/commands/doctor.py`, `docs/api/cli-commands.md`.
- **Steps**:
  1. In the `topology` command docstring add one sentence: it reports Missions only, a `kitty-specs/`
     folder that Mission selection does not list is not a row, and `spec-kitty doctor identity` reports
     such a folder as residue with its reason and remedy.
  2. Regenerate the reference with the docs script (`uv run python -m scripts.docs.build_cli_reference`,
     check `--help` for the exact form) and confirm the only diff is the `doctor topology` section.
  3. Run the freshness check (`uv run python -m scripts.docs.check_cli_reference_freshness`) and expect
     clean.
- **Notes**: keep the docstring short; it is rendered verbatim into the reference.

### Subtask T015 – Changelog entry

- **Files**: `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink to it).
- **Steps**: add one entry under `## [Unreleased] - 4.0.0rc8` → `### Fixed`, in the file's style:
  `- **<impact-first headline>** (#6758). **Before:** … **After:** … **What to do:** …`
  Content: `doctor topology` no longer lists a `kitty-specs/` folder that is not a Mission as a Mission
  with `meta.json not found`; the coordination scan, review-cycle-reconcile scan, `materialize`, the
  charter-activate in-flight warning and the release-changelog block skip such folders too; they are
  reported by `doctor identity` with a reason and a remedy. Keep it under 1,200 characters.
- **Validation**: `uv run pytest tests/release/test_validate_changelog_entry.py tests/docs -q -k changelog`
  and the changelog style checker (`scripts/docs/check_changelog_style.py`) — run whatever the repository's
  test for it uses.

### Subtask T016 – Blast radius, docs freshness and formatting

- **Steps**:
  1. `uv run pytest tests/architectural/test_mission_resolver_walker_gate.py tests/architectural/test_migration_walkers_use_mission_predicate.py -q`
  2. `uv run pytest tests/release tests/cli tests/specify_cli/cli/commands -q`
  3. `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`) and
     `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
  4. `uv run ruff check` and `uv run ruff format --check` on the four owned files.
  5. Record exact commands and counts for the PR body.

## Test Strategy

- The architectural gate is itself tested (planted walker, unknown function name) so it cannot pass
  vacuously.
- The changelog entry is validated by the repository's own style check, not by eyeballing.

## Risks & Mitigations

- **Vacuous pin**: an unknown function name must raise, not return `False`; T012's third assertion pins it.
- **Generated docs drift**: regenerate and check freshness in the same commit.
- **Changelog length**: keep before/after tight; the checker enforces 1,200 characters.

## Review Guidance

- The ledger has exactly the six walkers, each present in the module it names.
- Removing `_identity_audit.py` from the allowlist does not silence the gate for any other module.
- The changelog entry names the issue, leads with impact, and stays within the length bound.
