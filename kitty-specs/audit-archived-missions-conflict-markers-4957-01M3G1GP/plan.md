# Implementation Plan: Audit archived missions for committed git conflict markers

**Branch**: `issue-4957-archived-conflict-markers` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/audit-archived-missions-conflict-markers-4957-01M3G1GP/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

## Summary

Repair the one confirmed committed-conflict-marker corruption in the archived corpus
(`kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`,
lines 758–773), register that repair as a fourth entry in the existing
`_OPERATOR_SANCTIONED_CORRECTIONS` carve-out in
`tests/architectural/test_archive_root_byte_identical.py` so the always-on `archive-freeze`
CI job (`.github/workflows/ci-router.yml`, job `archive-freeze`, line 489, invoking this exact
file by name at line 502) does not red on this mission's own necessarily-differing diff, and
add a new always-on, non-vacuous conflict-marker guard (five new test functions) to the same
file so a future botched-merge artifact reds the PR that introduces it instead of surfacing
years later. Two files change; no CI workflow edit; one PR.

## Technical Context

**Language/Version**: Python 3.11+ (repo standard; the guard is a pytest test function, no
new runtime module).
**Primary Dependencies**: `git` (subprocess, via a new, narrowly-scoped
`_enumerate_tracked_files` helper added to the same file — the file's pre-existing
`_run_git`/`_git_bytes` helpers are left untouched; no new dependency), `pytest` (existing test
framework). No new third-party package.
**Storage**: N/A — no persisted state; the guard reads the working tree via `git ls-files` and
per-file content reads.
**Testing**: pytest, scoped to `tests/architectural/test_archive_root_byte_identical.py` plus
the mission's declared three-file baseline (`tests/git_ops/test_git.py`,
`tests/upgrade/preview_support/test_public_witnesses.py`) per spec.md Clarification (f)/SC-002.
**Target Platform**: Linux CI runner (`ubuntu-24.04`, per `ci-router.yml`); no
platform-specific behavior introduced.
**Project Type**: Single project — this is spec-kitty's own test suite, not a new
application surface.
**Performance Goals**: NFR-001 — the new guard adds no more than a few seconds to
`test_archive_root_byte_identical.py -q`'s current runtime (baseline
`test_no_preexisting_archived_file_was_modified` alone: 1.99s).
**Constraints**: C-001 (no CI workflow edit), C-002 (two-file blast radius), C-003 (#4956
sequencing — see FR-009).
**Scale/Scope**: One archived Markdown file byte-repair, one test file gaining a carve-out
entry plus five new test functions. No src/ change, no new module, no new CLI surface.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Standing Order #5 (Architectural gate discipline)** — verbatim from
  `.kittify/charter/charter.md`: *"Close defect classes by construction with a NON-VACUOUS
  call-site gate (concrete floor + self-mutation test + shrink-only allowlist); a gate-unmask
  cannot self-validate."* **PASS-BY-DESIGN**: FR-004 (concrete, ground-truth-tied floor),
  FR-006 (self-mutation positive control for the marker-scan leg), FR-005/NFR-003 (shrink-only
  exemption allowlist) with FR-008 as that allowlist's own non-vacuity positive control are all
  separately-failing test functions (Section B below) — none folded into another.
- **Standing Order #4 (Test remediation & bug-fix discipline / red-first)** — PASS-BY-DESIGN:
  every new test function is its own red-first proof (Section D); FR-001's repair has a
  distinct red-first demonstration (the FR-003 guard, run today, already fails against the
  live tree).
- **Standing Order #2 (Campsite cleaning)** — analyzed in Section E: no campsite-clean
  warranted (reasoned, not a default), because the touched file has no live complexity-ceiling
  or duplicate-literal violation today (`ruff check … --select C901` on the file: "All checks
  passed"; `_OPERATOR_SANCTIONED_CORRECTIONS`/`_APPEND_ONLY_SPINE_EXCEPTIONS` are each
  referenced exactly twice today, below the `>=3` Sonar S1192 threshold, and the mission's own
  additions add only a handful more references to named constants, not raw literal
  duplication).
- **Standing Order #6 (Canonical sources)** — PASS: scaffold verified byte-identical against
  the canonical template (Tooling section below); no improvised template.
- **Standing Order #3 (Mission tracer files)** — PASS: seeded this phase (Step 3 below).
- **Standing Order #7 (Git & workflow discipline)** — PASS-BY-DESIGN: one PR, operator merges
  (Section G).
- No Charter Check violations requiring justification — Complexity Tracking table below is
  empty by design.

## Project Structure

### Documentation (this mission)

```
kitty-specs/audit-archived-missions-conflict-markers-4957-01M3G1GP/
├── spec.md                       # DONE — R1-R6 reviewed, PASSED
├── plan.md                       # This file
├── tracer-tooling-friction.md    # Seeded this phase
├── tracer-approach.md            # Seeded this phase
├── tracer-design-decisions.md    # Seeded this phase
└── tasks/                        # Phase 2 output (/spec-kitty.tasks — not this phase)
```

No `research.md`, `data-model.md`, `quickstart.md`, or `contracts/` are produced: this mission
has no new data model, no new contract surface, and no open unknowns requiring research — the
spec's Clarifications (a)–(k) already resolved every open question against the live checkout.

### Source Code (repository root)

**Structure Decision**: No new source tree. Exactly two existing files change, per C-002:

```
kitty-specs/025-cli-event-log-integration/tasks/
└── WP01-git-dependency-setup-and-library-integration.md   # content repair (FR-001)

tests/architectural/
└── test_archive_root_byte_identical.py                     # carve-out entry (FR-002) +
                                                               # 5 new test functions (FR-003–008)
```

No `src/`, `packs/built-in/`, agent-profile, or any other archived-mission file changes. This
is a "single project" plan in the template's sense (no frontend/backend/mobile split) — the
Option-1/2/3 placeholder tree in the canonical template does not apply and is omitted rather
than filled with an irrelevant structure.

## Complexity Tracking

*Fill ONLY if Charter Check has violations that must be justified*

No violations. Table intentionally empty.

## Implementation Concern Map

> **Note**: Implementation concerns are NOT work packages and are NOT executable units.
> `/spec-kitty.tasks` translates these into executable WPs.

### IC-01 — Repair + carve-out registration (coupled via a claim-time dependency edge, landed as two commits in two lanes — see Section D's correction)

- **Purpose**: Resolve the WP01 conflict-marker corruption to the `HEAD` side and register the
  corrected path as the fourth `_OPERATOR_SANCTIONED_CORRECTIONS` entry in the same change, so
  the always-on `archive-freeze` job never sees a commit where the file is repaired but
  un-registered (which would red) or registered but un-repaired (which would defeat the
  mission's purpose).
- **Relevant requirements**: FR-001, FR-002, C-003.
- **Affected surfaces**:
  `kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`
  (lines 758–773 → resolved); `tests/architectural/test_archive_root_byte_identical.py` (the
  `_OPERATOR_SANCTIONED_CORRECTIONS` frozenset, lines 150–156, gains a fourth entry + comment
  block following the existing two-entry comment pattern immediately above it).
- **Sequencing/depends-on**: none (first concern); IC-02 is hard-gated on IC-01, not
  implemented in parallel — WP02 carries a claim-time `dependencies: [WP01]` edge and cannot
  even be claimed until WP01 reaches `approved`/`done` (see Section D's correction).
- **Risks**: Landing order coupling — resolved via that claim-time `dependencies: [WP01]`
  edge plus the operative discipline (stated in both WP files) of not pushing the mission
  branch or opening/updating a PR until both WPs reach `approved`/`done`; see Section D's
  correction for the full mechanism and why a literal same-commit landing is not achievable.

### IC-02 — Non-vacuous conflict-marker guard + shrink-only exemption ratchet

- **Purpose**: Add the always-on guard (FR-003/004/006/007) and the exemption shrink-only
  ratchet with its own positive control (FR-005/008) as five new, separately-failing test
  functions in the same file, closing the defect class by construction (Standing Order #5).
- **Relevant requirements**: FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, NFR-001, NFR-002,
  NFR-003.
- **Affected surfaces**: `tests/architectural/test_archive_root_byte_identical.py` only (new
  module-level exemption frozenset + five new `def test_*` functions; no new file).
- **Sequencing/depends-on**: hard-gated on IC-01, not "none strictly" — WP02 carries a
  claim-time `dependencies: [WP01]` edge and cannot be claimed until WP01 reaches
  `approved`/`done`; the guard's real-tree pass (FR-003 scenario 1) is only true once IC-01's
  repair has landed, but that is a consequence of the hard claim-time gate, not a separate,
  softer constraint — see Section D's correction.
- **Risks**: None beyond the standard red-first discipline (Section D); no external
  dependency, no workflow edit (C-001).

### IC-03 — Issue #4956 informational comment (tracker action, not a file change)

- **Purpose**: Post the FR-009 comment enumerating the full four-entry
  `_OPERATOR_SANCTIONED_CORRECTIONS` membership and the correct current exemption-check line
  reference (728) to GitHub issue #4956, as an explicit PR-closing-step action item — not a
  file change, so it does not expand C-002's blast radius.
- **Relevant requirements**: FR-009, C-003.
- **Affected surfaces**: none (tracker-only; `gh issue comment 4956 --body "..."`).
- **Sequencing/depends-on**: IC-01 (the four-entry membership and line-728 reference are only
  final once IC-01 lands).
- **Risks**: None — informational only; the comment explicitly disclaims closing #4956.

---

## A. Seam / module placement

C-002 names both files exactly; there is no seam ambiguity to resolve, but it is stated
explicitly per this mission's brief rather than left implicit:

- **`kitty-specs/025-cli-event-log-integration/tasks/WP01-git-dependency-setup-and-library-integration.md`**
  is the right (only) place for the content repair because it *is* the corrupted artifact —
  FR-001 names it exactly, and it is the sole file `git grep -nE '^(<<<<<<<|>>>>>>>) ' --
  kitty-specs/` currently matches outside the test fixture exemption (re-verified this phase,
  see Tooling section below).
- **`tests/architectural/test_archive_root_byte_identical.py`** is the right (only) place for
  both the carve-out entry and the new guard, because:
  - It already hosts `_OPERATOR_SANCTIONED_CORRECTIONS` (confirmed at lines 150–156 on this
    checkout — the frozenset opens at line 150, holds three existing entries at lines
    152–154, closes at line 156) and `_APPEND_ONLY_SPINE_EXCEPTIONS` (line 114) — both
    module-level constants in this exact file, re-read fresh this phase, not taken from
    spec.md's citation (spec.md cites line 150 for the frozenset and line 728 for the
    exemption-check clause — both independently re-confirmed byte-exact on this checkout).
  - `.github/workflows/ci-router.yml`'s `archive-freeze` job (job block starts line 489) runs
    `uv run --frozen pytest tests/architectural/test_archive_root_byte_identical.py -q` at
    line 502 — re-confirmed by direct grep this phase, not assumed from the spec. Adding test
    functions to this exact file means the always-on job picks them up with **zero** workflow
    edit (C-001) — the file is already the job's sole invocation target.
  - The exemption-check clause spec.md's Clarification (b) says moved from line 679 to line
    728 is confirmed still at **line 728** on this checkout (`if not
    path.startswith(_ARCHIVE_ROOTS) or path in _APPEND_ONLY_SPINE_EXCEPTIONS or path in
    _OPERATOR_SANCTIONED_CORRECTIONS:`), inside `test_no_preexisting_archived_file_was_modified`
    (function starts line 713).

## B. Concrete test functions to add (Standing Order #5 non-vacuity)

Charter `.kittify/charter/charter.md`, Quality & Tech-Debt Standing Orders, item 5, verbatim:

> **5. Architectural gate discipline.** Close defect classes by construction with a
> NON-VACUOUS call-site gate (concrete floor + self-mutation test + shrink-only allowlist); a
> gate-unmask cannot self-validate. After merge, run the full arch-gate sweep with a cross-base
> pre-existing check. → `DIRECTIVE_043`, `architectural-gate-non-vacuity`,
> `frozen-baseline-shrink-only-ratchet`, `post-merge-arch-gate-adjudication`.

Five **separately-failing** test functions (each its own `def test_*`, none folded into
another), added to `tests/architectural/test_archive_root_byte_identical.py`:

1. **`test_no_conflict_markers_in_tracked_files`** (FR-003/FR-004) — enumerates tracked files
   via `git ls-files` (through the new, narrowly-scoped `_enumerate_tracked_files` helper
   detailed in the fold-in note below — not the file's existing `_run_git`/`_git_bytes` call
   sites, which this mission leaves untouched; the new helper does reuse their env-hardening
   by name rather than re-deriving it), scans each for `^(<<<<<<<|>>>>>>>) ` (the anchor-pair regex from
   spec.md Clarification (d) — not a bare `^=======$`), skips the exemption allowlist, and
   asserts (a) zero matches outside the allowlist and (b) the self-reported scanned-file count
   is both non-empty **and** exactly equal to the count `git ls-files` itself enumerated for
   that invocation (FR-004's ground-truth tie — not merely "non-empty"). This is the real-tree
   negative control (paired with SC-001).

2. **`test_conflict_marker_guard_self_mutation_catches_synthetic_marker`** (FR-006) — plants a
   synthetic line matching the guard's regex in a `tmp_path`-based fixture file outside the
   exemption allowlist, asserts the guard (invoked as a helper function the guard test above
   also calls, not duplicated logic) reports a failure identifying that path and line; then
   removes the synthetic line and asserts it passes. This is the guard's own positive control,
   proving test 1's pass is a real negative, not a probe that cannot see anything.

3. **`test_conflict_marker_exemption_allowlist_is_shrink_only`** (FR-005/NFR-003) — asserts the
   live exemption allowlist equals exactly `{"tests/git_ops/test_git.py"}` (this mission's
   landed baseline) and fails if it ever contains anything beyond that set without an explicit
   re-baseline of this test. Mirrors the *shape* of `_APPEND_ONLY_SPINE_EXCEPTIONS` (Clarification
   (d)) but is new *enforcement* — no such growth/shrink test exists for either frozenset today
   (independently re-verified this phase: `grep -rn _APPEND_ONLY_SPINE_EXCEPTIONS tests/` shows
   only its line-114 definition and one line-728 use site, no ratchet wiring).

4. **`test_conflict_marker_exemption_shrink_only_ratchet_has_positive_control`** (FR-008) — a
   **distinct** test from #2 and #3: it constructs a fixture-augmented allowlist (the real
   allowlist plus one spurious extra path) and asserts the *shrink-only assertion logic* (the
   comparison test 3 performs, factored so both tests call the same comparator helper against
   different input sets — not copy-pasted) fails against the augmented fixture. This proves
   test 3 is a real negative — it would not have passed identically before any growth, because
   this test demonstrates growth *is* detected. This guards the allowlist-ratchet mechanism,
   which is a different mechanism from the marker-scan guard (FR-006) is a positive control
   for — the two self-mutation tests are not interchangeable.

5. **`test_conflict_marker_guard_fails_closed_on_enumeration_failure`** (FR-007/NFR-002) —
   monkeypatches the guard's file-enumeration call (the `git ls-files` subprocess invocation)
   to raise (simulating "git unavailable") and separately to return an empty result where a
   non-empty one is expected, and asserts the guard raises/fails in both cases rather than
   silently reporting zero conflict markers as a pass. This is the fail-closed leg — distinct
   from tests 1–4, which all assume enumeration succeeds.

A sixth scenario from spec.md (Acceptance Scenario 5 of User Story 2 — the ground-truth-tied
floor over an independently-counted `N`-file fixture subtree, including a binary file) is
folded into **test 1** above as an additional assertion against a small fixture subtree
(`tmp_path`-materialized, not a new tracked repo directory — keeping C-002's two-file blast
radius intact), rather than a seventh test function, because it exercises the *same* guard
invocation as test 1's real-tree assertion, just against a controlled fixture instead of the
live tree — folding it here avoids a redundant sixth guard invocation while still keeping it a
distinct, separately-assertable check within that test's body. Concrete mechanism: the file's existing `_run_git`/`_git_bytes` helpers are hardcoded to `-C
{REPO_ROOT}` (`REPO_ROOT` a fixed module-level constant) and are left completely untouched by
this mission — no signature change, and no new call added at any of their ~10 existing call
sites. Instead, the guard's own enumeration lives in a genuinely new, narrowly-scoped helper
used only by this guard's tests (never by the file's other pre-existing tests), parameterized
by root (`_enumerate_tracked_files(root: Path = REPO_ROOT)`, internally calling `git -C <root>
ls-files`). This new helper reuses `_git_bytes`'s env-hardening dict by name rather than
re-deriving it by hand: `_git_bytes` itself applies `GIT_NO_REPLACE_OBJECTS`,
`GIT_OPTIONAL_LOCKS=0`, and `SPEC_KITTY_ENABLE_SAAS_SYNC=0` unconditionally on every call it
makes — including its own pure-read callers (`cat-file blob`, `ls-tree`) — so there is no
read/write-adjacency conditionality in its actual behavior. The new helper follows that same
precedent: it applies all three vars unconditionally on every call it makes, for both the
real-tree scan and the fixture-subtree call below alike, with no conditional branching. The
fixture-subtree check git-inits a throwaway repo under `tmp_path`, commits the N fixture
files (including the binary one, so they are genuinely `git ls-files`-tracked per spec.md's AS5
wording, not a bare filesystem walk), and calls this same new helper with `root=tmp_path_repo` —
the real-tree scan and the fixture-subtree check both go through this one new helper, so there is
exactly one enumeration code path for the guard (the sense in which this remains the *same* guard
invocation), even though that path is new rather than reused from `_run_git`/`_git_bytes`. The
binary/non-text handling
(Edge Cases: a per-file decode failure is skipped-and-logged, not fatal, and still counts
toward the floor) is asserted as part of this same fixture-subtree check: the fixture includes
one deliberately non-UTF-8 binary file, and the assertion confirms it is (a) counted in the
enumerated-file floor and (b) does not raise or abort the scan.

## C. The gate set

Per `~/.hermes/skills/sk/SKILL.md` §Gates (re-verified 2026-09-23 against `.github/workflows/`
@ `6b4164dbf` — the hub table, not the overlay/design-pipeline's stale gate-bullet lists).
`make ci-parity` was run this phase against the current (spec-only) diff; its "Selected code
shards (0)" and job list are a partial preview (the diff does not yet touch either of this
mission's two target files), so the guard-touching selection below is reasoned statically from
`.github/workflows/ci-router.yml` and `.github/ci-module-registry.yml`, re-grepped fresh this
phase, per the brief's instruction.

**Enforced gates that apply to this mission's final diff** (exactly the two C-002 files):

| Gate | Applies? | Why |
|---|---|---|
| ruff lint + `ruff format --check` | Yes | Always-on, whole-repo; the new test functions must satisfy both. |
| `uv lock --check` | Yes (trivially) | Always-on; this mission adds no dependency, so it passes unchanged. |
| import-linter (banned API / TID251) | Yes (trivially) | Always-on; the new tests add a new `_enumerate_tracked_files` helper in the same file (the file's existing `_run_git`/`_git_bytes` helpers are left untouched), adding no new import crossing a boundary. |
| `spec-kitty regen --check` | Yes (trivially) | Always-on; confirmed this phase that `test_archive_root_byte_identical.py` is not a regen-manifest target (`grep -rn` across `*.yaml`/`*.yml`/`*.json` for the filename found no regen/generation registration) — hand-editing it is not "hand-patching a generated file." |
| terminology guard (`test_no_legacy_terminology.py`) | Yes (trivially) | Always-on; no `ceremony`/`status-writing` terms introduced. |
| layer rules / pyproject shape | Yes (trivially) | Always-on; no import-direction or package-shape change. |
| **archive-freeze** (`test_archive_root_byte_identical.py -q`) | **Yes — central** | Always-on; this IS the job whose invoked file gains the carve-out entry (FR-002) and the new guard tests. This mission's PR necessarily diffs a frozen archive-root path (the WP01 repair), which is exactly why FR-002/the carve-out entry exists. |
| `architectural-heavy` job | **No** | Re-confirmed this phase: its `if:` in `ci-router.yml` (lines ~520–536) fires only when one of a specific list of `changes` outputs is true (status/review/next/lanes/dashboard/upgrade/cli/charter/agent/kernel/glossary/execution_context/core_misc/unit/specify_cli_runtime) — none of which this diff's two paths match. Even if it ran, its own pytest invocation explicitly `--deselect`s `test_archive_root_byte_identical.py` (line ~560), so it would never double-run this mission's new tests regardless. |
| `tests (corpus)` (`tests-corpus` job, marker-selected `-m "corpus and not windows_ci"`) | **Yes** | Its path filter (`ci-router.yml` lines 168–174) includes `kitty-specs/**/tasks/**`, which the WP01 repair path matches exactly, so this row's "Yes" verdict is correct. Note this is unrelated to why `tests/upgrade/preview_support/test_public_witnesses.py` is in spec.md's SC-002 baseline command: that file is `pytest.mark.integration`-marked (not `corpus`), and `.github/ci-module-registry.yml` has no entry for `tests/upgrade/preview_support`, so no per-PR CI job (this one included) actually exercises it — it is in the baseline command purely as an extra local safety check the mission chose to run (per spec.md Clarification (f)), not because this or any CI gate would catch a regression in it for this diff. |
| per-module shards (`ci-modules.yml`) | No | Confirmed via `make ci-parity` this phase ("Selected code shards (0)") and independently: neither `tests/architectural/**` nor `kitty-specs/**` is claimed by any `modules[].test_dirs` row — `tests/architectural` is explicitly listed under `out_of_matrix_test_dirs` (its per-PR home is the always-on `architectural-heavy`/`archive-freeze` jobs directly, not a module shard; claiming it in a row would only double-run it). |
| **diff-cover ≥90% (changed critical-path lines)** | **No — does not bind** | Traced this phase through `scripts/ci/aggregate_source.py`: the scored diff (`critical.diff.patch`) is built via `git diff … -- $CRITICAL_PATHS` where `CRITICAL_PATHS` is a fixed literal tuple (`src/kernel/*`, `src/charter/*`, `src/specify_cli/status/*`, `src/specify_cli/lanes/branch_naming.py`, `src/specify_cli/dashboard/handlers/*`, `src/specify_cli/dashboard/scanner.py`, `src/specify_cli/merge/*`, `src/runtime/next/*`, `src/mission_runtime/*`). Neither of this mission's two files matches any entry. The scored diff is therefore empty for this mission, and `diff-cover --fail-under=90` over an empty statement diff passes vacuously-but-legitimately — not because 90% coverage was achieved on new code, but because this diff contributes zero lines to the scored denominator. This is stated explicitly so a reviewer does not mistake "diff-cover passed" for "the new guard tests are covered" — pytest-cov's own `--cov=<target>` instrumentation (per module row) never measures `tests/` files either, so the guard's own test-function lines are never in any coverage report at all; their correctness is proven by the tests running and by the self-mutation positive controls (Section B), not by a coverage percentage. |
| `packs.yml` | No | No `packs/` path touched. |
| commit-msg / markdownlint | No (never fail) | `commit-msg` only prints (`\|\| true`); `markdownlint-cli2` also `\|\| true`. Listed for completeness, not treated as gates. |
| wheel build + `clean-install-verification` (`ci-quality.yml`) | Yes (trivially) | Always-on; no packaging-relevant change. |

**Explicitly NOT treated as gates, per the hub table (overriding the overlay/design-pipeline's
stale lists)**:
- **commitlint** — configured but not run by any workflow; prints only.
- **markdownlint** (as an enforced check) — runs with `|| true`; can never fail.
- **Bandit / pip-audit** — run in no workflow.
- **mypy** — runs in no workflow (only `make typecheck`'s two-file local check, which this
  mission's diff does not touch — neither target file is `runtime/agent_commands.py` or
  `git/commit_helpers.py`).
- **"kernel 90%" / "mission-loader ≥90%" named coverage floors** — no such floors exist in the
  workflows; the only real per-PR coverage gate is diff-cover, addressed above.
- **SonarCloud** (`sonar-pr` in `ci-aggregate.yml`) — `continue-on-error`, structurally excluded
  from the terminal `aggregate-gate`'s `needs:` set-equality assertion; reported, not required.

## D. Baseline and red-first

**Measured baseline (orchestrator, `main` @ `46ea5bd7f`, before any change in this mission)**:

```
pytest tests/architectural/test_archive_root_byte_identical.py tests/git_ops/test_git.py tests/upgrade/preview_support/test_public_witnesses.py
→ 48 passed, 0 failed
```

Per `CLAUDE.md`'s "Test-run baseline-red gotcha," any wider run than these three files must be
attributed before being treated as this mission's problem, using the four categories:
(1) pre-existing known-P0 reds (confirm by running the same test on `upstream/main`/merge-base
or checking the tracker — never "fix" them), (2) CI-environment failures (auth, gate opt-out —
config, not diff), (3) stale-install false reds (a `spec-kitty`-shelling-out test failing until
`pip install -e .` reruns), (4) stale-venv false reds (`uv sync --frozen --all-extras` before
attributing an import failure to the diff). Per the charter's Pre-existing Failure Reporting
Rule, any **newly-discovered** pre-existing failure hit during this mission's implementation
phase requires a GitHub issue filed *before* being treated as accepted baseline — that filing
is an orchestrator action, not a task the WP implementer performs unilaterally, and this plan
records the obligation rather than executing it now (no such failure has been discovered as of
this planning phase).

**Red-first sequencing per changed behaviour:**

- **FR-001 (the repair)**: The new guard test (`test_no_conflict_markers_in_tracked_files`,
  FR-003) run against the **current** tree — which still has the two marker lines in the WP01
  file, independently re-confirmed this phase at exact lines 758/771/773 — already fails
  today, because the guard's regex matches `<<<<<<< HEAD` at line 758 and `>>>>>>> 5eda48f7
  (chore: Start WP01 implementation [claude-planner])` at line 773 in a path outside the
  exemption allowlist. That failure **is** the red-first proof for FR-001 — distinct from
  FR-006's synthetic self-mutation fixture, which proves the guard can catch a *planted*
  marker, not that it already caught a *real* one. Once FR-001's repair lands, the same guard
  test transitions to green against the real tree (paired with SC-001's independent `git grep`
  check).
- **FR-002 (carve-out) and FR-001 (repair) landing-order coupling**: `test_no_preexisting_archived_file_was_modified`
  does not do a raw byte comparison — it classifies each archived-root path's `git diff
  --name-status` status against `merge-base(HEAD, main)` and skips a path only if it matches one
  of five admission mechanisms: the two module-level frozensets
  (`_APPEND_ONLY_SPINE_EXCEPTIONS`, `_OPERATOR_SANCTIONED_CORRECTIONS`), a fixed lifecycle-log
  path check (`status == "M"` on the one lifecycle-log path), a fixed op-closures path check
  (same shape, one fixed path), or one of three per-mission lifecycle/recovery admission helpers
  (`_check_recovery`, `_check_dead_port_recovery`, `_terminal_lifecycle_paths`) that structurally
  gate specific `meta.json`/`status.json`/`status.events.jsonl` triples for a mission directory
  (plus one further, narrower escape the function itself carries: `status == "A" and path not in
  baseline`, i.e. a path added since merge-base that was never in the historical baseline at all —
  irrelevant here since the WP01 file **is** in the baseline). Once the WP01 file is repaired, it
  necessarily differs from `merge-base(HEAD, main)` under the frozen `kitty-specs/` archive root,
  so this test would fail on any commit where the repair exists **without** the carve-out entry
  also existing (the reverse ordering — carve-out entry registered for a not-yet-repaired file —
  would not fail this test either, since none of the five admission mechanisms inspect content
  validity, only path/status classification; but it would leave the corruption live in the
  working tree between commits, which is not acceptable). None of the three per-mission
  lifecycle/recovery helpers (nor the `status == "A"` escape) can admit a `tasks/WP*.md` path:
  `_check_recovery`/`_check_dead_port_recovery` are keyed to fixed, hardcoded singleton paths
  (a specific cyclic-dependency/snapshot recovery tree and a specific dead-port status.json,
  respectively) unrelated to WP01's location, and `_terminal_lifecycle_paths` only ever inspects
  the fixed filenames `meta.json`, `status.json`, and `status.events.jsonl` within a mission
  directory — never a `tasks/` subpath. So while the simpler two-frozenset framing is not a
  complete description of the function as a whole, it happens to be sufficient for reasoning
  about this specific file: only the carve-out frozenset can admit it. **Decision: land both in
  the same commit.** Justification: this is the smaller, safer option — a
  same-commit landing means neither intermediate git history state is ever inconsistent
  (repaired-but-unregistered, which reds CI; or registered-but-uncorrupted, which is
  semantically premature), and IC-01 already treats them as one concern for exactly this
  reason. The alternative (sequenced across two commits within the topic branch, relying on
  "CI gates the PR tip, not every intermediate commit") is not chosen: this repo's own
  `clean-linear-commit-history` tactic (charter, PR requirements) expects a small, logically-sliced
  commit set, and splitting a tightly-coupled repair+registration pair across two commits adds
  no reviewability benefit while introducing a real transiently-red window a force-push or
  rebase mistake could expose.

  **Correction (tasks phase, 2026-09-27): a literal single commit is not achievable, and this
  decision is superseded by a two-lane/two-commit mechanism with a compensating operative
  discipline.** The reasoning above still explains why a same-commit landing would have been the
  ideal outcome (it remains the correct statement of *intent* — never let the archive-freeze job
  see a repaired-but-unregistered or registered-but-uncorrupted intermediate state), but the
  tasks phase discovered a hard constraint this section did not anticipate: this repo's
  `tasks-finalize` ownership validation (`INVALID_WP_OWNED_FILES_KITTY_SPECS`) bans a single WP
  from owning both a `kitty-specs/` path and a `tests/` path, which makes a literal single commit
  across a WP boundary structurally impossible. The repair (a `planning_artifact` WP, owning only
  the `kitty-specs/` file) and the carve-out registration + guard (a `code_change` WP, owning only
  the `tests/` file) must therefore be two separate WPs, each producing its own commit, in two
  separate lanes (`lane-planning` for the repair, `lane-a` for the carve-out/guard) — joined only
  by a claim-time `dependencies: [WP01]` / `depends_on_lanes` edge, **not** the shared-worktree or
  same-lane framing this plan originally assumed and IC-01's "coupled, must land together" phrase
  implied. That edge only gates *when* the second WP can be claimed; it is not a merge-and-gate
  checkpoint over the first WP's commit, and no code-level gate (see `_assert_mission_terminal_ready`,
  a mission-wide precondition evaluated once before any lane consolidation — Section D above
  already reasons about this file's mechanics in detail) stops the two-commit branch from being
  pushed or opened as a PR between the two WPs landing. The compensating control adopted instead is
  a manual **operative discipline**, stated in both WP files: do not push the mission branch to
  origin, and do not open or update a pull request from it, until BOTH WPs have reached
  `approved`/`done`. This preserves this section's underlying goal — no publicly-visible,
  CI-gated intermediate inconsistent state ever reaches the remote or a PR — even though the
  intermediate state (repaired-but-unregistered) briefly exists in local git history on the shared
  repo-root checkout between the two commits landing. This correction supersedes "land both in the
  same commit" as originally written (which assumed a single-WP or literal-single-commit
  implementation was possible) and correspondingly narrows IC-01's "coupled, must land together"
  framing above to "coupled via a claim-time dependency edge, landed as two commits in two lanes,
  published together only after both are approved."

- **FR-003/004/006/007/008 (the guard and its self-tests)**: each of the five test functions in
  Section B is itself its own red-first proof — a test function that does not yet exist is
  definitionally "not passing," so the real red-first discipline here is per-function:
  1. `test_no_conflict_markers_in_tracked_files` — write the enumeration + regex-scan +
     floor-count assertions; confirm it fails today (real corruption present, per FR-001
     above); implement no new production logic (the guard *is* the test body plus small local
     helpers in the same file — there is no separate `src/` implementation to red/green); after
     FR-001 lands, confirm green.
  2. `test_conflict_marker_guard_self_mutation_catches_synthetic_marker` — write the fixture
     (planted marker) and assert-fails; confirm it fails if the guard helper does not yet exist
     (import/attribute error counts as red); once the guard helper exists (written for test 1),
     confirm this test goes green with the marker planted (asserting failure-detection) and
     stays green with the marker removed (asserting pass) — both assertions live in the same
     test, so "green" here means both halves hold.
  3. `test_conflict_marker_exemption_allowlist_is_shrink_only` — write the equality assertion
     against the landed baseline; confirm it fails before the exemption frozenset constant
     exists (`NameError`/import failure), passes once it is defined as exactly
     `{"tests/git_ops/test_git.py"}`.
  4. `test_conflict_marker_exemption_shrink_only_ratchet_has_positive_control` — write the
     augmented-fixture comparison; confirm it fails if the shared comparator helper (used by
     test 3) does not yet raise/assert on growth; passes once that comparator correctly detects
     the fixture's spurious extra entry.
  5. `test_conflict_marker_guard_fails_closed_on_enumeration_failure` — write the
     monkeypatched-failure fixture; confirm it fails if the guard's enumeration call silently
     swallows the injected error (i.e., if the guard is not yet fail-closed); passes once the
     guard's enumeration path is written to raise/fail on that condition.
  Each function's red state is confirmed by running it in isolation
  (`pytest tests/architectural/test_archive_root_byte_identical.py -k <name>`) before the
  corresponding implementation piece is written, per Standing Order #4.
- **NFR-001 closing verification**: after all five new test functions are green, re-run
  `pytest tests/architectural/test_archive_root_byte_identical.py -q` and record the wall-clock
  delta against the 1.99s (this file alone) / 276.09s (three-file baseline) figures measured
  above, in the PR body — closing NFR-001's verification loop explicitly rather than leaving it
  implicit in the stated performance goal.

## E. Campsite-clean

Charter Standing Order #2 requires opening a mission by campsite-cleaning the surfaces it will
touch *first*, as a distinct, behavior-preserving step — or an explicit, reasoned "no
campsite-clean warranted" if nothing in-domain is found. Analysis performed this phase, not
deferred:

- **Current file shape**: `tests/architectural/test_archive_root_byte_identical.py` is 831
  lines, with 30 top-level `def` symbols (functions + tests). `ruff check
  tests/architectural/test_archive_root_byte_identical.py --select C901` (the repo's mccabe
  complexity gate, ceiling 15 per `pyproject.toml`) returns **"All checks passed"** — no
  function in this file is currently at or above the complexity ceiling, including
  `_terminal_lifecycle_paths` (the one function carrying a `# noqa: C901` suppression comment
  at its definition, line 342) — the noqa is defensive/historical, not evidence of a live
  violation.
- **Repeated-literal check (Sonar S1192, `>=3` occurrences)**: `_OPERATOR_SANCTIONED_CORRECTIONS`
  and `_APPEND_ONLY_SPINE_EXCEPTIONS` are each referenced exactly **2 times** today (their
  definition plus one use site each, confirmed via `grep -c` this phase) — below the `>=3`
  threshold. This mission's additions reference the named constants (not raw string literals)
  from the five new test functions, which does not introduce literal-string duplication of the
  kind S1192 flags; it is normal use of an existing module-level constant, structurally
  identical to how `_ARCHIVE_ROOTS` is already referenced from multiple functions in this file
  without triggering S1192.
- **Decision: no campsite-clean warranted.** This is a reasoned exception, not a default:
  the file was inspected for (a) complexity-ceiling proximity, (b) duplicate-literal risk, and
  (c) any obviously stale/dead code near the touch points (`_OPERATOR_SANCTIONED_CORRECTIONS`,
  `_APPEND_ONLY_SPINE_EXCEPTIONS`, `test_no_preexisting_archived_file_was_modified`) — none
  found. C-002's two-file blast radius is a *constraint* on scope (it does not, by itself,
  excuse this analysis), but the analysis independently concludes there is no domain-matched
  debt in this file worth a preceding tidy-first commit. The Reconciling-change-scope-tensions
  policy's step 1 (smallest-viable-diff picks the file set first) already yields exactly the
  two C-002 files with no opportunistic file-set growth; step 2 (Boy Scout Rule inside that
  file set) finds nothing broken to fix; step 3 (Locality of Change) is therefore not needed as
  a brake.

## F. #4956 sequencing and the carve-out mechanism

This is the **fourth** entry in `_OPERATOR_SANCTIONED_CORRECTIONS` (one #4936-precedent entry,
two #4972 entries landed together, plus this mission's). Issue #4956 removes the whole
mechanism (all four entries) later, once every correction is baseline on `main` — that cleanup
is explicitly **out of scope** for this mission (C-003). Per FR-009, this mission's
**PR-closing-step action item** (not a file change — IC-03 above) is: post a comment directly
on GitHub issue #4956 (via `gh issue comment 4956 --body "..."`, per `CLAUDE.md`'s GitHub CLI
auth guidance if `GITHUB_TOKEN` scope issues arise) enumerating:
1. The full, current four-entry `_OPERATOR_SANCTIONED_CORRECTIONS` membership (the three
   pre-existing entries plus this mission's WP01 path), and
2. The correct current line reference for the exemption-check clause — **line 728** on this
   checkout, re-verified this phase (not the issue's stale "line-679" reference, itself already
   one correction behind spec.md's Clarification (b) citation).

The comment must explicitly state it is an informational correction only, posted from mission
#4957, and does not claim or commit to closing #4956. This is a task-phase action item (the
`/spec-kitty.tasks` phase should carry it as an explicit closing step of whichever WP handles
IC-01/IC-03, or as a final mission-level step before PR handoff), not something performed
during planning.

## G. PR shape

**One PR for this whole mission.** This is the sk-hub default (`sk-implement` doctrine: one PR
per mission unless the mission is large enough to need a per-WP split). C-002's blast radius
(two files, five new test functions, one repaired archive file, one tracker comment) is far too
small to justify splitting into multiple PRs or even multiple WPs beyond what
`/spec-kitty.tasks` decomposes IC-01/IC-02/IC-03 into for tracking purposes — the PR itself is
singular.

## H. Blast radius on downstream workspaces

- This guard is added directly to `tests/` in the spec-kitty **source** repo, not to
  `packs/built-in/` doctrine content. Per `pyproject.toml`'s wheel/sdist `packs` include
  (narrowed to `packs/built-in/` only, guarded by
  `tests/cross_cutting/packaging/test_packaging_safety.py`) and the fact that `tests/` is never
  packaged into the PyPI wheel/sdist at all, this guard ships in **no** distributed artifact.
  It has **zero** behavioral effect on downstream consumer repos (`team-kitty-missions`,
  `muster-missions`, or any project that installs the `spec-kitty` CLI via PyPI) — those repos
  never receive this test file and never run it.
- It only changes **this repo's own CI**. The `archive-freeze` job already invokes
  `tests/architectural/test_archive_root_byte_identical.py` by name (confirmed this phase, line
  502) and **no workflow edit is made** (C-001) — adding five test functions to that same file
  does not change which paths trigger the job (the job's own trigger is "always-on," not
  path-filtered — it runs on every PR regardless), it only adds a few seconds of runtime within
  the already-scheduled invocation, within NFR-001's stated budget (a few seconds against a
  measured 1.99s baseline for the pre-existing freeze test alone; the whole three-file baseline
  command's 276.09s is dominated by the unrelated `test_public_witnesses.py` suite, not by this
  file). That suite is `pytest.mark.integration`-marked, not `corpus`, and is claimed by no
  per-PR CI job (`.github/ci-module-registry.yml` has no entry for `tests/upgrade/preview_support`)
  — it runs here only as part of this mission's local SC-002 baseline command (spec.md
  Clarification (f)), not because any CI gate exercises it for this diff.

---

## Tooling / verification notes for this phase (see tracer files for the full record)

- Scaffold (`spec-kitty agent mission setup-plan --mission
  audit-archived-missions-conflict-markers-4957-01M3G1GP --json`) succeeded on the first
  invocation this phase — **no** `StartupAssetError` was hit during plan scaffolding (contrast
  with the three occurrences during the spec phase, per spec.md Clarification (j)).
- SK-248/SK-276 re-verification: `diff .kittify/overrides/missions/software-dev/templates/plan-template.md
  packs/built-in/missions/software-dev/templates/plan-template.md` is **byte-identical** on
  this checkout (confirmed fresh this phase, not assumed from the orchestrator's earlier
  diff). The scaffolded `plan.md` carries the canonical `## Charter Check` section (not a
  retired `## Constitution Check`), confirming the scaffold came out canonical — no SK-248/
  SK-276 recurrence this phase.
- All spec.md line-number citations this plan depends on (150, 728, 758, 771, 773, 489, 502)
  were independently re-read against this checkout's live files this phase, not taken on the
  spec's word — all matched exactly.
