# Mission Specification: Preserve user assets in `migrate --force` and git-source fetch

**Mission Branch**: `spec/asset-preservation-migrate-fetch`
**Created**: 2026-09-26
**Status**: Draft
**Input**: Fix GitHub issues #4961, #4960, #4989 — the last two unrouted destructive flows in epic #4915 (user-data & customization preservation) that silently destroy operator-authored content with a zero/success exit.

## Context

`spec-kitty` treats operator-authored governance content as sacred: no mutating flow may
overwrite, delete, or corrupt user-authored files without proving package ownership and, where
ownership is unproven, preserving or backing up the content (charter *User Customization
Preservation* invariant; epic #4915). Every mutating flow has been routed through the shared
`asset_preservation` guard **except two**: the `migrate --force` asset classifier
(`runtime/migrate.py`) and the git-source charter/doctrine fetch
(`doctrine/sources/git_source.py`). This mission closes those last two holes, reusing the
established primitives — it does not build a new framework.

Three confirmed-live P0 defects (verified present on `main`, none superseded):

- **#4961** — `migrate --force` deletes a team-customised `.kittify/templates/spec-template.md`
  as "superseded (outdated defaults)", no backup, exit 0; every later mission silently reverts
  to package defaults. (Second deletion path after the closed init bug #4931.)
- **#4960** — `charter fetch` (git source) `rmtree`s a pre-existing hand-authored org pack at
  `local_path` whenever `git clone` fails (directory already exists, or remote unreachable);
  exit 1 prints only git's error. Org packs live outside the repo (`~/.kittify/org/…`) so the
  loss is unrecoverable.
- **#4989** — `charter fetch` (git source) `git reset --hard`s the existing pack clone on every
  run, discarding locally committed **and** uncommitted org directives, exit 0; and a configured
  `ref: main` resets to the *local* branch (never `origin/main`), so the pack never advances.

Parent epic: #4915. Pattern precedents (context only): #4931 / #4861 (init deletion, fixed via
the guard at `init.py`), #4895 (`backup_before_overwrite`), #4859 / #4862 (asset-preservation
guard). Version-skew rationale for the `SUPERSEDED` disposition: #285.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A customised template survives `migrate --force` (Priority: P1)

A team has customised `.kittify/templates/spec-template.md` (the shipped template plus a team
section) and committed it. Following the CLI's own `Run 'spec-kitty migrate'` nudge, they run
`spec-kitty migrate --force`. Their customisation must not be destroyed.

**Why this priority**: Silent, irreversible loss of operator content from a command the CLI
actively recommends; every subsequent mission silently loses the team section. This is the
mission's headline defect (#4961).

**Independent Test**: Customise a shipped template, commit, run `migrate --force`; assert the
customised bytes still exist (in place or in a reported backup) and a fresh `mission create`
still renders the team section. Fully testable via the CLI without the other stories.

**Acceptance Scenarios**:

1. **Given** a `.kittify/templates/spec-template.md` whose bytes differ from the current package
   default because of a team customisation, **When** `spec-kitty migrate --force` runs, **Then**
   the file is preserved (kept in place, moved to `overrides/`, or archived to a reported backup
   path) — never `unlink`ed — and the command exits 0 with honest messaging (not "superseded ...
   removed").
2. **Given** the same file, **When** `spec-kitty migrate --dry-run` runs, **Then** it is labelled
   as customised/preserved, never "superseded (outdated defaults)".
3. **Given** a `.kittify/` file that is byte-identical to its shipped package default, **When**
   `migrate --force` runs, **Then** it is still removed (no behavioural regression for genuine
   duplicates), exit 0.

### User Story 2 - A hand-authored org pack survives a failed `charter fetch` (Priority: P1)

An operator has a hand-authored org pack at a git-sourced `local_path` (from `charter org init`
+ `charter new`), or a pre-provisioned snapshot. They run `spec-kitty charter fetch` while the
remote is unreachable, or with the directory already populated. Their pack must not be deleted.

**Why this priority**: Unrecoverable deletion of governance content that lives outside the repo,
triggered by a routine sync command and by ordinary conditions (offline, pre-existing dir)
(#4960).

**Independent Test**: Seed a non-empty `local_path`, run `charter fetch` with a failing clone;
assert every file still exists and the command reports the refusal without deleting.

**Acceptance Scenarios**:

1. **Given** a non-empty `local_path` that is not a clone of the configured `url`, **When**
   `charter fetch` runs, **Then** the command refuses up front (clear, non-destructive error) and
   leaves every file in place.
2. **Given** a git-source fetch whose `git clone` fails for any reason, **When** cleanup runs,
   **Then** only a directory the fetch itself created (a fresh temp) is removed; a pre-existing
   `local_path` is never `rmtree`d.
3. **Given** a clone that succeeds into a staging area but whose subsequent `git checkout <ref>`
   fails, **When** cleanup runs, **Then** any pre-existing installed pack is left intact.

### User Story 3 - `charter fetch` update never discards local pack edits and actually advances (Priority: P1)

An operator has local edits (committed and/or uncommitted) in an installed git-sourced pack, and
`charter fetch` performs its update path. It must not silently discard those edits, and a
configured `ref` must actually move the pack forward.

**Why this priority**: Per-fetch silent loss of committed directives with exit 0, plus a
correctness defect where the pack never advances (#4989); same module and fix surface as Story 2.

**Independent Test**: Install a git-sourced pack, add a local commit and an uncommitted edit, run
`charter fetch`; assert the edits are preserved or backed up (never silently dropped) and that a
`ref: main` update targets `origin/main` so the pack advances.

**Acceptance Scenarios**:

1. **Given** an installed git-sourced pack with a dirty working tree or local commits ahead of
   upstream, **When** `charter fetch` updates it, **Then** the local content is preserved or
   backed up (reported) before any hard reset — never silently discarded.
2. **Given** a pack configured with `ref: main`, **When** `charter fetch` updates it after the
   remote advanced, **Then** the reset target resolves to `origin/main` (the fetched
   remote-tracking ref) so the pack advances to the new upstream tip.

### User Story 4 - The destructive-op class stays closed by construction (Priority: P2)

A future contributor adds a new raw destructive filesystem operation to `runtime/migrate.py` or
`doctrine/sources/git_source.py`. The architectural gate must fail until it is routed through the
preservation guard or explicitly rationalised.

**Why this priority**: Prevents regression of this class; both modules are currently outside the
gate's scanned set. Guards the fix rather than adding user-facing behaviour.

**Independent Test**: Add an un-rationalised raw `unlink`/`rmtree`/`reset --hard` literal to a
scanned module in a scratch copy and assert the gate goes red; revert and assert green.

**Acceptance Scenarios**:

1. **Given** the fixed sites, **When** the destructive-op / mutation-ownership arch gate runs,
   **Then** it passes and reports no un-rationalised raw destructive literal in either module.
2. **Given** a newly introduced un-rationalised raw destructive literal in either module,
   **When** the gate runs, **Then** it fails (the gate is proven fail-able in both directions).

### Edge Cases

- A `.kittify/templates/*` file that differs from the package because it is a genuinely *outdated
  default* (the #285 version-skew case) is unprovable as customisation from content alone —
  handled fail-closed toward preservation (preserved/archived, not deleted), the same as a real
  customisation. Name/content identity is never treated as proof of ownership.
- A `local_path` that *is* a legitimate clone of the configured `url` continues through the normal
  update path unchanged (no refusal).
- A genuine partial-clone temp created by the fetch itself is still cleaned up (no orphaned temp
  dirs).
- `migrate --dry-run` performs no filesystem mutation and reports the same disposition the real
  run would apply.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | migrate preserves customised assets (#4961) | As an operator, I want `spec-kitty migrate` to never delete a `.kittify/` asset that differs from its package default, so that my team's customisations survive; the removal path is routed through the asset-preservation guard, unprovable content is preserved or archived (reported), and only byte-identical defaults are removed. | High | Open |
| FR-002 | migrate dry-run and messaging are honest (#4961) | As an operator, I want `migrate --dry-run` and the real run to label a differing customised asset as customised/preserved (never "superseded (outdated defaults)"), and never report "removed" for a file that was preserved, so that the output tells the truth. | High | Open |
| FR-003 | git-source first-install never deletes a pre-existing pack (#4960) | As an operator, I want a git-source `charter/doctrine fetch` to clone into a fresh staging directory and swap into place only on success — and to refuse up front when `local_path` exists and is not a clone of `url` — so that a failed clone never `rmtree`s my hand-authored pack; only a fetch-created temp is ever removed. | High | Open |
| FR-004 | git-source update preserves local edits and advances (#4989) | As an operator, I want the git-source update path to dirty/ahead-check and preserve-or-back-up local pack content (reported) before any `git reset --hard`, and to resolve the reset target against `origin/<ref>`, so that committed/uncommitted directives are never silently discarded and a configured `ref` actually advances the pack. | High | Open |
| FR-005 | Close the class in the architectural gate | As a maintainer, I want the destructive-op / mutation-ownership arch gate to scan `runtime/migrate.py` and `doctrine/sources/git_source.py` so that any future un-rationalised raw destructive literal in those modules fails CI, and the existing line-pinned allowlist entry for the git-source reset is re-pinned or removed to match the fix. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fail-closed toward preservation | On any ambiguity about ownership (differs-from-package, unreadable, non-boolean, probe error), the flow preserves/backs up rather than destroys; 0 code paths delete or reset user content on unproven ownership. | Reliability | High | Open |
| NFR-002 | Honest exit + messaging | Preservation is signalled via diagnostic/verdict with the backup path reported; the command still exits 0 on success and never prints a false "removed"/"reset"/"normalized" for content it preserved. 0 false-success messages. | Reliability | High | Open |
| NFR-003 | Reuse the shared preservation primitives | The fix routes through existing `asset_preservation` primitives (`guard_destructive_removal`, `backup_before_overwrite`, `archive_into`) and the existing dirty-check (`git/ref_advance` residue-aware predicate); 0 new bespoke backup/ownership frameworks introduced. | Maintainability | High | Open |
| NFR-004 | No behavioural regression for genuine duplicates | Byte-identical shipped defaults are still removed by migrate; a `local_path` that is a valid clone of `url` still updates normally. Existing green tests for these paths remain green (adjusted only where they pinned the defect). | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | ATDD red-first | Each FR carries at least one issue-pinned `@pytest.mark.regression` reproduction that is RED on the mission base and GREEN after the fix; tests that pinned the defect are re-pinned to the corrected contract, never weakened or deleted. | Technical | High | Open |
| C-002 | No CLI version bump | These are bug fixes; do not bump the CLI version or touch `__init__.py` version/CHANGELOG version gating solely for this mission (a CHANGELOG *entry* documenting the fix is expected). | Technical | High | Open |
| C-003 | git-source has no manifest | The git-source paths cannot use manifest/prover ownership proof (no shipped manifest for a fetched pack); they use the clone-to-temp-swap + backup primitives, mirroring the existing atomic-install-with-backup pattern in `doctrine/snapshot.py`. | Technical | Medium | Open |
| C-004 | Deferred, not silently dropped | The following are explicitly OUT of scope and tracked elsewhere: the #4961 P2 `.kittify/missions/**` counterpart-lookup miss (recoverable move-to-overrides; own ticket); the encoding cluster #4968 / #4962 / #4946; the skills-CRLF bug #4998; and the merge-integrity items under epic #5001. | Business | Medium | Open |

### Key Entities

- **`.kittify/` project asset**: an operator-visible file under a project's `.kittify/` (templates,
  missions, agent configs) that may be a shipped default, a customised shipped default, or a
  genuinely user-created file. Ownership is proven by content hash / managed-path / canonical
  marker — never by name.
- **Org pack (`local_path`)**: a git-sourced doctrine/charter pack directory, possibly outside the
  repository, possibly hand-authored, possibly with local commits ahead of upstream.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 of the three seed defects reproduce after the fix — the three issue-pinned
  regression tests are RED on the mission base and GREEN on the fix tip.
- **SC-002**: 100% of operator-authored content in the covered flows is recoverable after a
  destructive-trigger run (preserved in place, moved, or in a reported backup) — no path deletes
  or resets it on unproven ownership.
- **SC-003**: A configured git-source pack with `ref: <branch>` advances to the new upstream tip
  after `charter fetch` (the "never advances" defect is gone).
- **SC-004**: The architectural gate covers both previously-unrouted modules and is proven
  fail-able; no un-rationalised raw destructive literal remains in either module.
