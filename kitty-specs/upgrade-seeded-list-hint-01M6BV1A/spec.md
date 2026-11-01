# Feature Specification: the upgrade hint recognises an activation list a released preset wrote

**Mission Branch**: `issue-6684-upgrade-seeded-list-hint`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #6684 — "Decide whether upgrade resets activation lists an earlier release filled with the whole catalogue", with the operator ruling of 2026-10-26 (option (b)).

## Context

`spec-kitty upgrade` step `4.0.0rc8_promote_interview_selections` never narrows a
present `activated_<kind>` list (#6629, #6499). When a list looks machine-written it
*warns* and names `charter interview --narrow-activation` and
`charter activate <kind> <id> --only`. The warning is the whole remedy on the upgrade
side: an operator decides, nothing is written.

The warning has a hole. `_seeded_list_hints` recognises a seeded list by set-equality
with **today's** full in-force set for that kind. A list an earlier CLI wrote from a
*released `default` activation preset* — `unify_charter_activation_promote_answers`
seeded an absent key from exactly that list
(`charter.default_pack.load_default_pack_activation_ids`) between 3.2.6rc1 and the #4400
effective-set rewrite — holds that release's preset ids (19 directives at 3.2.6rc1, not
today's 38). The catalogue has since grown, so equality with today's set fails and the
project gets no hint at all, even though its list is machine-written in exactly the way
the hint exists to report.

The operator ruling on #6684 (2026-10-26, comment on the issue) settles the decision the
issue was opened for:

- **Option (b): no reset migration.** Upgrade stays warn-only, so a deliberate
  activate-all (#6499) is never silently undone.
- The provenance question ("is this list mine or did a tool write it?") is answered in
  synthesis, by the twin #6685 (merged as #6875), not by a reset.
- **The warning's hint gap is still fixed**: a list seeded before the catalogue grew must
  get the hint. The ruling suggests comparing against the set as it was at the seeding
  version.

The released preset lists a seeding migration could have written are already frozen
in-tree: `_charter_pack_cutover_snapshots.DEFAULT_SNAPSHOTS` holds every distinct released
`default.yaml` per-key list (174 PyPI releases, sha256-verified), and
`_charter_pack_cutover_resets` already compares a project's list against them for the same
reason. This Mission reuses that frozen comparison for the hint; it adds no new frozen
data and no new write.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A project seeded from an old released preset learns how to narrow (Priority: P1)

An operator upgrades a project whose `activated_directives` still holds the 19 directives
a 3.2.6rc1-era `default` preset wrote, while the built-in pack now ships 38. Today the
upgrade is silent. After this change it warns, names the two narrowing commands, and says
how many of the listed ids the interview actually selected.

**Why this priority**: this is the issue's documented gap. A silent upgrade leaves
`implement` blocked with no route out except guessing.

**Independent Test**: build a project whose present list is set-equal to a released
`default` preset list, run the migration's `apply` directly, and assert it warns, writes
nothing, and still records success.

**Acceptance Scenarios**:

1. **Given** an `activated_directives` list set-equal to a released `default` preset list
   and an interview that selected some of those ids, **When** the upgrade step runs,
   **Then** the result carries one warning naming the key and both narrowing commands, and
   neither the activation file nor any other file changes.
2. **Given** the same project, **When** the step runs twice, **Then** the second run writes
   nothing either and the activation surface still holds the list unchanged.
3. **Given** a list that is the released preset plus an interview id the preset lacks,
   **When** the step runs, **Then** the same hint is reported (the seeding appended the
   interview's ids after the preset).

### User Story 2 - A deliberate list is not nagged (Priority: P1)

An operator who narrowed a list by hand to a set that matches no released preset gets no
hint, and a list that equals today's in-force set keeps the hint it has today.

**Why this priority**: #6499 is why the ruling refuses a reset. A hint is harmless only
while it stays specific; a broad "you have more than you selected" warning would train
operators to ignore it.

**Independent Test**: run the step on a hand-narrowed list of two directives and on a
list equal to today's in-force set; assert no hint and the existing hint respectively.

**Acceptance Scenarios**:

1. **Given** a list of two directives the operator picked, **When** the step runs, **Then**
   no seeded-list hint is reported.
2. **Given** a list equal to today's full in-force set, **When** the step runs, **Then** the
   existing "lists every available directive" warning is still reported.

### User Story 3 - The decision itself is recorded (Priority: P2)

A maintainer reading the ADR and the changelog finds the ruling (no reset; warn-only; the
hint covers released-preset seeds), the alternative that was refused, and why.

**Why this priority**: the issue is decision-shaped; the code change is small but the
decision must not live only in a commit message.

**Independent Test**: read the ADR amendment and the changelog entry; each states the
decision, the refused alternative (a reset migration), and the residual.

**Acceptance Scenarios**:

1. **Given** the ADR for the activation ledger, **When** a maintainer reads its #6684
   amendment, **Then** it says no reset migration was added, why, and what the upgrade
   warns about instead.

## Edge Cases

- **The catalogue grows again.** The comparison is against frozen released preset lists,
  so it keeps working for released-preset seeds; a whole-catalogue seed from a release
  whose catalogue later grows would still be missed. Recorded as a residual in the ADR with
  the condition that makes it reachable.
- **A retired id in the list.** A listed id no longer in the catalogue is not "in force";
  the released-preset hint requires the listed set to be inside today's in-force set, so
  such a list is left alone (the other warnings still apply).
- **Several kinds at once.** Each kind gets its own hint, as today.
- **The interview selected every listed id.** No hint: there is nothing to narrow.
- **An unresolvable effective set** (malformed org pack). No hint, no crash: the existing
  lazy resolution already fails closed.
- **The identity spelling differs** (`DIRECTIVE_003` vs the file stem). Both sides are
  compared as stems through the resolver, so a declared-id spelling is not a false miss.

## Requirements *(mandatory)*

**FR-001**: The upgrade step MUST report the seeded-list hint for a present activation list
that is set-equal, in identity-stem space, to a **released** `default` preset list for that
kind, in addition to the existing today's-in-force equality case.

**FR-002**: The same hint MUST be reported when the list is a released preset list plus
interview-selected ids the preset lacks (the shape the superseded seeding produced), and
MUST NOT be reported when the list holds an id that is neither in the preset nor in the
interview's selection.

**FR-003**: The hint MUST NOT be reported when the preset accounts for none of the listed
ids — that is, when nothing would be narrowed — and MUST NOT be reported for a list that is
not a subset of today's in-force set for that kind.

**FR-004**: The step MUST NOT write, narrow or reset any activation list because of this
hint (unchanged from #6629/#6499). The ruling's guarantee — upgrade never undoes a choice —
stays exactly as it is.

**FR-005**: The released preset lists MUST be read from the existing frozen snapshot module
(`_charter_pack_cutover_snapshots.DEFAULT_SNAPSHOTS`), not from a live preset file and not
from a second copy of the data.

**FR-006**: The warning text MUST say which provenance it reports and how many of the listed
ids the interview selected, and MUST name both narrowing commands it names today.

**FR-007**: The decision, the refused alternative (a reset migration) and the residual MUST
be recorded in an ADR amendment on the activation ledger, with a changelog entry under
`[Unreleased]`.

**FR-008**: A test MUST prove the gap red-first: a released-preset-shaped list gets no hint
before the change and one hint after it, driven through the migration's public
`apply`/`detect` entry point.

## Non-Requirements

- No reset migration, no new activation key, no provenance record in the ledger (refused by
  its L1 validation and impossible to backfill — the ruling says so).
- No change to what `charter interview`, `charter activate` or `charter synthesize` do.
- No change to the today's-in-force hint path beyond routing both provenances through one
  function.

## Success Criteria *(mandatory)*

- The issue is closed by a PR that adds the hint and records the ruling.
- The upgrade writes exactly what it wrote before for every input: the existing migration
  suite stays green and the activation surfaces stay byte-identical.
- The new test fails on `main` for the prescribed reason and passes on the branch.
- `docs/changelog/CHANGELOG.md` and the ADR describe the behaviour an operator will see.

## Assumptions

- The seeding writer's preset lists are the released `default.yaml` lists; the frozen
  snapshot module already holds every distinct one and is the single source of that data.
- The whole-catalogue seeding eras wrote the catalogue that is still shipped (38
  directives, 14 paradigms, 121 tactics, 25 styleguides, 23 procedures, 18 toolguides, 26
  agent profiles at both 4.0.0rc6/rc7 and today), so today's equality check covers them and
  the residual is not reachable with any released CLI.
