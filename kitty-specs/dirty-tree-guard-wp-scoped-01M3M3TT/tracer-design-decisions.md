# Tracer: Design Decisions

Seeded at mission planning (spec phase), 2026-09-28.

## Charter-vs-hub branch-naming drift

> **Charter-vs-hub branch-naming drift**: This mission's branch is named
> `issue-5007-dirty-tree-guard-wp-scoped`, following the spec-kitty CHARTER's
> `issue-<n>-<slug>` convention (charter §Agent Push Authorization / "Issue branch first"). This
> deliberately overrides the sk hub doctrine's `<type>/<slug>-<issue>` branch-naming convention.
> The charter is the binding authority for this repo, so this is intentional, not an error —
> recorded here so a later reader does not "fix" the branch name to match the hub convention.

## Other design decisions from spec authoring

### 1. Ownership mechanism: path-convention, not the `owned_files` module

**Decision**: Ownership of a dirty `kitty-specs/` path is determined by the existing
`kitty-specs/<mission_slug>/tasks/<WPxx>-*/` directory-naming convention (already partially
implemented in `_is_review_handoff_survivor_path`'s `wp_task_pattern`), not by
`src/specify_cli/ownership/`'s `owned_files` frontmatter-driven module.

**Rationale**: `packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md:223`'s
"kitty-specs ownership ban" forbids a `code_change` WP from listing any `kitty-specs/` path in
`owned_files` (`INVALID_WP_OWNED_FILES_KITTY_SPECS`). Since nearly every WP is `code_change`,
that module cannot be the ownership source for `kitty-specs/` bookkeeping paths without either
violating the ban or requiring every WP to be reclassified as `planning_artifact` (a much larger,
out-of-scope change). The path-convention mechanism is already implicit in the codebase, requires
no frontmatter lookup, and is identical across every mission topology (`single_branch`, `lanes`,
`coord`, `lanes_with_coord`) because it is a pure string convention rather than something read
from `lanes.json` or a coordination structure. This rules out reaching for the ownership module
as a plan-time shortcut.

### 2. Unowned dirty paths keep failing closed

**Decision**: A dirty path that cannot be attributed to any WP's task directory (and does not
match an existing benign category) continues to block the transition. The fix narrows false
positives (cross-WP misattribution); it never introduces a silent pass for undetermined
ownership.

**Rationale**: Operator decision (Clarifications Q2), and consistent with this guard family's
long-standing design precedent recorded in `SPEC-KITTY-LEDGER.md` SK-114/SK-115 — every prior fix
in this family has been "recognise a specific known-safe residue as benign," never "make
unrecognised dirty state pass silently." Also the charter's dominant failure-mode class: an
undetected silent success is a documented recurring hazard (#3133/#3212/#3282/#3336 precedent
line in the dispatch brief) that this mission must not add a new instance of.

### 3. Sequencing behind #5151's WP02

**Decision**: Design (spec/plan/tasks/analyze) proceeds now. Implementation is held until
sibling mission `lane-history-safe-handoff-5151-01M3JR6R`'s WP02 has landed or been
reviewed/approved on its own branch.

**Rationale**: WP02's `owned_files` lists the exact same file
(`src/specify_cli/cli/commands/agent/tasks_parsing_validation.py`) and the same two test files
this mission's blast radius touches, targeting a different function
(`_check_kitty_specs_contamination` and neighbours, the lane-worktree contamination refusal seam)
— not `_validate_research_artifacts`, which this mission fixes. Both WP02's own frontmatter and
#5151's `spec.md` (~line 116) explicitly exclude this mission's fix from WP02's scope ("dirty-root
attribution assigned to #5007" / "transferred by operator ruling to canonical #5007"). Running
both concurrently would create real same-file merge risk on a large, gate-sensitive file
(module coverage, complexity ceiling) with no assigned reconciler for the two refusal-message
styles. Going second and rebasing onto one known diff is the lower-risk order. This gates the
*implement* phase only — recorded as Constraint C-002.

### 4. New WP-scoped benign category is not restricted by file extension

**Decision**: FR-001/FR-002 apply to any dirty path under another WP's task directory, regardless
of file extension — not only `.md` files.

**Rationale**: #5151 ask 3's reported occurrence is "another WP's in-progress script," which is
not a `.md` file. The existing `wp_task_pattern` regex in `_is_review_handoff_survivor_path` is
`.md`-suffixed by construction, so a naive reuse of that pattern for the new WP-scoped check would
silently fail to cover the exact case that motivated part of this mission. Verified this gap is
real (not already covered) by direct regex testing during spec authoring.

### 5. Wholly-untracked WP directories must be attributable from the directory path alone

**Decision**: FR-003 requires ownership determination to work when `git status --porcelain`
reports a WP task subdirectory as a bare directory path (trailing slash, no filename) because
nothing inside it is tracked yet — not only when it reports a fully-qualified file path.

**Rationale**: Verified empirically in a sandbox git repository during spec authoring: a fresh,
wholly-untracked `kitty-specs/<slug>/tasks/WP01-foo/` containing one new file reports as `??
kitty-specs/<slug>/tasks/WP01-foo/` in porcelain output — not as the file path inside it. This is
the concrete mechanism behind kentonium3's Friction 2 report (a `review-cycle-1.md` verdict
record blocking the next WP's transition) and would not be caught by a fix that only pattern-matches
fully-qualified `.md` file paths.

## Plan phase, 2026-09-28

Six plan-level decisions deferred by spec.md, settled here (full reasoning in `plan.md`'s "Design
Approach and Decisions" section — summarized here for the tracer record):

### 6. Ownership mechanism: one new public sibling helper, not a reused/mutated `_is_benign`

**Decision**: add `owning_wp_for_path(path, mission_slug) -> str | None` to `dirty_classifier.py`
(public, no leading underscore — deliberately consumed cross-module). `classify_dirty_paths` calls
it only for paths `_is_benign` (unchanged) does not already classify benign. A single combined regex
(`(?:\.md|/.*)` alternation) covers the flat-file, nested-any-extension, and bare-directory shapes in
one pattern, anchored to the exact `mission_slug` via `re.escape` (not a wildcard) so FR-008 holds
regardless of caller. `_is_benign` itself is left untouched because it has direct callers outside
`classify_dirty_paths` (a kitty-ops-orphan counter-contract and pinned wp_id-blind tests) that must
not be disturbed.

### 7. No shared refusal-wording convention with #5151 WP02

**Decision**: proceed independently. WP02 targets a different function
(`_check_kitty_specs_contamination`, lane-history provenance) with a different vocabulary (git refs,
byte-preservation) than this mission's FR-005 (WP-directory ownership, "owned by {wp_id}" / "not
attributable to a specific work package"). #5151's own plan.md confirms dirty-root ownership was
transferred out of WP02's scope entirely. Residual same-file merge risk is real but is a
sequencing/rebase concern (mitigated by confirming WP02 is actually merged to `main` before this
mission's implement starts), not a wording-convergence requirement.

### 8. The two wp_id-blind pinned tests are left unmodified

**Decision**: `test_other_wp_task_files_are_benign` and `test_wp_task_file_other_double_digit_is_benign`
exercise flat `.md` task-file paths, which `_is_benign` (unchanged) already classifies benign before
`owning_wp_for_path` is ever consulted — their code path is untouched by this mission, so no
re-pinning is warranted.

### 9. Explicit no-new-blocking regression test added

**Decision**: add `test_no_previously_benign_path_becomes_blocking` in
`tests/review/test_dirty_classifier.py`, sweeping every path already benign under `main`'s current
behavior across a representative set of `wp_id` values, asserting none regresses to blocking — a
concrete, nameable verification of spec's Compatibility & Reflexivity claim, distinct from (and
narrower/more explicit than) SC-002's "existing tests keep passing unmodified."

### 10. One PR, not a per-WP split

**Decision**: default one-PR-per-mission applies; C-003's blast radius (2 source + 3 test files) is
small enough for one sitting.

### 11. Seam placement is binding: service owns logic, CLI only consumes it

**Decision**: `dirty_classifier.py` owns the ownership regex/helper; `tasks_parsing_validation.py`
imports `owning_wp_for_path` directly from the `dirty_classifier` submodule (mirroring its existing
`classify_dirty_paths` import), never reimplementing the pattern. `src/specify_cli/review/__init__.py`
is left untouched (out of C-003's named blast radius) since the direct-submodule-import style already
matches existing precedent in the consuming file.

## Tasks phase, 2026-09-28

### 12. Canonical authoring flow — confirmed as the single `tasks` mission-step, not `wps.yaml`

**Decision**: authored `tasks.md` and the two WP prompt files directly (via the CLI's `tasks` /
`finalize-tasks` commands), never creating a `wps.yaml` file. **Verified before writing anything**:
this checkout's `software-dev` mission type declares `tasks` (`sequence_index: 2,
in_action_sequence: true`) as its one action-sequence tasks step
(`packs/built-in/missions/mission-steps/software-dev/tasks/step.yaml`); the alternative
`tasks-outline` / `tasks-packages` / `tasks-finalize` three-step flow that produces a `wps.yaml` and
a "Generated by finalize-tasks from wps.yaml. Do not edit directly." `tasks.md` (observed directly
in a sibling mission's checkout, `audit-archived-missions-conflict-markers-4957-01M3G1GP/wps.yaml`)
exists in the same `mission-steps/software-dev/` directory but is NOT wired into this mission type's
action sequence (`sequence_index: null`, `in_action_sequence: false` for all three). Some
doctrine-skill prose describes the `wps.yaml` flow as canonical — that description is stale for THIS
checkout/mission-type combination (spec-kitty-cli 4.0.0rc5, v3.2.7rc1); the actual source of truth
is `packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md`, per this repo's own
"canonical templates, never improvise" rule. This finding is worth an upstream look (is the
three-step flow dead code, or does some other mission type still wire it in?) — not filed as a
separate issue this session; recorded here per the tracer convention.

### 13. WP shape: two WPs, one per plan.md Implementation Concern, no split and no merge

**Decision**: WP01 = IC-01 (WP-scoped ownership attribution mechanism), WP02 = IC-02 (honest
per-path refusal attribution), WP02 depends on WP01. No campsite-clean WP (plan.md's own Charter
Check rules one out explicitly). No further split (the 5-file blast radius is too small to
decompose further without padding) and no merge (the two ICs are genuinely sequenced — IC-02 calls
`owning_wp_for_path`, which IC-01 introduces — and each opens with its own separately-committed
RED-first test per charter C-011, so folding them into one WP would blur two distinct red-first
proofs into one commit sequence).

### 14. FR-009 split across both WPs, stated explicitly in both requirement_refs

**Decision**: FR-009 (red-first regression coverage + the FR-009-adjacent truncation-branch
coverage) is mapped to BOTH WP01 (`requirement_refs`) and WP02 (`requirement_refs`) rather than to
just one. Rationale: FR-009's text names two distinct deliverables — the three-occurrence ATDD
reproduction through `move-task` (WP01's T001) and the previously-uncovered blocking-lines
truncation branch in `_validate_research_artifacts` (WP02's T007) — and both genuinely belong to
their respective WP's surface. `spec-kitty agent tasks map-requirements --batch` accepted this
dual-mapping without complaint (`unmapped_functional: []` on the first attempt), and
`finalize-tasks --validate-only` raised no ownership or requirement-coverage warning about it.

## Analyze phase, 2026-09-28

### 15. Operator ruling restores spec.md's original "approved" bar for #5151 WP02 sequencing

**Decision**: plan.md, tasks.md, and both WP body files (WP01, WP02) were corrected to state that
this mission's implement phase may start once sibling mission
`lane-history-safe-handoff-5151-01M3JR6R`'s WP02 has **landed OR been reviewed/approved on its own
branch** — spec.md's C-002 / Clarifications Q1 bar, exactly as originally written. spec.md itself
was not touched (it already carried the correct bar).

**Rationale**: during the plan phase, in its resolution of review finding PLAN-GOV-002, plan.md's
Design Decision (b) deliberately tightened C-002/Clarifications Q1's "landed-or-approved" minimum
to a stricter "must have actually merged to `main`" bar. This tightening was never authorized by
the operator — spec.md's C-002 and Clarifications Q1 were never updated to match, and continued to
state the original, looser bar throughout. The tasks phase then propagated the same unauthorized
stricter bar into tasks.md's "Known, accepted cross-mission file overlap" section and into both
WP01's and WP02's "Mission-level pre-implement gate" sections.

On 2026-09-28 the operator ruled (binding, "operator ruling"):

> "Implement for this mission may start once sibling mission
> lane-history-safe-handoff-5151-01M3JR6R's WP02 is approved (reviewed/approved on its own branch);
> this mission builds off main and rebases onto #5151 at PR time; the residual same-file risk is
> accepted as a small conflict in a different function."

During this analyze phase, `plan.md` (Design Decision (b), the "Mid-flight consumer" bullet under
Compatibility/Rollout/Risks, and the IC-01 "Sequencing/depends-on" bullet), `tasks.md` (the
cross-mission overlap section and the "Next steps" list), `tasks/WP01-wp-scoped-ownership-attribution.md`,
and `tasks/WP02-honest-per-path-refusal-attribution.md` (both the pre-implement gate and the Risks
section) were all updated to state the restored bar and to record this history, without changing
this mission's scope, FRs, ICs, or WP breakdown.

### 16. Operator ruling LIFTS the #5151 WP02 implement-phase hold outright (2026-09-28)

**Decision**: spec.md's C-002 and Clarifications Q1 were updated (WP01's own Step 0, ahead of
implementation) to record that the operator, later on 2026-09-28, went further than decision #15's
"approved" restoration and lifted the implement-phase hold entirely. This mission's implement
phase proceeds now, off `main`, without waiting for sibling mission
`lane-history-safe-handoff-5151-01M3JR6R`'s WP02 to land or be reviewed/approved first.

**Rationale**: operator ruling, recorded verbatim in WP01's dispatch: "the operator on 2026-09-28
LIFTED the implement-phase hold on sibling mission #5151's WP02 (lane-history-safe-handoff-5151-01M3JR6R).
Implementation proceeds now, off main; whichever of the two PRs merges second rebases (the shared
file's edits are in different functions)." This supersedes decision #15's "landed-or-approved" bar
(itself already a correction of an earlier, unauthorized "merged-to-main" tightening) — the
sequencing history is now three layers: (i) plan.md's original unauthorized "must merge to main"
tightening, (ii) the 2026-09-28 operator ruling restoring spec.md's original "landed-or-approved"
bar (decision #15), (iii) this later 2026-09-28 operator ruling removing the bar altogether. Only
spec.md's C-002 (status + text) and Clarifications Q1 were touched for this step, per the
dispatch's explicit "touch NO other file for this step" instruction; plan.md, tasks.md, and the WP
body files still describe the intermediate "landed-or-approved" bar and are now stale on this one
point — recorded here rather than edited, since WP01's dispatch scoped this step to spec.md and
this tracer file only.
