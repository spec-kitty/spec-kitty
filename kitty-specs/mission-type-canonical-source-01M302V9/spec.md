# Mission Specification: Single canonical mission-type source (#3831 #4088)

**Mission Branch**: `fix/mission-type-canonical-source-3831`
**Created**: 2026-09-20
**Status**: Draft
**Input**: GitHub issues #3831 (org-tier custom mission type invisible to the mission loader, silently replaced by software-dev) and #4088 (`.kittify/overrides/missions/` override tier never consulted) — the same `specify_cli/mission.py::_mission_path_by_name` org-blind loader defect.

## Context & Problem

Spec Kitty resolves a mission's *type* through **three** independent registries that disagree:

1. **Legacy template loader** — `src/specify_cli/mission.py` loads a `Mission` from a directory containing `mission.yaml` via `_mission_path_by_name`, consulting only two tiers (`.kittify/missions/<name>`, then packaged built-ins). It is **org-blind** and bypasses the six-tier resolver (`src/specify_cli/runtime/resolver.py`) that the *command-template* lookup (`Mission.get_command_template` → `resolve_command`) already uses.
2. **Org-tier governance resolver** — `charter.activation.mission_type_profiles.resolve_mission_type_context` (+ `MissionTypeRepository`, `resolve_org_dirs`), which *is* org-aware.
3. **`mission-runtime.yaml` resolver** — `runtime/next/runtime_bridge_io.py`, org-aware, owns the runtime step-DAG.

Because (1) never consults the org tier, an org-pack-activated custom mission type falls through `_mission_path_by_name`, `get_mission_for_feature` swallows the `MissionNotFoundError`, and the mission is loaded as **software-dev** — carrying software-dev's path conventions and required/optional artifact sets. Since #3836 this is a *warn-and-substitute* (the `warnings.warn` at `mission.py:804` is CLI-visible), but the wrong-type load itself is unchanged. #4088 is the same function failing to consult a project override for a mission type.

**Resolution:** converge mission-type loading onto the single canonical charter `ResolvedMissionType` source and **retire** the `specify_cli/mission.py` `Mission`/`MissionConfig`/`mission.yaml` resolver. This is the #2652 "single canonical mission-type source" slice.

**Scope boundary (two distinct fallbacks — do not conflate):**
- `mission.py:783` **typeless coalesce** (`meta.json` records *no* type → software-dev *template*): **PRESERVED** here (C-006/FR-003a). Removing it is **#2660**, sequenced later.
- `mission.py:801-806` **typed-but-unknown** `except MissionNotFoundError` warn-and-substitute: **IN SCOPE** — this *is* the #3831 defect (an org-tier type is "unknown" only because the loader is org-blind). Routing through the charter source makes a real type resolve and a genuinely-unknown type surface visibly. This is a consequence of FR-003 resolver-retirement, distinct from #2660's `:783` removal.

## Re-scope (2026-09-21, operator decision)

WP03 discovered that the charter/doctrine tier does **not** carry built-in path/artifact data equivalent to legacy `mission.yaml`, and the two encode *different concerns*: legacy `artifacts.required/.optional` is **template-selection**; charter `expected_artifacts.required_by_step` is **runtime step-gate completeness**. `path_conventions` is unpopulated (`null`) for all built-ins, and the token sets diverge materially. Therefore "retire the resolver and converge everything onto charter" is the **full #2652 epic** (a two-concern merge + canonical built-in-data authoring), not this slice.

**This mission is re-scoped to the targeted, behavior-safe fix** (the fix #3831's author originally proposed): extend the loader to resolve through the org-aware tiers (override → project → org → packaged), building a `Mission` for an org-tier type from its sparse `mission_types/<type>.yaml` with **neutral own conventions (not software-dev's)**; consult the `.kittify/overrides/missions/` override tier **live**. Built-ins keep their existing legacy path (NFR-001 safe). The `path_conventions` slot (WP02) is retained so org types *can* declare conventions. Full convergence + built-in-data reconciliation is deferred to **#2652**.

Superseded by this re-scope: **FR-005, FR-006** (no built-in consumer rewire / field retirement) and **FR-008 / SC-006** (no migration — override consulted live). See tracer-design-decisions D10.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Org-tier custom mission type loads as itself, not software-dev (Priority: P1)

An operator on a consumer project activates a custom mission type via an org-tier doctrine pack (`.kittify/config.yaml` → `doctrine.org.packs`) and has no `.kittify/missions/` directory. When any command loads the `Mission` for a feature of that type, it must resolve the **actual configured type** — its own conventions and artifact expectations — not software-dev's.

**Why this priority**: This is the core defect (#3831). A silent substitution validates a mission against the wrong conventions with no reliable operator signal.

**Independent Test**: On a fixture consumer project with an org-activated custom type and no `.kittify/missions/`, `get_mission_for_feature(feature_dir)` returns a mission whose identity, path conventions, and artifact expectations match the custom type — verified against a red repro that currently returns `Software Dev Kitty`.

**Acceptance Scenarios**:

1. **Given** an org-activated custom mission type and a feature whose `meta.json` records that type, **When** the mission is loaded, **Then** the loaded mission's identity and expected artifacts are the custom type's, and no software-dev substitution occurs.
2. **Given** the same project, **When** `spec-kitty accept` runs against that feature, **Then** the accept gate evaluates the custom type's artifact/convention set, not software-dev's `data-model.md`/`quickstart.md`/`src/`+`tests/`.

---

### User Story 2 - Project override tier is consulted (Priority: P1)

A project ships a mission-type override under `.kittify/overrides/missions/<type>/`. Loading that type must consult the override tier (the OVERRIDE tier of the canonical six-tier chain), not skip straight past it.

**Why this priority**: #4088 — same root-cause function; without it, project overrides are silently ineffective.

**Independent Test**: A fixture with a `.kittify/overrides/missions/<type>/` entry resolves to the override, verified by a red repro that currently ignores it.

**Acceptance Scenarios**:

1. **Given** a `.kittify/overrides/missions/<type>` override, **When** the type is resolved, **Then** the override tier wins per the canonical precedence (OVERRIDE → LEGACY → ORG → GLOBAL_MISSION → GLOBAL → PACKAGE).

---

### User Story 3 - Path conventions survive the convergence (Priority: P2)

The path-convention accept check must keep working for mission types that declare conventions, and must no-op (not apply software-dev's `src/`/`tests/`) for types that declare none.

**Why this priority**: `paths` is the *only* legacy field with no org-tier home; the accept-blocking path check (ADR 2026-08-28-1) depends on it. It must migrate to a real doctrine home rather than being lost.

**Independent Test**: A custom type declaring `path_conventions` is enforced; a type declaring none produces a no-op (not a software-dev-shaped verdict).

**Acceptance Scenarios**:

1. **Given** a mission type with a declared `path_conventions` slot, **When** `evaluate_path_conventions` runs, **Then** it evaluates that type's conventions.
2. **Given** a mission type with no path conventions, **When** the same check runs, **Then** it no-ops rather than applying software-dev's layout.

---

### User Story 4 - Typeless legacy missions still load (Priority: P2)

A pre-mission-type (typeless) feature must continue to load via the software-dev **template** default, with no spurious "not found" warning.

**Why this priority**: Backward compatibility (C-006 / FR-003a). Removing the typeless→software-dev default is #2660's job, sequenced *after* this mission; this mission must preserve it.

**Independent Test**: A typeless feature loads the software-dev template and emits no warning.

**Acceptance Scenarios**:

1. **Given** a feature whose `meta.json` records no mission type, **When** loaded, **Then** it loads the software-dev template with no warning.
2. **Given** a feature whose `meta.json` records a *typed-but-unknown* mission type, **When** loaded, **Then** the failure is surfaced visibly (CLI/JSON), never warn-and-substituted to software-dev.

---

### User Story 5 - Consumer projects migrate cleanly (Priority: P2)

Consumer projects with legacy `.kittify/missions/<type>/mission.yaml` overrides get an automatic, audited migration so nothing breaks when the legacy resolver and tree are retired.

**Why this priority**: The legacy tree is deleted later (#2661); a mandatory migration + audit prevents silent breakage of existing consumer overrides.

**Independent Test**: `spec-kitty upgrade` on a project carrying a legacy `mission.yaml` override migrates `paths` → the `path_conventions` slot and templates → template dirs; `spec-kitty doctor` reports the migration state.

**Acceptance Scenarios**:

1. **Given** a legacy `.kittify/missions/<type>/mission.yaml`, **When** `spec-kitty upgrade` runs, **Then** its `paths` and templates are relocated to their new homes and a doctor audit records the result.

### Edge Cases

- A typed-but-unknown mission type (org pack not activated / typo): must surface a visible error, never a warn-and-substitute software-dev load.
- A legacy `mission.yaml` carrying now-retired fields (`domain`, `version`, `validation`, `mcp_tools`, …): migration must not fail on them; they are dropped with an audit note.
- `artifacts.required/.optional` on a legacy override vs the org tier's per-step `required_by_step`: migration must preserve required + optional + blocking semantics with no loss.
- Built-in types (`software-dev`, `research`, `documentation`) must resolve byte-for-byte the same expected-artifact and convention sets after convergence.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Org-aware mission loading | As an operator, I want the `Mission` for a feature to resolve through the canonical charter `ResolvedMissionType` source so an org-tier custom type loads as itself, not software-dev. | High | Open |
| FR-002 | Honour project mission-type overrides (#4088) | As a project owner, I want `.kittify/overrides/missions/<type>/` consulted **live** by the loader (the override tier of the org-aware resolution chain that command-templates already use), so a project override takes effect without migration. | High | Open |
| FR-003 | Org-aware loader (extend, not retire) | As a maintainer, I want `_mission_path_by_name`/`get_mission_by_name`/`get_mission_for_feature` extended to resolve org-tier custom types (building a `Mission` from the sparse `mission_types/<type>.yaml` with neutral own conventions) and the override tier. The legacy resolver is **not** retired here — full convergence is deferred to #2652 (see Re-scope). | High | Open |
| FR-004 | `path_conventions` doctrine slot | As a mission-type author, I want a `path_conventions` slot on the mission-type doctrine artifact, with `VALID_PATH_KEYS` relocated into `charter`. | High | Done (WP02) |
| FR-005 | Migrate artifact expectations | SUPERSEDED by the 2026-09-21 re-scope — the charter manifest and legacy artifacts encode different concerns; convergence deferred to #2652. | High | Superseded |
| FR-006 | Retire vestigial legacy fields | SUPERSEDED by the 2026-09-21 re-scope — no built-in field retirement / display rewire in this slice; deferred to #2652. | Medium | Superseded |
| FR-007 | Preserve typeless default; correct typed-unknown | As an operator, I want typeless features to keep loading the software-dev template with no warning (C-006/FR-003a — #2660 removes this later), while a **typed** mission type resolves through the org-aware loader and a genuinely-unknown typed value surfaces visibly (never warn-and-substitute). The typed-unknown correction is the #3831 fix, not #2660. | High | Open |
| FR-008 | Consumer migration + audit | SUPERSEDED by the 2026-09-21 re-scope — #4088's override tier is consulted live (no migration). | Medium | Superseded |
| FR-009 | Decision record | As a maintainer, I want an ADR recording "org-aware mission-type loader + `path_conventions` doctrine slot; the two-concern data divergence between legacy `mission.yaml` and charter `expected_artifacts`; full convergence deferred to #2652." | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No built-in regression | The three built-in types (software-dev, research, documentation) resolve identical expected-artifact and convention sets before/after; accept + dossier golden shards remain green. | Reliability | High | Open |
| NFR-002 | Layer discipline | Canonical source lives in `charter`; `specify_cli` depends on `charter` only (C-001 forbids reverse); no routing via `mission_runtime` (shrink-only ledger). Enforced by `tests/architectural/test_layer_rules.py`. | Architecture | High | Open |
| NFR-003 | Code quality gates | New/changed functions ≤15 cyclomatic complexity; every new branch/helper carries a focused test in the same commit (Sonar new-code gate); ruff + mypy clean, no new suppressions. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Scope lock | Resolve #3831 + #4088 only. Preserve the **typeless→software-dev _template_ default** (`mission.py:783`, C-006/FR-003a) — its removal is #2660. In scope (intrinsic to #3831 via FR-003): correcting the **typed-but-unknown** path (`mission.py:801-806`). Do NOT delete the legacy tree (#2661). | Technical | High | Open |
| C-002 | Name the `routing` sense | This mission touches the *placement* sense of mission-type routing (artifact-placement seam), distinct from #3830's dispatch/profile routing. Name the sense in code/docs. | Technical | Medium | Open |
| C-003 | Single canonical authority | Reconcile onto the existing charter `ResolvedMissionType` — do not introduce a second mission-type authority or a parity shim. | Technical | High | Open |

### Key Entities

- **`ResolvedMissionType`** (charter): the canonical bundle unifying expected-artifacts, template-set, governance, action-sequence, step-contracts — org-aware via `existing_mission_types()`. The convergence target.
- **`MissionType` / `MissionTypeProfile`** (charter/offering): the org-tier mission-type model (schema_version, id, display_name, extends, action_sequence).
- **`path_conventions`** (new doctrine slot): the migrated home for legacy `paths`; `VALID_PATH_KEYS` moves into charter.
- **`ExpectedArtifactManifest` / dossier `ManifestRegistry`**: the org-aware home for required/optional/blocking artifact expectations.
- **Legacy `Mission` / `MissionConfig` / `mission.yaml`** (`specify_cli/mission.py`): the retired resolver.

## Consumer census & brownfield seam notes *(informative — from post-spec squad)*

Retiring surface in `specify_cli/mission.py`: `_packaged_missions_dir:73`, `_mission_path_by_name:81` (the org-blind defect), `list_available_missions:496`, `get_mission_by_name:519`, `get_mission_for_feature:759` (fallback `warnings.warn:804`), `discover_missions:809`. **Keep `get_mission_type:562` — already charter-clean.**

External consumers to rewire onto charter `ResolvedMissionType` / dossier `ManifestRegistry`:

| file:line | reads | canonical replacement |
|---|---|---|
| `core/worktree.py:654,657,661` | `get_required_artifacts()`/`get_optional_artifacts()` (sparse-checkout inventory) | `expected_artifacts` (flat-list adapter; **lossy-collapse risk — red-first exact-token repro incl. `checklists/`**) |
| `acceptance/__init__.py:20,715-728,1295` | `get_mission_for_feature`, `_optional_artifact_tokens` | `expected_artifacts` / dossier `ManifestRegistry` |
| `acceptance/summary_core.py:165` | `mission.config.paths` (accept-blocking) | new `path_conventions` slot |
| `validators/paths.py:287` | `mission.config.paths` | new `path_conventions` slot |
| `config/path_conventions.py:20,92` | imports `VALID_PATH_KEYS` from `specify_cli.mission` | repoint to charter (2nd importer beyond `mission.py:159,191`) |
| `dashboard/handlers/features.py:109-112` | `.config.domain/.version/.description` | display-only — retire/degrade (FR-006) |
| `cli/commands/mission_type.py:82-120,195-215` | panel + **existing partial-#3831 `catch_warnings` band-aid** | rewire to charter; **replace the band-aid, do not stack** |

Notes the plan must carry:
- **Fixture-first dependency:** no org-activated-custom-type consumer-project fixture (nor `.kittify/overrides/missions/` fixture) exists under `tests/`. SC-001/SC-002 red repros are net-new; mine `tests/doctrine/` org-pack helpers (`test_org_pack_subdir.py`, `drg/test_org_pack_config_resolve_existing_org_roots.py`). This fixture WP is the dependency root.
- **`Mission` name collision:** `charter/offering/missions/models.py:137` also defines `class Mission` (schema-gen). The ADR must name both to prevent import confusion.
- **Gate-companions to fold into the commit that trips them:** `tests/architectural/test_layer_rules.py` (with the `VALID_PATH_KEYS`/path-convention relocation); dossier/accept golden shards (`tests/dossier/*`, `tests/specify_cli/acceptance/test_missing_artifacts_from_config.py`) with the artifact rewire; pack-manifest regen (`spec-kitty doctrine regenerate-graph`) with the doctrine `path_conventions` schema addition.
- **Atomic per-consumer rewire:** while both sources exist, never leave a consumer reading the legacy `Mission` after `get_mission_type` resolves via charter (typed-unknown disagreement window).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fixture consumer project with an org-activated custom mission type and no `.kittify/missions/`, the loaded `Mission` reports the custom type's identity, path conventions, and expected artifacts — never `Software Dev Kitty`. (Direct repro of #3831.)
- **SC-002**: A project mission-type override takes effect — a red repro shows the `.kittify/overrides/missions/<type>/` override ignored today; after the fix the loader consults it **live** (override tier of the resolution chain). (Resolves #4088.)
- **SC-003**: A typed-but-unknown mission type produces a visible CLI/JSON error; a typeless feature loads the software-dev template with zero warnings.
- **SC-004**: The path-convention accept check enforces a type's declared `path_conventions` and no-ops for a type declaring none.
- **SC-005**: All built-in mission-type accept/dossier golden shards and `tests/architectural/test_layer_rules.py` remain green; ruff + mypy clean.
- **SC-006**: SUPERSEDED by the 2026-09-21 re-scope (no migration — override consulted live).
