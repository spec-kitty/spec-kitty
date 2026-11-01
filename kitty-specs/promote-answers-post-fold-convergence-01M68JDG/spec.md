# Mission Specification: Pin the post-fold convergence of the interview promotion (#6549)

**Mission Branch**: `issue-6549-promote-answers-post-fold-convergence`
**Created**: 2026-10-31
**Status**: Draft
**Input**: `kitty-mission-from-issue` batch 5, agent R6: spec-kitty/spec-kitty#6549

## Context and grounding

#6549 reports that `spec-kitty upgrade` is not convergent: on a project upgraded from
a pre-ledger build, the first pass applies `consolidate_charter_bundle_fold` (which
relocates `activated_*` from `.kittify/config.yaml` into `charter.yaml`), and the second
pass then applies `unify_charter_activation_promote_answers`, which — reading only
`config.yaml` and finding no `activated_directives` there — seeds the key from the
kind's whole in-force set and writes all 38 built-in directives back into `config.yaml`,
contradicting the authority. A third pass wrote nothing only because both migrations
were then recorded `success`.

**Grounding result (current `main`, `35318ef51c`): the reported non-convergence no
longer reproduces.** #6629 superseded `unify_charter_activation_promote_answers`
(registered as a recorded no-op through `specify_cli.upgrade.supersession.
SUPERSEDED_MIGRATIONS`, module bytes untouched per DIRECTIVE_044) and added
`4.0.0rc8_promote_interview_selections`, which resolves the activation write target
(`charter.activation.pack_manager.resolve_activation_write_target`) instead of reading
`config.yaml` alone, and never writes an absent key. A pre-ledger project that carries
`activated_directives: [001-architectural-integrity-standard]` in `config.yaml` and a
mirrored `answers.selected_directives: [DIRECTIVE_001]` converges on the first upgrade;
a second and third upgrade change zero bytes and create no commit.

What #6549 still asks for is the regression evidence it names in its own *Suggested
Fix*: `tests/upgrade/test_activate_builtin_post_fold_dedup.py` pins the rc35 pair's
post-fold dedup and `tests/upgrade/test_upgrade_keeps_absent_activation_6629.py` pins
the absent-key rule, but **nothing pins the promote step's post-fold behaviour or the
two-run convergence of the project shape that regressed**. This Mission adds that pin
and keeps it non-vacuous, so a future change that drops the supersession entry — the
one line that stops the shipped step re-firing — goes red instead of silently
re-introducing the 38-directive copy.

Out of scope (see `## Deferred`-facing constraint C-003): repairing projects that
already took the bad second pass on an rc8 build before #6629. Their stale
`config.yaml` copy is ignored by every reader (the activation ledger wins), is reported
by `spec-kitty doctor charter-packs` as `LEGACY_KEYS_PRESENT`, and its removal is a
documented operator action. Stripping a tracked activation key automatically is a
maintainer decision, not this Mission's.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A second upgrade of a fold-crossing project is a no-op (Priority: P1)

A maintainer upgrades a project that straddled the charter fold: its `config.yaml`
still carries `activated_directives`, its charter interview record mirrors that
selection, and it has no activation ledger yet. The first upgrade folds the charter
bundle, moves the activation keys into the ledger and runs the interview promotion.
The maintainer runs `spec-kitty upgrade --project --yes` a second time and nothing
happens: no file changes, no auto-commit, no "not needed" thrash that writes.

**Why this priority**: This is the exact defect #6549 reports. Convergence is the
property; the regression test is the only thing standing between it and a repeat.

**Independent Test**: Drive the real `MigrationRunner` twice over a pre-ledger project
that mirrors its interview selection, snapshot every non-`.git` file, and assert the
second run changes zero bytes and adds no commit.

**Acceptance Scenarios**:

1. **Given** a project stamped below the promotion's `3.2.6rc1` whose `config.yaml`
   carries the one directive the interview selected, **When** `upgrade` runs, **Then**
   the fold and the promotion apply and `.kittify/config.yaml` carries no `activated_*`
   key afterwards.
2. **Given** that project at the post-first-upgrade state, **When** `upgrade` runs a
   second time, **Then** every tracked file's bytes are unchanged and the migration
   ledger gains no record and the run creates no commit.

---

### User Story 2 - The supersession entry is proven load-bearing (Priority: P2)

A maintainer reading the supersession table asks "what happens if this row is
deleted?". The answer must be a test failure, not a silent regression.

**Why this priority**: The fix for #6549 is a one-line table entry. A guard test that
only observes the fixed state would stay green if the entry were removed, because the
successor would still write through the right target — the shipped step would simply
re-fire first. Proving the entry is what holds the line keeps the guard honest.

**Independent Test**: Remove the id from `SUPERSEDED_MIGRATIONS`, re-discover the
registry, run the same two-upgrade fixture, and assert the second run *does* write the
whole-kind `activated_directives` list back into `config.yaml` — then restore and
assert it does not.

**Acceptance Scenarios**:

1. **Given** the supersession table without `unify_charter_activation_promote_answers`,
   **When** the two-upgrade fixture runs, **Then** `.kittify/config.yaml` gains
   `activated_directives` with the full built-in set on the second run (the #6549
   symptom), proving the probe can see the defect.
2. **Given** the table as shipped, **When** the same fixture runs, **Then** the second
   run writes no `activated_directives` key into `config.yaml`.

---

### User Story 3 - The registered step is a recorded no-op after the fold (Priority: P3)

An operator asks why the promote step still appears in `upgrade --dry-run`/selection
lists after its behaviour was replaced. The registry answer is pinned: the registered
class is the superseded substitute, its `detect()` is False on a post-fold project, and
its `apply()` writes nothing.

**Why this priority**: It is the narrow seam #6549 names ("the promote migration's
`detect()` is False" in its Suggested Fix), and it documents the supersession contract
where a future reader will look.

**Independent Test**: Run the real fold migration over a legacy fixture whose
`config.yaml` carries `activated_directives` and whose answers mirror it, then assert
`MigrationRegistry.get_all()` returns a `SupersededMigration` for that id with
`detect() is False`, and that `apply()` leaves every file byte-identical.

**Acceptance Scenarios**:

1. **Given** a post-fold project, **When** the registered promote step is asked,
   **Then** `detect()` is False and `apply()` changes zero bytes.
2. **Given** the same project, **When** the shipped class is instantiated directly,
   **Then** its own `detect()` still reports True — the direct import keeps the shipped
   behaviour by design (DIRECTIVE_044), which is why the registry entry, not the class,
   is the guard.

### Edge Cases

- A project whose `answers.yaml` is absent: the successor settles with a no-op; the
  two-run fixture still converges.
- A project already stamped at or above `4.0.0rc8` that never folded: the fold is not
  selected, so the fixture must assert convergence for the shape under test only and
  not claim more.
- The bite fixture edits a module-level table: it must restore the table and the
  registry in a `finally`/fixture teardown so no later test sees a superseded entry
  missing.
- Registry re-discovery reloads migration modules; the bite fixture must go through
  `auto_discover_migrations()` (the production discovery path) so it exercises the
  real substitution branch instead of a hand-built substitute.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Two-run convergence of a fold-crossing project | As a maintainer, I want the second upgrade of a project that straddled the charter fold to change nothing so that `upgrade` is a fixed point. | High | Open | [build] | no |
| FR-002 | The registered promote step is a no-op after the fold | As an operator, I want the promote step to report "not needed" on a post-fold project so that it cannot write a contradicting activation copy. | High | Open | [build] | no |
| FR-003 | The supersession entry is proven load-bearing | As a maintainer, I want a test that goes red when the supersession entry is dropped so that the #6549 fix cannot silently regress. | High | Open | [build] | no |
| FR-004 | The shipped class keeps its direct-import behaviour | As a maintainer, I want the shipped class's own `detect()` pinned as still-True so that the guard is visibly the registry entry, not the class. | Medium | Open | [build] | no |
| FR-005 | The ADR names the pin | As a reader of ADR `2026-10-17-1` Amendment 2026-10-25, I want the convergence pin named so that the documented contract and its test are one hop apart. | Low | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | New tests are fast | The added test module completes in under 60 s on the reference machine and carries `pytest.mark.unit`/`pytest.mark.fast` or `pytest.mark.integration`+`pytest.mark.git_repo` matching what it drives; no network, no `uvx`, no full-suite run. | Performance | High | Open |
| NFR-002 | No production change | The Mission's diff under `src/` is empty: the guard pins shipped behaviour rather than altering it, and `git diff --stat origin/main -- src/` reports nothing. | Reliability | High | Open |
| NFR-003 | No gate weakened | No test is skipped, xfailed, deselected or loosened to pass; no CI gate, allowlist or threshold is edited. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Shipped module bytes stay untouched | `m_unify_charter_activation.py` is never edited (DIRECTIVE_044, `content_hash`); supersession is the only sanctioned mechanism. | Technical | High | Open |
| C-002 | Drive the production entry point | Every acceptance test drives `MigrationRunner.upgrade` / `MigrationRegistry` / `auto_discover_migrations`, not only the migration class, so a wiring gap fails the test. | Technical | High | Open |
| C-003 | No automatic removal of a divergent activation copy | Projects damaged by the pre-#6629 second pass keep their stale `config.yaml` copy; stripping it is a maintainer decision (the `#6496` refusal semantics are deliberate). This Mission reports it, it does not change it. | Business | High | Open |

### Key Entities

- **Fold-crossing project**: a project whose recorded version predates the charter-bundle
  fold and whose `config.yaml` still carries the activation keys the fold relocates.
- **Superseded substitute**: the registry-visible no-op class that carries the shipped
  migration's identity and `content_hash` while `detect()` returns False.
- **Bite proof**: the same fixture run with the supersession entry removed, asserting the
  defect reappears — the positive control that keeps the guard non-vacuous.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The two-run fixture reports zero changed files and zero new commits on its second run, asserted byte-for-byte over every non-`.git` file. — [build] · no-op passable: no
- **SC-002**: The bite proof turns the same fixture red (the full built-in directive list reappears in `config.yaml`) when the supersession entry is removed, and green when it is restored. — [build] · no-op passable: no
- **SC-003**: `git diff --stat origin/main -- src/` is empty and the changed-lines coverage gate still passes on the PR head. — [ratchet] · no-op passable: no
- **SC-004**: The new module runs green locally in a single `pytest` invocation under 60 s, and CI's changed-test shard for `tests/upgrade` selects it. — [build] · no-op passable: no
