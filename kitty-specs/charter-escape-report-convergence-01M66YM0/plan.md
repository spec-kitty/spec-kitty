# Implementation Plan: Charter escape-report convergence

**Branch**: `issue-6733-charter-escape-report-convergence` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/charter-escape-report-convergence-01M66YM0/spec.md`
**Input**: Mission specification from `kitty-specs/charter-escape-report-convergence-01M66YM0/spec.md`

## Summary

Three commands answer "is this org pack sound?" three different ways. `doctor charter-packs`
reports an authored fragment `body_path` that escapes its pack root
(`ORG_FRAGMENT_BODY_PATH_ESCAPE`) and an org asset sidecar `path` that escapes its `assets/` root
(`ORG_ASSET_PATH_ESCAPE`) and exits non-zero. `charter status --json` reports neither
(`org_layer.errors: []`) and `charter org validate` misses the `body_path` half.

The fix routes both surfaces through the containment predicates #6418 already built
(`find_body_path_escapes`, `find_asset_path_escapes` and their registry-aware wrappers), each into
the channel that surface already owns — status's `org_layer.errors`, the validator's structured
`ValidationIssue` list — and adds one portable case table that asserts all three surfaces agree, so
the replacement offering inherits the rule as data.

Nothing is re-derived: no new containment implementation, no new command, no change to
`doctor charter-packs`' output, and no new key in `charter status --json` (NFR-003).

## Technical Context

**Language/Version**: Python 3.11+ (repo requires `>=3.11`; runtime here is CPython 3.11)
**Primary Dependencies**: `typer` (CLI), `rich` (console), `ruamel.yaml` (YAML), `pydantic` (pack schemas) — all already installed; no new dependency
**Storage**: files only (`.kittify/config.yaml`, the org pack's `pack.yaml` / `drg/fragment.yaml` / `assets/*.asset.yaml`); nothing new is persisted
**Testing**: pytest, targeted modules only (`tests/specify_cli/cli/commands/charter/`, `tests/charter/packs/`, `tests/charter/conformance/`), plus `uv run mypy --strict` on the touched modules; no full-suite sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: the Spec Kitty CLI on Linux, macOS and Windows 10+ (no platform-specific code; containment is the existing cross-platform primitive)
**Project Type**: single project — one CLI/library wheel with `src/charter/**` (offering) and `src/specify_cli/**` (runtime)
**Performance Goals**: the added checks reuse the fragments each surface already loaded — zero new graph loads, subprocesses or filesystem reads, one extra linear pass per pack (NFR-004, verified structurally: a wall-clock threshold would be flaky in a fast unit tier)
**Constraints**: no file reads of declared targets (NFR-002); `charter status --json` schema unchanged (NFR-003); `doctor charter-packs` codes and keys unchanged; `charter.offering.api` untouched (C-003)
**Scale/Scope**: 3 org packs × N authored nodes and M asset sidecars per pack: one linear pass per pack, same as `doctor charter-packs` today

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan honours it |
| --- | --- |
| Governing principle — single canonical authority; `DIRECTIVE_044` | The containment verdict has one authority (the offering predicates). Both new call sites import it; neither restates the rule. |
| `DIRECTIVE_001` architectural integrity; layer chain `kernel <- charter <- specify_cli` | `charter status` (runtime) calls the charter-layer wrapper `charter.activation.drg_activation.find_org_*`; the validator is charter-layer and calls the offering predicates directly. No new layer edge is introduced. |
| Standing Order #4 / `DIRECTIVE_034` ATDD red-first, through the pre-existing entry point | Each surface's test drives the real CLI command and is red before the fix (recorded in the PR body). |
| Standing Order #5 `DIRECTIVE_043` — close defect classes by construction, non-vacuously | The convergence is closed by one corpus that asserts all three surfaces per pack shape, with an escaping case and a contained case on the same fixture builder (no gate that only ever passes). |
| Standing Order #6 `DIRECTIVE_044` canonical sources | `/spec-kitty` templates and the shipped corpus style are used as-is; no structure copied from an older mission. |
| `RECONCILE_CHANGE_SCOPE_TENSIONS` | Smallest viable file set: two production files changed, no new production module. The corpus is test data + a runner. Opportunistic cleanup is limited to the docstrings the change makes stale. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Targeted test files and the owning module's fast tier only; CI owns the full sweep. |
| ATDD-First Discipline (charter C-011) | The red test is the first commit of the branch, before the production change. |
| Pre-existing Failure Reporting Rule | Any unrelated red is reproduced on pristine `origin/main` in a clean worktree, then cited or filed — never skipped. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-escape-report-convergence-01M66YM0/
├── plan.md              # This file
├── research.md          # Discovery + Phase 0 grounding (D1–D6)
├── spec.md              # Mission specification
└── tasks/               # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/
├── charter/                                  # charter layer (offering + activation)
│   └── offering/
│       ├── packs/pack_validator.py           # CHANGED: body_path leg on `charter org validate`
│       ├── drg/org_pack_loader.py            # unchanged: find_body_path_escapes (authority)
│       └── assets/repository.py              # unchanged: find_asset_path_escapes (authority)
└── specify_cli/                              # runtime layer (CLI)
    └── cli/commands/charter/
        └── _status_collectors.py             # CHANGED: escape findings on org_layer.errors

tests/
├── specify_cli/cli/commands/charter/
│   └── test_status_org_layer_path_escapes.py # NEW: status surface, red-first
├── charter/packs/
│   └── test_pack_validator_body_path_escape.py  # NEW: validate surface, red-first
└── charter/conformance/
    ├── pack_containment_cases.yaml           # NEW: portable case table (rule as data)
    └── test_pack_containment_conformance.py  # NEW: runner, three adapters
```

**Structure Decision**: the repository is a single Python project with the enforced layer chain
`kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`. The two production
changes sit in the layer that already owns each surface (validator → `charter.offering.packs`,
status → `specify_cli.cli.commands.charter`), and both consume the charter-layer predicate rather
than introducing a new module.

## Design

### D-1 — `charter status --json`: findings on the existing channel

`src/specify_cli/cli/commands/charter/_status_collectors.py::_collect_org_layer_status` gains two
helpers that mirror `doctor charter-packs`' `_record_*_escapes`, called immediately after the
fragments load and **before** `merge_three_layers`:

- `find_org_body_path_escapes(repo_root, fragments)` → each `BodyPathEscape.message` appended to
  `result["errors"]`;
- `find_org_asset_path_escapes(repo_root, fragments)` → each `AssetPathEscape.message` appended to
  `result["errors"]`.

Both wrap the call in `try/except Exception` and, on failure, append
`"org-layer body_path check failed: …"` / `"org-layer asset path check failed: …"` — a check that
could not run is not a check that passed (FR-003). Placement before the merge means a refused merge
(`OrgDRGConflictError`) cannot hide the findings; the existing merge/completeness error handling is
unchanged. No new key: the collector's own docstring already ratchets against unread payload slots,
and `status` renders every `errors` entry, so the human view follows for free.

### D-2 — `charter org validate`: a `body_path_escape` finding

`src/charter/offering/packs/pack_validator.py`:

- add `body_path_escape` to the documented `ValidationIssue.category` vocabulary;
- in `validate_pack`, after `org_fragment, org_errors = _validate_org_fragment(pack_dir)` succeeds,
  run a new `_validate_fragment_body_paths(pack_dir, org_fragment)` leg that calls
  `find_body_path_escapes(fragment, pack_dir)` — the same predicate `doctor` uses — and returns one
  `ValidationIssue(severity="error", artifact_type="drg", artifact_id=<node id>,
  file=str(pack_drg_fragment(pack_dir)), message=<escape.message>, category="body_path_escape")` per
  escape. The predicate is imported lazily (module convention: heavy charter offering imports stay
  lazy so `--help` stays snappy).
- Ordering: the new leg runs next to the existing asset leg, so both halves report in one run and
  neither can hide the other (FR-004 acceptance 3). An empty `body_path` and discovered nodes are
  already excluded by the predicate.
- `charter org validate` renders every `ValidationIssue` and exits non-zero on errors, so no CLI
  change is needed.

### D-3 — The conformance case table

`tests/charter/conformance/pack_containment_cases.yaml` (`schema: pack-containment-conformance/1`)
holds plain-data cases: a pack shape (`node_body_path`, `asset_path`) plus the expected finding per
surface. `tests/charter/conformance/test_pack_containment_conformance.py` holds three adapters that
call the production entry points:

- **doctor** — `specify_cli.cli.commands.doctor._collect_org_layer_data` (the command's real
  collector), reading `body_path_escapes` / `asset_path_escapes` codes and `errors`;
- **status** — `specify_cli.cli.commands.charter._collect_org_layer_status`, reading `errors`;
- **validate** — the `charter org validate` CLI through `CliRunner`, reading issue categories and
  the exit code.

Cases: `escaping-body-path`, `escaping-asset-path`, `both-escapes`, `contained` (the paired positive
control). Each case asserts all three surfaces, so the table is both the red-first convergence test
and the inheritable statement of the rule (FR-005, SC-001..SC-004).

### D-4 — Docs and changelog

- `docs/api/charter-commands.md`: document the status behaviour and the new validator category beside
  the existing #6418 documentation of the doctor keys and codes.
- `docs/changelog/CHANGELOG.md` `[Unreleased]`: one entry, impact-first, `(#6733)`.
- Promise index `tests/scenarios/charter/PROMISES.md` row `PR-CHARTER-SHARING-004`: extend the
  authority column to name all three surfaces (no scenario change: the Act drives the doctor and the
  promise is about the verdict, not the command).

## Complexity Tracking

No charter violations. No entry.

## Implementation Concern Map

### IC-01 — Status surface converges on the shared predicate

- **Purpose**: stop `charter status --json` handing out `org_layer.errors: []` for a pack whose paths escape their roots.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-003, C-001
- **Affected surfaces**: `src/specify_cli/cli/commands/charter/_status_collectors.py`
- **Sequencing/depends-on**: none
- **Risks**: the registry-aware wrapper raises `KeyError` for an unregistered pack (`_org_pack_roots_by_name`) — the helper must catch it as "the check could not run" and never crash `status`. Covered by a test.

### IC-02 — Validator gains the fragment half

- **Purpose**: `charter org validate` refuses an authored `body_path` that escapes its pack root, with a stable category, matching its existing asset-sidecar finding.
- **Relevant requirements**: FR-004, NFR-001, NFR-002, C-002
- **Affected surfaces**: `src/charter/offering/packs/pack_validator.py`
- **Sequencing/depends-on**: none
- **Risks**: the finding must not fire for discovered (validator-owned) nodes or an empty `body_path`; the predicate already enforces both, so the leg must pass the *loaded* fragment (never a re-validated copy) and `pack_dir` as the root.

### IC-03 — Portable case table and its runner

- **Purpose**: state the containment rule as data, and prove the three surfaces agree on every pack shape.
- **Relevant requirements**: FR-005, FR-006, SC-001..SC-004
- **Affected surfaces**: `tests/charter/conformance/pack_containment_cases.yaml`, `tests/charter/conformance/test_pack_containment_conformance.py`
- **Sequencing/depends-on**: IC-01 and IC-02 for a green run (the table is written first and is red until both land — that is the red-first proof)
- **Risks**: the runner must drive production entry points, not helpers; a case whose `expect` names a surface field the adapter does not observe must fail (the same "unknown expect key" discipline the activation corpus runner uses).

### IC-04 — Docs, changelog and promise index

- **Purpose**: the user-facing surfaces tell the same story as the code.
- **Relevant requirements**: C-004, SC-004
- **Affected surfaces**: `docs/api/charter-commands.md`, `docs/changelog/CHANGELOG.md`, `tests/scenarios/charter/PROMISES.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: the docs index/freshness gates must stay green (`check_docs_freshness --ci`, `test_no_legacy_terminology.py`).

## Test Strategy

| Surface | Test | Red proof |
| --- | --- | --- |
| status (body_path) | `test_status_org_layer_path_escapes.py::test_status_reports_an_escaping_body_path` | `org_layer.errors == []` on `main` |
| status (asset) | `::test_status_reports_an_escaping_asset_path` | `org_layer.errors == []` on `main` |
| status (clean / no false positive) | `::test_contained_pack_is_clean` | passes before and after (positive control) |
| status (check cannot run) | `::test_crashed_check_is_reported_not_silent` | n/a — new behaviour |
| validate (body_path) | `test_pack_validator_body_path_escape.py::test_validate_reports_an_escaping_body_path` | no `body_path_escape` on `main`; CLI exit 0 |
| validate (clean) | `::test_contained_body_path_is_not_a_finding` | passes before and after (positive control) |
| all three | `test_pack_containment_conformance.py` (4 cases × 3 adapters) | 2 of 3 surfaces fail on `main` |

Commands:

```bash
uv run pytest tests/specify_cli/cli/commands/charter/test_status_org_layer_path_escapes.py \
  tests/charter/packs/test_pack_validator_body_path_escape.py \
  tests/charter/conformance/test_pack_containment_conformance.py -q
uv run pytest tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py \
  tests/charter_offering/drg/test_org_body_path_escapes.py \
  tests/charter_offering/assets/test_org_asset_path_escapes.py \
  tests/specify_cli/cli/commands/charter/test_status_org_layer_completeness.py -q
uv run mypy --strict src/charter/offering/packs/pack_validator.py \
  src/specify_cli/cli/commands/charter/_status_collectors.py
```

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| `status` starts reporting a fault for a pack that is actually fine | the contained case in the corpus and the clean test are on the same fixture builder as the escaping case (SC-003) |
| a broken registry turns `charter status` into a traceback | the helper catches and reports "check could not run" (FR-003) |
| drift returns after this Mission | the rule is a portable table, not three command behaviours (FR-005) |
| validator message diverges from doctor's | the validator prints the predicate's own `message`; no re-derivation |
