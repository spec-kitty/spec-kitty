---
work_package_id: WP03
title: Machine-readable --json diagnostics (unresolved_references)
dependencies:
- WP02
requirement_refs:
- FR-004
planning_base_branch: fix/charter-generation-drops-scoped-references-5257
merge_target_branch: fix/charter-generation-drops-scoped-references-5257
branch_strategy: Planning artifacts for this mission were generated on fix/charter-generation-drops-scoped-references-5257. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-generation-drops-scoped-references-5257 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-generation-drops-scoped-references-01M3M1KF
base_commit: 3759ea9e4f334e5fea85f4c74a9e99fb831bb7fc
created_at: '2026-09-28T23:18:27.588969+00:00'
subtasks:
- T016
- T014
- T015
history: []
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/charter/generate.py
- tests/specify_cli/cli/commands/test_charter_generate_autotrack.py
role: implementer
tags: []
tracker_refs: []
---

# WP03 — Machine-readable `--json` diagnostics (`unresolved_references`)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add a new, additive `unresolved_references` field to `charter generate --force --json`'s
output, sourced from WP02's new structured-records field on the compiler's result type, so
automated callers (CI, readiness probes) can detect an unresolved-reference condition without
string-matching the free-text `diagnostics` field.

This WP produces TWO separate commits, each independently verified, per charter C-011 (binding,
no size-based carve-out): commit 1 = T016's Acceptance Scenario 2 assertion, committed ALONE,
verified RED against WP02's already-landed compiler fix (at that point `--json` does not yet
emit `unresolved_references` at all); commit 2 = T014 (the `unresolved_references` emit) + T015
(the `diagnostics`-shape regression check), committed together strictly after commit 1, turning
T016's assertion GREEN. FR-004 (the `unresolved_references` JSON field) is a genuine,
user-observable contract addition with no pre-existing red-first test — WP01 explicitly disclaims
covering `--json` wiring ("WP03's job") — so this WP owns its own red-first commit.

## Context

Read `kitty-specs/charter-generation-drops-scoped-references-01M3M1KF/contracts/charter-generate-json-diagnostics.md`
IN FULL before writing any code — this contract document was already written and finalized
during planning (rounds 3, 5, and 6 all added content to it). **Your job is to make the CODE
match the already-written contract, not to rewrite the contract doc.** Do not edit the contract
doc unless you find it is factually wrong about what the code actually does once WP02 lands (in
which case, fix the doc to match reality and note the correction in your WP completion note —
this should not normally be necessary).

**The contract, summarized (verify against the actual document, this is not a substitute for
reading it):**

- New top-level key `unresolved_references: list[{"kind": str, "id": str, "cause": str,
  "detail": str}]`, always present (empty list `[]` when there are no unresolved DRG-backed
  references) — same always-present convention as the existing `diagnostics` field.
- `kind` is one of the six DRG-backed kinds `_render_kind_references` covers (`directive`,
  `tactic`, `styleguide`, `toolguide`, `procedure`, `agent_profile`), OR one of the reserved
  sentinel values `_graph` (graph-load failure) / `_unattributed` (malformed URN).
- `id` is the bare activated id (no `KIND:` prefix), OR the reserved sentinel `_load_failure`,
  OR the full malformed URN string for the `_unattributed` case.
- `cause` is one of: the three `CatalogMissCause.value` strings (`"missing_artifact"`,
  `"typo_suspected"`, `"scope_filtered"`), or `"graph_load_failed"`, or `"malformed_urn"`, or
  `"unattributed_kind"`.
- `detail` is the human-readable text WP02's structured record already carries — do not
  reformat or truncate it.
- The existing `diagnostics: list[str]` field's SHAPE is completely unchanged (still a flat list
  of strings) — only its per-line CONTENT gains a reason suffix, which WP02 already did. You
  must not touch how `diagnostics` is built in `generate.py`, only add the new key alongside it.

**Why additive-alongside, not widening `diagnostics`** (do not "improve" this design — it was a
deliberate, reviewed decision): any existing consumer that treats `diagnostics` as `list[str]`
(CI scripts, readiness probes, `_finalize_sync_result`'s own sync-warning concatenation) keeps
working unchanged. A new, always-present key is additive and detectable
(`"unresolved_references" in payload`) without touching the existing key's shape.

## Subtask T016: Acceptance Scenario 2 — id + reason present machine-readably (commit 1 — authored and committed FIRST, alone)

**Purpose**: Directly pin spec.md's User Story 1 Acceptance Scenario 2: "the JSON output's
diagnostics field carries the same reference id and reason machine-readably... so CI and
readiness probes consuming `--json` can detect the condition without parsing prose." This is
WP03's own red-first test for the FR-004 behavior it delivers — per charter C-011, it is authored
and committed BEFORE T014's implementation.

**Steps**: Using the Scenario-1 fixture pattern (a repo whose `.kittify/charter/charter.yaml`
activates `styleguide/java-conventions` in a repo whose `infer_repo_languages` excludes `java`),
run `spec-kitty charter generate --force --json` against WP02's already-landed compiler fix (at
this point `--json` does not yet emit `unresolved_references` at all) and assert:
`unresolved_references` contains an entry with `kind: "styleguide"`, `id: "java-conventions"`,
`cause: "scope_filtered"`, and a non-empty `detail` naming the active language set. Confirm this
assertion FAILS (RED) before committing — the key does not exist pre-T014.

**Files**: `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` (extended — the
only real candidate that already exercises `generate --json`; do not create a new test file).

**Validation**: Run this new assertion against WP02's landed compiler fix, before T014's
implementation, and confirm it FAILS (RED) — record the exact RED pytest output. Commit this
assertion ALONE (`git add tests/specify_cli/cli/commands/test_charter_generate_autotrack.py &&
git commit`), with a message naming the RED verification, before starting T014.

## Subtask T014: Add `unresolved_references` to the `--json` emit block (commit 2, with T015)

**Purpose**: Thread WP02's new structured-records field through to the CLI's JSON output, turning
T016's red-first assertion GREEN.

**Steps**:
1. Locate the existing JSON-emit block in `src/specify_cli/cli/commands/charter/generate.py`
   (the `diagnostics: list[str]` field is built around lines ~538-559 per plan.md's "Whether any
   contract moves" citation — re-verify the exact current line numbers against live `HEAD`
   source, do not trust the plan's citation blindly since other line numbers drifted across
   planning rounds).
2. Read the new structured-records field WP02 exposed on the compiler's result type (e.g.
   `compiled.unresolved_reference_records` — confirm the exact attribute name WP02 actually
   used; it is documented in WP02's own completion note / `git log`/`git show` on WP02's commit
   if you need to check).
3. Add `"unresolved_references": [...]` to the emitted JSON dict, mapping each structured record
   to the exact `{kind, id, cause, detail}` shape the contract doc defines — no reformatting, no
   truncation, no additional keys.
4. Ensure the key is present (as `[]`) even when there are zero unresolved references — do not
   conditionally omit the key.

**Files**: `src/specify_cli/cli/commands/charter/generate.py` (small, localized addition to the
existing JSON-emit block — do not restructure the surrounding function).

**Validation**: Manually construct (or reuse a WP02 fixture) a repo with a mix of
`SCOPE_FILTERED`, `MISSING_ARTIFACT`, and graph-load-failure causes; run
`spec-kitty charter generate --force --json` against it and confirm the JSON output's
`unresolved_references` array matches the contract doc's documented shape exactly. Confirm
T016's commit-1 assertion is now GREEN.

## Subtask T015: Regression check — `diagnostics` field shape unchanged (commit 2, with T014)

**Purpose**: Prove the additive-alongside design did not accidentally widen or restructure the
existing `diagnostics` field.

**Steps**: Add or extend a test asserting `diagnostics` in the `--json` output is still a flat
`list[str]` (every element is a `str`, never a `dict`) both before and after this WP's change,
using the same fixture(s) T014 used.

**Files**: `tests/specify_cli/cli/commands/test_charter_generate_autotrack.py` (same file as
T014/T016 — the only real candidate that already exercises `generate --json`; do not create a
new test file for this WP).

**Validation**: Test passes both before (trivially — nothing changed about `diagnostics`) and
after your `unresolved_references` addition. Commit T014 and T015's changes together as ONE
commit — commit 2 of this WP, strictly after T016's red-first commit — turning T016's assertion
GREEN.

## Definition of Done

- T016's Acceptance Scenario 2 assertion is committed ALONE, in its own commit (commit 1), and
  was verified RED against WP02's landed compiler fix before that commit (record the exact RED
  pytest output/count in your WP completion note).
- T014+T015 are committed together in ONE commit (commit 2), strictly after T016's commit,
  turning T016's assertion GREEN on this WP's final commit — two separate commits, verified RED
  then GREEN, matching WP01's and WP04's two-commit red-first pattern. (WP02 has a different,
  four-commit shape with no internal red-first commit of its own, since it turns WP01's
  already-landed red tests green rather than authoring its own — it is not a comparable match.)
- `unresolved_references` key present in `charter generate --json` output, always (even `[]`),
  matching `contracts/charter-generate-json-diagnostics.md`'s documented shape exactly.
- `diagnostics` field's shape (flat `list[str]`) is provably unchanged (T015's regression test).
- The contract doc itself required no edits (or, if it did — because it was found factually
  wrong against the real WP02 output — the edit and its reason are recorded in your WP
  completion note).
- Per-subtask completion evidence recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T014-T016.

## Risks

- **Risk**: Guessing at WP02's structured-record attribute name instead of checking what WP02
  actually shipped. **Mitigation**: read WP02's committed diff (`git show` on WP02's commit(s)
  touching `compiler.py`) before writing T014's code — do not assume the illustrative name used
  in this prompt (`unresolved_reference_records`) is exactly what WP02 used.
- **Risk**: Accidentally restructuring or reformatting `diagnostics` while adding the new key.
  **Mitigation**: T015's explicit regression test; keep the diff to `generate.py` as small and
  localized as possible.
- **Risk**: Omitting the `unresolved_references` key when the list is empty (breaking the
  always-present convention `diagnostics` already sets). **Mitigation**: T014 step 4 explicit
  requirement; test the zero-unresolved-references case too.

## Gates (run these; do not invent others)

- `.venv/bin/python -m ruff check .` (whole-repo, always-on)
- `.venv/bin/python -m ruff format --check .` (whole-repo, always-on)
- Targeted shard for the touched module and its test tree:
  `.venv/bin/python -m pytest -q tests/specify_cli/cli/commands/charter/ tests/specify_cli/cli/commands/test_charter_generate_autotrack.py`
- Baseline (must stay 56 passed, 0 failed — this WP does not touch any file this baseline
  covers, but confirm anyway since it depends on WP02):
  `.venv/bin/python -m pytest -q tests/doctrine/test_activation_parity_guard.py tests/charter/test_active_languages_idempotency.py tests/charter/test_context_catalog_miss.py tests/charter/test_catalog_completeness_4785.py`
- `spec-kitty regen --check` — **NOT APPLICABLE**: no schema-generated file changes.
- `tests/architectural/test_no_dead_symbols.py` — **NOT APPLICABLE by the letter of C-007**:
  `src/specify_cli/cli/commands/charter/generate.py` is not under `src/charter/` or
  `src/kernel/`, so C-007's `__all__` convention does not bind this file at all, and this WP adds
  no new `__all__` entry regardless. Not required.
- `tests/architectural/test_no_legacy_terminology.py` — not required by path (`src/specify_cli/`
  is neither `src/charter/offering/` nor prose-heavy user documentation). This WP does add a new
  JSON field, but field names/keys are not the kind of "user-facing prose" this guard targets
  (it gates exactly two retired natural-language terms). Skip.
- diff-cover ≥90% of changed lines — informational locally; the real gate is
  `ci-aggregate.yml`'s `diff-cover` job. Re-run `make ci-parity` once this WP's diff lands
  alongside WP02's, per plan.md's "Gate set" section.

## Reviewer Guidance

- Confirm `unresolved_references` is present (as `[]`) even in the zero-unresolved case — this
  is easy to get wrong with a naive `if unresolved: payload["unresolved_references"] = ...`
  conditional.
- Confirm the entry shape matches the contract doc EXACTLY — field names (`kind`/`id`/`cause`/
  `detail`), no extra/missing keys, no renamed keys.
- Confirm `diagnostics`'s shape is untouched — spot-check that no code path anywhere in this
  WP's diff pushes a `dict` into the `diagnostics` list.
- Confirm the contract doc was not rewritten unless the WP completion note explains why (it
  should already match reality — this WP is meant to make code match doc, not the reverse).
- Confirm the two commits are genuinely separate (`git log --oneline` on this WP's branch shows
  two distinct commits, T016's red-first assertion first, T014+T015's implementation second) —
  NOT squashed into one.

## Implementation Command

```bash
spec-kitty agent action implement WP03 --agent claude
```
