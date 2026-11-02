---
work_package_id: WP01
title: Authority-sourced activation field set in the acceptance test
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-7038-acceptance-activation-field-pin
merge_target_branch: issue-7038-acceptance-activation-field-pin
branch_strategy: Planning artifacts for this mission were generated on issue-7038-acceptance-activation-field-pin. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7038-acceptance-activation-field-pin unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-11-02T16:58:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/acceptance/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/acceptance/test_unmigrated_cli_still_runs.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '7038'
---

# Work Package Prompt: WP01 – Authority-sourced activation field set in the acceptance test

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Make `tests/acceptance/test_unmigrated_cli_still_runs.py::test_charter_yaml_with_all_ten_activation_fields_still_loads`
green by fixing the **subject** — a stale, self-referential hard-coded count — not by re-pinning a
different number.

Success means:

- the test's activation field set comes from `charter.activation.pack_manager.ACTIVATION_YAML_KEYS`
  (the single vocabulary authority), never from a literal list or a count;
- the test still builds a `charter.yaml` document carrying every key the activation writer may
  write, validates it through `CharterYaml` (so `extra="forbid"` still proves each key is a
  declared field), and loads it through the real `charter context --action implement --json` CLI;
- an explicit non-vacuity guard fails if the authority vocabulary is ever empty;
- the test is renamed to state the property and its docstring points at the parity gate that owns
  set-equality;
- no `src/` file changes; `CharterYaml`, `ACTIVATION_YAML_KEYS` and `extra="forbid"` are untouched.

## Context

Issue #7038. `CharterYaml` declares 13 activation fields — `activated_kinds`,
`mission_type_activations`, `activated_directives`, `activated_tactics`, `activated_styleguides`,
`activated_toolguides`, `activated_paradigms`, `activated_procedures`, `activated_agent_profiles`,
`activated_mission_step_contracts`, `activated_glossary_packs`, `activated_skills`,
`activated_anti_patterns`. That is intentional: #6556 (`4d948f52c9`) added the last three because
`charter activate` on an unmigrated project writes them and the model then rejected a legitimate
charter with `extra_forbidden`. `ACTIVATION_YAML_KEYS` holds exactly those 13, and
`tests/charter/test_activation_vocabulary_setequal.py::test_charter_yaml_activation_fields_set_equal_to_authority`
already enforces model/authority set-equality in both directions.

The acceptance test was written in #6496 when the model had ten fields, so `assert len(fields) == 10`
was true then and went stale at #6556. #6556 updated the unit-level field test but missed this
file. The count was also tautological — it derived names from `CharterYaml.model_fields` and then
asserted their number — so it could only fail on a legitimate addition and never detect a wrong
key set.

Requirements: FR-001 (authority-sourced field set), FR-002 (behavioural proof kept), FR-003
(non-vacuity guard), FR-004 (name/docstring), NFR-001 (no production change), NFR-002 (test cost
unchanged), C-001 (one authority), C-002 (no duplicate parity assertion), C-003 (no gate
weakening).

## Branch Strategy

- **Planning base branch**: `issue-7038-acceptance-activation-field-pin`
- **Final merge target**: `issue-7038-acceptance-activation-field-pin` (the mission branch, which
  becomes the PR branch; `main` is never a push target)
- Execution worktrees are allocated per computed lane from `lanes.json`; do not build a workspace
  path by hand.

## Detailed Guidance

### T001 — Take the field set from the authority

Add a small function-scoped helper near the top of the test module:

```python
def _activation_field_names() -> tuple[str, ...]:
    """The flat activation-key vocabulary, from its single authority.

    Function-scoped import: ``charter.activation.pack_manager`` imports this
    module's package on its own import path, so a module-level back-import here
    would be a needless import-order dependency (same reason #6556's unit test
    imports it lazily).
    """
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS

    return tuple(ACTIVATION_YAML_KEYS)
```

Then replace

```python
fields = [name for name in CharterYaml.model_fields if name.startswith("activated_") or name == "mission_type_activations"]
assert len(fields) == 10
```

with a derivation from `_activation_field_names()`. Do **not** bump the number to 13: a second
hand-restated copy of the vocabulary is exactly what C-001 forbids, and it would go stale again on
the next legitimate addition.

### T002 — Keep the behavioural load, add non-vacuity

Keep the rest of the test's structure: exclude `activated_directives` and
`mission_type_activations` when filling the derived keys (the fixture already sets them), add the
`catalog` block, write the document, `CharterYaml.model_validate(document)`, then
`_ok(cli(repo, "charter", "context", "--action", "implement", "--json", "--no-mark-loaded"))`.

Add `assert fields` (or equivalent) before building the document so an empty authority cannot turn
the loop into a no-op. Do not add a second set-equality assertion against the model — the parity
gate owns that (C-002). If a model field were ever missing, the document would carry the key and
`model_validate` would fail with `extra_forbidden`, which is the real defect surfacing.

### T003 — Rename and document

Rename to `test_charter_yaml_loads_every_activation_field_the_writer_may_write`. Keep the "Hole 5"
reference in the docstring, state that the key list comes from the vocabulary authority, and name
`tests/charter/test_activation_vocabulary_setequal.py::test_charter_yaml_activation_fields_set_equal_to_authority`
as the owner of set-equality so a future reader does not re-add a count. Mention why the count was
wrong (#6496 wrote it at ten fields; #6556 grew the model to thirteen).

### T004 — Prove it

1. Before the change, on the current branch, run the old test and capture the failure
   (`assert 13 == 10`) — this is the red-first proof, through the pre-existing entry point.
2. After the change, run:
   - `uv run pytest tests/acceptance/test_unmigrated_cli_still_runs.py -q -p no:randomly`
   - `uv run pytest tests/charter/test_activation_vocabulary_setequal.py tests/charter/test_charter_yaml_model.py -q -p no:randomly`
3. Show the negative control without editing the model permanently: with the fix in place, confirm
   the test would fail if a key were not declared by checking that `CharterYaml.model_validate`
   rejects an unknown `activated_*` key (the parity gate's
   `test_rejects_unknown_activated_key` and this test's `extra="forbid"` path cover it). Do not
   commit any temporary mutation of `src/`.
4. `uv run ruff check tests/acceptance/test_unmigrated_cli_still_runs.py` and
   `uv run mypy tests/acceptance/test_unmigrated_cli_still_runs.py` if the module set is cheap to
   type-check; otherwise run the repository's targeted lint task for the file.

Do not run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).

### T005 — Changelog fragment and PR body input

Create `docs/changelog/unreleased/<pr>.internal.md` once the PR number exists (a test-only,
non-user-facing change), following `docs/changelog/unreleased/README.md`. Record, for the PR body,
the decision (test stale, model right), the #6496/#6556 history that proves it, and the tests run.

## Definition of Done

- [ ] `test_charter_yaml_loads_every_activation_field_the_writer_may_write` passes on the branch.
- [ ] No hard-coded activation-field count remains in the file (`grep -n "len(fields)"` is empty).
- [ ] The field set comes from `ACTIVATION_YAML_KEYS`; no second literal list exists.
- [ ] Non-vacuity guard present; behavioural model + CLI assertions still present.
- [ ] No `src/` file changed; `git diff --stat` shows the test file and Mission/changelog
      artifacts only.
- [ ] Targeted suites from T004 are green.
- [ ] Changelog fragment added (`.internal.md` for this test-only change).

## Risks and Reviewer Guidance

- **Reviewer focus**: is anything weakened? The gate must still fail when the model is missing an
  authority key (trace the `extra="forbid"` path), and the loop must not be vacuous. Confirm the
  parity gate is still the sole owner of set-equality and that no `xxfailed`/skipped/deleted test
  was introduced.
- **Reviewer focus**: does the diff touch `src/` or `ACTIVATION_YAML_KEYS`? It must not.
- **Risk**: reintroducing `activated_assets`. It is deliberately not charter-activatable; neither
  the test nor the authority should gain it.
