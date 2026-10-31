---
work_package_id: WP02
title: One write cycle per compiled-charter refresh
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- NFR-001
planning_base_branch: issue-6506-charter-write-roundtrip-latency
merge_target_branch: issue-6506-charter-write-roundtrip-latency
branch_strategy: Planning artifacts for this mission were generated on issue-6506-charter-write-roundtrip-latency. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6506-charter-write-roundtrip-latency unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-write-roundtrip-latency-01M68ZVK
base_commit: 1b1a513e5459ca91efcbed2eaa88e85524fa1689
created_at: '2026-10-31T14:50:25.840244+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 2 - Compiled-charter refresh
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/compiler.py
- tests/specify_cli/cli/commands/charter/**
- tests/specify_cli/charter_runtime/test_references_parity_refresh.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – One write cycle per compiled-charter refresh

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this
work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

`write_compiled_charter` must refresh the compiled charter's derived sections in **one** prepared
write cycle instead of one per section, and must take the preserved-timestamp decision from the
same read that produces the write. This is the user-facing half of the fix: it is what turns
17-18 s into a single-digit number.

Done means:

- one `charter.yaml` write cycle per refresh (down from two), and `charter.yaml` output is
  identical to what the previous code produced for the same input;
- a no-op recompile still writes nothing and still does not restamp `metadata.generated_at`;
- the targeted suites listed under **Test Strategy** are green, `mypy` is clean, with **no edits
  to existing assertions**.

## Context & Constraints

Read first:

- `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/research.md` — Decision 1 (where the time
  goes: 45 % of the command is this write path) and Decision 4 (why one cycle, and why the
  timestamp decision belongs to the same read).
- `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/plan.md` — "The compiled-charter refresh".
- `src/charter/activation/compiler.py::write_compiled_charter`'s docstring: it explains the
  Landmine-3 `#2772` clobber this function must never reintroduce by overwriting `charter.md`, and
  why `catalog`/`metadata` are the only sections it may touch.

Hard constraints:

- **C-001 (INV-9)**: the write still goes through the one shared helper. WP01 has already landed
  `prepare_charter_yaml_sections`; use it, do not write a second writer.
- **C-004**: `compile_charter` and the reference-building logic are out of scope. Do not touch
  them, do not cache them, do not reorder them.
- Do not touch `specify_cli/cli/commands/charter/activate.py` or `generate.py` — the call sites
  stay as they are.

## Branch Strategy

- **Strategy**: single-lane mission on the mission branch.
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Do NOT change them
> manually.

## Subtasks & Detailed Guidance

### Subtask T005 – Rewire `write_compiled_charter` to one merged prepare

- **Purpose**: Replace the two sequential `update_charter_yaml_section(charter_yaml_path,
  "catalog", catalog)` / `(..., "metadata", metadata)` calls with one
  `prepare_charter_yaml_sections(...)` + `apply_yaml_write(...)`.
- **Steps**:
  1. Keep `_assert_safe_charter_output_dir` before and after `mkdir` exactly as it is.
  2. Replace the two `update_*` calls with a single `prepare_charter_yaml_sections(
     charter_yaml_path, sections_from_document=..., )` and one `apply_yaml_write(...)`.
  3. Preserve the surrounding order precisely: the write, then `provision_mission_type_activations
     (repo_root)`, then `restamp_bundle_hash(repo_root)`, still only when `repo_root is not None`.
     The manifest's `bundle_content_hash` parity depends on running after the charter write
     (`#6366`).
  4. Leave the bootstrap branch (`charter_yaml_path` absent → `_bootstrap_charter_yaml`) alone.
- **Files**: `src/charter/activation/compiler.py`
- **Notes**: `WriteBundleResult(files_written=["charter.yaml"])` stays the return value. The
  `force` parameter stays accepted and logged (`force` no longer gates an overwrite — that is the
  Landmine-3 fix, do not "restore" it).

### Subtask T006 – Preserved timestamp from the same read

- **Purpose**: `_preserved_generated_at` currently loads the whole 165 KB document a third time
  to read one scalar and compare one section. Besides costing ~0.3-1.2 s, it opens a window where
  the file changes between that read and the write's own read.
- **Steps**:
  1. Use the `sections_from_document` callback: it receives the document loaded from the exact
     bytes the write is about to replace.
  2. Inside the callback, compute `preserved_generated_at` with the existing rule (keep the
     on-disk `metadata.generated_at` when the on-disk `catalog` is unchanged, else `None`), then
     `metadata = _build_metadata_dict(preserved_generated_at=...)`, and return
     `{"catalog": catalog, "metadata": metadata}`.
  3. Refactor `_preserved_generated_at` into a document-taking form (e.g.
     `_preserved_generated_at_from(document, catalog)`), keeping the old signature as a thin
     wrapper **only if** something else calls it. Check with `rg '_preserved_generated_at'`; if
     nothing else calls it, replace it rather than keeping dead surface.
  4. The callback must not mutate the document. State that in a comment.
- **Files**: `src/charter/activation/compiler.py`
- **Notes**: A no-op recompile (identical catalog) must still return the original bytes and
  therefore a `changed == False` prepared write. `tests/charter/test_charter_yaml_write_refusal.py`
  and the parity test in `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` are
  the guards.

### Subtask T007 – Prove output parity across both callers

- **Purpose**: `write_compiled_charter` has two callers. `charter generate` is the one that would
  notice a semantic change in the preserved-timestamp rule.
- **Steps**:
  1. Run and record: `tests/specify_cli/cli/commands/charter/` (whole tree) and
     `tests/specify_cli/charter_runtime/test_references_parity_refresh.py`.
  2. Run the mission's own byte-identity test from WP01 against the compiled-charter path: add one
     case there (or a focused test in this WP's owned test surface) that runs
     `write_compiled_charter` twice — once with the merged implementation, once with a
     monkeypatched two-cycle equivalent — and asserts identical resulting `charter.yaml` bytes.
     If the "two-cycle equivalent" is awkward to reconstruct, instead assert the resulting bytes
     equal the bytes produced by `main` for the same fixture (record the fixture's expected bytes
     against a committed copy of a small charter document).
  3. Record the round-trip count you observe before and after, using the counting approach WP03
     will formalise (a rough count is enough here; quote it in the WP history note).
- **Files**: `tests/specify_cli/cli/commands/charter/`, `tests/specify_cli/charter_runtime/`
- **Notes**: Do not add an absolute-seconds assertion anywhere (NFR-004). Report timings in the
  WP history note instead, as measurements, not as gates.

## Test Strategy

```bash
uv run pytest tests/specify_cli/cli/commands/charter/ -q
uv run pytest tests/specify_cli/charter_runtime/ -q
uv run pytest tests/charter/ -q
uv run pytest tests/architectural/ -q -k "charter or dead_symbol"
uv run mypy src/charter/activation/compiler.py
uv run ruff check src/charter/activation/compiler.py
```

Also measure the real thing, and put the numbers in your history note:

```bash
# scratch project seeded from this repository's own .kittify/
mkdir -p /tmp/wp02-repro && cd /tmp/wp02-repro && git init -q .
cp -r <repo>/.kittify . && cp -r <repo>/packs .
time spec-kitty charter deactivate tactic analysis-extract-before-interpret
time spec-kitty charter activate   tactic analysis-extract-before-interpret
```

Before the change this is ~17.3 s / ~17.9 s on the mission's reference machine; record what you
measure. **Do not turn those numbers into an assertion** — WP03 owns the measured test.

## Risks & Mitigations

- **Timestamp restamping**: if the callback's catalog comparison is wrong, every no-op recompile
  starts showing a `metadata` diff (FR-008/NFR-002 regression from the original mission). The
  parity test and the write-refusal test are the guards.
- **Manifest hash drift**: moving the write after `restamp_bundle_hash` would leave the synthesis
  manifest's `bundle_content_hash` stale. Keep the order.
- **Two-caller divergence**: `charter generate` passes `repo_root` and creates the charter; the
  bootstrap branch must stay untouched.
- **Silent output change**: if `prepare_charter_yaml_sections` normalises sections in a different
  order than the sequential calls did, key insertion order can change. WP01's byte-identity test
  covers this; run it and do not weaken it.

## Review Guidance

- Diff the write against `git show main:src/charter/activation/compiler.py` and confirm the only
  behavioural change is "two cycles → one".
- Confirm `_preserved_generated_at`'s rule is unchanged (same condition, same fallback to
  `None`).
- Confirm nothing was added to `compile_charter` or `_build_references`.
- Confirm no absolute-seconds assertion was introduced.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
