---
work_package_id: WP01
title: Split the no-cascade report into already-in-force and not-in-force
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6742-no-cascade-already-in-force
merge_target_branch: issue-6742-no-cascade-already-in-force
branch_strategy: Planning artifacts for this mission were generated on issue-6742-no-cascade-already-in-force. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6742-no-cascade-already-in-force unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Behaviour
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/activate.py
- src/specify_cli/cli/commands/charter/_activation_report.py
- tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_output.py
- tests/specify_cli/cli/commands/charter/test_activation_text_golden.py
- tests/specify_cli/cli/commands/charter/test_activation_json_6525.py
- tests/specify_cli/cli/commands/charter/test_activate_include_deactivated.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Split the no-cascade report into already-in-force and not-in-force

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match
for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record each fix with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Deliver the whole behaviour change of issue #6742:

1. A referenced artifact that the project's activation state admits ("in force") is no
   longer reported as `Warning: referenced <kind>/<id> was not activated (no --cascade).`.
   It is reported as a note instead:
   `Note: referenced <kind>/<id> is already in force (<reason>); not added by this command.`
2. A referenced artifact that is **not** in force keeps the existing warning, unchanged.
   A deactivated one keeps `Warning: referenced <kind>/<id> is deactivated and was not activated.`
3. The `--cascade` recovery hint is printed only when at least one referenced artifact is
   still not in force.
4. `charter activate … --json` exposes `referenced_already_in_force` and no longer mixes
   those artifacts into `referenced_not_cascaded`.
5. Nothing about the activation itself changes: same writes, same exit code (NFR-002).

**Acceptance**: spec.md SC-001 … SC-004, and the mission's `--only`, deactivated and
kind-filtered edge cases.

## Context & Constraints

- Read `kitty-specs/no-cascade-already-in-force-01M66YRN/research.md` first: decisions D1–D5
  are already argued there (membership authority, post-write evaluation, wording, hint
  gating, JSON split).
- Read `plan.md` § Design decisions for where each change goes.
- The charter's **single canonical authority** principle is the constraint that matters
  here: do not invent a second rule for "what is in force". Use
  `PackContext.admits(kind, token, available)` (`src/charter/activation/pack_context.py`,
  documented as "the membership accessor, M2") for the verdict and
  `load_activation_ledger(repo_root).allow` (three-state: `None` = key absent) for the
  reason text.
- Do **not** change `src/charter/activation/cascade.py`. Its `NoCascadeReport` is pure
  graph logic with no project state, and it stays that way.
- **Locality of change**: the diff belongs in the two CLI modules plus tests. No new module.

## Branch Strategy

- **Strategy**: single branch — planning and implementation land on
  `issue-6742-no-cascade-already-in-force`
- **Planning base branch**: `issue-6742-no-cascade-already-in-force`
- **Merge target branch**: `issue-6742-no-cascade-already-in-force`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first test: an absent activation key reports already in force

- **Purpose**: witness the defect through the pre-existing entry point before touching
  production code (charter, ATDD-First Discipline; DIRECTIVE_034).
- **Steps**:
  1. In `tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_output.py`
     add a focused class, e.g. `TestNoCascadeAlreadyInForce`, reusing the module's existing
     fixture builders (`_write_artifact`, `_write_graph_fragment`, `_write_org_pack_config`,
     `_activate_kind_filtered_fixture`) — do not invent a new fixture stack.
  2. First case: a project with **no** `activated_<kind>` key (only
     `mission_type_activations`, exactly like the module's `project_root` fixture) and a
     source directive that `suggests` a tactic. Assert:
     - `result.exit_code == 0`
     - the output contains `already in force` for `tactic/<id>`
     - the output does **not** contain `Warning: referenced tactic/<id> was not activated`
     - the output contains no `Hint: Re-run with` line
  3. Run it. It must fail on the unfixed tree for the right reason (the old wording is
     printed). Paste the failure into the WP history note.
- **Files**: `tests/specify_cli/cli/commands/charter/test_charter_activate_commands_cascade_output.py`
- **Notes**: `spec-kitty charter activate --no-compile mission-type software-dev` on a
  project with only `mission_type_activations` is the issue's own reproduction; a small
  org-pack fixture is cheaper and equally faithful.

### Subtask T002 – Split the referenced artifacts into an already-in-force bucket

- **Purpose**: compute the verdict once, where the CLI already builds the report.
- **Steps**:
  1. `_activation_report.py`: add `already_in_force: tuple[ArtifactRef, ...] = ()` to the CLI
     `NoCascadeReport`, with a docstring that names FR-001/FR-002. Leave `warned` as
     `skipped + deactivated` and extend its docstring: the notes are not warnings.
  2. `activate.py` `_no_cascade_report(...)`: after the engine report is bucketed, build the
     project's `PackContext` (`PackContext.from_config(repo_root)`), read the ledger once
     (`load_activation_ledger(repo_root)`) for the three-state allow, and move every
     referenced artifact that is admitted out of `skipped` into `already_in_force`.
  3. Verdict: `ctx.admits(kind_enum, ref.id, available=frozenset({ref.id}))`. Skip the
     check (treat as not in force) when the kind token cannot be resolved to an
     `ArtifactKind` — `admits` needs one, and a mission type is not a referenced artifact
     kind here.
  4. Reason text helper: `allow is None` (key absent) ⇒ `"no explicit list"`; otherwise
     `f"listed in {allow_key(kind_enum)}"`. Sort and de-duplicate as the existing code does.
  5. Keep the function's docstring accurate: it now answers "referenced but not in force",
     not just "not cascaded".
- **Files**: `src/specify_cli/cli/commands/charter/_activation_report.py`,
  `src/specify_cli/cli/commands/charter/activate.py`
- **Notes**: `admits` nets the deny list first, so a deactivated artifact is never
  "in force" even when its kind has no explicit list — that is exactly FR-007. Evaluate
  after the direct write so `--only` narrowing is reflected (FR-004).

### Subtask T003 – Render the bucket as a `Note` line and re-gate the hint

- **Purpose**: the operator-facing fix. The note must not read as a warning, and the hint
  must not advertise a no-op.
- **Steps**:
  1. `render_no_cascade_warning`: print one `[dim]Note[/dim]: referenced <kind>/<id> is
     already in force (<reason>); not added by this command.` per `already_in_force` entry,
     before the remaining warnings (the position the removed warnings occupied).
  2. Leave the `skipped` and `deactivated` warning lines byte-identical.
  3. Gate the hint on the *reported* skipped set: in `_no_cascade_report`, set `hint` only
     when the post-split `skipped` tuple is non-empty (the engine's own gate stays as is).
  4. Escape nothing extra: `ArtifactRef.label` and the reason are fixed-format ASCII.
- **Files**: `src/specify_cli/cli/commands/charter/activate.py`
- **Notes**: the wording is prescribed by the issue: "already in force (no explicit list);
  not added by this command". Keep that punctuation exactly.

### Subtask T004 – Add `referenced_already_in_force` to the `--json` change report

- **Purpose**: the machine surface must keep the same distinction (FR-005, C-002).
- **Steps**:
  1. `ActivationChangeReport.to_json()`: add
     `"referenced_already_in_force": [ref.to_json() for ref in self.referenced.already_in_force] if self.referenced else []`.
  2. Place it next to `referenced_not_cascaded`, and extend that key's inline comment to say
     it now names only what is not in force.
  3. `referenced_not_cascaded` and `referenced_kind_filtered` keep their names and shapes.
- **Files**: `src/specify_cli/cli/commands/charter/_activation_report.py`
- **Notes**: `schema_version` stays `1.0.0`; the key is additive (C-002).

### Subtask T005 – Update the golden-text, JSON and cascade-output tests

- **Purpose**: the suite encodes today's wording on purpose; each changed expectation must
  be a deliberate, explained change, and the negative cases must keep proving the warning
  survives.
- **Steps**:
  1. `test_activation_text_golden.py`: update only the goldens whose fixture leaves the
     referenced artifact in force, and add a comment naming #6742 at each changed line.
     Expected updates: `activate_only` (`activated_procedures` is absent ⇒ note, and the
     hint disappears), `activate_direct_deactivated_child` (the two absent-list kinds become
     notes; the deactivated tactic keeps its warning, the hint goes).
     `activate_direct` seeds `activated_directives: []`, an explicit empty list, so all
     three references stay warnings — it must **not** change. That is the negative control
     for SC-002.
  2. `test_activation_json_6525.py`: assert the new key on the absent-list fixture and that
     `referenced_not_cascaded` no longer contains those entries; keep the `--cascade` case
     asserting both lists are `[]`.
  3. `test_charter_activate_commands_cascade_output.py`: finish the class from T001 with the
     remaining cases — explicit list that omits the reference keeps the warning; explicit
     list that already names it yields a note; `--only` narrowing keeps the warning for a
     sibling reference; deactivated reference keeps its warning; `--json` partitions.
  4. `test_activate_include_deactivated.py`: no expectation should move (both fixtures use
     explicit empty lists); if one does, stop and report rather than editing it.
- **Files**: the four test modules listed in `owned_files`
- **Notes**: do not delete an existing assertion to make the suite pass. If a fixture proves
  the split over-reaches, the production code is wrong.

### Subtask T006 – Verify no activation behaviour changed

- **Purpose**: NFR-002 and SC-004 — this is a report change.
- **Steps**:
  1. Run the four modules plus the charter activation-adjacent ones:
     `uv run pytest tests/specify_cli/cli/commands/charter/ -q -m fast`.
  2. For at least one fixture, capture the activation write before and after
     (`read_activation_ledger`) and assert it is unchanged by the report change; the golden
     tests already assert the ledger in several places — confirm rather than add.
  3. `uv run ruff check` and `uv run mypy` (or `spec-kitty lint`) on the two changed source
     files; CI runs both.
- **Files**: n/a (verification)
- **Notes**: a red caused by another module is out of scope — record it, do not weaken it.

## Test Strategy

- Red-first: T001's test fails before T002/T003 and passes after.
- `uv run pytest tests/specify_cli/cli/commands/charter/ -q -m fast`
- Type/format gate: `uv run ruff check src/specify_cli/cli/commands/charter/` and
  `uv run mypy src/specify_cli/cli/commands/charter/activate.py src/specify_cli/cli/commands/charter/_activation_report.py`
  (or `spec-kitty lint` on the touched files), matching CI.
- Diff coverage: every new branch (in-force, not-in-force, hint gate, JSON key) is exercised
  by the new tests; the CI diff-cover gate requires ≥90% on changed lines.

## Risks & Mitigations

- **Over-reach**: treating an explicit-but-empty list as "absent" would silence real
  warnings. The ledger's three-state read is the guard, and `activate_direct`'s golden is
  the regression control.
- **`--only`**: computing the verdict before the write would mislabel a narrowed list.
  Evaluate after `manager.activate`.
- **Doubled reads**: `PackContext.from_config` re-reads the ledger internally. Accept it
  (NFR-004 allows one extra read each); do not thread a half-built context into the
  activation path.
- **Wording drift**: the note text is a documented contract; copy it exactly and let the
  docs WP mirror it.

## Review Guidance

- Confirm the verdict comes from `PackContext.admits`, not from a hand-rolled
  `effective_when_absent` branch.
- Confirm every changed test expectation is justified by an absent or listed key, and that
  `activate_direct` and `test_mission_type_without_cascade_warns_about_its_references`
  (explicit empty lists) still expect warnings.
- Confirm the hint only appears when `skipped` is non-empty after the split.
- Confirm `ruff` and `mypy` ran on the touched sources.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never
in this file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
