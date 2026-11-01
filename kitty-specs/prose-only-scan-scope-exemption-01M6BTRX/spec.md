# Mission Specification: Exempt declared scan-scope matches from the prose-only down-route

**Mission Branch**: `kitty/mission-prose-only-scan-scope-exemption-01M6BTRX`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Issue #6999 (P1, `domain:ci`), follow-up from #6994 / PR #6996, carrying the operator ruling of 2026-11-01.

## Intent Summary *(confirmed)*

A pull request whose entire Python diff is proven prose-only (comments and/or
docstrings only, `scripts/ci/prose_only.py`) is down-routed off the code test
matrix and off the heavy architectural battery (#4842). That down-route is
content-blind about *what the heavy gates scan*: several heavy-battery gates read
comment and docstring text in `scripts/**`, `tests/**`, `docs/**`, `packs/**` and
other trees, and a docstring-only change is exactly the edit that can trip them.
Today such a change runs none of them, so the gates that guard prose are skipped
for prose.

#6994 / PR #6996 added the missing mechanism: every heavy gate declares the paths
it reads beyond its code scope in `.github/ci-module-registry.yml`
(`special_tiers.architectural.scan_scopes`), and a diff that touches only such
paths runs, per leg, only the gates whose scope it touches (the *scoped leg*).
The prose-only down-route was left as an interaction and filed as this issue.

**Operator ruling (2026-11-01, recorded on #6999):** exempt declared scan-scope
matches from the subtraction. A prose-only diff still skips the battery *as a
whole*, but every gate whose declared `scan_scopes` entry matches the diff runs,
through the #6996 scoped-leg mechanism.

**Load-bearing invariant (unchanged).** `prose_only` stays strictly subtractive
and fail-closed: it may only ever *narrow* a run, never widen selection of a lane
whose own gate is false, and any uncertainty (no diff base, a git or selection
error) still resolves to the whole leg. No gate is disabled, skipped, xfailed or
weakened to make this pass.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A prose-only diff still runs the gates that read prose (Priority: P1)

A maintainer opens a PR that only rewords a docstring in
`scripts/release/extract_changelog.py`. The PR is proven prose-only, so the
module matrix and the code shards stay skipped. Because several heavy gates
declare `scripts/**` in their scan scope (`test_clock_import_ban`,
`test_clock_call_ban`, `test_no_deprecated_doctrine_command_in_guidance`,
`test_no_retired_subsystems`, `test_first_party_hosts_are_owned`), the heavy
battery now runs *those gates only* instead of being dropped whole.

**Why this priority**: it is the defect in the issue. A comment-scanning gate
that never sees comment-only diffs is a gate with a permanent blind spot.

**Independent Test**: feed a proven-prose-only diff path to the selection
authority and the router `if:` evaluator; assert the battery is selected, the
selected gate set is exactly the scan-scope matches, and it includes the
comment-scanning gates whose declared scope covers the path.

**Acceptance Scenarios**:

1. **Given** a proven prose-only diff touching a path declared in some heavy
   gate's `scan_scopes`, **When** the router is evaluated, **Then**
   `architectural-heavy` is selected and the scoped selection lists every heavy
   gate whose declared scope matches the path, and no other gate.
2. **Given** that same diff, **When** the scoped selection runs per leg,
   **Then** each selected gate appears in exactly one leg, and the two legs'
   union equals the selection.
3. **Given** a proven prose-only diff whose paths match no declared scan scope,
   **When** the router is evaluated, **Then** the battery is still skipped (the
   #4842 down-route is unchanged for it).
4. **Given** a non-prose (code) diff, **When** the router is evaluated,
   **Then** routing is byte-identical to today: whole battery, unchanged.

---

### User Story 2 - The exemption can never be silently dropped again (Priority: P1)

A maintainer or agent later edits the battery `if:` or the selection helper.
A planted mutation that removes the exemption must turn a test red.

**Why this priority**: the issue's third "done when" is exactly a regression
guard. A pin that only asserts the happy path passes under the old, broken
expression shape too.

**Independent Test**: mutate a copy of the workflow `if:` back to the pre-#6999
single subtraction and assert the golden evaluator now reports the battery
skipped for the prose-only scan-scope context; mutate the prose branch of the
selection helper and assert the unit pin reds.

**Acceptance Scenarios**:

1. **Given** the shipped `if:`, **When** the prose-only + declared-scope context
   is evaluated, **Then** it is true; **When** the same expression with the
   exemption removed is evaluated, **Then** it is false.
2. **Given** the shipped selection, **When** `prose_only=True`, **Then** a diff
   inside a code group still yields only scan-scope matches (never the whole
   leg); **When** the prose branch is removed, **Then** the pin reds.

---

### User Story 3 - Uncertainty still runs the whole leg (Priority: P2)

A maintainer opens a prose-only PR from a fork with an unusable base SHA, or the
git diff fails. The selection must never narrow on doubt.

**Why this priority**: it is the fail-closed invariant the #4842 down-route has
always carried; a narrowed run on uncertainty would be silent under-testing.

**Independent Test**: call the CLI with no base (and with a failing selection)
and assert `mode=full`, `run=true`.

**Acceptance Scenarios**:

1. **Given** no usable diff base, **When** the selection runs, **Then** it
   answers the whole leg, prose-only or not.
2. **Given** a selection error under a prose-only verdict, **When** the CLI
   runs, **Then** it warns and answers the whole leg.

### Edge Cases

- A prose-only PR that also edits `docs/**`: the doc paths are not `.py`, so the
  prose verdict is unaffected; the doc-scanning heavy gates (for example
  `test_retired_charter_vocabulary`, scope `docs/**`) must be selected.
- `merge_group` and `push` events: `prose_only` is not true there today; the
  change must leave those answers byte-identical (whole battery).
- `workflow_dispatch` / full mode: full mode always means the whole leg.
- A prose-only change inside a battery *code helper* (`tests/conftest.py`,
  a `scripts/ci` module a battery gate imports): prose-only proves no behaviour
  change, so it is scoped like any other prose diff; it must not force the whole
  battery through the helper rule.
- Always-on gates (fast roster, `base.deselect`) run on every PR shape and are
  never listed by the scoped selection; their scopes are excluded from the
  router group, so a prose diff that touches only an always-on gate's scope
  keeps the battery skipped — that gate already runs.
- A path whose comment text is read by a gate that does not declare it: out of
  scope here (declared scopes only); #7000 owns mechanical completeness.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Prose-only exempts declared scan-scope matches | As a maintainer, I want a prose-only diff to still run the heavy gates whose declared scope covers it, so that comment-scanning gates are not blind to comment-only edits. | High | Open | [build] | no |
| FR-002 | Scoped selection for prose-only diffs | As a maintainer, I want the prose-only battery run restricted to the declared scan-scope matches per leg, so that the down-route still saves the battery it was built to save. | High | Open | [build] | no |
| FR-003 | Non-prose routing unchanged | As a maintainer, I want every non-prose diff to route exactly as today, so that the exemption is invisible to code PRs. | High | Open | [ratchet] | no |
| FR-004 | Planted regression guard | As a maintainer, I want a planted mutation of the exemption to turn a test red, so that the fix cannot be silently reverted. | High | Open | [build] | no |
| FR-005 | Goldens cite the ruling | As a reviewer, I want the #4842 goldens that pin the subtraction to be updated and to cite the 2026-11-01 operator ruling, so that the changed behaviour is traceable. | Medium | Open | [folded] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fail-safe selection | On no usable diff base, a git error, or a selection error, the answer is the whole leg (`mode=full`, `run=true`) — never a narrower run; prose-only never changes that. | Reliability | High | Open |
| NFR-002 | Single source for scope | The gate→scope authority stays `special_tiers.architectural.scan_scopes` read through `gate_selection`; no second hand-kept list is added, and the router transcription stays test-pinned. | Maintainability | High | Open |
| NFR-003 | Cost bound | A prose-only diff runs at most the declared scan-scope matches of both legs (bounded by the existing 98 declarations), never the whole battery, and adds no new CI job. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No gate weakening | No gate is disabled, skipped, xfailed, deselected or narrowed for a diff it declares; the change may only add runs a prose diff needs. | Technical | High | Open |
| C-002 | Router group model intact | `gate_selection`'s `needs.changes.outputs.<group>` model and the `HEAVY_BATTERY_NON_SRC_GROUPS` oracle keep their member sets; the battery `if:` gains no new group. | Technical | High | Open |
| C-003 | Scope limit | Declared (`scan_scopes`) matches only; a gate that reads an undeclared path stays out of scope (see #7000). | Business | Medium | Open |

### Key Entities

- **Prose-only verdict**: the PR-level, fail-closed boolean computed by
  `scripts/ci/prose_only.prose_only_pr_verdict` and published as the
  `prose-scan` job output.
- **Declared scan scope**: one `special_tiers.architectural.scan_scopes` row in
  `.github/ci-module-registry.yml`, a gate file plus the globs it reads beyond
  its code scope.
- **Scoped leg**: the #6996 mechanism that restricts one heavy leg to a gates
  file (`SK_BATTERY_GATES_FILE`), or skips it when it holds none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A proven prose-only diff touching `scripts/**` selects both clock-ban gates plus the other declared `scripts/**` scanners, and no more than the declared matches for that diff — [build] · no-op passable: no
- **SC-002**: A proven prose-only diff that matches no declared scan scope keeps the heavy battery skipped, exactly as #4842 ruled — [ratchet] · no-op passable: no
- **SC-003**: Every non-prose diff's lane set is unchanged (the existing golden still passes unmodified in its code-PR branch), and the four `if:`-goldens that pinned the old subtraction carry the ruling citation — [ratchet] · no-op passable: no
- **SC-004**: Removing the exemption from the battery `if:`, or dropping the prose branch of the selection, makes at least one pinned test fail — [build] · no-op passable: no
