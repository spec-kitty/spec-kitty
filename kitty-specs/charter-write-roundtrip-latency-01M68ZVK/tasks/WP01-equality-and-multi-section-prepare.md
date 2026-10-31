---
work_package_id: WP01
title: Cheap, exact document equality and a single-pass section writer
dependencies: []
requirement_refs:
- FR-002
- FR-007
- NFR-002
- NFR-003
planning_base_branch: issue-6506-charter-write-roundtrip-latency
merge_target_branch: issue-6506-charter-write-roundtrip-latency
branch_strategy: Planning artifacts for this mission were generated on issue-6506-charter-write-roundtrip-latency. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6506-charter-write-roundtrip-latency unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-write-roundtrip-latency-01M68ZVK
base_commit: 3123a6102efba9e9ac9fb213295f4852f472020c
created_at: '2026-10-31T12:51:54.634525+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Governed-document write path
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_charter_yaml_io_equality.py
- tests/charter/activation/test_charter_yaml_io_sections.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/charter_yaml_io.py
- tests/charter/activation/test_charter_yaml_io_equality.py
- tests/charter/activation/test_charter_yaml_io_sections.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Cheap, exact document equality and a single-pass section writer

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

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

Make `src/charter/activation/charter_yaml_io.py` stop paying a full serialise-and-reparse
comparison for a document it already holds in memory, and let it apply several owned sections in
**one** prepared write, with:

- **zero** change to any `yaml_documents_equal` verdict (NFR-003 / SC-004);
- **zero** change to the bytes any writer produces for the same mutation (FR-007 / SC-003);
- the existing `tests/charter/**` suite green **without editing a single assertion**.

Done means: the two new test files exist and pass, and the whole `tests/charter/` tree plus
`tests/specify_cli/upgrade/migrations/` is green.

## Context & Constraints

Read first:

- `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/research.md` — Decisions 2, 3 and 4 carry
  the measured unit costs and the exact step breakdown of one `render_yaml_document`.
- `kitty-specs/charter-write-roundtrip-latency-01M68ZVK/plan.md` — "Phase 1 — Design" has the
  equality rule and the multi-section signature already worked out.
- The module docstring of `src/charter/activation/charter_yaml_io.py`: it explains INV-9 (three
  writers, one helper) and the INV-7 layer rule. Both still hold when you are done.

Hard constraints:

- **C-001 (INV-9)**: this stays the single writer. You are removing a redundant *pass*, not
  adding a second authority.
- **C-002 (INV-7)**: this module must not import `specify_cli`. `tests/architectural/` guards it.
- **C-004**: do not touch `compiler.py` (that is WP02) and do not touch any gate.

## Branch Strategy

- **Strategy**: single-lane mission on the mission branch.
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Equality-equivalence corpus (write this FIRST)

- **Purpose**: A behaviour-preserving refactor is only safe if something pins the old behaviour
  before you change it. This test is that pin, and it is the red-first artefact: as a
  *characterisation* test it passes against the current implementation and must keep passing.
- **Steps**:
  1. Create `tests/charter/activation/test_charter_yaml_io_equality.py`.
  2. Keep a frozen copy of today's implementation in the test module as
     `_event_only_equal(left, right)` — literally `bool(left == right) or
     _yaml_value_events(left) == _yaml_value_events(right)` using the module's own private
     helpers — so the corpus compares "new" against "the behaviour that shipped", not against a
     rewritten restatement of it.
  3. Build the corpus from, in this order:
     - this repository's own `.kittify/charter/charter.yaml` (skip with `pytest.skip` if absent,
       e.g. in an sdist install);
     - every `packs/built-in/**/*.yaml` document that the round-trip loader can parse (cap the
       count so the test stays fast, e.g. the first 120 by sorted path);
     - synthetic documents covering each opaque case: an explicit tag (`!!str`, a custom
       `!foo`), an anchored-and-aliased subtree, a mapping with non-string keys, an
       insertion-order permutation of the same mapping, a tagged scalar nested inside an
       otherwise-equal mapping.
  4. For each base document, compare these pairs against `_event_only_equal`: (a) an identical
     copy, (b) a deep copy with one leaf changed, (c) a deep copy with one top-level key removed,
     (d) an order-permuted copy.
  5. **Non-vacuity assertion**: assert that the corpus contains at least one pair the reference
     implementation calls `True` and one it calls `False`, per category. A corpus that is all
     `False` proves nothing.
- **Files**: `tests/charter/activation/test_charter_yaml_io_equality.py`
- **Parallel?**: yes — independent of T003.
- **Notes**: `_yaml_value_events` is private; importing it in a test is acceptable here because
  the whole point is to freeze the pre-change behaviour. Name the import accordingly and add a
  comment that the frozen copy exists on purpose.

### Subtask T002 – Structural equality with a leaf-level event fallback

- **Purpose**: The two whole-document comparisons in `render_yaml_document` cost ~1.2 s each
  because the fallback dumps the entire value and re-parses it. Make it cost the changed leaf.
- **Steps**:
  1. Reimplement `yaml_documents_equal(left, right)` as a depth-first comparison:
     - `left is right` → `True`;
     - `bool(left == right)` → `True` (keep this clause FIRST; it is what makes the no-op case
       free and it is the existing contract);
     - both `Mapping` with the same key set → recurse pairwise (do **not** compare order; the
       `==` clause above is order-insensitive too, so comparing order here would make the new
       function stricter than the old one);
     - both non-string `Sequence` with equal length → recurse element-wise;
     - otherwise → the existing `_yaml_value_events(left) == _yaml_value_events(right)`.
  2. Implement the recursion iteratively or with an explicit stack — a deeply nested doctrine
     document must not raise `RecursionError` where it previously did not.
  3. Document the rule in the docstring: which clause decides what, and why the event fallback
     is still needed (opaque tagged scalars / anchors compare by identity).
- **Files**: `src/charter/activation/charter_yaml_io.py`
- **Notes**: Do not "improve" `_yaml_value_events`; it must stay byte-for-byte the old fallback so
  T001 can prove equivalence. `command_renderer.py` and `installer.py` also call
  `yaml_documents_equal` and get faster for free — do not edit them.

### Subtask T003 – Multi-section prepared write

- **Purpose**: `write_compiled_charter` writes `catalog` and `metadata` as two independent
  cycles; each cycle re-observes, re-loads, re-renders and re-verifies the whole document. One
  cycle must be able to carry several owned sections.
- **Steps**:
  1. Add `prepare_charter_yaml_sections(path, *, sections=None, sections_from_document=None,
     remove=())`:
     - exactly one of the two keyword forms; raise `ValueError` if both or neither;
     - `sections`: a `{section: values}` mapping; `sections_from_document`: a callable given the
       freshly loaded, **not yet mutated** document, returning the same mapping (it exists so a
       caller can decide one section's content from the document it is about to overwrite —
       WP02 needs it for the preserved timestamp);
     - validate **every** section with the existing `_validate_section` and the removals with the
       existing `_validate_removals`; do not add a parallel validation path;
     - under the `"activation"` pseudo-section semantics, keep the existing behaviour: activation
       values are flat root keys, every other section is `{section: values}`;
     - observe the input once, load once, apply all changes and removals, render once, and
       return one `prepare_yaml_write(...)` with the same `inputs=` as today.
  2. Rewrite `prepare_charter_yaml_section(path, section, values, *, remove=())` as a thin
     delegation to it, so all eight existing call sites (activation ledger, pack manager, two
     upgrade migrations) keep working unchanged.
  3. Keep `update_charter_yaml_section` exactly as it is apart from delegating.
  4. Keep `__all__` in step with the new export.
- **Files**: `src/charter/activation/charter_yaml_io.py`
- **Parallel?**: yes — independent of T001.
- **Notes**: The `remove=` contract belongs to the `activation` section only; preserve that
  refusal. Preserve the "a key both set and removed is a `ValueError`" refusal for the merged
  form too, across all supplied sections.

### Subtask T004 – Byte-identity corpus

- **Purpose**: Prove the merged path produces exactly the bytes the sequential path produced
  (FR-007 / SC-003). This is the guard that lets a governed document be rewritten by new code.
- **Steps**:
  1. Create `tests/charter/activation/test_charter_yaml_io_sections.py`.
  2. For a corpus of base documents (this repository's own `charter.yaml`, a couple of shipped
     pack documents, and small synthetic ones with comments, a document prefix comment, a
     null-root document and a flow-style root where applicable), and for a matrix of section
     sets, assert:
     `prepare_charter_yaml_sections(p, sections={"a": va, "b": vb}).desired_bytes ==
      apply-of prepare_charter_yaml_section(p, "a", va) then prepare_charter_yaml_section(p, "b", vb)`.
     Do this by driving the *sequential* form against a real temporary file twice (that is the
     old behaviour, still reachable through the delegating single-section call) and the merged
     form once against a fresh copy, then comparing the resulting bytes.
  3. Cover the edge cases from the spec: a section absent from the document (must be appended in
     the same position the sequential path chose), a `remove=`-only write, and a no-op write
     (identical bytes back, and `PreparedYamlWrite.changed` is `False`).
  4. Cover `sections_from_document`: assert the callable is handed a document equal to the
     on-disk content (not the mutated one), and that what it returns is what gets written.
- **Files**: `tests/charter/activation/test_charter_yaml_io_sections.py`
- **Notes**: Use `tmp_path`; never mutate a fixture in the repository. Assert on bytes, not on
  parsed structures — the whole point is byte identity.

## Test Strategy

Run, from the repository root:

```bash
uv run pytest tests/charter/ -q
uv run pytest tests/charter/activation/test_charter_yaml_io_equality.py \
               tests/charter/activation/test_charter_yaml_io_sections.py -q
uv run pytest tests/architectural/ -q -k "charter or dead_symbol or perf_limit"
uv run mypy src/charter/activation/charter_yaml_io.py
uv run ruff check src/charter/activation/charter_yaml_io.py \
                  tests/charter/activation/test_charter_yaml_io_equality.py \
                  tests/charter/activation/test_charter_yaml_io_sections.py
```

`mypy` must be clean — this repository runs it strict on `src/` and a passing pytest run does not
substitute for it.

## Risks & Mitigations

- **Lenient equality** (the dangerous direction): a recursive comparison that says "equal" where
  the serialised forms differ would let a lossy render through. Mitigation: T001's corpus
  includes the negative pairs and asserts verdict equality in both directions.
- **Order sensitivity**: comparing mapping order would make the new function stricter than the
  old one and could start refusing writes that used to succeed. Mitigation: do not compare order;
  the `==` clause is order-insensitive.
- **Recursion depth**: use an explicit stack.
- **Receipts**: `apply_yaml_write`'s `precondition_changed` checks must be untouched. The
  existing tests in `tests/charter/test_charter_yaml_write_refusal.py` are the guard; they must
  pass without modification.

## Review Guidance

- Confirm the frozen `_event_only_equal` in the test really is today's behaviour (diff it against
  `git show main:src/charter/activation/charter_yaml_io.py`).
- Confirm no assertion in an existing test was edited to accommodate the change.
- Confirm `prepare_charter_yaml_section`'s eight call sites are untouched.
- Confirm `__all__` and the module docstring still describe what the module does.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in this
prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
