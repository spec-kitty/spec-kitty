# Implementation Plan: pack file-name collision diagnostic

**Branch**: `issue-6743-pack-file-name-collision-diagnostic` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/spec.md`
**Input**: Mission specification from `kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/spec.md`

## Summary

Add one detection query to `charter.activation.identity_index.IdentityIndex` — "which
file names stand for more than one declared id" — computed from the per-kind tables
the index already builds, and surface it in the two operator commands the issue
names: `spec-kitty charter pack validate` (pack being validated vs the built-in
layer) and `spec-kitty doctor charter-packs` (the configured project/org/built-in
chain). Both report an error; there is no opt-in. No activation behaviour changes.

## Technical Context

**Language/Version**: Python 3.11 (repository floor; `pyproject.toml` requires >=3.11)
**Primary Dependencies**: `typer`, `ruamel.yaml`, `pydantic` (existing); no new dependency is introduced
**Storage**: Filesystem only — pack directories, `.kittify/config.yaml`, `.kittify/charter-packs/` (no database)
**Testing**: `pytest` with the repository's `unit`/`fast` and `integration` markers; CLI tests drive the real commands through `typer.testing.CliRunner`
**Target Platform**: Linux/macOS developer and CI hosts (`spec-kitty` CLI)
**Project Type**: Single Python package (`src/`) with a layered `kernel` → `charter` → `specify_cli`/`runtime` import direction
**Performance Goals**: one `IdentityIndex` scan per kind per command and zero re-walks or re-parses inside the query (NFR-001); `validate packs/internal` and `doctor charter-packs` stay inside their current wall-clock envelope, before/after measured (NFR-004)
**Constraints**: `charter.offering` must not import `charter.activation` (C-002); detection lives only in `identity_index.py` (C-001); `validate` takes a bare path and may run outside a repository (C-004)
**Scale/Scope**: 4 files touched in `src/` (identity index, org-charter validation door, doctor collector, doctor renderer), 3-4 test files, one changelog entry, two doc surfaces

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan honours it |
|---|---|
| Single canonical authority | The collision set is computed once, in `IdentityIndex`; validate and doctor are two callers, and `collision_error()` (the writer refusal) reads the same per-stem declarations. No second walk, no second message table. |
| Architectural alignment / shared-package boundaries | The leg is wired at `charter.activation.org_charter.validate_pack_with_org_charter` because `charter.offering.pack_validator` may not import `charter.activation` (C-002). Doctor's leg sits in the existing `_run_*_check(report, repo_root)` collector family, not in a new module. |
| ATDD-first (DIRECTIVE_034) | Each surface gets a failing test through its real entry point (`CliRunner` on `charter_app` / `doctor_app`) before the code exists; the assertion names the id, the file name and both layers. |
| Glossary & terminology adherence | "Charter pack", "layer" (`built-in` / `org` / `project`), "declared id", "file name (stem)" are used in their `docs/context/charter.md` senses. The new finding is named `file_name_collision`, matching the recorded Decision. |
| Locality of change (DIRECTIVE_024) | Four source files, all on the existing identity/validation/doctor path. No refactor of `pack_validator`, no change to writers or migrations. |
| Tests as scaffold (DIRECTIVE_041) | New tests guard a standing invariant (a pack-content error an operator can hit) and a regression pin (same-id override stays clean). No characterisation-only tests are added. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Only the touched modules' fast tiers and the two named CLI test files are run locally; CI owns the full sweep. |

No violations: no entry in Complexity Tracking.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/
├── plan.md              # This file
├── spec.md              # Mission specification
├── research.md          # Discovery findings and decisions
├── tasks.md             # Task outline (/spec-kitty.tasks)
└── tasks/               # Work-package prompts (finalize-tasks)
```

### Source Code (repository root)

```
src/
├── charter/
│   ├── activation/
│   │   ├── identity_index.py          # NEW: FileNameCollision record + file_name_collisions() query
│   │   ├── activation_engine.py       # unchanged: ActivationIdCollisionError message/declarations
│   │   └── org_charter.py             # validate_pack_with_org_charter(): adds the collision leg
│   └── offering/packs/pack_validator.py   # unchanged: ValidationIssue/ValidationResult reused
└── specify_cli/cli/commands/
    ├── _charter_pack_collect.py       # NEW: _collect_file_name_collisions() + _run_file_name_collision_check()
    ├── _profile_health_render.py      # NEW: rendered finding section
    └── doctor.py                      # wires the leg + renderer on both output paths

tests/
├── charter/activation/
│   ├── test_identity_index.py                       # unit: the query, including the same-id control
│   └── test_file_name_collision_diagnostic_6743.py  # NEW: agreement with the writer refusal (FR-005)
├── charter/packs/test_org_charter_hooks.py          # validate door carries the leg
└── specify_cli/cli/commands/
    ├── charter/test_charter_pack_tooling.py         # CLI: validate exit 1 + --json payload
    └── test_doctor_charter_packs_file_name_collision.py  # NEW: doctor text/JSON/RC + chain case
```

**Structure Decision**: existing layered package; no new module and no new package
boundary. The only new source symbols are `FileNameCollision` /
`IdentityIndex.file_name_collisions()` (charter.activation) and the doctor
collector/renderer pair that follows the established `_run_*_check` pattern in
`_charter_pack_collect.py`.

## Phase 0 — Research (already captured)

`research.md` records the reproduction, the six decisions (detection in
`IdentityIndex`; error severity with no opt-in; validate scope = pack + built-in;
validate wiring at the org-charter door; doctor wiring as a `_run_*_check` leg;
one shared message builder) and the evidence files. No open questions block
planning.

## Phase 1 — Design

### DD-1 — Detection record and query (FR-001, FR-004, NFR-001, NFR-002)

`identity_index.py` gains:

```python
@dataclass(frozen=True)
class FileNameCollision:
    kind: ArtifactKind
    file_name: str                                   # the activation stem
    declarations: tuple[tuple[str, str, Path | None], ...]  # (layer, declared id, path), precedence order

    @property
    def sort_key(self) -> tuple[str, str]: ...        # (kind.value, file_name) — NFR-002
    def message(self, *, label=None) -> str: ...      # one wording, both surfaces (FR-004)
```

and `IdentityIndex.file_name_collisions(*, kinds: Sequence[ArtifactKind] | None = None) -> tuple[FileNameCollision, ...]`,
which walks the already-memoised `_table(kind)` entries and yields a record for
every stem whose entries carry **more than one distinct declared id**, sorted by
`sort_key`. It performs no scan of its own: each command pays one `IdentityIndex`
scan per kind (the shared cost every reader of that index pays) and the query adds
zero further globs and zero further YAML reads on top of it (NFR-001, asserted
with a scan-counting spy). `collision_error()`
is refactored to build its declarations list through the same private helper the
query uses, so the writer refusal and the diagnostic cannot disagree (FR-005).

`message()` takes an optional per-path label override so `validate` can call a
pack-under-validation file by its *declared* level (`pack.yaml → pack_level`)
while doctor uses the index's chain layers (`project` / `org` / `built-in`).
Rename advice mirrors `ActivationIdCollisionError`: name the non-built-in files
when a built-in file participates, else "rename one of them".

### DD-2 — Validate leg (FR-002, FR-006, C-002, C-004)

`charter/activation/org_charter.py::validate_pack_with_org_charter` runs
`validate_pack(...)` as today, then builds
`IdentityIndex(org_roots=[pack_dir], project_root=None, offering_root=resolve_offering_root())`
— the pack under validation plus the built-in layer, and nothing from the
current repository's config (C-004). Each `FileNameCollision` whose declarations
include a file under `pack_dir` becomes an error `ValidationIssue` with
`artifact_type = kind.plural`, `artifact_id = None`, `file = <the pack file>`,
`category = "file_name_collision"`. `render_validation_result` and the `--json`
shape need no change (FR-007). A collision that involves only built-in files
(no file under `pack_dir`) is still reported, attributed to the built-in file,
because it is equally a pack-content error in the validated tree.

### DD-3 — Doctor leg (FR-003, FR-007, NFR-003)

`_charter_pack_collect.py` gains `_run_file_name_collision_check(report, repo_root)`,
called from `charter_packs` **before** `exit_code` is derived, mirroring
`_run_cross_grain_check`:

* builds `IdentityIndex.build(repo_root)` (chain via `resolve_pack_chain(strict=False)`,
  project pack root, built-in offering root) and queries `file_name_collisions()`;
* always writes the structured list to `org_drg["file_name_collisions"]`
  (present-and-empty on a clean tree, so "checked, nothing found" is
  distinguishable from "not checked");
* when non-empty, appends one message to `org_drg["errors"]`, which
  `CharterPackHealthReport.healthy` already reads → RC=1;
* catches every exception and records it as an `org_drg["errors"]` entry
  (NFR-003: a collector that could not run is never a silent pass).

`_profile_health_render.py` gains a renderer for the human path; `doctor.py`
calls it beside `_render_cross_grain_findings` on the no-packs and normal paths.

### DD-4 — Test plan (ATDD, red first)

1. `tests/charter/activation/test_identity_index.py`: query returns the collision
   for the org-vs-built-in directive fixture, returns nothing for a same-id
   override on the same fixture, and returns nothing for a disjoint pack.
   (Written first; fails because the method does not exist.)
2. `tests/charter/activation/test_file_name_collision_diagnostic_6743.py`:
   FR-005 agreement — `FileNameCollision.declarations` equals
   `ActivationIdCollisionError.declarations` on one fixture.
3. `tests/charter/packs/test_org_charter_hooks.py`: the validate door reports the
   collision as an error and stays clean for the control fixture.
4. `tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py`: the
   real `charter pack validate` command exits 1, names the file and both ids, and
   carries `category: file_name_collision` in `--json`.
5. `tests/specify_cli/cli/commands/test_doctor_charter_packs_file_name_collision.py`:
   org-vs-project chain case in text and `--json`, RC=1, plus the no-collision
   control on the same fixture family.

Red-first order: 1 and 4 first (the two user-facing surfaces), then 2, 3, 5.

### DD-5 — Docs and changelog

* `docs/changelog/CHANGELOG.md` `[Unreleased]`: one entry, bold impact-first lead
  with `(#6743)`, before/after.
* `docs/api/charter-commands.md`: `charter pack validate` gains the new category.
* `docs/api/cli-commands.md`: the `doctor charter-packs` section documents
  `org_drg.file_name_collisions`.
* `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`: one paragraph
  in the validate step ("a file name is taken; rename it").

## Complexity Tracking

No Charter Check violations — nothing to justify.

## Implementation Concern Map

### IC-01 — Identity query and one message (charter.activation)

- **Purpose**: make "which file names stand for more than one declared id" a first-class, shared answer derived from the index's own tables.
- **Relevant requirements**: FR-001, FR-004, FR-005, NFR-001, NFR-002
- **Affected surfaces**: `src/charter/activation/identity_index.py`, `src/charter/activation/activation_engine.py` (read-only reuse)
- **Sequencing/depends-on**: none — everything else consumes it
- **Risks**: the query must not materialise kinds it was not asked for in a way that adds scans; `collision_error()` must keep its exact current message (C-005).

### IC-02 — Validate surface (charter.activation door + CLI)

- **Purpose**: a pack author sees the collision when validating the pack, with the pack's own file named as the thing to rename.
- **Relevant requirements**: FR-002, FR-006, FR-007, C-002, C-004
- **Affected surfaces**: `src/charter/activation/org_charter.py`, `src/specify_cli/cli/commands/charter/pack_tooling.py` (unchanged, verification only)
- **Sequencing/depends-on**: IC-01
- **Risks**: the pack's declared `pack_level` may be absent (advisory window) — fall back to `"org"` labelling rather than failing; a pack outside a repo must not touch repo config.

### IC-03 — Doctor surface (collector + renderer + exit code)

- **Purpose**: a colliding configured chain is never reported healthy, in text and in JSON.
- **Relevant requirements**: FR-003, FR-007, NFR-002, NFR-003
- **Affected surfaces**: `src/specify_cli/cli/commands/_charter_pack_collect.py`, `src/specify_cli/cli/commands/_profile_health_render.py`, `src/specify_cli/cli/commands/doctor.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: must not disturb the existing `Collisions:` (same-id override) section or `PackHealth`; the `_run_*_check` family order affects rendered section order.

### IC-04 — Docs, changelog, mission records

- **Purpose**: the new error is documented where an operator looks, and the mission's tracer/issue records stay current.
- **Relevant requirements**: (charter Documentation Standards; no FR)
- **Affected surfaces**: `docs/changelog/CHANGELOG.md`, `docs/api/charter-commands.md`, `docs/api/cli-commands.md`, `docs/guides/how-to/governance/create-an-org-doctrine-pack.md`, `kitty-specs/pack-file-name-collision-diagnostic-01M66YTQ/traces/`
- **Sequencing/depends-on**: IC-01..IC-03 (wording must match the shipped message)
- **Risks**: changelog conflicts with concurrent missions — keep both sides.

## Branch contract (restated)

Current branch at workflow start: `issue-6743-pack-file-name-collision-diagnostic`.
Planning/base branch for this mission: `issue-6743-pack-file-name-collision-diagnostic`.
Completed changes must merge into `issue-6743-pack-file-name-collision-diagnostic`,
and the resulting pull request targets `main` on `spec-kitty/spec-kitty`
(`branch_matches_target: true`).
