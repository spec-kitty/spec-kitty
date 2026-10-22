---
work_package_id: WP03
title: Dead hosted lifecycle builder and public-imports gate (#6607, part 1)
dependencies:
- WP02
requirement_refs:
- FR-006
- FR-007
- SC-002
- C-001
planning_base_branch: feat/event-write-hygiene
merge_target_branch: feat/event-write-hygiene
branch_strategy: Planning artifacts for this mission were generated on feat/event-write-hygiene. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/event-write-hygiene unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
phase: 'Phase 3 - #6607'
history:
- at: '2026-10-22T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/status/lifecycle_events.py
- src/specify_cli/status/__init__.py
- tests/architectural/test_events_tracker_public_imports.py
- tests/architectural/test_status_module_boundary.py
- tests/integration/test_owned_lifecycle_acceptance_finalize.py
- tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py
- tests/specify_cli/coordination/test_simple_case_flat_topology.py
- tests/specify_cli/write_side/test_characterization_root_walks.py
- tests/status/test_hermetic_ambient_git.py
- tests/status/test_lifecycle_events.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Dead hosted lifecycle builder and public-imports gate (#6607, part 1)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter, and follow its guidance before reading the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission event-write-hygiene-01M5HS55` for a `review_ref`. Address every item, and record what you changed with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

- **Delete the dead hosted-era lifecycle builder family** in `src/specify_cli/status/lifecycle_events.py`. This is the operator's ruling; none of these has a `src/` caller:
  - `_validate_lifecycle_payload` (:342). It holds the private import `spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL` at :368.
  - `_canonical_lifecycle_payload_for_saas` (:381).
  - `build_saas_lifecycle_queue_event` (:408).
  - `repo_root_for_lifecycle_log` (:398), the public alias kept only for the removed sync handler. Keep the private `_repo_root_for_lifecycle_log`, which `migrate_lifecycle_envelope.py:76` and the module itself still use.
  - Remove their facade exports in `status/__init__.py` (:289, :305, :563, :580) and their entries in `lifecycle_events.__all__` (:1287, :1288).
- **Widen `tests/architectural/test_events_tracker_public_imports.py`, red first.** It currently scans only `src/specify_cli` and bans only `._internal` modules. After this WP it scans every production root and bans any private `spec_kitty_events` / `spec_kitty_tracker` import. It gets no allowlist.
- **Done when**: no `src/` module imports a private symbol of either package. That covers a `_`-prefixed module segment and a `_`-prefixed imported name, checked on `alias.name`, never `asname`. The widened gate is red on the pre-change tree and green after.
- **Requirements**: FR-006, FR-007, NFR-004, SC-002.

## Context & Constraints

- **Read first**:
  - `kitty-specs/event-write-hygiene-01M5HS55/plan.md`, IC-04;
  - `research.md` R-1, which explains why deletion beats a public-API replacement and gives the upstream proposal;
  - `research-census.md` sections 5 and 6.
- **Public imports aliased to private local names must not trip the gate.** Examples: `glossary/events.py:41` and `tasks_transition_core.py:263`.
- **Docstrings that mention private names must not trip it either.** Examples: `validate.py:192` and `reducer.py:160`. The gate parses imports; it never matches text.
- **Test files that import `spec_kitty_events.diary` privates are out of scope.** Four files do so deliberately as library-sync gates. Per the plan, they get no allowlist and stay untouched; an upstream ask is proposed in the PR. Keep the gate scoped to `src/`.
- **Leave `tests/architectural/test_shared_package_boundary.py` alone.** It guards retired and vendored imports. Reuse its `_PRODUCTION_ROOTS` tuple (`specify_cli`, `runtime`, `charter`, `glossary`, `kernel`, `mission_runtime`) by importing it, or define the same tuple once and cite it. Do not invent a third list.
- **No lock change.** `uv.lock` and the events range stay as they are.

## Branch Strategy

- **Strategy**: `single_branch`, in the repository root checkout on `feat/event-write-hygiene`.
- **Planning base branch**: `feat/event-write-hygiene`. **Merge target branch**: `feat/event-write-hygiene`.
- **Command**: `spec-kitty agent action implement WP03 --agent claude --mission event-write-hygiene-01M5HS55`.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first: widen the public-imports gate

- **Steps**:
  1. Rewrite `_private_imports(paths)` in `test_events_tracker_public_imports.py` so it reports:
     - an `ImportFrom` whose module starts with one of the two packages and has any dotted segment starting with `_` (dunder segments like `__init__` excluded);
     - an `ImportFrom` from one of the packages whose `alias.name` starts with a single `_` (not `__`);
     - an `Import` of a dotted name with a `_` segment.

     Keep the output format `f"{path}:{lineno} -> {module}"`, extended with `:{name}` for a private name, so failures stay legible.
  2. Scan every production root (see Context), not just `src/specify_cli`, and keep the corpus-non-empty floor.
  3. Planted controls in the same test. Each must be exercised through the same `_private_imports` function:
     - public import (control): `from spec_kitty_events import Event` → no finding;
     - public import with a private local alias: `from spec_kitty_events.status import reduce as _reduce` → no finding;
     - private module: `from spec_kitty_tracker._internal.store import TrackerStore` → reported (keep this existing case);
     - private name: `from spec_kitty_events.conformance.validators import _EVENT_TYPE_TO_MODEL` → reported;
     - `import spec_kitty_events._private_mod` → reported;
     - a docstring mentioning `_EVENT_TYPE_TO_MODEL` → no finding.
  4. Update the module docstring to say the gate enforces public symbols only (ADR 2026-04-25-1 amendment, written in WP05).
  5. Run it. It must fail, reporting `src/specify_cli/status/lifecycle_events.py:368`. Commit only this file, with the message `test(arch): ban private spec_kitty_events/tracker imports across production roots (red)`, and record the red output in history.

### Subtask T011 – Delete the builder family and its exports

- **Steps**:
  1. In `lifecycle_events.py`:
     - delete `_validate_lifecycle_payload`, `_canonical_lifecycle_payload_for_saas`, `build_saas_lifecycle_queue_event` and `repo_root_for_lifecycle_log`;
     - drop their `__all__` entries;
     - remove any imports that become unused, such as `now_utc_iso` or `_generate_event_id`. Check with `ruff check`, and remove only what is truly unused.
  2. Fix stale text that names them: `lifecycle_events.py:827` and the docstring of `fanout_lifecycle_event_hosted` (:462-), which cites the removed `hosted_posture.drain_posture`. Keep that function, since WP04 renames it; make its docstring factual now.
  3. In `status/__init__.py`, remove both imports and both `__all__` entries.
  4. `src/specify_cli/status/adapters.py:329` mentions `lifecycle_events.repo_root_for_lifecycle_log(log_path)` in a docstring. Rephrase it to `_repo_root_for_lifecycle_log`, or drop the example. This is a recorded one-line leeway edit; WP04 owns the file.
- **Validation**: `rg -n "build_saas_lifecycle_queue_event|_canonical_lifecycle_payload_for_saas|_validate_lifecycle_payload|\brepo_root_for_lifecycle_log" src` is empty.

### Subtask T012 – Retarget or delete the builder's tests; run the blast radius

- **Steps**:
  1. In `tests/status/test_lifecycle_events.py`:
     - delete the tests of `_validate_lifecycle_payload` (from about :926) and `build_saas_lifecycle_queue_event` (around :1050-), including the `_EVENT_TYPE_TO_MODEL` private import at :1013;
     - keep every other test.
  2. In `tests/architectural/test_status_module_boundary.py:131-132`, update the comment or allowlist that names `build_saas_lifecycle_queue_event` / `repo_root_for_lifecycle_log`. Read the test to see whether it pins an import-boundary exemption for these names, and shrink that exemption.
  3. These five tests use `repo_root_for_lifecycle_log` and are owned by this WP:
     - `tests/integration/test_owned_lifecycle_acceptance_finalize.py`
     - `tests/specify_cli/cli/commands/agent/test_mission_setup_plan_phases.py`
     - `tests/specify_cli/coordination/test_simple_case_flat_topology.py`
     - `tests/specify_cli/write_side/test_characterization_root_walks.py`
     - `tests/status/test_hermetic_ambient_git.py`

     Only two of the five use the **public** alias: `test_simple_case_flat_topology.py` and `test_characterization_root_walks.py`. The other three name only the private `_repo_root_for_lifecycle_log`, so verify them and leave them unchanged. Read each use:
     - if it only resolves a repo root, switch it to `kernel`'s / charter's canonical resolver (`resolve_canonical_root` as imported in `lifecycle_events.py`), or to the private `_repo_root_for_lifecycle_log` through the `lifecycle_events` module;
     - if it monkeypatches the public alias to observe the hosted path, retarget it to what it actually observes, or drop that patch when it only guarded the deleted builder.

     Record each decision in history.
  4. Run:
     ```bash
     PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_events_tracker_public_imports.py tests/architectural/test_shared_package_boundary.py tests/architectural/test_status_module_boundary.py tests/architectural/test_no_dead_symbols.py -q
     PWHEADLESS=1 .venv/bin/python -m pytest tests/status <the five files above> -q -n auto --dist loadfile
     ```
     Then run `make test-fast`. Finally run mypy on `lifecycle_events.py` and `status/__init__.py`, and ruff check plus `ruff format --check --force-exclude` on the changed files.
- **Note**: deleting public facade names can trip `tests/architectural/test_no_dead_symbols.py` in the other direction, or a facade-shape test. Run the facade or contract tests that list the `status` package exports (`rg -l "__all__" tests/architectural | xargs rg -l "specify_cli.status"`).

## Risks & Mitigations

- **A facade export snapshot test** may pin the old names. Update the snapshot deliberately and note it in history.
- **Over-broad gate**: aliased public imports. The planted alias control guards against this.

## Review Guidance

- The red commit precedes the deletion, and its output names `lifecycle_events.py:368`.
- The gate scans all production roots, checks `alias.name`, has every planted control, and has no allowlist.
- `_repo_root_for_lifecycle_log`, which is still used, survives.

## Progress & Status

Use `add-history`, `mark-status T010 T011 T012 --status done`, then `move-task WP03 --to for_review`.
