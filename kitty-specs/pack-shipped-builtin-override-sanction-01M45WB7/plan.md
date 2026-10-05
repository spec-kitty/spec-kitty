# Implementation Plan: Pack-shipped built-in override sanction

**Branch**: `issue-replaceable-builtins-sanction` | **Date**: 2026-10-05 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/pack-shipped-builtin-override-sanction-01M45WB7/spec.md`
**Grounding**: [research/code-grounding.md](research/code-grounding.md) · Decisions: [research.md](research.md)

## Summary

An org pack ships `replaceable-builtins.yaml` at its pack root. It uses the same `{urn, reason}` grammar as the consumer allowlist. `doctor doctrine` reads that file in place, from the root of every org fragment it has already loaded. It honours an entry only for overrides contributed by that same pack, and unions the result with the consumer allowlist.

The consumer allowlist is checked first. It can revoke pack-delivered sanctions per URN or per pack.

The sanction semantics live in one place: `charter.offering.drg.override_policy`. These callers wire that single loader and pure adjudicator in, and none of them carries its own copy of the logic:
- `doctor doctrine`
- the built-in-override architectural gate
- `doctrine pack validate`
- `doctrine pack assemble`

No strict schema changes, so pre-fix CLIs ignore both the new pack file and the new consumer key.

## Technical Context

**Language/Version**: Python 3.11+.

**Primary Dependencies**: Existing only. The modules involved are:
- PyYAML (`yaml.safe_load`, already used by `override_policy`)
- `typer` / `rich` (doctor rendering)
- `charter.offering.drg.org_pack_config.resolve_relative_path_within_root` (containment)

No dependency is added, removed or upgraded, so the supply-chain section is N/A.

**Storage**: YAML files on disk. The new pack-root `replaceable-builtins.yaml`, plus an additive key in the consumer file.

**Testing**: pytest. Red-first through the real `doctor doctrine` entry point (`CliRunner` on the doctor app, plus the real CLI for the reproduction). Pure predicate tests, an architectural parity test, and validator and assembler tests.

**Target Platform**: The CLI on Linux, macOS and Windows. Paths are handled with `pathlib`, and console output is escaped (NFR-005).

**Project Type**: single (`src/charter`, `src/specify_cli`).

**Performance Goals**: One extra small-file read per configured org pack. This is asserted as a read count (NFR-001).

**Constraints**: C-001 to C-008. In particular, no widening of `extra="forbid"` models, `charter.offering` stays free of `charter.activation` and `specify_cli` imports, and merge behaviour is unchanged.

**Scale/Scope**: About 5 source files and about 8 test files. No migration.

## Charter Check

| Charter rule | Status | Notes |
|---|---|---|
| Single canonical authority | PASS | One loader and one adjudicator in `override_policy` (C-003, FR-013). The arch gate switches to it, and a parity test pins this. |
| Architectural alignment / layer rules | PASS | Pack roots arrive as a `Mapping[str, Path]` built from the `OrgDRGFragment` objects already in `charter.offering`. `test_layer_rules.py` and `test_charter_offering_does_not_import_activation.py` run as named gates. |
| ATDD-first / red-first (DIRECTIVE_034/041, C-011) | PASS | The acceptance tests SC-001 and SC-004 land as a separate commit, RED, before the wiring. The issue-pinned reproduction is marked `regression` only transitionally. |
| Tidy-first enabler (DIRECTIVE_025) | PASS | The first concern is behaviour-preserving: a generic parser seam, the merge docstring, and a characterisation pin of the untested doctor hint block. |
| Pack tiers (built-in vs internal) | PASS | No pack content changes. `packs/internal/` keeps no sanction file, so its live gate stays vacuously green. |
| Terminology canon | PASS | "Mission", never "feature". No new "doctrine pack" prose (#3732). Use "org pack" and "pack root". |
| No new size or ratchet gates | PASS | Only a parity test is added. No allowlists or baselines. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | PASS | Targeted test files plus named arch gates only. |
| `__all__` convention (`src/charter`) | PASS | New public names are added to `override_policy.__all__`, each with a `src` caller (dead-symbol gate). |

## Project Structure

### Documentation (this mission)

```
kitty-specs/pack-shipped-builtin-override-sanction-01M45WB7/
├── spec.md
├── plan.md                 # this file
├── research.md             # decisions log (Phase 0)
├── research/code-grounding.md
├── data-model.md           # entities + decision table (Phase 1)
├── contracts/
│   ├── replaceable-builtins-file.md   # consumer + pack file grammar
│   └── doctor-doctrine-json.md        # additive org_drg keys
├── quickstart.md
└── tasks/
```

### Source Code (repository root)

```
src/charter/offering/drg/override_policy.py   # parser seam, pack loader, effective policy, adjudicator, legacy probe
src/charter/offering/drg/merge.py             # docstring correction only (:1208)
src/specify_cli/cli/commands/_doctrine_collect.py  # wiring: fragments → pack roots → effective policy → org_drg keys
src/specify_cli/cli/commands/doctor.py        # render sanctioned block, legacy-template hint, generic hint, docstring
src/specify_cli/doctrine/pack_validator.py    # validate pack-root sanction (FR-014)
src/specify_cli/doctrine/pack_assembler.py    # union sanctions into assembled pack (FR-015)
tests/doctrine/drg/test_override_policy_predicates.py      # pure decision-table tests
tests/doctrine/drg/test_override_policy_pack_sanctions.py  # loader: containment, isolation, revocation parse (new)
tests/architectural/test_builtin_override_policy.py        # switch to effective loader + parity test
tests/specify_cli/cli/commands/test_doctor_override_diagnostics.py  # CLI acceptance + negatives + hints
tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py    # honest docstring re-pin
tests/specify_cli/doctrine/test_pack_validator*.py / assembler tests  # FR-014/015
docs/adr/4.x/2026-10-05-3-org-packs-ship-their-builtin-override-sanction.md
docs/guides/how-to/governance/create-an-org-doctrine-pack.md  # new section + troubleshooting
docs/changelog/CHANGELOG.md   # [Unreleased]
```

**Structure Decision**: This is a single project. All governance logic goes in `src/charter/offering/drg/override_policy.py`, and the `specify_cli` surfaces only wire it in.

## Design

### `override_policy` API (charter.offering; pure predicates plus explicit loaders)

**Tidy-first seam (behaviour-preserving):** `_parse_policy_document(data, *, source_label, allow_revocations)`.
- The existing consumer parsing moves into this function, and error messages carry `source_label`.
- The consumer loader keeps its exact messages for the consumer file, and it becomes private (`_load_consumer_policy`). Its only caller is the effective loader, because the dead-symbol gate counts every public name.

**`ReplaceableBuiltinsPolicy`** gains two defaulted fields: `revoked_urns: frozenset[str] = frozenset()` and `revoked_packs: frozenset[str] = frozenset()`. The existing `ReplaceableBuiltinsPolicy(entries=...)` constructions keep working.

**Consumer file:** the optional `revoked_pack_sanctions: [{urn: ...} | {pack: ...}]` key is parsed only for the consumer file. An entry needs exactly one of `urn` / `pack`. `reason` is an optional string. Anything else makes the file malformed.

**`load_pack_sanction(pack_name, pack_root) -> ReplaceableBuiltinsPolicy`:**
- It resolves `replaceable-builtins.yaml` through `resolve_relative_path_within_root`, so an escape is treated as malformed.
- It requires a regular file. An absent file gives an empty policy.
- On a malformed file, an `OSError`, or a `revoked_pack_sanctions` key, it raises `OverridePolicyError` naming the pack and the path.

**`EffectiveOverridePolicy`** is a frozen dataclass with these fields:
- `consumer: ReplaceableBuiltinsPolicy`
- `packs: Mapping[str, ReplaceableBuiltinsPolicy]`
- `pack_errors: tuple[str, ...]`
- `consumer_error: str | None`
- `revocation_errors: tuple[str, ...]`

**`load_effective_override_policy(repo_root, pack_roots: Mapping[str, Path]) -> EffectiveOverridePolicy`:**
- It is eager: it reads every pack.
- Errors are isolated per pack: a failing pack is excluded from `packs`, and its message goes into `pack_errors`.
- A malformed consumer file is recorded in `consumer_error`, and the consumer is treated as empty, which fails closed. An unknown `revoked_pack_sanctions.pack` is recorded in `revocation_errors`.
- A pack whose sanction path resolves to the consumer file is skipped before parsing, so that file counts for the consumer only.
- Every pack's file is read eagerly, before any check for whether there are overrides at all.

**`pack_roots_from_fragments(fragments, repo_root) -> dict[str, Path]`** maps `frag.pack_name` to `Path(frag.source_ref)`, resolved against `repo_root` when it is relative.

**`OverriddenBuiltin(urn, kind, pack)`** and **`find_overridden_builtins(merged, built_in_urns) -> list[OverriddenBuiltin]`**: here `pack` is parsed from `org:<pack>` provenance. It replaces `find_overridden_builtin_urns`, which is retired.

**`adjudicate_overrides(overrides, effective) -> OverrideAdjudication(unsanctioned, sanctioned)`:**
- It is pure and implements the spec's decision table.
- Each `SanctionedOverride` carries `(urn, kind, pack, source, reason)`, where `source` is `"consumer"` or `"pack"`.
- Each `UnsanctionedOverride.why` contains the substring `replaceable-builtins`.

**Retired:** `find_unsanctioned_overrides`. Keeping it would mean a second authority, and a dead symbol. Its tests migrate to `adjudicate_overrides`.

**`legacy_template_entries(pack_root, urns) -> dict[str, str]`** is a tolerant probe of `templates/setup/replaceable-builtins.yaml`. A malformed or escaping template gives `{}`. It is read only for URNs that are unsanctioned and owned by that pack.

### Wiring (`_doctrine_collect`)

- `_run_post_merge_org_checks` receives the loaded `fragments`.
- `_adjudicate_org_overrides(merged, built_in_urns, repo_root, *, fragments=())` keeps its call-compatible signature and its unsanctioned-list return. A sibling helper does the following:
  - writes `org_drg["sanctioned_overrides"]` (only when it is non-empty);
  - writes `org_drg["unsanctioned_overrides"]`, whose entries may carry `legacy_template: {path, reason}`;
  - writes `org_drg["pack_sanction_errors"]`;
  - appends to `errors`.
- No top-level `profile_health` key is added, so the frozen #5729 key set holds.

### Rendering (`doctor.py`)

- A "Sanctioned built-in override(s)" block lists each URN with its source and reason. It is dim and informational, and it is shown on green runs too.
- The unsanctioned block adds a per-finding legacy hint and a generic hint that names both files.
- All interpolated values pass through `rich.markup.escape`.
- The `doctor doctrine` docstring mentions pack sanctions. The golden snapshot is re-pinned honestly.

### Pack authoring

- **`validate_pack`**: when `replaceable-builtins.yaml` exists at the root, it is parsed with `load_pack_sanction`, and failures are errors with category `pack_sanction`. It also checks two more things:
  - A directive entry with an empty reason is an error.
  - An entry whose URN the pack does not override (that is, the URN is not among the pack's node ids at built-in URNs, derived from the fragment) is an advisory.
- **`assemble_pack`**: unions the input packs' sanction files (parsed with the same parser) into `<output>/replaceable-builtins.yaml`. If the same URN carries different reasons, assembly fails with a conflict, unless `force` is set, in which case the last pack wins and an advisory is emitted. No file is written when no input has one.

### Architectural gate and parity

`test_builtin_override_policy.py::test_builtin_overrides_are_sanctioned` (WP01) uses these, and merges with `project=None`, as doctor does:
- `load_effective_override_policy(_REPO_ROOT, pack_roots_from_fragments(org_fragments, _REPO_ROOT))`
- `find_overridden_builtins`
- `adjudicate_overrides`

The parity test lives in a new WP02-owned file, `tests/architectural/test_override_policy_parity.py`. It has three parts:
- An AST check that the collector uses the shared loader and adjudicator, with a synthetic non-vacuity self-test.
- A behavioural check that the collector and the gate recipe give identical verdicts on a two-pack fixture.
- An AST check that both paths call `merge_three_layers` with `project=None`.

## Complexity Tracking

No charter violations.

## Implementation Concern Map

### IC-01 — Tidy-first enabler on the governance seam

- **Purpose**: Make `override_policy` parsing source-agnostic and correct the `merge.py:1208-1211` docstring drift. This is behaviour-preserving and happens before any functional change. The doctor hint characterisation pin is part of IC-03's red-first commit.
- **Relevant requirements**: enables FR-001, FR-006, FR-010 and FR-013. Docstring correctness relates to C-005.
- **Affected surfaces**: `override_policy.py` (`_parse_policy_document`) and `merge.py` (docstring only).
- **Sequencing/depends-on**: none.
- **Risks**: The consumer error messages must stay byte-identical, because `test_drg_merge.py::TestReplaceableBuiltinsPolicy` pins them.

### IC-02 — Effective policy and decision-table adjudicator

- **Purpose**: Add the pack loader, the containment check, the per-pack isolation, the revocation parse, the provenance-aware detector, and the pure adjudicator. Switch the arch gate to them and add the parity test.
- **Relevant requirements**: FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-013, SC-005, NFR-001, NFR-002.
- **Affected surfaces**: `override_policy.py`, `tests/doctrine/drg/test_override_policy_predicates.py`, the new `tests/doctrine/drg/test_override_policy_pack_sanctions.py`, and `tests/architectural/test_builtin_override_policy.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**:
  - The dead-symbol gate needs every new `__all__` name to have a `src` caller, so the IC-03 and IC-04 callers must land in the same mission. Export only what those callers use.
  - The layer rules (pack roots come in as a mapping).

### IC-03 — Doctor wiring, rendering and acceptance

- **Purpose**: Thread fragments into the collector, emit the new `org_drg` keys, render the sanctioned, legacy-hint and generic-hint blocks with escaping, update the docstring and re-pin the golden.
- **Relevant requirements**: FR-001, FR-008, FR-009, FR-010, FR-012, NFR-005, SC-001 to SC-004.
- **Affected surfaces**: `_doctrine_collect.py`, `doctor.py`, `test_doctor_override_diagnostics.py`, `test_doctor_cli_surface_golden.py`, `docs/api/cli-commands.md` (docstring mirror, if generated).
- **Sequencing/depends-on**: IC-02. The acceptance tests (SC-001, SC-004) are committed RED first.
- **Risks**:
  - The byte-identity of the no-packs output (FR-012).
  - The frozen `profile_health` keys.
  - The JSON contract enumeration test (`tests/architectural/test_json_contract_enumeration.py`).

### IC-04 — Pack authoring surfaces (validate and assemble)

- **Purpose**: Make `doctrine pack validate` check the sanction file, and make `doctrine pack assemble` carry the union of the sanctions.
- **Relevant requirements**: FR-014, FR-015.
- **Affected surfaces**: `pack_validator.py`, `pack_assembler.py`, and their tests.
- **Sequencing/depends-on**: IC-02. It can run in parallel with IC-03.
- **Risks**:
  - Assembly rolls back on a validation failure, so the sanction must be written before `validate_pack` runs.
  - The pre-existing org-charter loss is out of scope (#5770).

### IC-05 — ADR, how-to and changelog

- **Purpose**: Record the decision and its #2594 absorption path, document authoring, migration and troubleshooting for org packs, and add the `[Unreleased]` entry.
- **Relevant requirements**: FR-011, C-007.
- **Affected surfaces**: a new ADR under `docs/adr/4.x/`, `docs/adr/4.x/index.md`, `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`, `docs/changelog/CHANGELOG.md`, and the docs retrieval index (`scripts/docs/docs_index.py --write`).
- **Sequencing/depends-on**: IC-02 (semantics settled). It can run in parallel with IC-03 and IC-04.
- **Risks**: Docs freshness and terminology gates (`scripts/docs/check_docs_freshness.py --ci`, `tests/architectural/test_no_legacy_terminology.py`).

## Targeted test surface (declared for review)

```
make test-fast
pytest tests/doctrine/drg/ tests/doctrine/test_drg_merge.py tests/charter/test_org_drg_cannot_override_shipped_invariants.py
pytest tests/specify_cli/cli/commands/test_doctor_override_diagnostics.py tests/specify_cli/test_doctor_doctrine.py \
       tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py tests/specify_cli/cli/commands/test_doctrine_collect.py \
       tests/specify_cli/cli/commands/test_doctor_doctrine_*.py tests/cli/test_doctor_doctrine_selections_snapshot.py
pytest tests/specify_cli/doctrine/  (validator / assembler / org-charter / snapshot)
pytest tests/charter/ tests/doctrine/   (owning subsystems)
pytest tests/architectural/test_builtin_override_policy.py tests/architectural/test_layer_rules.py \
       tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_no_dead_symbols.py \
       tests/architectural/test_json_contract_enumeration.py tests/architectural/test_charter_kind_vocabulary_single_authority.py \
       tests/architectural/test_no_legacy_terminology.py tests/cross_cutting/packaging/test_packaging_safety.py
ruff check <changed>; ruff format --check --force-exclude <changed>; mypy <changed src>
```
