# Implementation Plan: Charter generation drops configured scoped references and breaks parity

**Branch**: `fix/charter-generation-drops-scoped-references-5257` | **Date**: 2026-09-28 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-generation-drops-scoped-references-01M3M1KF/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

## Summary

`_render_kind_references`/`_build_references_from_service` in `src/charter/activation/compiler.py` look up every DRG-backed activated reference against `_raw_kind_repository`, which strips only the *activation-config* filter — the underlying per-kind repository was already constructed with `active_languages=infer_repo_languages(repo_root)` baked in, so a language/scope-filtered id (present on disk, excluded by scope) misses the lookup exactly like a genuinely nonexistent id. The miss is recorded as an opaque `"Unresolved reference: <kind>/<id>"` diagnostics-list string and the reference silently vanishes from `catalog.references` (#5257 / #5253). This mission makes that loss impossible: a scope-filtered activated id (present on disk, excluded solely by language/scope — the actual #5257/#5253 defect) is uniformly preserved as a reason-bearing placeholder `CharterReference` (never a silent omission, never a second fail-closed code path), while a genuinely-nonexistent id stays on the pre-existing, currently-tested diagnostics-only path (`Contract C4`, issue #4785 — deliberately not superseded, see "WP-CORE reconciliation" below) with its diagnostic now made reason-bearing too; the reason distinguishes never-existed from scope-filtered by reusing the already-built `charter.activation._catalog_miss` classifiers, the `--json` output gains an additive structured `unresolved_references` field so automated callers stop string-matching prose, and a generator-to-parity regression test (extending `tests/charter/test_active_languages_idempotency.py`'s fixture precedent) pins the fix at the real `compile_charter`/`charter generate` entry point. A related pre-existing swallow bug in the preflight auto-refresh path (`references_refresh.py`) — a targeted `generate` subprocess whose outcome is never inspected, masking a genuine references-parity failure behind an unconditional manifest re-stamp — is folded in as a bounded, same-defect-class fix per operator doctrine (silent-success is this mission's own acceptance bar).

## Technical Context

**Language/Version**: Python 3.11+ (uv-managed; `pyproject.toml` requires-python `>=3.11`)
**Primary Dependencies**: `charter` (specifically `charter.activation.compiler`, `charter.activation._catalog_miss`, `charter.offering.base.BaseDoctrineRepository`) and `specify_cli` (specifically `specify_cli.charter_runtime.preflight.references_refresh`, `.runner`, `.result`) — both already-vendored first-party packages in this repo; no new third-party dependency is expected. `ruamel.yaml` (existing dep) continues to back the round-trip `charter.yaml` write path untouched.
**Storage**: N/A — no database; the artifact under change is the YAML file `.kittify/charter/charter.yaml` (`catalog.references` section) that `charter generate` writes, plus the JSON stdout of `charter generate --json`.
**Testing**: `.venv/bin/python -m pytest` (pytest, this repo's standard runner) — targeted module shards for `tests/charter/`, `tests/doctrine/`, and `tests/specify_cli/charter_runtime/` (preflight). No `uv run` (would re-sync the environment) and no full-suite run during mission work per `NO_FULL_HEAVY_SUITES_IN_MISSION`.
**Target Platform**: CLI, cross-platform (Linux/macOS/Windows 10+) — no platform-specific code introduced; the fix is pure Python inside the existing compiler/preflight modules.
**Project Type**: Single Python package (this repo, `spec-kitty` — the CLI/library monorepo, not a web/mobile split).
**Performance Goals**: No new perf goal beyond the charter's blanket "<2s for typical projects" CLI budget; the fix adds a bounded number of extra dict/set lookups per unresolved id (never a new network or subprocess call in the compiler seam) and does not change the auto-refresh path's step count in the success case.
**Constraints**: NFR-001 (idempotent regeneration — byte-identical `catalog.references` across repeated runs), NFR-002 (every diagnostic/placeholder names `kind/id` and a reason category), C-001–C-004 (parity guard untouched, no hardcoded six-id special case, no machine-local absolute paths reintroduced, no local-path/private-ledger citations in mission artifacts).
**Scale/Scope**: Two files change behavior (`src/charter/activation/compiler.py`, `src/specify_cli/charter_runtime/preflight/references_refresh.py` + its one caller in `runner.py`); one new/extended test module; no data migration, no schema change to any persisted file format beyond the additive JSON field described below.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Seams this mission touches (both named explicitly — DIRECTIVE_001 architectural alignment)

1. **`src/charter/activation/compiler.py`** (the `charter` package / doctrine-compiler seam) — the core FR-001/FR-002/FR-003/FR-004 fix. `_render_kind_references` and `_build_references_from_service` change so every DRG-backed activated id (directive/tactic/styleguide/toolguide/procedure/agent_profile) that misses the raw-repository lookup is classified via the existing `charter.activation._catalog_miss` primitives: a `SCOPE_FILTERED` miss is preserved as a reason-bearing placeholder `CharterReference` (never silently dropped); a `MISSING_ARTIFACT`/`TYPO_SUSPECTED` miss stays on the pre-existing diagnostics-only path (Contract C4, #4785 — see "WP-CORE reconciliation" below), also made reason-bearing.
2. **`src/specify_cli/charter_runtime/preflight/` (`references_refresh.py` + `runner.py::_attempt_auto_refresh`)** (the `specify_cli` / CLI-orchestration seam) — the auto-refresh fold-in decided below (Edge Cases "Mid-flight missions").

No CLI command reaches past a service into kernel internals here: `references_refresh.py` calls `charter generate` only via `subprocess.run` (already the existing pattern — this mission changes what the CALLER does with the `CompletedProcess`, not the invocation mechanism), and the compiler fix stays entirely inside `charter.activation`/`charter.offering`, never reaching into `specify_cli`. No unguarded core-loop → sync coupling is introduced: the preflight fold-in only tightens an existing synchronous subprocess-result check: it does not add a new sync dependency.

### What is generated, and by which command

`catalog.references` inside `.kittify/charter/charter.yaml` is recompiled ONLY by `spec-kitty charter generate` (`src/specify_cli/cli/commands/charter/generate.py` → `charter.activation.compiler.compile_charter`/`write_compiled_charter`; see `references_refresh.py`'s own module docstring: "Only `spec-kitty charter generate` recompiles that section"). This mission does not hand-patch a generated file — it changes the generator itself (`_render_kind_references`/`_build_references_from_service`) so its OUTPUT is correct on every future run, including the targeted `generate` invocation the preflight auto-refresh boundary fires internally.

### Whether any contract moves

- **`CharterPreflightResult`'s JSON shape** (`contracts/charter-preflight-json.md` in `kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/`, the binding doc `src/specify_cli/charter_runtime/preflight/result.py`'s own docstring cites) does **NOT** change. `blocked_reason: str | None` already exists on `CharterPreflightResult` (`result.py` line 98) and is already populated with `auto_refresh_applied=True` at multiple existing call sites inside `_attempt_auto_refresh` (e.g. lines 686–692, 704–709 in the current `runner.py`) — the fold-in below reuses that exact existing pattern for the new failure branch. No new field, no field-shape change, no change to `to_dict()`/`to_json()`.
- **`charter generate`'s `--json` output** (`src/specify_cli/cli/commands/charter/generate.py`, the `diagnostics: list[str]` field at the JSON-emit block, current lines ~538–559) DOES gain a new field. FR-004 requires the unresolved-reference id+reason to be machine-readable, not only free text a caller has to string-match. **Decision**: add a new top-level key `unresolved_references: list[{"kind": str, "id": str, "cause": str, "detail": str}]` alongside the existing `diagnostics: list[str]` field, which is left completely unchanged in shape (still a flat list of human-readable strings — its *content* per-line gains a reason suffix, per FR-002, but its type and key name are untouched). `cause` is the `CatalogMissCause` enum value (`"missing_artifact"`, `"typo_suspected"`, or `"scope_filtered"`); `detail` is the human-readable classifier suggestion text `classify_catalog_miss`/`classify_scope_filtered_miss` already produce. **Rationale for additive-alongside rather than widening `diagnostics` entries into objects**: any existing consumer that treats `diagnostics` as `list[str]` (CI scripts, readiness probes, `_finalize_sync_result`'s own sync-warnings concatenation which appends plain strings into the same list) keeps working unchanged — widening the existing field's element type to `str | dict` would be a breaking shape change for every such consumer with no compile-time signal in a dynamically-typed JSON contract. Adding a new, optional-in-practice-but-always-present key is additive and detectable (`"unresolved_references" in payload`) without touching the existing key at all. This is documented as a **versioned/additive JSON contract change**, not a silent one, in the new `contracts/charter-generate-json-diagnostics.md` (see Project Structure below).

### Gate set (authoritative — 2026-09-23 re-verification against `.github/workflows/` on `main`; supersedes any stale overlay list)

**Enforced on every PR**:
- `ruff check .` AND `ruff format --check .` (both, always-on)
- `uv lock --check`
- banned-API/import-boundary (ruff `TID251`, `import-linter`)
- `spec-kitty regen --check` (generated-artifact freshness) — **not applicable to this mission's diff**: no schema-generated file changes; stated explicitly rather than silently assumed passing.
- terminology guard (`tests/architectural/test_no_legacy_terminology.py`)
- layer rules / pyproject shape
- archive-freeze
- routed test groups, path-filtered by changed paths
- per-module test shards (`ci-modules.yml`, diff-scoped to touched module roots — `src/charter/` and `src/specify_cli/` once implementation lands)
- **diff-cover ≥90% of changed lines** (`ci-aggregate.yml` `diff-cover` job) — the REAL per-PR coverage gate, not a whole-module floor
- wheel build + `clean-install-verification`

**NOT enforced** (do not promise these; do not accept a review finding that demands them):
- commit-message lint (commitlint prints only, never fails)
- markdownlint (`|| true`, can never fail)
- Bandit/pip-audit (no workflow runs either)
- mypy (no workflow — `make typecheck` covers only 2 unrelated files, not this mission's surfaces)
- "kernel 90%"/"mission-loader ≥90%" named coverage floors (do not exist as named gates — diff-cover is the real, only per-PR coverage gate)
- SonarCloud (`sonar-pr` job is `continue-on-error`, informational, excluded from the terminal `aggregate-gate` job's `needs:` set — never a merge blocker)
- Typer JSON error surface / `patch()` target validation / Contextive glossary freshness as dedicated CI jobs (no dedicated job for any of these; if covered at all it is inside a test group or the architectural battery, never a separate promise)

**`make ci-parity` was run against the current diff** (mission-dir-only so far — spec-phase artifacts: `meta.json`, `reviews/*.yaml`, `spec.md`, `status.events.jsonl`, `tasks/.gitkeep`, `tasks/README.md`) and selected **12 jobs**: `archive-freeze`, `commit-msg` (prints only), `import-linter`, `layer-rules`, `markdownlint` (prints only), `prose-scan`, `regen-check`, `router-gate`, `ruff`, `terminology`, `tests-corpus`, `uv-lock` — with **0 code shards**, which is expected since no `src/` diff exists yet at plan time. **Once implementation touches `src/charter/activation/compiler.py` and `src/specify_cli/charter_runtime/preflight/references_refresh.py`/`runner.py`, `make ci-parity` MUST be re-run on that diff** to see which additional module shards, the `architectural-heavy` lane, and `diff-cover` scoping actually apply — the shard list above is not guessed in advance.

### The baseline (stated as fact, not a TODO)

Already captured on this branch's base commit `af847be71d97c8a126e91c31a7d05629c69c93ba` (confirmed == `git merge-base main HEAD`, and `git diff af847be71d97c8a126e91c31a7d05629c69c93ba HEAD -- src/ tests/` is empty at plan time, so HEAD == base for src/tests purposes):

```
.venv/bin/python -m pytest -q tests/doctrine/test_activation_parity_guard.py \
  tests/charter/test_active_languages_idempotency.py \
  tests/charter/test_context_catalog_miss.py \
  tests/charter/test_catalog_completeness_4785.py
```
→ **56 passed, 0 failed, 1 warning (75.20s)**.

`tests/charter/test_catalog_completeness_4785.py` (issue #4785, mission `charter-catalog-coherence-01M2XQQF`)
is added to this baseline because it pins **Contract C4** ("Recompiled catalog is complete and
stable", `kitty-specs/charter-catalog-coherence-01M2XQQF/contracts/behavior-contracts.md`) directly
against `_render_kind_references` — the exact function WP-CORE rewrites — via
`test_render_kind_references_routes_genuine_miss_to_diagnostics_not_placeholder`, which asserts a
genuinely-nonexistent id produces `references == []` (diagnostics-only, never a placeholder row).
WP-CORE's design (see "WP-CORE reconciliation: Contract C4 scope and placeholder text format" below)
scopes the new placeholder mechanism to the `SCOPE_FILTERED` cause specifically so this contract is
preserved, not superseded — this file's inclusion in the baseline is what lets WP-CORE's own
green-bar re-check actually catch a regression against it, rather than silently missing it the way
the original (pre-review) 51-test command would have.

No pre-existing red in the relevant shards — nothing needs a Pre-existing Failure Reporting Rule issue for this mission's blast radius. This is stated plainly and will not be re-run at plan time.

### Campsite-clean scope

`_render_kind_references`'s unresolved-append (`diagnostics.append(f"Unresolved reference: {kind}/{raw_id}")`, compiler.py ~line 1140) and `_build_references_from_service`'s `graph.unresolved` loop (`diagnostics.append(f"Unresolved reference: {artifact_type}/{artifact_id}")`, ~line 1251) duplicate the same literal format string at two call sites. **Decision: no separate preceding campsite-clean commit.** FR-001/FR-002's own fix necessarily rewrites BOTH sites' unresolved-handling logic (turning "append a diagnostic string and drop the reference" into "classify the cause, build a placeholder reference, append a reason-bearing diagnostic AND a structured record") — a distinct prior commit that only extracted a shared "record unresolved" helper with unchanged behavior would be immediately overwritten by the functional commit that follows it, making the two-commit split circular rather than a genuine tidy-first enabler. The unification happens naturally as part of the functional change itself (both call sites end up calling one new shared classify-and-placeholder helper). This is a considered decision under Standing Order #2, not a silently skipped bullet.

**Round-3 note (closes the "both call sites" gap PLAN-FRESH2-001 identified).** Prior to the operator ruling captured in "WP-CORE reconciliation" point 3's invariant restatement below, this "both call sites end up calling one new shared classify-and-placeholder helper" claim was true only for `_render_kind_references`'s per-id miss loop — `_build_references_from_service`'s own `graph.unresolved` loop (`compiler.py:1250-1251`) was a second, unmentioned unresolved-tracking site that never called the shared helper and never contributed to the whole-kind aggregate check. Per I1/I2 below, `graph.unresolved` now routes through the SAME shared helper too, so this claim is accurate for both call sites — see the invariant restatement for the binding design.

### Tracer files

Seeded now at `kitty-specs/charter-generation-drops-scoped-references-01M3M1KF/tracer-tooling-friction.md`, `tracer-approach.md`, `tracer-design-decisions.md` (see repo for full content — summarized in this plan's Phasing section below).

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-generation-drops-scoped-references-01M3M1KF/
├── plan.md                                     # This file
├── tracer-tooling-friction.md                  # Seeded this phase (C-003 mission tracer files)
├── tracer-approach.md                          # Seeded this phase
├── tracer-design-decisions.md                  # Seeded this phase
├── contracts/
│   └── charter-generate-json-diagnostics.md    # New — documents the additive `unresolved_references` JSON field (FR-004)
└── tasks.md / tasks/                           # Phase 2 output (/spec-kitty.tasks command — NOT created by /spec-kitty.plan)
```

No `research.md` — this is a targeted defect fix against already-verified, already-read code (every claim above was checked against the current `HEAD` source, not assumed); there is no open unknown a research phase would resolve. No `data-model.md` — no new persisted data model; `CharterReference` (existing dataclass) and `CharterPreflightResult` (existing, unchanged) are the only data shapes involved, and both are already fully specified in the spec's Key Entities section and this plan's Charter Check section respectively. `contracts/charter-generate-json-diagnostics.md` IS added because FR-004 is a genuine, additive JSON-contract change that downstream automated consumers need documented (mirrors the precedent `contracts/charter-preflight-json.md` sets for the sibling preflight contract).

### Source Code (repository root)

```
src/
├── charter/
│   └── activation/
│       ├── compiler.py            # FR-001/FR-002/FR-003 fix: _render_kind_references,
│       │                          #   _build_references_from_service,
│       │                          #   _resolve_transitive_reference_graph (gains diagnostics/
│       │                          #   structured-records sink params, return type unchanged —
│       │                          #   binding sink-params ruling below (I3), closes PLAN-FRESH3-002),
│       │                          #   new _classify_and_placeholder_reference() helper (private,
│       │                          #   not added to __all__ — see C-007 section below); this helper
│       │                          #   is a NEW IMPORTER of context_renderers.catalog_diagnosis
│       │                          #   (round-8 fix, closes analyze D1/C1/U1 — see IC-02) — no
│       │                          #   import cycle, verified below
│       ├── context_renderers/
│       │   └── catalog_diagnosis.py  # CONSUMED, not modified: _diagnose_catalog_miss(missing_id,
│       │                             #   repository) — the existing single gate compiler.py now
│       │                             #   imports for its classify-and-placeholder helper (round-8
│       │                             #   fix). Depends only on the _catalog_miss leaf below; no
│       │                             #   import back to compiler.py anywhere in this package, so
│       │                             #   compiler.py -> catalog_diagnosis.py is a one-directional
│       │                             #   addition (see IC-02's import-direction note).
│       └── _catalog_miss.py       # REUSED, not modified: CatalogMissCause, classify_catalog_miss,
│                                  #   classify_scope_filtered_miss (already built, already tested).
│                                  #   Stays unmodified even after the round-3 graph-load-failure
│                                  #   addition: that diagnostic's cause value ("graph_load_failed")
│                                  #   is typed as a plain str on the new structured-records sink,
│                                  #   never as CatalogMissCause, so no fifth enum member is ever
│                                  #   added to this file (closes PLAN-FRESH3-004; see the binding
│                                  #   cause-typing ruling below and the contract doc's round-3/
│                                  #   round-5 additions).
├── specify_cli/
│   ├── cli/commands/charter/
│   │   └── generate.py            # FR-004 fix: add `unresolved_references` to the --json payload
│   └── charter_runtime/preflight/
│       ├── references_refresh.py  # Auto-refresh fold-in: refresh_references_if_needed's return
│       │                          #   contract widens from bool to a small outcome type
│       └── runner.py               # Auto-refresh fold-in: refresh_references_if_needed wrapper +
│                                    #   _attempt_auto_refresh's post-refresh branch

tests/
├── charter/
│   ├── test_active_languages_idempotency.py  # Precedent read for FR-005's fixture scaffolding
│   ├── test_catalog_completeness_4785.py     # UNCHANGED (Contract C4, #4785) — added to WP-CORE's
│   │                                          #   blast-radius/baseline command (see "The baseline"
│   │                                          #   above); pins that a genuine miss stays
│   │                                          #   diagnostics-only, never a placeholder row. WP-CORE
│   │                                          #   scopes its new placeholder mechanism to the
│   │                                          #   SCOPE_FILTERED cause specifically so this file
│   │                                          #   stays green, not red.
│   └── test_charter_generate_scoped_reference_parity.py  # NEW — FR-005 regression test (separate,
│                                                            #   failing-first commit, ATDD C-011)
├── doctrine/
│   └── test_activation_parity_guard.py       # UNCHANGED (C-001) — the existing coherence oracle
│                                              #   FR-005's new test also drives via run_consistency_check
└── specify_cli/charter_runtime/
    └── test_references_parity_refresh.py     # EXTENDED — the REAL, already-built test module for
                                                #   preflight.references_refresh (WP06's test home; it
                                                #   already ships _git_init, _make_generate_subprocess_fake,
                                                #   and _seed_baseline_repo fixture machinery). The
                                                #   auto-refresh fold-in's red-first regression case is
                                                #   added here — adapt _make_generate_subprocess_fake so
                                                #   the faked `generate` invocation returns a non-zero
                                                #   returncode/stderr — NOT a new preflight/ subdirectory
                                                #   (no such directory exists in the current test tree).
```

**Structure Decision**: Single Python package, existing module layout unchanged — no new top-level directories, no new packages. All changes land inside the two already-existing seams named above.

## Complexity Tracking

*No Charter Check violations requiring justification.* Both touched seams already exist and already own this exact responsibility (reference resolution in `compiler.py`; preflight auto-refresh orchestration in `references_refresh.py`/`runner.py`); no new abstraction layer, no new project, no repository-pattern addition. The `__all__`/dead-symbol convention (C-007) is honored without exception (see below) — no new public API surface requiring justification.

## `__all__` Convention (C-007, binding)

`src/charter/activation/compiler.py` already declares `__all__` (line ~53: `CharterReference`, `CompiledCharter`, `WriteBundleResult`, `compile_charter`, `provision_mission_type_activations`, `resolve_config_activated_roots`, `write_compiled_charter`). The new helper this mission introduces — a shared "classify the miss cause and build a placeholder `CharterReference`" function replacing the duplicated unresolved-append logic in `_render_kind_references`/`_build_references_from_service` — is **module-private** (leading underscore, e.g. `_classify_and_placeholder_reference`), matching the existing precedent that `_render_kind_references`, `_doctrine_model_reference`, and `_doctrine_yaml_reference` are themselves NOT in `__all__` — only genuinely public, cross-module API surfaces are listed. `tests/architectural/test_no_dead_symbols.py` walks `__all__` and requires every *listed* name to have a real caller; a private helper outside `__all__` is not subject to that walk, and it DOES have real callers (both `_render_kind_references` call sites) so it would pass regardless. If implementation later finds a reason to promote any new symbol to public (not currently planned), it must be added to `__all__` at that point.

`src/specify_cli/charter_runtime/preflight/` is **NOT** under `src/charter/` or `src/kernel/`, so the C-007 binding rule does not apply there by charter text. The module (`references_refresh.py`) does not currently declare a dataclass/NamedTuple for the widened `refresh_references_if_needed` return type in `__all__` either way — `references_refresh.py`'s own `__all__` is `["refresh_references_if_needed"]` today; the new return-type NamedTuple (see Phasing below) is an implementation detail of that one function's signature, consumed only by its one in-module caller and by `runner.py`'s wrapper — it will be added to `references_refresh.py`'s `__all__` only if a second, external caller ever needs to construct/inspect it directly (not the case here: `runner.py` only reads the returned object's attributes, never constructs one).

## ATDD-First Discipline (C-011, binding)

The FR-005 generator-to-parity regression test — `tests/charter/test_charter_generate_scoped_reference_parity.py`, extending `tests/charter/test_active_languages_idempotency.py`'s `_git_init`/`_invoke_generate`/`_read_catalog` helper precedent (that module was read in full during this planning phase; its helpers already build a real `tmp_path` git repo and drive the real `charter_app` `generate` CLI via `typer.testing.CliRunner`, which is exactly what User Story 2's Acceptance Scenario 1 requires) — lands as a **separate, committed, failing-first commit BEFORE any implementation commit** touches `compiler.py`. The reviewer verifies RED on this mission's `planning_base_branch` (`af847be71d97c8a126e91c31a7d05629c69c93ba`) and GREEN on the lane's final commit. This is stated here in the phasing section, not merely mentioned in passing, per the charter's ATDD-First Discipline section.

The auto-refresh fold-in (below) gets its OWN separate red-first test (an extension to `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` — the real, existing test module for `preflight.references_refresh`; NOT a new `preflight/` subdirectory, which does not exist in the current test tree) — it is a distinct defect class from FR-001–FR-005 and must not be conflated into the same red/green pair; conflating them would make it impossible for a reviewer to verify each fix independently caused its own test to flip.

**The whole-kind-unresolved fail-closed tests ALSO get this treatment (closes PLAN-FRESH2-002).**
"WP-CORE reconciliation" point 3's five invariants (I1–I5) introduce genuinely new, user-observable
behavior that neither WP-ATDD's FR-005 fixture (`SCOPE_FILTERED`-only, per decision 1 above) nor
the pre-round-2 implementation exercises. Per C-011 (binding), each invariant pins user-observable
behavior a WP cannot start coding against until a failing-first test exists. **All five invariants
are pinned by ONE dedicated red-first commit (WP-CORE-TESTS)** — bundled together (rather than one
commit per invariant) because all five pin different entry points into the SAME aggregate
whole-kind mechanism (one shared classify-and-placeholder helper, one aggregate per-kind count, one
fixture family), so authoring and verifying them together is more reviewable than splitting a
single cohesive mechanism's test coverage across five commits — mirroring how WP-ATDD's own FR-005
commit already bundles multiple acceptance-scenario assertions (ids-present, coherence-check,
`--json` shape) into one red-first commit rather than one commit per scenario. This dedicated
commit MUST be verified RED against the pre-round-2/pre-round-3 implementation (this mission's
`planning_base_branch`, `af847be71d97c8a126e91c31a7d05629c69c93ba`) and MUST land strictly BEFORE
the WP-CORE implementation commit(s) that touch `compiler.py` to make it pass — the reviewer
verifies RED on the base and GREEN on the lane's final commit, exactly as for WP-ATDD and
WP-AUTOREFRESH. See "PR Shape" below for how this changes the commit breakdown.

**Invariant → red-first fixture mapping (WP-CORE-TESTS's bundled commit, consolidated from the
fixtures already described in "WP-CORE reconciliation" point 3):**

| Invariant | Red-first fixture / assertion |
|---|---|
| I1 (completeness) | Whole-kind `MISSING_ARTIFACT` fixture (misconfigured pack root): assert `charter generate --force` exits non-zero, writes no catalog, and the error names the affected kind. Distinct `graph.unresolved` fixture: assert the id is routed through the shared helper, gets a reason-bearing diagnostic, and — as the sole activated id of its kind, classified `MISSING_ARTIFACT`/`TYPO_SUSPECTED` — trips the same whole-kind check. |
| I2 (single evaluation point, both buckets OR'd) | Same two fixtures as I1 — together they prove the check counts `graph.unresolved`-sourced ids alongside `graph.<kind>`-sourced ids before evaluating any kind, once, after all sources have contributed. |
| I3 (every diagnostic shaped) | The graph-load-failure fixture's structured-diagnostic assertions (below), plus the unattributable-`graph.unresolved`-URN cases (no `":"`; unrecognized kind prefix; no-repository kind; valid-but-untracked kind with a real repository — split per PLAN-FRESH5-003, round-6) — each asserted against the `kind`/`id`/`cause` shape `contracts/charter-generate-json-diagnostics.md` defines. |
| I4 (loud, not fail-closed) | Total-graph-load-failure fixture (corrupted/unparseable DRG fragment): assert `generate` exits 0, a graph-load-failure diagnostic is present in `diagnostics`, the same diagnostic appears in `--json`'s `unresolved_references`, and the transitive closure is not reconstructed. |
| I5 (determinism) | Idempotency assertion appended to the whole-kind-unresolved fixture: run `generate --force` twice, assert both invocations exit non-zero identically (same code, same kind named) and neither writes/modifies a catalog file. The graph-load-failure fixture is additionally covered by ordinary NFR-001 (byte-identical `catalog.references`), since that path is not fail-closed. |
| I1/I2 carve-out (transitive-only-reachable id + total graph-load failure; closes PLAN-FRESH5-002, round-6) | Fixture: an id activated ONLY via DRG-transitive closure (no direct `config.activated_*` root of its own kind), combined with a corrupted/unparseable DRG fragment forcing `_resolve_transitive_reference_graph`'s total-load-failure branch. Assert: the `_graph`/`_load_failure` sentinel diagnostic is present (in `diagnostics` and `--json`'s `unresolved_references`), no per-id record or placeholder exists for the transitively-only id, `generate` exits 0 (not fail-closed), and repeating the invocation twice produces the identical sentinel diagnostic and exit code (deterministic). |
| `_raw_kind_repository` raw-service degrade (folds in the `reviews/plan-verify-4.yaml` residual, round-6 ruling) | Fixture: call `_raw_kind_repository` with a raw/unwrapped `doctrine_service` (no `raw_repository` method, per the function's own docstring branch) and a `kind` with no matching attribute on it (e.g. `"templates"`/`"anti_patterns"`). Assert pre-fix behavior raises `AttributeError` (RED against `af847be71`) and post-fix returns `None` (GREEN) — a reported miss, not a crash, matching how the wrapped shape's own `raw_repository` accessor already degrades for the same class of kind. |

## Phasing & Sequencing

1. **WP-ATDD — FR-005 regression test (failing-first, committed alone).** Author `tests/charter/test_charter_generate_scoped_reference_parity.py`: build a `tmp_path` git repo fixture whose `.kittify/config.yaml` activates the six #5257 ids (`styleguide/java-conventions`, `toolguide/maven-review-checks`, `toolguide/typescript-mutation-tools`, `agent-profile/frontend-freddy`, `agent-profile/java-jenny`, `agent-profile/node-norris`) plus at least one additional, differently language-scoped id (per C-002, proving the general mechanism, not six special cases — e.g. a language-filtered `tactic` or `procedure`, chosen at implementation time from an artifact under `packs/built-in/` whose `applies_to_languages` excludes whatever this fixture's `infer_repo_languages` detects). Drive the real `charter_app` `generate` CLI (`_invoke_generate` precedent), then feed the resulting repo through `ProjectContext.from_repo()` + `run_consistency_check` directly (spec's Acceptance Scenario 3 — NOT the hardcoded-`_REPO_ROOT` `test_this_project_charter_pack_is_coherent`, which cannot be conditioned on an arbitrary fixture path). Assert: (a) every fixture id is present in `catalog.references`; (b) `run_consistency_check` reports coherent; (c) pre-fix, this test is RED (verified by running it against `af847be71` before the compiler fix lands — the reviewer's own verification step). Commit alone.
2. **WP-CORE-TESTS — dedicated red-first commit pinning invariants I1–I5 (closes PLAN-FRESH3-003; per the ATDD-First Discipline section's invariant-mapping table above).** Author, in ONE commit, the fixture-driven assertions the ATDD-First Discipline table requires: the whole-kind `MISSING_ARTIFACT`/`TYPO_SUSPECTED` fail-closed exit and the `graph.unresolved`-through-shared-helper routing case, including its four unattributable-URN classes (I1/I2/I3, round-6: split per PLAN-FRESH5-003); the total-graph-load-failure loud-structured-diagnostic case (I4); and the idempotency assertion (I5). Verify RED against this mission's `planning_base_branch` (`af847be71d97c8a126e91c31a7d05629c69c93ba`). Lands strictly AFTER WP-ATDD and strictly BEFORE WP-CORE's implementation commit(s) below. Commit alone (no implementation changes in this commit).
3. **WP-CORE — FR-001/FR-002/FR-003 compiler fix.** In `src/charter/activation/compiler.py`: replace the two duplicated `diagnostics.append(f"Unresolved reference: ...")` sites with a single shared classify-and-placeholder helper that (a) calls the existing canonical gate `_diagnose_catalog_miss(raw_id, repository)` (`src/charter/activation/context_renderers/catalog_diagnosis.py`, round-8 fix, closes analyze D1/C1/U1 — see IC-02) to get a `CatalogMissDiagnosis`; the gate already checks `getattr(repository, "scope_filtered_ids", frozenset())` defensively to route to `classify_scope_filtered_miss` (`CatalogMissCause.SCOPE_FILTERED`) vs. falls through to `classify_catalog_miss(raw_id, _available_catalog_ids(repository))` (`TYPO_SUSPECTED`/`MISSING_ARTIFACT`) for the never-existed case — no threading of `active_languages` and no hand-written `scope_filtered_ids` check in `compiler.py` itself; (b) **for the `SCOPE_FILTERED` cause only**, ALWAYS preserves the id as a placeholder `CharterReference` (uniform mechanism *within that cause*, per FR-001's cardinality-agnostic requirement — never a second fail-closed exit branch for scope-filtered misses); **for `MISSING_ARTIFACT`/`TYPO_SUSPECTED`, stays on the EXISTING Contract-C4-compatible diagnostics-only path — no placeholder row, `references` unchanged at `[]` for that id** (see "WP-CORE reconciliation: Contract C4 scope and placeholder text format" below — this scoping is a deliberate, reviewed decision, not an oversight); (c) records a reason-bearing diagnostic string (`"Unresolved reference: {kind}/{id} ({cause}): {detail}"` — extends, does not replace, the existing free-text format) into the existing `diagnostics: list[str]` **for both causes** (FR-002/NFR-002's reason-bearing requirement applies whether or not the id also gets a placeholder row); (d) additionally records a structured `(kind, id, cause, detail)` record for every cause that flows through to FR-004's `unresolved_references` JSON field, so a `MISSING_ARTIFACT`/`TYPO_SUSPECTED` miss is still machine-readable even though it has no placeholder row; (e) **aggregate, cause-agnostic whole-kind check (closes PLAN-FRESH-001, this fix round)**: after all of a kind's ids are classified via (a)-(d), if that kind had at least one activated id and NONE of them produced a reference (no resolution, no `SCOPE_FILTERED` placeholder — i.e. every one fell through to the diagnostics-only branch), raise a fail-closed error naming the kind and its unresolved ids before `_build_references_from_service` returns, so `compile_charter` never completes for this case and `generate.py`'s existing `RuntimeError` handler (`generate.py:584`) exits non-zero before `write_compiled_charter` runs — satisfying FR-001's second stated mechanism for the whole-kind-unresolvable case (e.g. a misconfigured pack root) that (b)'s `SCOPE_FILTERED`-only placeholder scoping does not cover. This is a per-kind cardinality count, not a check on the six #5257 ids (C-002) — see "WP-CORE reconciliation" point 3 for the full design and the ATDD-First Discipline section's invariant → red-first fixture mapping table for the test requirement. `--force` (FR-003) touches nothing in this path — it already only gates catalog-file overwrite permission upstream of `_build_references`, never reference resolution, so FR-003 is verified by a paired same-fixture run with/without `--force` producing identical diagnostic/placeholder content (no code change required for FR-003 itself, only a test assertion). Verify the WP-ATDD test now passes GREEN, the new whole-kind-unresolved fail-closed tests (the ATDD-First Discipline section's invariant → red-first fixture mapping table; design rationale in "WP-CORE reconciliation" point 3) pass GREEN, and the existing 56-test baseline (`test_activation_parity_guard.py` + `test_active_languages_idempotency.py` + `test_context_catalog_miss.py` + `test_catalog_completeness_4785.py`, per "The baseline" above) stays green (NFR-001, C-001, FR-006) — `test_catalog_completeness_4785.py` specifically proves Contract C4 (the `MISSING_ARTIFACT`/`TYPO_SUSPECTED` diagnostics-only path) is undisturbed by this change.
4. **WP-JSON — FR-004 structured diagnostics.** In `src/specify_cli/cli/commands/charter/generate.py`'s `--json` emit block: thread the structured unresolved-reference records from `compiled` (via a new field on the compiler's own result type carrying the list WP-CORE built) into the new `unresolved_references` key, alongside the unchanged `diagnostics` list. Add/extend `contracts/charter-generate-json-diagnostics.md`. Test: Acceptance Scenario 2 (id + reason present machine-readably in `--json` output).
5. **WP-AUTOREFRESH — preflight auto-refresh swallow fold-in.** Bounded fix to `references_refresh.py`/`runner.py`'s `_attempt_auto_refresh` (full design in tracer-design-decisions.md and restated below) — its own red-first test (T019) committed alone as commit 1, then a second commit (T017+T018) turning it GREEN — two commits total, per `tasks/WP04-autorefresh-foldin.md`'s Objective section — sequenced independently of WP-CORE/WP-JSON (touches a disjoint file set, no ordering dependency either direction).
6. **WP-CLEANUP-VERIFY** (folded into WP-CORE/WP-JSON's own commits, not a separate step): re-run `make ci-parity` against the real `src/` diff once WP-CORE/WP-JSON/WP-AUTOREFRESH land, to confirm the actual module-shard/architectural-heavy/diff-cover selection (deferred — cannot be predicted at plan time, stated explicitly above).

## WP-CORE reconciliation: Contract C4 scope and placeholder text format

Three design decisions, made across two planning-phase adversarial-review rounds, bind WP-CORE's
implementation. Full reasoning lives in `tracer-design-decisions.md` (three decision entries —
the third added this round, closing PLAN-FRESH-001); this section states the resolutions plainly
so an implementing agent does not have to reconstruct them from the tracer.

**1. Contract C4 is NOT superseded — WP-CORE's placeholder path is scoped to `SCOPE_FILTERED` only.**
`_render_kind_references` (`src/charter/activation/compiler.py:1096`) is also the function a prior,
COMPLETED mission (`charter-catalog-coherence-01M2XQQF`, issue #4785) pinned as **Contract C4**
("Recompiled catalog is complete and stable",
`kitty-specs/charter-catalog-coherence-01M2XQQF/contracts/behavior-contracts.md`): "Given a directive
id with genuinely no bundled definition, Then it surfaces through the `graph.unresolved` diagnostics
channel, not as a silent placeholder `catalog.references` row." This is pinned today by
`tests/charter/test_catalog_completeness_4785.py::test_render_kind_references_routes_genuine_miss_to_diagnostics_not_placeholder`,
currently green (5 passed on this branch). An always-placeholder design — regardless of cause — would
flip that test red. **Decision: option (b), narrow the scope.** WP-CORE's new placeholder mechanism
applies ONLY to the `SCOPE_FILTERED` cause (the actual #5257/#5253 defect: an id present on disk,
excluded solely by language/scope). A `MISSING_ARTIFACT`/`TYPO_SUSPECTED` miss (genuinely no bundled
definition) stays on the existing Contract-C4-compatible diagnostics-only path — Contract C4 and its
pinning test are **not modified**. FR-001's disjunctive "preserve OR loudly report" bar is still met
for the genuinely-missing case: a reason-bearing diagnostics-list entry (FR-002/NFR-002 apply to this
path too) is the "loudly report" branch; it does not also need to become a placeholder row.
Consequence: `tests/charter/test_catalog_completeness_4785.py` is added to WP-CORE's blast-radius
baseline command (see "The baseline" above, now 56 tests) so this contract's continued health is
actually verified, not assumed.

**2. `SCOPE_FILTERED` placeholder summary text — extend the existing baseline string, don't replace
it.** NFR-002 requires the new `SCOPE_FILTERED` placeholder's `summary` to name the reason category.
The current baseline text (`_doctrine_yaml_reference`'s fallback, `compiler.py:1505`:
`"Definition unavailable in bundled doctrine."`, already committed verbatim in this repo's own
`.kittify/charter/charter.yaml` for the still-unresolved ids) names no reason at all, and spec.md's
Edge Case requires a repo already carrying that baseline to "not further diverge from" it on
regeneration. **Decision: option (a), extend as a stable prefix.** The new placeholder's `summary`
keeps `"Definition unavailable in bundled doctrine."` verbatim as a prefix and appends a
reason-bearing suffix sourced from `classify_scope_filtered_miss`'s own suggestion text:
`"Definition unavailable in bundled doctrine. Reason: scope_filtered — <suggestion>"`. This satisfies
NFR-002 (reason category + detail present) without diverging from the Edge Case's existing
convention (the literal prefix is preserved byte-for-byte). WP-CORE adds one concrete test: regenerate
a fixture seeded with today's exact baseline row shape for a still-unresolvable `SCOPE_FILTERED` id
and assert the post-fix `summary` matches this prefix+suffix format exactly (placed alongside the
other WP-CORE unit-level assertions in `tests/charter/test_charter_generate_scoped_reference_parity.py`
or a narrower `compiler.py`-level unit test, implementer's choice — either satisfies IC-01/IC-04).

**3. A new aggregate, cause-agnostic whole-kind check closes FR-001's "misconfigured pack root"
gap that decision 1's `SCOPE_FILTERED`-only narrowing reopened (PLAN-FRESH-001, this fix round).**
Decision 1 above narrows the *placeholder* mechanism to `SCOPE_FILTERED` only — a `MISSING_ARTIFACT`/
`TYPO_SUSPECTED` miss never gets a placeholder row, only a reason-bearing diagnostic. FR-001's own
text and its matching Edge Case bullet give "a misconfigured pack root" (a `MISSING_ARTIFACT`-class
cause, not `SCOPE_FILTERED`) as an illustrative *whole-kind-unresolvable* scenario, and state that
placeholder-preservation and a fail-closed non-zero exit naming the kind are the **two** mechanisms
that satisfy FR-001 "at any cardinality." Decision 1 leaves the whole-kind `MISSING_ARTIFACT`/
`TYPO_SUSPECTED` case with neither: no placeholder (by decision 1's own scoping) and no fail-closed
exit (`generate` still exits 0, still writes a structurally valid but silently-empty-for-that-kind
catalog section) — exactly the vacuous success FR-001 forbids, using FR-001's own literal example.
This decision closes that gap **without reopening decision 1**: it adds a second mechanism (the
fail-closed exit FR-001 already names) that operates at a different level than decision 1's per-id
placeholder scoping. `--force` (FR-003) touches nothing in this path — it already only gates
catalog-file overwrite permission upstream of `_build_references`, never reference resolution.

### Round-5 restatement: five binding invariants (closes PLAN-FRESH4-001..004; replaces the prior line-level mechanism prose)

Four rounds of adversarial review found real inconsistencies in how this mechanism was described at
the line-level: activation-detection input conflated with the output-emptiness condition; three
mutually contradictory statements of WHEN the check runs; undefined `kind`/`id` shapes for
edge-case `graph.unresolved` entries; an arithmetic error in "PR Shape"'s own commit count. Per the
operator's round-5 ruling (`reviews/plan.ruling.md`, "Round-5 ruling"), this section now states the
mechanism as five testable invariants rather than a step-by-step mechanism recipe — each one a WP
implementer or reviewer must be able to check directly against real behavior, without needing any
deleted mechanism prose:

- **I1 — completeness.** Every activated reference id, from any source bucket (`graph.<kind>` or
  `graph.unresolved`), ends up either in `catalog.references` (resolved or placeholder) or in a
  structured diagnostic — never silently absent. **Carve-out (total graph-load failure; closes
  PLAN-FRESH5-002, round-6 ruling):** this per-id guarantee does not extend to ids reachable ONLY
  via DRG-transitive closure when the whole graph fails to load. Under a total graph-load failure
  (`_resolve_transitive_reference_graph`'s `except` branch, I4), those ids are covered collectively —
  never individually — by the single loud `_graph`/`_load_failure` sentinel diagnostic (see I4 and
  the contract doc's Round-3 addition): no per-id `catalog.references` entry, no per-id structured
  diagnostic, and no fail-closed exit for this class specifically. This is a direct, explicit
  consequence of the round-3 ruling declining to reconstruct the transitive closure on graph-load
  failure (`reviews/plan.ruling.md`, "Round-3 ruling") — stated here rather than left to be inferred.
- **I2 — single evaluation point, both source buckets counted.** The whole-kind fail-closed check is
  evaluated once per kind, after ALL sources (all per-kind `_render_kind_references` calls AND the
  kind-mapped `graph.unresolved` pass) have contributed. A kind counts as **activated** if EITHER
  `graph.<kind>` is non-empty OR at least one `graph.unresolved` URN was attributed to it via the
  kind-mapping step — the two conditions are OR'd, never just the output-emptiness condition alone.
  (Closes PLAN-FRESH4-001 and PLAN-FRESH4-002 — the prior text's activation-detection-vs-output
  conflation and its three contradictory timing statements are both replaced by this one statement.)
  **Same carve-out as I1, restated for this OR condition (closes PLAN-FRESH5-002):** under total
  graph-load failure, `graph.unresolved` is never populated (the exception fires before
  `resolve_transitive_refs` produces any bucket) and `graph.<kind>` reflects only that kind's direct
  config roots — so a kind whose activated ids are ALL transitively-reachable (no direct root of that
  kind) never satisfies this OR condition in that failure mode, and correctly is never evaluated by
  the whole-kind check: I1's graph-wide sentinel diagnostic stands in for that kind's coverage
  instead, not a silently-skipped case.
- **I3 — every diagnostic is shaped.** Every structured diagnostic record carries a defined `kind`,
  `id` and `cause`, including for unresolved URNs whose kind is outside the six tracked kinds, has
  no repository mapping, or has no `":"` at all. `contracts/charter-generate-json-diagnostics.md`
  defines the sentinel/shape for each of these four unattributable classes (round-6: the
  no-repository-mapping class split into a genuinely-`None`-repository case and a
  valid-but-untracked-kind case, per PLAN-FRESH5-003); `cause` is a plain
  `str` value, distinct from the four `CatalogMissCause` values and from `"graph_load_failed"`.
  (Closes PLAN-FRESH4-003.)
- **I4 — graph-load failure is loud, not fail-closed.** A total DRG graph-load failure yields a loud
  structured diagnostic and does NOT fail closed (round-3 ruling, unchanged this round).
- **I5 — determinism.** Generation is deterministic across repeat invocations on both the fail-closed
  and diagnostic paths.

Each invariant maps to a named red-first test fixture — see the table in "ATDD-First Discipline"
below. Mechanism-level detail beyond the binding decisions retained below (exact call ordering,
helper signatures, line numbers) is deferred to the tasks squad and WP review, where the red-first
tests catch any drift.

**Binding mechanism decisions retained from prior rounds (load-bearing operator rulings, not
mechanism trivia the squad kept re-litigating — stated here as binding, not as sketch):**

- **URN split and kind mapping.** A `graph.unresolved` entry's URN is split with
  `kind_prefix, _, bare_id = urn.partition(":")` (matching `resolve_transitive_refs`'s own
  successful-lookup branch, `query.py:394`'s `urn.split(":", 1)` pattern) and the singular
  `kind_prefix` is mapped to the plural repository key using the EXISTING
  `ArtifactKind(kind_prefix).plural` mapping (`src/charter/offering/artifact_kinds.py`, already
  imported into `compiler.py` and already used the same way in `_bare_ids_for_kind`) — never a new,
  invented mapping.
- **Diagnostics/structured-record sink, not a return-type widening.** The `diagnostics: list[str]`
  and the new structured-records sink are appended to INSIDE `_resolve_transitive_reference_graph`'s
  own `except` branch, passed in as parameters by its caller — not by widening the function's return
  type and not via a marker exception (both explicitly declined by the operator).
  `ResolveTransitiveRefsResult` (`charter.offering.drg.query`) stays UNCHANGED.
- **`cause` is a plain `str`, never the `CatalogMissCause` enum type.** The new structured record's
  `cause` field (including `"graph_load_failed"` and the round-5 sentinel values the contract doc
  adds for I3) is typed `str` on the structured-records sink. `CatalogMissCause`/
  `src/charter/activation/_catalog_miss.py` stay REUSED, NOT MODIFIED — no fifth enum member is ever
  added to that file.
- **Graph-load failure never fails closed** (round-3 ruling, restated as I4 above).
- **Classification reuses the canonical `_diagnose_catalog_miss` gate, no `active_languages`
  threading (round-8 fix, closes analyze findings D1/C1/U1).** The per-id classify-and-placeholder
  helper calls `_diagnose_catalog_miss(raw_id, repository)`
  (`src/charter/activation/context_renderers/catalog_diagnosis.py`) instead of re-deriving the
  `scope_filtered_ids`-check-then-`classify_catalog_miss`-fallback sequence inline in `compiler.py`,
  and instead of threading a new `active_languages` parameter through `compile_charter` →
  `_build_references` → `_build_references_from_service` → `_render_kind_references`. The gate
  already reads `active_languages` off the repository's own `_active_languages` attribute and
  already sources the fuzzy-match corpus from `_available_catalog_ids(repository)` — see IC-02 for
  the full design and the import-direction/no-cycle verification. This does not touch the
  whole-kind check, the `graph.unresolved` URN-split/kind-mapping, the graph-load diagnostics sink,
  the plain-`str` `cause` typing, or the `_raw_kind_repository` `getattr` fold-in above — all of
  those stay exactly as ruled in rounds 3-7.
- **The auto-refresh fold-in is UNCHANGED by this round** — see "Auto-refresh fail-closed swallow —
  decision: FOLD IN (bounded)" below; only its cross-references to this section were updated.

**Non-binding implementation sketch, illustrative only — the invariants above are binding, this
sketch is not.** The mechanism lives in `src/charter/activation/compiler.py`. Roughly:
`_build_references_from_service` orchestrates the six per-kind `_render_kind_references` calls and
the `graph.unresolved` pass, feeding both into one shared classify-and-placeholder helper so that
I1's completeness and I2's single-evaluation-point invariants hold; `_resolve_transitive_reference_graph`
is where total graph-load failure is caught and reported per I4. Exact call ordering, helper
signatures, and line numbers are implementation detail for the tasks squad and WP review to pin down
against the red-first tests below, not restated here.

## Auto-refresh fail-closed swallow — decision: FOLD IN (bounded)

**Verified against the actual current code** (read `src/specify_cli/charter_runtime/preflight/references_refresh.py` lines 145–189 and `runner.py` lines 553–773 in full at plan time, not restated from a prompt sketch on faith):

- `references_refresh.refresh_references_if_needed` (lines 145–189) spawns `subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=..., check=False)`, binds the `CompletedProcess` to a discarded expression (no variable capture of the return value at all — confirmed: line 175's `subprocess.run(...)` call result is not assigned), catches only `(OSError, subprocess.TimeoutExpired)` at debug-log level, and **unconditionally `return`s `True`** (line 189) regardless of whether the subprocess exited 0 or non-zero.
- Its caller, `runner.py::_attempt_auto_refresh` (lines 724–759), receives that `True` as `references_refreshed` and — with no outcome information available — unconditionally re-runs `spec-kitty charter synthesize` (the manifest re-stamp, lines 749–759) to re-stamp `synthesized_drg`'s stored content-hash against whatever is CURRENTLY in `charter.yaml`. Per the module's own "post-#2759 retirement" docstring note, `synthesized_drg` staleness is fundamentally "does the manifest's stored hash match a hash of charter.yaml's CURRENT content" — so restamping over a `charter.yaml` that `generate` FAILED to actually reconcile makes the recompute at lines 763–765 see `synthesized_drg="fresh"` even though the underlying references-parity condition was never actually resolved.
- **This is confirmed live in the current code, independent of whether this mission's own FR-001 fix ever triggers a fail-closed `generate` exit** (per the plan's placeholder-for-`SCOPE_FILTERED` design above, `generate` itself should now essentially never need a fail-closed non-zero exit for the scoped-reference defect class specifically — but the swallow is reachable for ANY reason `generate` exits non-zero at this call site: a crash, a lock conflict, a schema error, disk-full, etc.), so it is a real pre-existing defect this mission's own investigation surfaced, not a hypothetical.

**Bounded design (verified sound, adopted as proposed by the phase agent orchestrating this plan, with the verification checks above confirming each of its load-bearing claims):**

1. Widen `references_refresh.refresh_references_if_needed`'s return contract from `bool` to a small frozen outcome type — `RefreshOutcome(attempted: bool, succeeded: bool, detail: str | None)` (a `NamedTuple` or `@dataclass(frozen=True)`, implementation's choice) — where `succeeded` reflects `completed.returncode == 0` (now the `CompletedProcess` IS bound to a name and inspected) and `detail` is a short excerpt (e.g. last non-empty stderr line, or stdout if stderr is empty) on failure. This is an internal signature confined to this one module and its one in-repo caller (`runner.py`'s `refresh_references_if_needed` wrapper, lines 553–582, and `_attempt_auto_refresh`, ~line 733) — NOT a change to `CharterPreflightResult` or any documented/public contract.
2. In `runner.py::_attempt_auto_refresh`: when the outcome is `attempted and not succeeded`, return `CharterPreflightResult(passed=False, checks=initial_checks, auto_refresh_applied=True, auto_refresh_actions=actions, blocked_reason=f"references-parity refresh failed: {detail}")` **immediately, skipping the manifest-restamp step entirely** — restamping over content that was not actually regenerated is precisely the masking mechanism being removed. When `not attempted` or `attempted and succeeded`, the existing restamp+recompute flow (lines 749–773) is unchanged, byte-for-byte.
3. Red-first test (`tests/specify_cli/charter_runtime/test_references_parity_refresh.py`, extended — the real, existing test module for `preflight.references_refresh`, which already ships `_git_init`, `_make_generate_subprocess_fake`, and `_seed_baseline_repo` fixture machinery directly reusable here; NOT the nonexistent `tests/specify_cli/charter_runtime/preflight/` path): adapt `_make_generate_subprocess_fake` so the faked `generate` subprocess invocation inside the auto-refresh path returns a non-zero returncode/stderr instead of success. Assert (a) BEFORE the fix, the swallow means the failure never reaches an actionable `blocked_reason` — `passed` can report `True` despite the underlying `generate` failure (demonstrating the bug is real, RED on `af847be71`); (b) AFTER the fix, `passed=False` and `blocked_reason` names the failure detail (GREEN).

**Why this qualifies as "bounded" under operator doctrine** (fold-in, not defer-to-follow-up, not HALT): one call site (`_attempt_auto_refresh`'s post-`refresh_references_if_needed` branch), one function's return-type widening confined to a module and its single caller, testable red-first in isolation, **no contract change** to `CharterPreflightResult`/`contracts/charter-preflight-json.md` beyond reusing the field that already exists (`blocked_reason: str | None`) in exactly the pattern the function already uses elsewhere in the same branch (lines 686–692, 704–709 already return `blocked_reason=reason` with `auto_refresh_applied=True` for a failed refresh step — this fold-in makes the references-parity step behave consistently with every OTHER step in the same sequence, rather than being the one step whose failure is invisible). It does not reach into `charter generate`'s own exit-code contract, does not touch the CLI's `--json` output shape, and does not touch any file outside the two named preflight modules. This clears the fold-in bar; a HALT-for-operator framing is not warranted here.

## Implementation Concern Map

### IC-01 — Placeholder-preservation for `SCOPE_FILTERED` unresolved DRG-backed references

- **Purpose**: Close the silent-drop defect (FR-001) by making every activated-but-unresolvable id whose cause is `SCOPE_FILTERED` a placeholder `CharterReference` instead of a dropped one, uniformly regardless of cardinality (one scope-filtered id or every scope-filtered id of a kind). `MISSING_ARTIFACT`/`TYPO_SUSPECTED` misses stay on the existing Contract-C4-compatible diagnostics-only path (never a placeholder row) — see "WP-CORE reconciliation: Contract C4 scope and placeholder text format" above; this is a deliberate cause-conditioned scoping, not an unconditional "every unresolved id" rule. **IC-01 additionally closes FR-001's aggregate whole-kind sub-clause (PLAN-FRESH-001, this fix round):** after per-id classification, `_build_references_from_service` checks whether an entire kind's activated ids produced zero references (no resolution, no `SCOPE_FILTERED` placeholder) and, if so, fails closed with a non-zero exit naming the kind — a cause-agnostic, per-kind cardinality check layered on top of the per-id `SCOPE_FILTERED` vs. `MISSING_ARTIFACT`/`TYPO_SUSPECTED` distinction above, not a replacement for it. See "WP-CORE reconciliation" point 3 for the full design, and the ATDD-First Discipline section's invariant → red-first fixture mapping table for the test requirement.
- **Relevant requirements (split by mechanism, closes PLAN-FRESH2-003)**: FR-001, FR-003, NFR-001, NFR-002, C-001, C-002, SC-001, SC-004 back IC-01 as a whole. **SC-005** backs, specifically, the `SCOPE_FILTERED` per-id placeholder mechanism (Acceptance Scenario 4's `SCOPE_FILTERED` whole-kind fixture — see decision 1/tracer-design-decisions.md) — it does NOT exercise, and does not back, the whole-kind `MISSING_ARTIFACT`/`TYPO_SUSPECTED` fail-closed mechanism (decision 3 above, now stated as invariants I1–I4: the `graph.unresolved`-through-shared-helper and graph-load-failure widenings). That whole-kind fail-closed mechanism is backed only by **FR-001's own Edge Case text** ("All activated references of a kind... are unresolvable") — spec.md has no dedicated Success Criterion for it; the plan's own invariant restatement (I1–I5) above is the only acceptance-level statement of that mechanism's bar. (Minimal fix per PLAN-FRESH2-003's remediation option (a) — split the citation rather than add a new spec.md SC, since spec.md is otherwise untouched by this mission.)
- **Affected surfaces**: `src/charter/activation/compiler.py` (`_render_kind_references`, `_build_references_from_service`, `_resolve_transitive_reference_graph` — gains `diagnostics`/structured-records sink parameters per the binding sink-params ruling above (I3), closes PLAN-FRESH3-002 — its return type is unchanged, still `ResolveTransitiveRefsResult` — new private classify-and-placeholder helper, new private whole-kind fail-closed check/exception in `_build_references_from_service`; `_raw_kind_repository` — its raw-service fallback branch, `compiler.py:1093` (`return getattr(doctrine_service, kind)`, no default), changes to `getattr(doctrine_service, kind, None)` — round-6 ruling, folds in the `reviews/plan-verify-4.yaml` residual, see below).
- **Sequencing/depends-on**: Follows WP-ATDD (the FR-005 test must exist and be RED first).
- **Risks**: (1) The existing diagnostic string format (`"Unresolved reference: <kind>/<id>"`) is extended, not replaced — implementation must grep the test suite for any exact-string assertion on the OLD format before changing it, to avoid an unrelated test regression outside this mission's stated scope. (2) Regression risk against **Contract C4**: `tests/charter/test_catalog_completeness_4785.py` (added to the baseline command above) must stay green — a `MISSING_ARTIFACT`/`TYPO_SUSPECTED` id must never fall through to the placeholder branch; the `_diagnose_catalog_miss(raw_id, repository)` call (whose returned `cause` gates placeholder-vs-diagnostics-only, per IC-02's round-8 reuse decision) must run BEFORE any placeholder-construction code, not after — and its `_EmptyRepository`-safe `getattr(repository, "scope_filtered_ids", frozenset())` guard is what keeps this test green (closes analyze C1), not a separate hand-written check. (3) **Timing (closes PLAN-FRESH4-002, restates I2 as the single, unambiguous statement of when the check runs):** the aggregate whole-kind check is evaluated ONCE per kind, after ALL sources for that kind have contributed — every per-kind `_render_kind_references` call AND the kind-mapped `graph.unresolved` pass — never "immediately after" any single source. It trips only when a kind produced NEITHER a resolution NOR a `SCOPE_FILTERED` placeholder for ANY of its activated ids, where "activated" means either `graph.<kind>` was non-empty OR at least one `graph.unresolved` URN was attributed to it (I2's OR condition) — a kind with even one `SCOPE_FILTERED` id among otherwise-`MISSING_ARTIFACT` ids must NOT trip the fail-closed path, since that kind's reference list is non-empty. Implementation must add the fixture test proving a whole-kind-unresolvable `MISSING_ARTIFACT` case (e.g. a misconfigured pack root) actually exits non-zero before any catalog write — see "WP-CORE reconciliation" point 3 and the ATDD-First Discipline invariant table.
- **Residual from `reviews/plan-verify-4.yaml`, FOLDED IN this round (round-6 ruling, reverses the round-5 "out of scope" disposition):** `_raw_kind_repository`'s raw-service fallback branch (`compiler.py:1093`, `return getattr(doctrine_service, kind)`, no default) raises `AttributeError` rather than degrading to `None` for `kind_prefix` values `"template"`/`"anti_pattern"` specifically, when `doctrine_service` is the raw/unwrapped `charter.offering.service.DoctrineService` shape (reachable only via an explicit test-supplied override, per the function's own docstring — never via `compile_charter`'s default production path). This is fixed in this mission, not deferred: the fallback becomes `getattr(doctrine_service, kind, None)`, so it degrades to a reported miss (a `None` repository, handled the same way the rest of this function's callers already handle a missing raw repository) rather than raising. Covered by a small, dedicated red-first test — see the ATDD-First Discipline invariant table's dedicated fixture row for `_raw_kind_repository`. There is no follow-up issue for this residual.

### IC-02 — Reason classification reusing the canonical `_diagnose_catalog_miss` gate

- **Purpose**: Satisfy FR-002/NFR-002 by distinguishing never-existed from filtered-by-language-scope, reusing the existing single gate `_diagnose_catalog_miss(missing_id, repository)` (`src/charter/activation/context_renderers/catalog_diagnosis.py`, already in that module's `__all__`) — the SAME gate `selection_block.py` and `profile_sections.py` already call for the identical FR-013 classification — rather than inventing a second, parallel classify helper and threading a new `active_languages` parameter through `compiler.py` (DIRECTIVE_044, single canonical authority). **Round-8 fix (post-analyze):** this replaces the prior round's four-call-level `active_languages`-threading design and closes analyze findings D1 (duplication), C1 (Contract-C4 test-compatibility), and U1 (underspecified fuzzy-match corpus) — see `kitty-specs/charter-generation-drops-scoped-references-01M3M1KF/analysis-report.md`.
- **Relevant requirements**: FR-002, NFR-002, SC-003 (User Story 3 acceptance scenarios).
- **Affected surfaces**: `src/charter/activation/compiler.py` imports `_diagnose_catalog_miss` from `charter.activation.context_renderers.catalog_diagnosis` and calls `_diagnose_catalog_miss(raw_id, repository)` inside the classify-and-placeholder helper described under IC-01 — that ONE call replaces both the `raw_id in repository.scope_filtered_ids` membership check and the `classify_catalog_miss`/`classify_scope_filtered_miss` fallback, because the gate already implements exactly that sequence (`catalog_diagnosis.py:33-58`): it checks `getattr(repository, "scope_filtered_ids", frozenset())` first, and on a genuine miss calls `classify_catalog_miss(missing_id, _available_catalog_ids(repository))` — so the fuzzy-match corpus (closes U1) is sourced from the gate's own `_available_catalog_ids(repository)` helper, never built or passed by `compiler.py`. **No `active_languages` parameter threading is needed anywhere**: the gate reads `active_languages` directly off `getattr(repository, "_active_languages", None)`, the value each per-kind repository already carries from its own construction (`BaseDoctrineRepository.__init__`, `src/charter/offering/base.py:106`) — so `compile_charter` does NOT pass `active_languages` to `_build_references`, `_build_references_from_service` does NOT forward it to `_render_kind_references`, and none of the six per-kind call sites gains a new parameter for this reason. Neither `_catalog_miss.py` nor `catalog_diagnosis.py` is itself modified — both are consumed as-is.
  - **Import direction (verified against live `HEAD` source, not assumed)**: `charter.activation.compiler` → `charter.activation.context_renderers.catalog_diagnosis` → `charter.activation._catalog_miss` (a leaf — imports only `difflib`/`logging`/`warnings`/stdlib `collections.abc`/`dataclasses`/`enum`, nothing from `charter.activation`). Checked for a cycle: neither `catalog_diagnosis.py` nor `context_renderers/__init__.py` (nor its sibling modules `authority_paths.py`, `fetch_stanza.py`, `section_bodies.py`, `token_budget.py`) imports `compiler` anywhere in the package — so `compiler.py` gaining this new import is a one-directional addition with no import cycle.
  - **Contract C4 compatibility (closes analyze finding C1)**: the mandatory baseline test `tests/charter/test_catalog_completeness_4785.py::test_render_kind_references_routes_genuine_miss_to_diagnostics_not_placeholder` calls `_render_kind_references` with `_EmptyRepository()`, a test double exposing only `.get()` — no `scope_filtered_ids` attribute. This stays green because `_diagnose_catalog_miss` already guards that access with `getattr(repository, "scope_filtered_ids", frozenset())` (`catalog_diagnosis.py:51`) rather than an unguarded membership check — WP02 need not add its own defensive `getattr` for this; the reused gate already carries the precedent analyze finding C1 was worried would be missed.
- **Sequencing/depends-on**: IC-01 (same commit/WP — the classify step and the placeholder-build step are one cohesive change, not separable without circularity, per the Campsite-clean decision above).
- **Risks**: The prior round's risk ("implementation must not skip the `active_languages` threading, or the suggestion text degrades to the generic fallback") no longer applies — there is no threading to skip; the gate always has language context available directly from the repository. The live risk instead is re-deriving the `scope_filtered_ids`-check-then-classify sequence inline in `compiler.py` rather than calling the gate, which would reintroduce the D1 duplication this round closes. Add one assertion (WP-ATDD or WP-JSON, implementer's choice) that the emitted detail/suggestion text for a `SCOPE_FILTERED` case names the actual active language set — this passes once `_diagnose_catalog_miss` is called with the real repository, since the gate itself sources `_active_languages` from it.

### IC-03 — Machine-readable `--json` diagnostics

- **Purpose**: FR-004 — carry unresolved-reference id+reason structurally in `charter generate --force --json` output.
- **Relevant requirements**: FR-004, SC-001 (JSON half).
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/generate.py` (JSON emit block), a new field on the compiler's result type to carry the structured records from `_build_references` through to the CLI layer, `contracts/charter-generate-json-diagnostics.md` (new).
- **Sequencing/depends-on**: IC-01/IC-02 (the structured records must exist before the CLI layer can surface them).
- **Risks**: Must not change the `diagnostics: list[str]` field's existing shape (additive-only contract change, verified against every current reader of that field before landing).

### IC-04 — Generator-to-parity regression test

- **Purpose**: FR-005 — pin this defect class at the real `compile_charter`/`charter generate` entry point so it cannot silently regress.
- **Relevant requirements**: FR-005, SC-002, SC-003, SC-004.
- **Affected surfaces**: `tests/charter/test_charter_generate_scoped_reference_parity.py` (new), extending `tests/charter/test_active_languages_idempotency.py`'s fixture helpers by reference (not by copy — import/reuse where the helpers are already suitably general, or lift near-identical private helpers into the new module per existing test-module conventions in this codebase).
- **Sequencing/depends-on**: None (this is WP-ATDD, sequenced FIRST — see Phasing above).
- **Risks**: Fixture construction must avoid hardcoding the six #5257 ids as the ONLY proof (C-002) — the extra differently-scoped id is mandatory, not optional.

### IC-05 — Preflight auto-refresh swallow fold-in

- **Purpose**: Close the pre-existing silent-success masking bug in `_attempt_auto_refresh`'s references-parity step, per operator doctrine (fold bounded same-defect-class fixes rather than defer).
- **Relevant requirements**: Edge Cases "Mid-flight missions" (spec.md), this mission's own NFR-002/FR-001 silent-success bar applied reflexively to the preflight seam.
- **Affected surfaces**: `src/specify_cli/charter_runtime/preflight/references_refresh.py`, `src/specify_cli/charter_runtime/preflight/runner.py` (`_attempt_auto_refresh` only — no other function in this module changes), `tests/specify_cli/charter_runtime/test_references_parity_refresh.py` (the real, existing test module for `preflight.references_refresh` — extended with the fold-in's red-first case via its own `_make_generate_subprocess_fake` helper, not a new `preflight/` subdirectory).
- **Sequencing/depends-on**: None — independent of IC-01–IC-04 (disjoint file set, no shared state).
- **Risks**: Must not alter `_attempt_auto_refresh`'s behavior for any OTHER step in the sequence (source-remediation, synthesize, bundle-validate) — the change is scoped exclusively to the branch immediately following `refresh_references_if_needed`'s call.

## PR Shape

**One PR for this whole mission** (the default per charter: spec-kitty carries no per-WP-PR mandate, and `spec-kitty accept` → `spec-kitty merge` assumes one mission branch / one PR). The combined compiler.py + preflight fix is not judged too large for one reviewable PR: it is now **five** small, independently-testable, mostly-disjoint changes — IC-04 as the leading FR-005 ATDD commit; WP-CORE-TESTS as a second, dedicated red-first commit pinning invariants I1–I5 per the ATDD-First Discipline section's invariant-mapping table above (the `MISSING_ARTIFACT` whole-kind case, the `graph.unresolved`-through-shared-helper case, and the graph-load-failure loud-diagnostic case, bundled together and justified there); WP02 (IC-01/IC-02) as **four** logically-scoped implementation commits (T007+T008, T009+T010, T011 alone, T012+T013 — see `tasks/WP02-compiler-fix.md`'s "Commits" section) that together turn WP01's two red-first commits GREEN, with **no internal red-first commit of its own** (WP02 authors no new failing test — it turns WP01's already-landed red tests green); WP03 (IC-03) as **two** commits (T016's red-first assertion committed alone, then T014+T015's implementation together, turning it GREEN); WP04/WP-AUTOREFRESH (IC-05) as **two** commits (T019's red-first test committed alone, then T017+T018's implementation together, turning it GREEN) — totalling **ten** commits across the mission (WP01: 2, WP02: 4, WP03: 2, WP04: 2), well under the scale that would warrant a split (closes PLAN-FRESH4-004, which found the prose's prior "six" count did not match its own five-item enumeration), and splitting the preflight fold-in into a separate PR would require re-litigating the "fold vs. defer" operator decision as a second review cycle for no material review-burden reduction. Default (one PR) applies; no split recommended.
