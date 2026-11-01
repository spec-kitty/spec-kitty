# Work Packages: Prose-only down-route scan-scope exemption (#6999)

**Inputs**: Design documents from `/kitty-specs/prose-only-scan-scope-exemption-01M6BTRX/`
**Prerequisites**: plan.md, spec.md, research.md, contracts/prose-only-scan-scope-exemption.md, quickstart.md

**Tests**: Red-first reproduction through the existing entry points is required by the spec (FR-004) and the charter's ATDD-First discipline; the failing reproduction stays as the regression pin.

**Organization**: Two work packages: the routing fix with its pins (WP01), and the living documentation the change requires (WP02). They are file-disjoint; WP02 depends on WP01 so the docs describe the shipped behaviour.

## Subtask Format: `Txxx Description (WPxx)`

Subtask rows are reference rows, not checkboxes; completion is recorded with
`spec-kitty agent tasks mark-status`.

## Path Conventions

- Single Python project: `scripts/`, `tests/`, `docs/`, `.github/`.

---

## Work Package WP01: Prose-only diffs keep the gates that read prose (Priority: P1)

**Goal**: A proven prose-only diff still runs every heavy-battery gate whose
declared `special_tiers.architectural.scan_scopes` entry matches it, through the
#6996 scoped-leg mechanism, while the module matrix and code shards stay
down-routed.
**Independent Test**: `uv run --frozen python -m pytest tests/ci/test_battery_scope.py tests/ci/test_ci_module_wiring.py tests/ci/test_ci_config_battery_routing.py -q` plus the reproduction in `quickstart.md` §1.
**Prompt**: `/tasks/WP01-prose-only-scan-scope-selection.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, NFR-002, NFR-003, C-001, C-002, SC-001, SC-002, SC-003, SC-004

### Included Subtasks

T001 Red-first: prove the defect through `select_battery_gates` and the real battery `if:` (a prose-only `scripts/release/extract_changelog.py` diff selects five gates yet the job is skipped)
T002 Add the `prose_only` input to `gate_selection.select_battery_gates` (declared scan-scope matches only; never the whole battery for a code group or battery code helper under a prose verdict)
T003 Thread the flag through `scripts/ci/battery_scope.py` (`decide`, `select --prose-only`, fail-safe unchanged)
T004 Wire the `prose-scan` output into the heavy-battery selection step and add the `arch_scan_scope` exemption to the battery `if:` in `.github/workflows/ci-router.yml`
T005 Pin the prose selection per leg in `tests/ci/test_battery_scope.py`, including the code-group-under-prose control and the fail-safe paths
T006 Update the #4842 goldens (`tests/ci/test_ci_module_wiring.py`, `tests/ci/test_ci_config_battery_routing.py`) to the ruling and add the planted mutation controls
T007 Run the targeted suites plus ruff/mypy on the touched Python and record the exact results

### Implementation Notes

- The content classifier `scripts/ci/prose_only.py` is unchanged; content never
  moves into the path router.
- `arch_scan_scope` is already an OR term of the battery `if:`; only the trailing
  subtraction changes, so `HEAVY_BATTERY_NON_SRC_GROUPS` and `job_gates` keep
  their member sets.
- No gate, registry row, or transcription is edited. No new job.

### Parallel Opportunities

- T002/T003 are one seam and move together; T006's golden text depends on T004's
  final `if:` shape. T005 is independent of T006 within the same WP.

### Dependencies

- None (starting package). Needs the spec/plan only.

### Risks & Mitigations

- Widening by accident: pin the negative — a prose-only diff matching no
  declared scope must keep the battery skipped.
- Silent reversion: the planted controls in T006 must fail when the exemption is
  removed.

---

## Work Package WP02: Document the exemption and record the issue verdict (Priority: P2)

**Goal**: The CI reference and the changelog describe the shipped behaviour, and
the mission's issue matrix resolves #6999.
**Independent Test**: `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` (errors=0), `uv run --frozen python -m scripts.docs.check_changelog_style`, and `spec-kitty agent issue-verdict --mission <slug> --issue "#6999" --verdict fixed ...` returning success.
**Prompt**: `/tasks/WP02-docs-changelog-and-issue-verdict.md`
**Requirement Refs**: FR-005, C-003, SC-003

### Included Subtasks

T001 Add the `docs/changelog/unreleased/6999.changed.md` fragment (impact-first lead, `(#6999)`, before/after)
T002 Update the heavy-leg table's "When" column and the prose-only paragraph in `docs/development/reference/ci-gate-mechanics.md`
T003 Record the `#6999` issue-matrix verdict (`fixed`) with the WP01 evidence ref

### Implementation Notes

- The changelog fragment is the `[Unreleased]` mechanism this repository uses;
  do not edit `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink).
- The docs wording must state the scope limit: declared scopes only (#7000 owns
  completeness).

### Parallel Opportunities

- T001 and T002 are independent pages; T003 needs the WP01 evidence to cite.

### Dependencies

- WP01 (describe shipped behaviour, cite its tests).

### Risks & Mitigations

- Docs drift: keep the wording tied to the registry field name and the
  `prose-only` output, not to a gate list that will age.
