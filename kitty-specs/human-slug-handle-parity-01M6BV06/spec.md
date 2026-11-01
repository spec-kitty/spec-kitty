# Mission Specification: One answer for a Mission's human slug

**Mission Branch**: `human-slug-handle-parity-01M6BV06`
**Created**: 2026-11-01
**Status**: Draft
**Input**: User description: "Issue #6278 — `implement --mission smoke-test` refuses the human
slug that `agent tasks status --mission smoke-test` accepts. Two handle resolvers disagree."

## Context

A Mission created today gets a composed slug, `<human-slug>-<mid8>` (for example
`smoke-test-01M6BTQX`, `kitty-specs/smoke-test-01M6BTQX/`, `meta.json.mission_slug`).
Three handle forms name such a Mission: the composed slug itself, the `mid8`
(`01M6BTQX`), and the human slug (`smoke-test`).

Both commands already accept the first two. Only the human slug behaves differently:
`agent tasks status` resolves it through the read-path placement seam's bare-modern-slug
fold (`resolve_bare_modern_mission_dir_name`), while `implement` resolves through
`specify_cli.cli.selector_resolution.resolve_mission_handle` →
`specify_cli.context.mission_resolver.resolve_mission`, whose "human slug" rung compares
`strip_numeric_prefix(mission_slug) == handle`. That strips a leading `NNN-` prefix and
nothing else, so it can never match a slug minted with the `-<mid8>` suffix.

Result: the same operator, one command apart, is told a Mission that was just created
does not exist (exit 2, `No mission found for handle "smoke-test"`).

This mission adopts the issue's first option: the identity resolver learns the human
slug, so every command that resolves a Mission handle answers the same way. Refusing the
human slug everywhere was rejected because it would break the already-shipping
`agent tasks status` / `agent status` behavior, which operators are told to rely on.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - `implement` accepts the handle the previous command accepted (Priority: P1)

An operator creates a Mission, checks it with `agent tasks status --mission smoke-test`,
and then runs `implement WP01 --mission smoke-test`. The implement command resolves the
same Mission the status command resolved.

**Why this priority**: This is the reported defect and the user-visible half of it. It is
the whole value of the mission: one handle, one answer.

**Independent Test**: Create a Mission in a scratch project, then run
`implement WP01 --mission <human-slug>`; it must reach the work-package step (a
"WP file not found" style refusal, because no tasks exist yet) rather than refuse the
Mission itself.

**Acceptance Scenarios**:

1. **Given** a project with exactly one Mission `smoke-test-01M6BTQX`, **When**
   `implement WP01 --mission smoke-test` runs, **Then** the Mission resolves to
   `kitty-specs/smoke-test-01M6BTQX` and the command proceeds past mission resolution.
2. **Given** the same project, **When** any command resolves `--mission smoke-test`,
   `--mission smoke-test-01M6BTQX`, or `--mission 01M6BTQX`, **Then** all three resolve
   to the same directory.

### User Story 2 - Two Missions sharing a human slug still refuse loudly (Priority: P1)

An operator has `smoke-test-01AAAAAA` and `smoke-test-01BBBBBB`. Typing `smoke-test` must
not silently pick one.

**Why this priority**: The new matching rung is a widening of accepted input. The
no-silent-fallback rule is what makes that widening safe; without it the fix would trade
a refusal for a coin flip.

**Independent Test**: Two Missions whose composed slugs share a human slug, then
`resolve_mission("smoke-test", repo_root)` and the CLI both raise/exit with the
ambiguity error carrying both candidates.

**Acceptance Scenarios**:

1. **Given** two Missions `smoke-test-01AAAAAA` and `smoke-test-01BBBBBB`, **When**
   `implement WP01 --mission smoke-test` runs, **Then** it exits non-zero with an
   ambiguity error listing both composed slugs, not a "not found" error and not a guess.
2. **Given** the same two Missions, **When** `--mission smoke-test-01BBBBBB` runs,
   **Then** it resolves that one Mission.

### User Story 3 - The two resolution paths cannot drift again (Priority: P2)

A maintainer changing either resolver sees a test that pins the handle matrix for both
paths.

**Why this priority**: The defect exists because two code paths answered the same
question with no test that compared them. The regression guard is the durable half of the
fix, but it is worthless without the behavior change above.

**Independent Test**: The selector-resolution test suite contains a table over the
handle forms that asserts both `resolve_mission_handle` and the read-path bare-modern
fold return the same mission directory.

**Acceptance Scenarios**:

1. **Given** the handle matrix, **When** both resolution paths run on the same fixture,
   **Then** they return the same directory for every handle form.

### Edge Cases

- A slug that merely ends in eight characters resembling a mid8 but whose tail is not the
  Mission's own `mission_id[:8]` must NOT have that tail stripped (a coincidental tail is
  not an identity marker). `smoke-test-01M6BTQX` with `mission_id` starting `01ZZZZZZ`
  keeps `smoke-test-01M6BTQX` as its human slug, so `smoke-test` still does not resolve
  to it.
- A legacy `NNN-` prefixed slug without a mid8 keeps resolving as before
  (`083-foo-bar` → `foo-bar`).
- A directory literally named `smoke-test` still wins at the exact-directory rung over any
  fold of a composed sibling.
- The `mid8` form, the full ULID, and the numeric-prefix form keep their current
  precedence and remain unambiguous.
- An unknown handle still raises `MissionNotFoundError` with the same message.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Identity resolver accepts the human slug of a mid8-composed Mission | As an operator, I want `--mission smoke-test` to name `smoke-test-01M6BTQX` so that the handle that worked one command earlier keeps working. | High | Open | [build] | no — the pre-existing resolver raises `MissionNotFoundError` for it |
| FR-002 | The suffix is stripped only when it is the Mission's own mid8 | As a maintainer, I want a coincidental eight-character tail left alone so that resolution never invents a handle. | High | Open | [build] | no — the fixture pair separates own-mid8 from coincidental-tail |
| FR-003 | Ambiguity still fails loudly with candidates | As an operator, I want two Missions sharing a human slug to produce an ambiguity error listing both so that I am never given a silent guess. | High | Open | [ratchet] | no — a bare first-match implementation fails this row |
| FR-004 | `implement` resolves the human slug end to end | As an operator, I want `implement WP01 --mission smoke-test` to reach the work package so that the reported command sequence works. | High | Open | [build] | no — the CLI exits 2 on the human slug today |
| FR-005 | Both resolution paths are pinned by one handle matrix | As a maintainer, I want the selector-resolution tests to assert the same answer from both paths so that they cannot drift again. | Medium | Open | [ratchet] | no — the matrix fails until both paths agree |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra filesystem cost | Resolution stays one `kitty-specs/` walk per call: the new rung compares already-indexed fields (`mission_slug`, `mid8`), adding no `meta.json` read beyond the existing index build. | Performance | High | Open |
| NFR-002 | Existing handle forms keep their precedence | The full ULID, `mid8`, exact-directory, `NNN-` human slug and numeric-prefix rungs answer exactly as before; the new matching is confined to the existing human-slug rung. | Compatibility | High | Open |
| NFR-003 | No new public symbols | The change adds at most a module-private helper; the documented public surface (`resolve_mission`, `resolve_mission_handle`, the resolver adapters) is unchanged. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One resolution algorithm | The fold belongs in `_resolve_from_index`, the single fail-closed-loud ladder shared by `FsMissionResolver` and `FakeMissionResolver`; no second ladder is introduced. | Technical | High | Open |
| C-002 | Fail closed, never guess | Every widening keeps `_resolve_or_raise`'s behaviour: more than one match raises `AmbiguousHandleError` with all candidates; zero matches falls through. | Technical | High | Open |
| C-003 | Scope stops at the shared resolver | The `--owned-checkout` sighting in the issue (a different read path) is out of scope unless the shared resolver change already fixes it. | Technical | Medium | Open |

### Key Entities

- **Mission handle**: what the operator types for `--mission`. Forms: full ULID, `mid8`,
  composed slug, human slug, numeric prefix.
- **Composed slug**: the `kitty-specs/` directory name and `meta.json.mission_slug`,
  `<human-slug>-<mid8>` for a Mission created today.
- **Human slug**: the composed slug with any `NNN-` prefix and the Mission's own trailing
  `-<mid8>` removed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a freshly created Mission, all three handle forms (`smoke-test`,
  `smoke-test-01M6BTQX`, `01M6BTQX`) resolve to the same directory through
  `resolve_mission`; a fourth, unknown handle still raises. — [build] · no-op passable: no
- **SC-002**: `implement WP01 --mission <human-slug>` exits past mission resolution (it
  reports the missing work package instead of the missing Mission). — [build] · no-op passable: no
- **SC-003**: Two Missions sharing a human slug produce an ambiguity error naming both
  candidates from both the identity resolver and the CLI. — [ratchet] · no-op passable: no
- **SC-004**: One selector-resolution test asserts identical directories from
  `resolve_mission_handle` and the read-path fold across the whole handle matrix. — [ratchet] · no-op passable: no
