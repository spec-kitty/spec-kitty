# Mission Specification: Real `--mission` scoping for the corpus-walking `migrate` commands

**Mission Branch**: `issue-6347-migrate-mission-scoping`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6347 (P2, milestone "4.0.0 release scope"), follow-up deferred by #5294 / PR #6345.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator can re-run one migration against a single Mission (Priority: P1)

Three `migrate` subcommands genuinely walk a whole corpus: `backfill-provenance`
(every `kitty-specs/*/acceptance-matrix.json`), `charter-encoding` (every
Mission's charter content plus the global charter store) and
`rebaseline-dossier-hashes` (every `.kittify/dossiers/<slug>/snapshot-latest.json`).
#5294 / PR #6345 made them **reject** `--mission` rather than silently ignore it,
which closed the false-success door but left the operator unable to legitimately
re-run one migration against one Mission — they must run it corpus-wide.

This Mission gives those three commands a real, working `--mission`: the flag
resolves through the standard selector resolver (`mission_id` / `mid8` /
`mission_slug`, exactly as the already-mission-scoped `backfill-identity` does)
and narrows the walk to that Mission's files. Omitting `--mission` keeps
today's corpus-wide default.

**Why this priority**: It is the entire feature. Without it the flag is merely
refused, and the operator's only recourse is an unscoped mutation.

**Independent Test**: Build a fixture with two Missions' files, run each of the
three commands with `--mission <handle>` for one of them, and assert the target
Mission's file changed while the other Mission's file is byte-identical — and
that a handle spelled as mission_id, mid8 and slug all select the same Mission.

**Acceptance Scenarios**:

1. **Given** two Missions each with an `acceptance-matrix.json` carrying a non-pending negative invariant with no `provenance_origin`, **When** `spec-kitty migrate backfill-provenance --mission <handle>` runs, **Then** only that Mission's matrix gains the `legacy_unrecorded` sentinel and the other Mission's matrix is byte-identical.
2. **Given** two Missions each with a non-UTF-8 charter file, **When** `spec-kitty migrate charter-encoding --mission <handle> --yes` runs, **Then** only that Mission's charter file is normalized and the other Mission's charter file is byte-identical.
3. **Given** two Missions each with a recorded `snapshot-latest.json` holding a non-canonical hash, **When** `spec-kitty migrate rebaseline-dossier-hashes --mission <handle>` runs, **Then** only that Mission's snapshot is re-baselined and the other Mission's snapshot is byte-identical.
4. **Given** the same Mission addressed as its full `mission_id`, its 8-character `mid8`, and its slug, **When** each spelling is passed to the three commands, **Then** all three resolve to the same Mission and scope identically.

---

### User Story 2 - `charter-encoding --mission` never touches the global charter store (Priority: P1)

`charter-encoding` walks two corpora in one run: per-Mission charter content and
the global `.kittify/charter/` store. A Mission-scoped run has no business
mutating the global store. Per the operator's triage disposition on #6347, the
scoped path **skips** the global store and says so explicitly in its report;
the run must not fail merely because a global store exists, and the store's
bytes must be provably unchanged.

**Why this priority**: Silently touching the global store is the one outcome the
operator ruling forbids outright; it is a scope-safety property, not a nicety.

**Independent Test**: Put a non-UTF-8 file in `.kittify/charter/` and a
non-UTF-8 file in the target Mission's charter dir, run the command with
`--mission`, then assert the Mission file was normalized, the global file is
byte-identical (no `.bak` sibling, no rewrite) and the report names the exclusion.

**Acceptance Scenarios**:

1. **Given** a project with a global charter store and a target Mission, **When** `charter-encoding --mission <handle>` runs, **Then** the global store's files are byte-identical afterwards and no `.bak` sibling was created for them.
2. **Given** the same run, **When** the report is rendered, **Then** both the human summary and the `--json` payload state that the global charter store was excluded by `--mission`, and the command's exit code reflects only the Mission-scoped files.

---

### User Story 3 - The corpus-wide default and the two non-Mission commands are unchanged (Priority: P2)

The three commands keep walking the whole corpus when `--mission` is omitted.
`rewrite-opposed-by` (pack-scoped, `--pack`) and `repin-hooks` (repo repair)
have no Mission concept and stay reject-only, exactly as PR #6345 shipped them.

**Why this priority**: The mission must narrow strictly to the three commands
that have a real Mission scope; un-scoping the other two would trade one silent
no-op for another.

**Independent Test**: Run each of the three without `--mission` over a two-Mission
fixture and assert both Missions were processed; run `rewrite-opposed-by` and
`repin-hooks` with `--mission` and assert exit 2 with the existing message; walk
the CLI tree and assert exactly those two remain in the reject set.

**Acceptance Scenarios**:

1. **Given** two Missions, **When** any of the three commands runs without `--mission`, **Then** both Missions are processed exactly as on current `main`.
2. **Given** `rewrite-opposed-by` or `repin-hooks`, **When** `--mission <h>` is passed, **Then** it exits 2 with the unchanged scope-neutral "not mission-scoped" message.
3. **Given** the assembled CLI tree, **When** every leaf command is inspected, **Then** exactly `rewrite-opposed-by` and `repin-hooks` carry the reject class and the other three declare a real `--mission`.

### Edge Cases

- **Unknown / ambiguous handle**: `--mission ghost` on any of the three must fail closed through the canonical resolver (exit 2 in human mode, exit 1 with a JSON error envelope under `--json`) and must never fall back to a corpus-wide run.
- **Mission with no matching file**: a scoped run against a Mission that has no matrix / no charter content / no recorded snapshot reports zero files inspected and exits 0 — it is a valid no-op, not an error, and must not widen the walk.
- **Coordination-homed Mission**: `backfill-provenance` resolves each Mission's matrix through `placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`; scoping must filter on the Mission identity, not on a primary-tree path join, so a coord-homed matrix is still found.
- **Dossier dir slug differs from the Mission slug**: `rebaseline-dossier-hashes` scoping must not miss a snapshot whose `.kittify/dossiers/<slug>/` directory name differs from the Mission's source directory name.
- **Global-store-only project** (no Missions): `charter-encoding --mission` reports the exclusion and inspects zero Mission files — it does not rewrite the global store.
- **`--mission` before the subcommand** (`spec-kitty migrate --mission <h> <sub>`) is unchanged: the group declares no `--mission`, so click rejects it at the group level; out of scope to unify.
- **Repeated scoped run**: each command stays idempotent under `--mission` — a second scoped run reports no changes.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `backfill-provenance` accepts a real `--mission` | As an operator, I want `migrate backfill-provenance --mission <handle>` to narrow the walk to one Mission's acceptance matrix so that I can re-run the migration against a single Mission. | High | Open | [build] | no — RED on current main (exit 2 today); paired with the two-Mission isolation control |
| FR-002 | `charter-encoding` accepts a real `--mission` | As an operator, I want `migrate charter-encoding --mission <handle>` to narrow the walk to one Mission's charter content so that I can repair one Mission without touching the corpus. | High | Open | [build] | no — RED on current main (exit 2 today); paired with the two-Mission isolation control |
| FR-003 | `rebaseline-dossier-hashes` accepts a real `--mission` | As an operator, I want `migrate rebaseline-dossier-hashes --mission <handle>` to narrow the walk to one Mission's recorded snapshot so that I can re-baseline one Mission. | High | Open | [build] | no — RED on current main (exit 2 today); paired with the two-Mission isolation control |
| FR-004 | `charter-encoding --mission` skips the global charter store and says so | As an operator, I want the scoped run to leave the global charter store untouched and report the exclusion so that a Mission-scoped repair can never mutate global state silently. | High | Open | [build] | no — asserts a diagnostic absent on current main, plus byte-identity of the global store |
| FR-005 | Handle resolution matches the mission-scoped `migrate` commands | As an agent, I want `--mission` on the three commands to accept `mission_id`, `mid8` and `mission_slug` through the canonical selector resolver so that the flag behaves like `backfill-identity --mission`. | High | Open | [build] | no — exercises three spellings against one Mission; a directory-name-only scope fails mid8/mission_id |
| FR-006 | Omitted `--mission` keeps the corpus-wide default | As an operator, I want the three commands to behave exactly as before when `--mission` is absent so that the change narrows strictly to the flag. | High | Open | [ratchet] | yes — same-fixture positive control proving the scoped filter does not break the unscoped walk |
| FR-007 | The two non-Mission commands stay reject-only | As an operator, I want `rewrite-opposed-by` and `repin-hooks` to keep rejecting `--mission` so that a command with no Mission concept is never given a fake scope. | Medium | Open | [ratchet] | no — tree-wide walk asserts the reject set is exactly those two |
| FR-008 | Unknown handles fail closed | As an operator, I want an unknown or ambiguous `--mission` to exit non-zero with the resolver's diagnostic so that a typo never degrades into a corpus-wide mutation. | High | Open | [build] | no — asserts non-zero exit and no mutation of any Mission |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Scoped runs are O(one Mission) | A `--mission` run reads at most the target Mission's files for each command: zero non-target files are read or written, asserted by byte-identity of every non-target fixture file. | Performance | High | Open |
| NFR-002 | Scoped runs are idempotent | Running any of the three commands twice with the same `--mission` reports zero changes and leaves every file byte-identical on the second run. | Reliability | High | Open |
| NFR-003 | Help text documents the real scope | `spec-kitty migrate <cmd> --help` for the three commands advertises `--mission` with the accepted handle forms; the two reject-only commands keep `--mission` out of `--help`. | Usability | Medium | Open |
| NFR-004 | No new I/O beyond the existing walks | A scoped run performs no additional whole-corpus glob beyond the existing discovery call it narrows, and no `--dry-run` path writes. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical resolver | `--mission` resolves through `specify_cli.cli.selector_resolution.resolve_mission_handle`; no new handle-parsing code. | Technical | High | Open |
| C-002 | Backends keep the directory-slug contract | The three backends keep taking a resolved canonical `mission_slug`; the CLI owns handle resolution, so no backend re-parses mission_id/mid8. | Technical | High | Open |
| C-003 | PR #6345's reject behaviour is preserved where it still applies | `rewrite-opposed-by` and `repin-hooks` keep `CorpusWideCommand` and the unchanged scope-neutral message; the corpus-wide default of the three scoped commands is unchanged. | Technical | High | Open |
| C-004 | No weakening of a gate | No test, gate or CI check may be skipped, xfailed or relaxed to make this land. | Process | High | Open |

### Key Entities

- **Mission handle**: what the operator types after `--mission` — a ULID `mission_id`, an 8-character `mid8`, or a slug; resolved to exactly one Mission.
- **Scoped walk**: the narrow form of each command's existing discovery — a matrix path, a set of charter files, or a recorded snapshot — derived from the resolved Mission, never from a whole-corpus glob filtered after the fact where a per-Mission lookup exists.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the three commands completes a scoped run against one Mission and leaves every other Mission's files byte-identical (3 of 3 commands, asserted per command). — [build] · no-op passable: no
- **SC-002**: `charter-encoding --mission` leaves the global charter store byte-identical and reports the exclusion in both human and JSON output (2 of 2 renderings). — [build] · no-op passable: no
- **SC-003**: The three commands remain byte-identical to current `main` when `--mission` is omitted, and exactly two `migrate` commands remain in the reject set. — [ratchet] · no-op passable: yes
- **SC-004**: A handle typed as mission_id, mid8 or slug selects the same Mission in all three commands (3 spellings × 3 commands). — [build] · no-op passable: no
