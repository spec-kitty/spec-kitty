---
work_package_id: WP01
title: Red-first regression tests — FR-005 parity + I1-I5 whole-kind invariants
dependencies: []
requirement_refs:
- FR-001
- FR-005
planning_base_branch: fix/charter-generation-drops-scoped-references-5257
merge_target_branch: fix/charter-generation-drops-scoped-references-5257
branch_strategy: Planning artifacts for this mission were generated on fix/charter-generation-drops-scoped-references-5257. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-generation-drops-scoped-references-5257 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-generation-drops-scoped-references-01M3M1KF
base_commit: 3759ea9e4f334e5fea85f4c74a9e99fb831bb7fc
created_at: '2026-09-28T18:45:32.738806+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history: []
agent_profile: implementer-ivan
authoritative_surface: tests/charter/
create_intent:
- tests/charter/test_charter_generate_scoped_reference_parity.py
- tests/charter/test_charter_whole_kind_invariants.py
execution_mode: code_change
model: ''
owned_files:
- tests/charter/test_charter_generate_scoped_reference_parity.py
- tests/charter/test_charter_whole_kind_invariants.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Red-first regression tests: FR-005 parity + I1-I5 whole-kind invariants

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write two new, failing-first (RED against this mission's base commit
`af847be71d97c8a126e91c31a7d05629c69c93ba`) test files that pin the entire user-observable
contract WP02's compiler fix must satisfy, **before any implementation code changes**. This
WP produces TWO separate commits, each independently verified RED, in this exact order:

1. `tests/charter/test_charter_generate_scoped_reference_parity.py` (FR-005) — committed alone.
2. `tests/charter/test_charter_whole_kind_invariants.py` (invariants I1–I5 + the I1/I2
   carve-out + the `_raw_kind_repository` degrade case) — committed alone, strictly after
   commit 1.

You do **not** touch any `src/` file in this WP. WP02 depends on WP01 and turns these tests
GREEN.

## Context

This is the ATDD-First Discipline (charter C-011) entry point for the whole mission
(issue #5257 / spec `charter-generation-drops-scoped-references-01M3M1KF`). Today,
`_render_kind_references`/`_build_references_from_service`
(`src/charter/activation/compiler.py`) silently drop an activated reference id whose raw
per-kind repository lookup misses because the id is excluded by language/scope filtering
(`SCOPE_FILTERED`) — it is recorded only as an opaque `"Unresolved reference: <kind>/<id>"`
diagnostics-list string and vanishes from `catalog.references`. Both new test files must FAIL
against the pre-fix code and PASS once WP02 lands.

**Design decision this WP embodies (mission brief's ownership resolution, option (a)):**
`finalize-tasks --validate-only` rejects two narrow (non-`codebase-wide`) WPs that list the
same file in `owned_files`, even with a `dependencies` edge between them (see
`packs/built-in/missions/mission-steps/software-dev/tasks-finalize/prompt.md` §1b). Rather
than force the two red-first commits plan.md calls "WP-ATDD" and "WP-CORE-TESTS" into two
separate WPs with artificially disjoint files, this mission merges them into ONE work
package (this one) that authors both red-first commits internally, in order, each verified
RED independently. This is not an ownership-overlap workaround — it is the cleaner shape:
the two commits are cohesive (both pin behavior WP02's single compiler change must satisfy)
and neither is independently implementable without the other's context.

**Precedent to extend, not rebuild** (per plan.md IC-04): `tests/charter/test_active_languages_idempotency.py`
already ships `_git_init`/`_invoke_generate`/`_read_catalog` helpers that build a real
`tmp_path` git repo and drive the real `charter_app` `generate` CLI via
`typer.testing.CliRunner`. Read this file in full before writing either new test file. Reuse
these helpers by import where general enough, or lift near-identical private helpers into
the new module per this codebase's existing test-module conventions (implementer's choice —
either satisfies IC-04).

**Binding invariants (do not re-derive — copied verbatim from plan.md's "Round-5
restatement" and round-6 amendments; cite `plan.md` line references in your test
docstrings/comments where helpful for the reviewer):**

- **I1 — completeness.** Every activated reference id, from any source bucket
  (`graph.<kind>` or `graph.unresolved`), ends up either in `catalog.references` (resolved or
  placeholder) or in a structured diagnostic — never silently absent. **Carve-out:** this
  per-id guarantee does NOT extend to ids reachable ONLY via DRG-transitive closure when the
  whole graph fails to load — those are covered collectively, never individually, by the
  single loud `_graph`/`_load_failure` sentinel diagnostic.
- **I2 — single evaluation point, both source buckets counted.** The whole-kind fail-closed
  check is evaluated once per kind, after ALL sources (every per-kind `_render_kind_references`
  call AND the kind-mapped `graph.unresolved` pass) have contributed. A kind counts as
  **activated** if EITHER `graph.<kind>` is non-empty OR at least one `graph.unresolved` URN
  was attributed to it via the kind-mapping step. Same carve-out as I1 under total graph-load
  failure.
- **I3 — every diagnostic is shaped.** Every structured diagnostic record carries a defined
  `kind`, `id`, `cause`. Four unattributable `graph.unresolved`-URN classes each get a defined
  shape per `contracts/charter-generate-json-diagnostics.md`'s "Round-5 addition" section:
  (a) no `":"` in the URN → `kind: "_unattributed"`, `cause: "malformed_urn"`; (b) kind prefix
  has no `ArtifactKind` counterpart (`ArtifactKind(kind_prefix)` raises `ValueError`) →
  `cause: "unattributed_kind"`, detail `"unrecognized artifact kind: <kind_prefix>"`; (c) kind
  prefix is a valid `ArtifactKind` whose repository is genuinely `None` (`template`, `asset`,
  `anti_pattern`) → `cause: "unattributed_kind"`, detail `"no repository for kind: <kind_prefix>"`;
  (d) kind prefix is a valid `ArtifactKind` with a real, non-`None` repository but outside the
  six tracked kinds (`paradigm`, `mission_step_contract`, `glossary_pack`) →
  `cause: "unattributed_kind"`, detail `"kind '<kind_prefix>' is not one of the six DRG-backed
  kinds tracked for reference resolution"`.
- **I4 — graph-load failure is loud, not fail-closed.** A total DRG graph-load failure yields
  a loud structured diagnostic (`kind: "_graph"`, `id: "_load_failure"`, `cause:
  "graph_load_failed"`) and does NOT make `generate` exit non-zero.
- **I5 — determinism.** Generation is deterministic across repeat invocations on both the
  fail-closed and diagnostic paths (same exit code, same diagnostics, same catalog content).
- **I1/I2 carve-out fixture.** An id activated ONLY via DRG-transitive closure (no direct
  `config.activated_*` root of its own kind) combined with a corrupted/unparseable DRG
  fragment forcing `_resolve_transitive_reference_graph`'s total-load-failure branch. Assert:
  the `_graph`/`_load_failure` sentinel diagnostic is present (in `diagnostics` and, once WP03
  lands, `--json`'s `unresolved_references` — WP01 asserts against `diagnostics` and the
  compiler-level structured record only, since `--json` wiring is WP03's job), no per-id
  record/placeholder exists for the transitively-only id, `generate` exits 0, and repeating the
  invocation twice produces the identical sentinel diagnostic and exit code.
- **`_raw_kind_repository` raw-service degrade fixture.** Call `_raw_kind_repository`
  (`src/charter/activation/compiler.py`, currently ~line 1093) directly with a raw/unwrapped
  `doctrine_service` (no `raw_repository` method — per the function's own docstring branch) and
  a `kind` with no matching attribute on it (e.g. `"templates"`/`"anti_patterns"`). Assert
  pre-fix behavior raises `AttributeError` (RED against `af847be71`) and, after WP02 lands,
  returns `None` (GREEN) — a reported miss, not a crash.

## Subtask T001: FR-005 generator-to-parity regression test (commit 1, alone)

**Purpose**: Prove, at the real `compile_charter`/`charter generate` entry point, that a
language/scope-filtered activated reference id no longer silently vanishes.

**Steps**:
1. Create `tests/charter/test_charter_generate_scoped_reference_parity.py`.
2. Build a `tmp_path` git repo fixture (reuse/extend `_git_init` and friends from
   `tests/charter/test_active_languages_idempotency.py`) whose `.kittify/config.yaml`
   activates the six #5257 ids: `styleguide/java-conventions`, `toolguide/maven-review-checks`,
   `toolguide/typescript-mutation-tools`, `agent-profile/frontend-freddy`,
   `agent-profile/java-jenny`, `agent-profile/node-norris` — all six already exist as real,
   on-disk built-in doctrine artifacts under `packs/built-in/`. Add at least one MORE,
   differently language-scoped id (per C-002 — proving the general mechanism, not six special
   cases; e.g. a language-filtered `tactic` or `procedure` whose `applies_to_languages` excludes
   whatever this fixture's `infer_repo_languages` detects — search `packs/built-in/` for a
   suitable candidate at implementation time).
3. Drive the real `charter_app` `generate` CLI via `_invoke_generate` (or equivalent,
   `typer.testing.CliRunner`-based) — NOT an internal helper function.
4. Feed the resulting repo through `ProjectContext.from_repo()` + `run_consistency_check`
   directly (spec.md Acceptance Scenario 3) — NOT the hardcoded-`_REPO_ROOT`
   `tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent`,
   which cannot be conditioned on an arbitrary fixture path.
5. Assert: (a) every fixture id (all six #5257 ids plus the extra one) is present in
   `catalog.references`; (b) `run_consistency_check` reports coherent; (c) this test is RED
   pre-fix.

**Files**: `tests/charter/test_charter_generate_scoped_reference_parity.py` (new, ~150-250
lines).

**Validation**: Run
`.venv/bin/python -m pytest -q tests/charter/test_charter_generate_scoped_reference_parity.py`
and confirm it FAILS against the current (pre-WP02) `compiler.py` — this is the expected,
required RED state. Commit this file ALONE (`git add
tests/charter/test_charter_generate_scoped_reference_parity.py && git commit`), with a message
naming the RED verification, before starting T002.

## Subtask T002: I1/I2 whole-kind fail-closed fixtures (part of commit 2)

**Purpose**: Pin the aggregate, cause-agnostic whole-kind check (plan.md "WP-CORE
reconciliation" point 3) — a kind whose activated ids ALL fail to resolve (none placeholdered,
none resolved) must fail `generate` closed with a non-zero exit naming the kind, before any
catalog is written.

**Steps**:
1. Create `tests/charter/test_charter_whole_kind_invariants.py`.
2. Fixture A — whole-kind `MISSING_ARTIFACT` (misconfigured pack root): configure a repo
   whose only activated id(s) of some kind point at a pack root with no matching artifact at
   all. Assert `charter generate --force` exits non-zero, writes NO catalog file, and the
   error names the affected kind.
3. Fixture B — `graph.unresolved` routing: an id reachable only via `graph.unresolved` (DRG
   transitive closure, not a direct `config.activated_*` root) that is the SOLE activated id of
   its kind and classifies `MISSING_ARTIFACT`/`TYPO_SUSPECTED`. Assert it is routed through the
   shared classify-and-placeholder helper, gets a reason-bearing diagnostic, and — because it is
   the sole activated id of its kind — trips the same whole-kind fail-closed check as Fixture A.
4. Both fixtures together prove I2: the check counts `graph.unresolved`-sourced ids alongside
   `graph.<kind>`-sourced ids, evaluated once per kind, after all sources have contributed —
   never after any single source.
5. Add a negative control: a kind with at least one `SCOPE_FILTERED` id among otherwise
   `MISSING_ARTIFACT` ids of the same kind must NOT trip the fail-closed path (that kind's
   reference list is non-empty because of the placeholder).

**Files**: `tests/charter/test_charter_whole_kind_invariants.py` (new — created here, extended
by T003-T006 below; this is all ONE file with one final commit).

**Validation**: These assertions must FAIL (RED) against `af847be71` — `generate` currently
exits 0 and silently writes an empty-for-that-kind but structurally "successful" catalog
section for Fixture A/B.

## Subtask T003: I3 — four unattributable `graph.unresolved` URN classes

**Purpose**: Pin the four distinct entry shapes `contracts/charter-generate-json-diagnostics.md`'s
"Round-5 addition" defines for `graph.unresolved` URNs that cannot be attributed to one of the
six DRG-backed tracked kinds.

**Steps**: In the same file (`test_charter_whole_kind_invariants.py`), add one fixture per
class, each asserting the compiler-internal structured record's `kind`/`id`/`cause`/`detail`
shape (read the record via whatever internal accessor WP02 will expose — if none exists yet at
RED time, assert directly against `diagnostics: list[str]` content and mark a `# TODO(WP02):
also assert the structured record once compiler.py exposes it` comment, since the structured
sink does not exist pre-fix):
1. No `":"` in the URN at all → `kind: "_unattributed"`, `cause: "malformed_urn"`.
2. `kind_prefix` has no `ArtifactKind` counterpart (e.g. `action:`, `glossary_scope:`,
   `glossary:`, `mission_type:`) → `cause: "unattributed_kind"`, detail names the unrecognized
   kind.
3. `kind_prefix` is a valid `ArtifactKind` whose repository is genuinely `None`
   (`template`/`asset`/`anti_pattern`) → `cause: "unattributed_kind"`, detail `"no repository
   for kind: <kind_prefix>"`.
4. `kind_prefix` is a valid `ArtifactKind` with a real, non-`None` repository but outside the
   six tracked kinds (`paradigm`/`mission_step_contract`/`glossary_pack`) → `cause:
   "unattributed_kind"`, detail `"kind '<kind_prefix>' is not one of the six DRG-backed kinds
   tracked for reference resolution"`.

**Files**: same file, extended.

**Validation**: RED against `af847be71` (today these URNs either crash, are silently dropped,
or produce the old opaque string with no `kind`/`cause` shape at all).

## Subtask T004: I4 — total graph-load failure, loud not fail-closed

**Purpose**: Pin that a corrupted/unparseable DRG fragment produces a loud, structured
diagnostic and does NOT make `generate` fail closed.

**Steps**: Add a fixture that forces `_resolve_transitive_reference_graph`'s `except` branch
(e.g. a deliberately corrupted DRG fragment file in the fixture repo). Assert: `generate` exits
0; a graph-load-failure diagnostic (`"Graph load failed: ... Transitive closure not resolved;
direct-root ids only."` pattern, per the contract doc) is present in `diagnostics`; the
transitive closure is NOT reconstructed (only direct-root ids are still resolved normally).

**Files**: same file, extended.

**Validation**: RED against `af847be71` (today this failure mode is not tested this way at
all, or produces different/absent diagnostics).

## Subtask T005: I5 — determinism + I1/I2 carve-out fixture

**Purpose**: Pin idempotency of the fail-closed and diagnostic paths, and the I1/I2 carve-out
for transitive-only-reachable ids under total graph-load failure.

**Steps**:
1. Append an idempotency assertion to Fixture A/B (T002): run `generate --force` twice, assert
   both invocations exit non-zero identically (same code, same kind named), neither writes/
   modifies a catalog file.
2. Add the graph-load-failure fixture's (T004) own idempotency check via ordinary NFR-001
   byte-identical-`catalog.references` comparison across two runs (that path is not
   fail-closed, so this is the applicable determinism check, not exit-code repetition).
3. Add the **I1/I2 carve-out fixture**: an id activated ONLY via DRG-transitive closure (no
   direct `config.activated_*` root of its own kind) combined with the T004 corrupted-DRG-
   fragment fixture. Assert: the `_graph`/`_load_failure` sentinel diagnostic is present, no
   per-id record or placeholder exists for the transitively-only id, `generate` exits 0, and
   repeating the invocation twice produces the identical sentinel diagnostic and exit code.

**Files**: same file, extended.

**Validation**: RED against `af847be71`.

## Subtask T006: `_raw_kind_repository` raw-service degrade fixture

**Purpose**: Pin the round-6-folded-in residual — `_raw_kind_repository`'s raw-service
fallback branch (`compiler.py` ~line 1093, `return getattr(doctrine_service, kind)`, no
default) raises `AttributeError` instead of degrading to `None` for kinds like `"templates"`/
`"anti_patterns"` when `doctrine_service` is the raw/unwrapped shape.

**Steps**: Call `_raw_kind_repository` directly (import it from `src/charter/activation/compiler.py`
— it is a private module function, importable for a white-box unit test) with a
raw/unwrapped `doctrine_service` test double (no `raw_repository` method) and a `kind` string
with no matching attribute. Assert `AttributeError` is raised pre-fix.

**Files**: same file, final subtask in this commit.

**Validation**: RED against `af847be71` (`AttributeError` raised — this IS the expected RED
behavior; post-WP02 it must instead return `None`).

**Commit T002-T006 together as ONE commit**, separate from T001's commit, per the ATDD-First
Discipline section's bundling rationale (all five invariants pin different entry points into
the SAME aggregate mechanism). Verify the whole file is RED against `af847be71` before
committing (run the full new test file and confirm every new test fails, not just some).

## Definition of Done

- `tests/charter/test_charter_generate_scoped_reference_parity.py` exists, is committed ALONE
  in its own commit, and was verified RED against `af847be71d97c8a126e91c31a7d05629c69c93ba`
  before that commit (record the exact RED pytest output/count in your WP completion note).
- `tests/charter/test_charter_whole_kind_invariants.py` exists, covers every row of the
  ATDD-First Discipline invariant→fixture table (I1, I2, I3 [all four URN sub-classes], I4, I5,
  the I1/I2 carve-out, and the `_raw_kind_repository` degrade fixture), is committed in ONE
  commit strictly after the FR-005 commit, and was verified RED against the same base commit.
- Neither commit touches any `src/` file.
- Per-subtask completion evidence recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T001-T006 (event-sourced, not
  a ticked checkbox).

## Risks

- **Risk**: Reusing `test_active_languages_idempotency.py`'s helpers by copy-paste instead of
  import could silently drift if that module's helpers change later. **Mitigation**: prefer
  import/reuse; if lifting is necessary, note it as a deliberate, reviewed decision.
- **Risk**: A fixture accidentally hardcodes only the six #5257 ids without the extra
  differently-scoped id, which would violate C-002 (no hardcoded six-id special case) and
  under-prove the general mechanism. **Mitigation**: T001 explicitly requires the extra id;
  verify it in review.
- **Risk**: T003's structured-record assertions may need adjustment once WP02 actually exposes
  the structured-records sink (it does not exist pre-fix). **Mitigation**: the `# TODO(WP02)`
  comment convention above; WP02's reviewer should confirm these TODOs are resolved, not
  silently left in place.
- **Risk**: Verifying RED requires actually running pytest against `af847be71`, not assuming
  it. **Mitigation**: this WP's base branch tip already IS `af847be71`'s descendant with no
  `src/`/`tests/` diff yet (per plan.md's "The baseline" section) — running the new test files
  against the current checkout before any WP02 commit lands **is** the RED verification; no
  separate checkout/stash dance is needed.

## Gates (run these; do not invent others)

- `.venv/bin/python -m ruff check .` (whole-repo, always-on)
- `.venv/bin/python -m ruff format --check .` (whole-repo, always-on — separate gate from lint)
- `.venv/bin/python -m pytest -q tests/charter/test_charter_generate_scoped_reference_parity.py tests/charter/test_charter_whole_kind_invariants.py` — expect FAILURES (this is the point: RED verification, not a passing gate, for this WP specifically).
- Baseline command (record its 56-passed count as context; it is unaffected by this WP since no `src/` file changes):
  `.venv/bin/python -m pytest -q tests/doctrine/test_activation_parity_guard.py tests/charter/test_active_languages_idempotency.py tests/charter/test_context_catalog_miss.py tests/charter/test_catalog_completeness_4785.py`
  → must stay 56 passed, 0 failed (this WP does not touch any file this baseline covers).
- `spec-kitty regen --check` — **NOT APPLICABLE**: no schema-generated file changes in this WP (test files only).
- `tests/architectural/test_no_dead_symbols.py` — **NOT APPLICABLE**: this WP adds no new public `__all__` name (it adds only test files, no `src/` change at all).
- `tests/architectural/test_no_legacy_terminology.py` — not required by path (this WP touches only `tests/charter/`, not `src/charter/offering/`); no new user-facing prose is introduced by test code either. Skip.
- diff-cover ≥90% of changed lines — informational locally; the real gate is `ci-aggregate.yml`'s `diff-cover` job. New test files are typically fully exercised by their own execution, so this should be trivially satisfied once GREEN (post-WP02); at RED time diff-cover is not meaningfully evaluable (the tests fail by design).

## Reviewer Guidance

- **The single most important check**: run both new test files against `af847be71` (or
  confirm the WP's own commits were made against that exact base with no intervening `src/`
  change) and confirm EVERY new test genuinely fails — not "some pass, some fail" (a partially-
  green red-first commit is a red flag: it may mean a fixture doesn't actually exercise the
  defect).
- Confirm the two commits are genuinely separate (`git log --oneline` on this WP's branch
  shows two distinct commits, FR-005 first, invariants second) — NOT squashed into one.
- Confirm the extra, non-#5257 id in T001's fixture is real (exists under `packs/built-in/`)
  and is genuinely language/scope-excluded by the fixture's `infer_repo_languages` result —
  not accidentally already-resolvable.
- Confirm no `src/` file was touched by either commit.
- Confirm T006's `_raw_kind_repository` fixture imports the private function directly (a
  legitimate white-box unit test pattern for a module-private helper) rather than trying to
  trigger it indirectly through `compile_charter`'s default production path (per the function's
  own docstring, this path is unreachable via the default production path — direct import/call
  is the only way to exercise it).

## Implementation Command

```bash
spec-kitty agent action implement WP01 --agent claude
```
