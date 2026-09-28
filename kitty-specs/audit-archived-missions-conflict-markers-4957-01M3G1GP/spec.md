# Mission Specification: Audit archived missions for committed git conflict markers

**Mission Branch**: `issue-4957-archived-conflict-markers`
**Created**: 2026-09-27
**Status**: Draft
**Input**: User description: "audit archived missions for committed git conflict markers (pre-existing corpus corruption class) — spec-kitty/spec-kitty#4957"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repair the confirmed corrupted archived artifact (Priority: P1)

As a spec-kitty maintainer, I want the one confirmed real conflict-marker corruption in the
archived corpus repaired — keeping the lineage that actually shipped — so that the historical
record stops carrying unparseable, unresolved-merge content and downstream tooling (Activity Log
readers, humans skimming mission history) sees a coherent record instead of raw `<<<<<<<` /
`=======` / `>>>>>>>` text.

**Why this priority**: This is the concrete, already-identified defect the issue was filed over
(#4957, escalated from #4936/#4880's precedent). Without the repair, the corpus still carries the
exact corruption class the issue exists to close.

**Independent Test**: `git grep -nE '^(<<<<<<<|>>>>>>>) ' -- kitty-specs/` on the mission's final
commit returns zero hits (the one exemption in `tests/git_ops/test_git.py` lives outside
`kitty-specs/`, so this scoped grep needs no exemption filtering). Diffing the repaired file
against its pre-mission blob shows only the marker lines and the losing (`5eda48f7`) side removed;
every HEAD-side Activity Log line that sat between the `<<<<<<< HEAD` marker and the `=======`
marker is preserved verbatim and in order, and no line from the losing side survives.

**Acceptance Scenarios**:

1. **Given** `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
   carries the botched-merge block at lines 758–773 (`<<<<<<< HEAD` … `=======` … `>>>>>>> 5eda48f7 (chore: Start WP01 implementation [claude-planner])`),
   **When** the correction is applied, **Then** the file contains every `HEAD`-side Activity Log
   line that originally sat between the `<<<<<<< HEAD` marker (line 758) and the `=======` marker
   (line 771) — the `df2dac046057f738cde3f172385faf474315a29d` lineage, confirmed an ancestor of
   `main` via `git merge-base --is-ancestor df2dac046 main` — preserved verbatim and in order, with
   no marker lines and no `5eda48f7`-side content surviving (that commit is confirmed **not** an
   ancestor of `main` via the same check).
2. **Given** the repaired file, **When** `git grep -nE '^(<<<<<<<|>>>>>>>) '` is run over
   `kitty-specs/`, **Then** it returns zero matches.

---

### User Story 2 - Close the defect class with a non-vacuous, always-on guard (Priority: P1)

As a spec-kitty maintainer, I want a fast, always-on test that fails the instant any tracked file
in a PR introduces a real conflict-marker line, so the next botched merge reds on the PR that
creates it instead of surfacing years later on an unrelated innocent PR (the exact trap #4957
documents: #4880's corruption was masked by a path-filtered shard and only surfaced via #4936's
unrelated shard un-skip).

**Why this priority**: Repairing the one known instance (User Story 1) does nothing to prevent a
recurrence. Standing Order #5 (architectural gate discipline) requires closing defect classes by
construction with a non-vacuous gate, not a one-off fix.

**Independent Test**: Add a synthetic conflict-marker line to a non-exempted fixture path and run
the new guard test directly (`pytest tests/architectural/test_archive_root_byte_identical.py -k
<guard_test_name>`) — it must fail. Remove the synthetic line — it must pass. This is the
self-mutation proof Standing Order #5 requires.

**Acceptance Scenarios**:

1. **Given** the current repository state after the User Story 1 repair, **When** the new guard
   test runs, **Then** it passes with a non-empty, real count of scanned files (a concrete floor —
   it does not vacuously pass over zero files).
2. **Given** a fixture that plants a line matching `^(<<<<<<<|>>>>>>>) ` in a path outside the
   exemption allowlist, **When** the guard test's self-mutation check runs against that fixture,
   **Then** the guard reports a failure identifying the offending path and line.
3. **Given** `tests/git_ops/test_git.py`'s intentional `conflict_content` fixture (lines 452–457,
   used to test `GitVCS` marker parsing), **When** the guard runs over the real repository tree,
   **Then** that file is excluded via the exemption allowlist and does not fail the guard.
4. **Given** a simulated environment where the guard cannot enumerate tracked files (e.g., `git`
   is unavailable or the working tree is unreadable), **When** the guard runs, **Then** it raises
   or fails — it never silently reports success or a zero-file scan as a pass.
5. **Given** a fixture subtree containing a known, independently-counted `N` tracked files with
   zero conflict-marker lines — `N` counts every file the guard enumerates in that subtree,
   including any binary/non-text file among them (FR-004's floor is defined over files enumerated,
   not files regex-matched; see Edge Cases) — **When** the guard runs scoped to that subtree,
   **Then** it reports a scanned-file count exactly equal to `N` — tying the self-reported floor
   (FR-004) to an independently verifiable ground truth, not merely a non-empty count.
6. **Given** a fixture exemption frozenset augmented with one spurious entry beyond this mission's
   landed baseline, **When** the shrink-only ratchet test (FR-005/FR-008) runs against that
   fixture, **Then** it fails, identifying the unexpected growth — proving the ratchet is a real
   negative rather than a check that would pass identically before any growth occurred.

---

### User Story 3 - Land the repair through the existing operator-sanctioned carve-out (Priority: P2)

As a spec-kitty maintainer, I want the User Story 1 correction registered as a fourth entry in the
existing `_OPERATOR_SANCTIONED_CORRECTIONS` mechanism in
`tests/architectural/test_archive_root_byte_identical.py` (which already holds three entries: one
`status.json` correction from the #4936 precedent, plus two more `status.json` corrections landed
together citing #4972), so this mission's own PR can pass the always-on `archive-freeze` CI job
despite necessarily differing from `merge-base(HEAD, main)` on a frozen archive-root path.

**Why this priority**: Without this, the always-on `archive-freeze` job (`.github/workflows/ci-router.yml`,
job `archive-freeze`, invoking `tests/architectural/test_archive_root_byte_identical.py`) reds on
this mission's own diff, because the corrected file necessarily differs from the pre-mission
baseline under `kitty-specs/` (one of the four frozen archive roots). This is process plumbing
for User Story 1 to land at all, not a new capability — hence P2 relative to the repair and guard.

**Independent Test**: Run
`pytest tests/architectural/test_archive_root_byte_identical.py::test_no_preexisting_archived_file_was_modified`
on the mission branch. It passes because the corrected path is now a declared, named entry in
`_OPERATOR_SANCTIONED_CORRECTIONS`; every other archived path remains byte-identical to
`merge-base(HEAD, main)`.

**Acceptance Scenarios**:

1. **Given** the repaired file differs from `merge-base(HEAD, main)`, **When** the byte-identical
   freeze test runs, **Then** it passes because
   `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
   is present in `_OPERATOR_SANCTIONED_CORRECTIONS` as a fourth, explicitly-commented entry
   following the same pattern as the three existing entries (one from #4936, two more from #4972).
2. **Given** any other archived-root file not in the exemption or correction sets, **When** the
   freeze test runs, **Then** it still fails on any byte difference from `merge-base(HEAD, main)` —
   this mission does not weaken the freeze for anything else.

---

### Edge Cases

- What happens when the guard's file-enumeration step (`git ls-files` or equivalent) returns an
  empty list on an otherwise healthy checkout? The guard must fail/raise rather than silently
  report zero conflict markers as a pass (concrete-floor requirement, FR-004).
- What happens when the guard runs in a shallow or `fetch-depth: 0`-less checkout where `git
  merge-base` cannot resolve? The new conflict-marker guard is a static content scan over the
  current tree (`git ls-files` + per-file content match), not a diff against a historical ref, so
  it does not depend on `merge-base` resolution at all — this sidesteps the failure mode the
  pre-existing byte-identical freeze test has. See Clarifications (h) for the explicit statement
  of this design choice and its limits.
- How does the guard treat the one legitimate exemption (`tests/git_ops/test_git.py`)? Via a
  frozenset-keyed-by-relative-path allowlist whose *shape* mirrors `_APPEND_ONLY_SPINE_EXCEPTIONS`'s
  — but whose shrink-only *enforcement* is new, introduced by this mission for the first time:
  `_APPEND_ONLY_SPINE_EXCEPTIONS` itself has no dedicated growth/shrink test to mirror (FR-005/NFR-003).
- What happens if a future contributor tries to grow the exemption allowlist to hide a new,
  non-fixture conflict marker? The shrink-only ratchet test (FR-005) fails any growth beyond the
  baseline set recorded at this mission's landing, forcing an explicit, reviewed decision rather
  than a silent widening.
- What happens to binary or non-text tracked files during the scan? The guard must not crash on
  them: a per-file binary/decode failure is skipped and logged at the per-file level (never fatal
  to the whole guard run) — and the skipped file is still counted toward FR-004's scanned-file
  floor, because that floor is defined over files *enumerated* (via `git ls-files` or equivalent),
  not over files successfully fed into the regex match — while the skip itself is separately logged
  for visibility, so a skip can never silently shrink the floor into a false "clean" result nor hide
  which files were not content-scanned. NFR-002's "fatal" language is scoped to enumeration-level
  failures only (git unavailable, an archive root unreadable) — this per-file skip/log-and-continue
  behavior is the more coherent reading given the guard's purpose (catching real conflict-marker
  corruption, not crashing on legitimate binary blobs).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Repair the WP01 Activity Log conflict-marker corruption | As a maintainer, I want the botched-merge block in `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md` (lines 758–773) resolved to the `HEAD` (`df2dac046`) side so the file is valid, coherent Markdown with no residual marker text. | High | Open | [build] | no |
| FR-002 | Register the repair in `_OPERATOR_SANCTIONED_CORRECTIONS` | As a maintainer, I want the corrected path added as a fourth, explicitly-commented entry in the existing carve-out frozenset in `tests/architectural/test_archive_root_byte_identical.py` (which already holds three entries: one from the #4936 precedent, two more from #4972), following the same pattern, so the always-on `archive-freeze` job passes on this mission's own PR without weakening the freeze for any other path. | High | Open | [build] | no |
| FR-003 | Add an always-on, repo-wide conflict-marker guard test | As a maintainer, I want a new test function in `tests/architectural/test_archive_root_byte_identical.py` (the file `ci-router.yml`'s always-on `archive-freeze` job already invokes by name — no workflow edit needed) that scans tracked repository content for lines matching `^(<<<<<<<|>>>>>>>) ` and fails on any hit outside the declared exemption allowlist, so a future botched-merge artifact reds on the PR that introduces it. | High | Open | [build] | no |
| FR-004 | Guard has a concrete, ground-truth-tied floor | As a maintainer, I want the guard test's self-reported scanned-file count asserted both non-empty and exactly equal to the count of files actually enumerated (via `git ls-files` or equivalent) for that same invocation — not merely the subset of those files successfully fed into the regex match after any per-file binary/decode skip (see Edge Cases) — verified against an independently-counted fixture subtree, not merely asserted non-empty, so neither an enumeration failure nor a hardcoded literal count can masquerade as "no conflict markers found." | High | Open | [build] | no |
| FR-005 | Guard exemption set is shrink-only | As a maintainer, I want the guard's exemption allowlist (containing exactly `tests/git_ops/test_git.py` for its intentional `conflict_content` fixture) enforced as a shrink-only ratchet — a new enforcement mechanism for this exemption set (see NFR-003), extending by analogy the repo-wide Burn-down Policy discipline rather than mirroring existing enforcement of `_APPEND_ONLY_SPINE_EXCEPTIONS`, which today has no dedicated growth/shrink test of its own — so the exemption set can shrink over time but never silently grow to hide a real corruption. | Medium | Open | [build] | no |
| FR-006 | Guard self-mutation test proves non-vacuity | As a maintainer, I want a companion test that plants a synthetic conflict-marker line in a non-exempted fixture and asserts the guard catches it, so the guard's pass on the real tree is proven to be a real negative rather than a probe that cannot see anything (Standing Order #5 / tactic `acceptance-criteria-non-vacuity`). | High | Open | [build] | no |
| FR-007 | Guard fails closed when it cannot scan | As a maintainer, I want the guard to raise/fail — never silently pass — when file enumeration fails (git unavailable, an archive root unreadable, or any other enumeration error), so a broken scan is never mistaken for a clean repository. | High | Open | [build] | no |
| FR-008 | Shrink-only ratchet has a positive control | As a maintainer, I want a companion test proving the exemption allowlist's shrink-only ratchet (FR-005/NFR-003) actually fails when a fixture augments the exemption frozenset with a spurious entry beyond its landed baseline — the same self-mutation pattern FR-006 uses for the marker-scan guard — so the ratchet's pass on the real tree is proven to be a real negative rather than a check that would pass identically before any growth occurred (Standing Order #5 / tactic `acceptance-criteria-non-vacuity`). | High | Open | [build] | no |
| FR-009 | Post current carve-out membership to issue #4956 | As a maintainer, I want the mission's implementation/PR-closing step to post a comment directly on GitHub issue #4956 enumerating the full, current `_OPERATOR_SANCTIONED_CORRECTIONS` membership (all four entries, after this mission's addition) and the correct current line reference for the exemption-check clause in `tests/architectural/test_archive_root_byte_identical.py`, so the issue itself — not just this mission's PR body — carries an accurate starting point for whoever closes it next, instead of the stale single-entry, wrong-line-number body it has today. The comment must explicitly state it is an informational correction only, posted from mission #4957, and that it does not claim or commit to closing #4956 (see C-003 — this mission is out of scope for that cleanup). | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Guard runtime stays within the existing job budget | The new guard test adds no more than a few seconds to `tests/architectural/test_archive_root_byte_identical.py -q`'s current runtime (measured baseline: `test_no_preexisting_archived_file_was_modified` alone ran in 1.99s during this mission's baseline capture; the whole three-file baseline ran in 276.09s dominated by the unrelated `test_public_witnesses.py` suite) so the always-on `archive-freeze` CI job's cost profile does not materially change. | Performance | Medium | Open |
| NFR-002 | Fail-closed on scan failure | Any condition that prevents the guard from completing file *enumeration* (git command failure, an archive root or working tree unreadable, or an unexpectedly empty result where FR-004 expects non-empty) must raise a test failure, never return/print a success or a "0 findings" result silently. A per-file binary/decode failure encountered during the *content scan* (after enumeration has already succeeded) is not scoped by this fatal requirement — see Edge Cases (binary/non-text files) for the per-file handling and its FR-004 floor-count interaction. | Reliability | High | Open |
| NFR-003 | Exemption growth is test-gated | Any growth of the exemption frozenset beyond this mission's landed baseline must fail a dedicated shrink-only test (FR-005/FR-008) until an explicit code review re-baselines it. No such growth/shrink enforcement exists today for `_APPEND_ONLY_SPINE_EXCEPTIONS` or `_OPERATOR_SANCTIONED_CORRECTIONS` — neither frozenset is registered in `tests/architectural/_baselines.yaml`, and no test in `tests/` currently gates either one's size — so this mission introduces that enforcement for the first time for this exemption set, extending by analogy the repo-wide Burn-down Policy discipline in `.kittify/charter/charter.md` (growth on a baselined allowlist FAILS CI, shrinkage WARNS) rather than mirroring an existing precedent specific to this file. This is a deliberate, documented deviation from registering in `_baselines.yaml` itself, not a silent bypass — see Clarification (k) for why. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No CI workflow edit | `.github/workflows/ci-router.yml` is not modified — the new guard is a test function added to the file its `archive-freeze` job already invokes by name (`tests/architectural/test_archive_root_byte_identical.py`). | Technical | High | Open |
| C-002 | Two-file blast radius | Changes are confined to `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md` (content repair) and `tests/architectural/test_archive_root_byte_identical.py` (carve-out entry + guard test function + self-mutation test + shrink-only allowlist test + shrink-only positive-control test, FR-008). No edits to `packs/built-in/` doctrine, agent profiles, or any other archived mission file. (FR-009's GitHub issue #4956 comment is a tracker action taken during the mission's PR-closing step, not a file change, and does not expand this blast radius.) | Technical | High | Open |
| C-003 | Sequencing with #4956 | This mission lands before issue #4956, which removes all four `_OPERATOR_SANCTIONED_CORRECTIONS` entries (the three existing entries — one from #4936, two from #4972 — plus this mission's fourth) and the whole carve-out mechanism, once every correction is baseline on `main`. This mission does not perform that cleanup; it only adds the fourth entry. Per FR-009, the mission's implementation/PR-closing step posts a comment directly on GitHub issue #4956 enumerating the full, current four-entry membership and the correct current line reference for the exemption-check clause, so the issue itself — not just this mission's PR body — carries an accurate starting point for whoever picks it up next. | Business | Medium | Open |

### Key Entities *(include if feature involves data)*

- **Archived mission artifact**: any tracked file under one of the four frozen archive roots
  enforced by `tests/architectural/test_archive_root_byte_identical.py` — `kitty-specs/`,
  `.kittify/mission-state-audit/quarantine/`, `kitty-ops/`, `.kittify/missions/` (this is the
  current, code-verified root set; the issue body's reference to
  `.kittify/migrations/mission-state/quarantine/` names the pre-#4928 path, since repointed — see
  Clarifications). Frozen byte-identical to `merge-base(HEAD, main)` except via the append-only
  spine exception or an operator-sanctioned correction.
- **Conflict-marker guard**: the new always-on test function scanning tracked repository content
  for lines anchored `^(<<<<<<<|>>>>>>>) `, with a concrete non-empty file-count floor, a
  self-mutation proof, and a shrink-only exemption allowlist.
- **Exemption allowlist**: a frozenset of relative paths (currently exactly
  `tests/git_ops/test_git.py`) whose marker-like content is a known, intentional fixture rather
  than corruption; grows only through explicit code review, never silently.
- **Operator-sanctioned correction**: an entry in `_OPERATOR_SANCTIONED_CORRECTIONS` naming a
  frozen-root file whose one-off, operator-reviewed correction is exempted from the byte-freeze
  diff for exactly that path, distinct from the exemption allowlist above (a correction is a
  one-time fix of corrupt content; an exemption is a standing, intentional non-corruption).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `git grep -nE '^(<<<<<<<|>>>>>>>) ' -- kitty-specs/ .kittify/missions/ kitty-ops/ .kittify/mission-state-audit/quarantine/` returns zero hits on the mission's final commit. — [build] · no-op passable: no
- **SC-002**: `pytest tests/architectural/test_archive_root_byte_identical.py tests/git_ops/test_git.py tests/upgrade/preview_support/test_public_witnesses.py` passes with a pass count at or above this mission's recorded baseline (48 passed, 0 failed, captured on `main` @ `46ea5bd7f` before any change in this mission) and zero new failures attributable to this diff. — [ratchet] · no-op passable: no
- **SC-003**: The new guard test's self-mutation fixture (FR-006) fails when a synthetic marker is planted in a non-exempted path and passes once it is removed — proving the guard is not a blind probe. — [build] · no-op passable: no — paired with SC-001 as the guard's positive control (SC-001 is the real-tree negative; this is the planted-marker positive on the same regex).
- **SC-004**: The exemption shrink-only test (FR-005 / NFR-003) fails if the exemption frozenset ever contains more than this mission's landed baseline (`{"tests/git_ops/test_git.py"}`) without an explicit re-baseline. — [build] · no-op passable: no — paired with SC-003's positive-control pattern: FR-008's dedicated fixture-augmentation test (Acceptance Scenario 6 of User Story 2) proves the growth-detection assertion is a real negative, not a check that would pass identically before any growth occurred.

## Clarifications / Decisions

These decisions were surfaced by a readiness probe ahead of this spec and are recorded here as
this mission's binding scope, each re-verified independently against this checkout rather than
taken on the probe's word alone (citations are repo-relative paths or issue numbers only — no
absolute filesystem paths appear anywhere in this mission's artifacts).

**(a) Liveness — independently reproduced on this checkout.** `git grep -nE
'^(<<<<<<<|>>>>>>>) '` at the current commit (`f7aa28670`, scaffolded from `main` @ `46ea5bd7f`)
hits exactly two files:
`kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md:758`
and `:773`, plus `tests/git_ops/test_git.py:453` and `:457`. The first is the real repair target
(FR-001); the second is confirmed (by reading the surrounding test body) to be the intentional
`conflict_content` fixture in `test_conflict_marker_parsing`, exercising `GitVCS` marker parsing —
it is an exemption (FR-005), not a repair target.

**(b) Sequencing — re-verified against the live frozenset, not the issue's stale count.**
`_OPERATOR_SANCTIONED_CORRECTIONS` (`tests/architectural/test_archive_root_byte_identical.py:150`)
already holds **three** entries, not two: the #4936-precedent `status.json` correction (commit
`f0fb552d6`, 2026-09-23), plus two more `status.json` corrections landed together in commit
`0ceff68a06` (2026-09-25, citing #4972). This mission lands before #4956 (see C-003). It repairs
the WP01 file and adds it as a **fourth** `_OPERATOR_SANCTIONED_CORRECTIONS` entry (FR-002) so this
mission's own PR does not red the always-on `archive-freeze` job on its own necessarily-differing
diff. #4956 later removes all four entries plus the mechanism, once every correction is baseline on
`main`; that cleanup is explicitly out of scope for this mission (C-003). Issue #4956 itself
(fetched 2026-09-27: OPEN, unassigned) is already stale — its body describes removing a single
entry and cites "the line-679 skip," but the exemption-check clause is now at line 728 (after the
two #4972 entries were added) and there are three entries to account for even before this
mission's fourth. Per FR-009, this mission's PR-closing step posts a comment directly on #4956
correcting both the membership count and the line reference, rather than only noting the drift in
this mission's own PR body (which the next person to open #4956 would never see).

**(c) Which side to keep — independently re-verified.** `git merge-base --is-ancestor df2dac046
main` returns true (`df2dac046057f738cde3f172385faf474315a29d`, "chore: Move WP01 to done on spec
025 [claude-reviewer]", is an ancestor of `main`); `git merge-base --is-ancestor 5eda48f7 main`
returns false (`5eda48f73d10405352bb13896a99e2acf3dbd185`, "chore: Start WP01 implementation
[claude-planner]", is not). This confirms the `HEAD` side of the marker (the completed-review
lineage) is the side that actually shipped to `main`, and the `5eda48f7`-named side is an orphaned
lineage. FR-001 keeps the `HEAD` side and deletes the marker lines and the losing side entirely.

**(d) Guard design.** The new guard is a single always-on test function appended to
`tests/architectural/test_archive_root_byte_identical.py` — the exact file `ci-router.yml`'s
`archive-freeze` job (`.github/workflows/ci-router.yml:489`) already invokes by name, so no
workflow edit is needed (C-001). The regex is anchored `^(<<<<<<<|>>>>>>>) ` (trailing space
required), not a bare `^=======$`: a repo-wide check on this checkout confirms both forms
currently hit the identical two files, so there is no live false positive either way, but the
anchor-pair form is structurally safer going forward because a Markdown setext-heading underline
(`=======` under a heading) can collide with a bare `^=======$` check while it cannot collide with
the seven-character anchor pair. The one exemption is `tests/git_ops/test_git.py`, added to a
frozenset-keyed-by-relative-path allowlist whose *shape* follows the existing
`_APPEND_ONLY_SPINE_EXCEPTIONS` a few lines above `_OPERATOR_SANCTIONED_CORRECTIONS` in the same
file — but the shrink-only *enforcement* guarding it is new: `_APPEND_ONLY_SPINE_EXCEPTIONS` has no
dedicated growth/shrink test of its own today, so this mission introduces that enforcement
mechanism for the first time for this exemption set (FR-005/NFR-003).

**(e) Ledger SK-249 (filed upstream as #4954).** The ledger entry headed "SK-249 — the
historical-preservation gate and the mission-corpus audit are mutually unsatisfiable once invalid
JSON reaches an archive root" (the ledger has a second, unrelated SK-249 heading elsewhere; this
entry is identified by its heading text and by #4954, not by line number, per the ledger's
known-unreliable numbering) documents the #4880/#4936 precedent that originated this mission's
carve-out mechanism (FR-002) — a mechanism since extended twice more by the #4972 landing (see
Clarification (b)), and extended a fourth time by this mission. Its closing note — *"A conflict-marker check over `kitty-specs/**` at
commit time would have caught it while the bytes were still mutable"* — names a **commit-time**
(pre-commit-hook) prevention as the ideal. This mission's guard (FR-003) is a **CI-time** test,
not a commit-time hook. That gap is deliberate, not silently ignored: a repo-wide pre-commit hook
would need to be installed by every contributor to have any effect, and this repository's own
workflow (documented in `CONTRIBUTING.md` / `CLAUDE.md`) does not assume or enforce universal local
hook installation, whereas the always-on `archive-freeze` CI job already runs on every PR shape
regardless of contributor tooling. A CI-time gate that fires on the introducing PR still achieves
the ledger's stated goal — catching it while still mutable, before it becomes years-old baseline —
for every contributor uniformly, without adding an opt-in local-tooling dependency. A commit-time
hook remains a possible *future* hardening (and would need its own mission to design distribution,
opt-out handling, and CI-vs-hook divergence), but is deliberately deferred here rather than folded
into this mission's scope (C-002's two-file blast radius).

**(f) Baseline (measured on this checkout before any change, at `main` @ `46ea5bd7f`, scaffolded
as `f7aa28670`).** `pytest tests/architectural/test_archive_root_byte_identical.py
tests/git_ops/test_git.py tests/upgrade/preview_support/test_public_witnesses.py` → **48 passed,
0 failed** (276.09s wall clock, dominated by the unrelated `test_public_witnesses.py` corpus-scan
suite; `test_no_preexisting_archived_file_was_modified` itself ran in 1.99s). This is the
red-main-discipline baseline (Standing Order #9) this mission's tests are attributed against —
SC-002 requires meeting or exceeding this exact count, not "tests pass" in the abstract.

**(g) Standing Order #5 — architectural gate discipline.** Verbatim from
`.kittify/charter/charter.md`: *"Close defect classes by construction with a NON-VACUOUS call-site
gate (concrete floor + self-mutation test + shrink-only allowlist); a gate-unmask cannot
self-validate."* FR-004 (concrete, ground-truth-tied floor), FR-006 (self-mutation test for the
marker-scan leg), and FR-005/NFR-003 (shrink-only allowlist) with FR-008 as that allowlist's own
non-vacuity positive control — mirroring FR-006's role for the marker-scan leg — are the explicit,
testable requirements this standing order demands of the new guard; none is optional or foldable
into the others.

**(h) Silent-success requirement.** FR-007/NFR-002 require the guard to fail/raise, never
silently pass, when it cannot complete a scan. Because the new guard is a static content scan over
the current tree (`git ls-files` plus a per-file regex match) rather than a diff against a
historical ref, it does not depend on `git merge-base` resolution and so does not inherit the
existing byte-identical freeze test's shallow-clone/`fetch-depth: 0` failure mode — but it still
must fail closed if file enumeration itself fails (git binary missing, permission error, or an
unexpectedly empty result where a non-empty one is expected per FR-004). This is stated explicitly
rather than left implicit, per this repository's dominant failure-mode class (a code path that
returns `None`, writes `unknown`, or counts `0` and calls it success).

**(i) Tracer files.** Per Standing Order #3 and the design pipeline's Plan-phase seeding point,
`tracer-tooling-friction.md`, `tracer-approach.md`, and `tracer-design-decisions.md` are not
created at this spec phase — they are seeded at plan phase per pipeline design. This spec records
the one piece of tooling friction encountered so far (item (j) below) so it is not lost before the
plan phase seeds the tracer file.

**(j) Reflexive tooling friction (for the plan-phase tracer file, not a spec defect).** Both
`spec-kitty agent mission create` (scaffolding this mission) and, independently, `spec-kitty
safe-commit --help` (checked while authoring this spec) first failed with a `StartupAssetError` /
`Error: slash_commands: Global asset input changed: <cache-path>; re-run the command` against a
stale global asset-freshness lock cache, then succeeded cleanly on an immediate, identical retry.
This is consistent, reproducible tooling friction (one retry resolves it every time observed so
far), not a spec-level defect — flagged here for the plan-phase tracer file to pick up.

**(k) Why the new exemption allowlist is not registered in `tests/architectural/_baselines.yaml`
(charter.md:599's Burn-down Policy) — a reasoned exception, not a silent bypass.** The charter's
Burn-down Policy states every mutable architectural allowlist is governed by a baseline there, with
growth-above-baseline failing CI. Read against the live mechanism
(`tests/architectural/test_ratchet_baselines.py`), registering a *new* gated module is not a bare
YAML edit: `_REQUIRED_TOP_LEVEL_KEYS` is a closed frozenset that a dedicated test
(`test_no_unregistered_baseline_keys_are_added`) fails on any unregistered key, and each registered
module's growth/shrink comparison is hand-wired per module (a dotted module path + attribute name
read via `_import_module_attr`, added to the growth and shrinkage test arms individually — there is
no generic "read any frozenset" path). Wiring the new marker-scan exemption allowlist through this
mechanism would therefore mean editing `tests/architectural/test_ratchet_baselines.py` as a third
file, which directly conflicts with C-002's binding two-file blast radius (Technical, High
priority) for this mission. This is also not a one-off gap this mission is inventing an excuse for:
`_APPEND_ONLY_SPINE_EXCEPTIONS` — the shape this mission's exemption allowlist already follows (see
Edge Cases and Clarification (d)) — lives in the exact same file and is *also* not registered in
`_baselines.yaml` today (independently re-verified via `grep -rn _APPEND_ONLY_SPINE_EXCEPTIONS
tests/`, which shows only its definition and one use site, no ratchet wiring), and no prior mission
has treated that as a Standing Order #6 violation. Given the closed-set registration mechanism's
real cost and this file's pre-existing precedent of guarding its own small, colocated allowlists
with bespoke tests rather than centralizing them in `_baselines.yaml`, FR-005/FR-008's bespoke
shrink-only test (extending the Burn-down Policy's discipline by analogy, per NFR-003) is the more
coherent choice for this mission's scope than expanding C-002's blast radius to retrofit the
centralized mechanism. A future mission remains free to migrate both this file's allowlists into
`_baselines.yaml` together as its own scoped piece of work. No tracker issue or
`SPEC-KITTY-LEDGER.md` entry is being filed for that follow-up here, and that omission is itself
deliberate rather than an oversight: unlike Clarification (b)'s `_OPERATOR_SANCTIONED_CORRECTIONS`
cleanup, which anchors to #4956 — an issue that already exists, is independently re-verified live
and stale on this checkout, and that FR-009 obligates this mission's own PR-closing step to correct
— this `_baselines.yaml` migration has no pre-existing tracker to attach to and no mandated action
tied to it. It is optional, low-priority tidying of a pre-existing gap — this same clarification
already establishes that `_APPEND_ONLY_SPINE_EXCEPTIONS` has sat unregistered and unflagged since
before this mission — not a newly introduced defect this mission owes a remediation trail for.
Filing a fresh tracker item for
every "a future mission could..." aside this spec names — see also Clarification (e)'s
commit-time-hook aside, deferred on the same reasoning and likewise without an opened issue — would
be disproportionate to work with no current urgency and no waiting owner.

**Drift flagged, not silently resolved.** The GitHub issue body's audit-target list (item 1 of the
"Ask") names `.kittify/migrations/mission-state/quarantine/` as one of the four archive roots.
This checkout's actual, code-enforced root set (`tests/architectural/test_archive_root_byte_identical.py`
`_ARCHIVE_ROOTS`, and its accompanying comment citing #4928) is
`.kittify/mission-state-audit/quarantine/` — the quarantine directory moved from the gitignored
`migrations/` path to the git-tracked `mission-state-audit/` path in #4928, after the issue text
was written. This spec scopes FR-001/FR-003 against the current, code-verified root set rather
than the issue's now-stale path.
