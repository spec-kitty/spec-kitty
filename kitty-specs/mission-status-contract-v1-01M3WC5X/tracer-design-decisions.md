# Tracer: Design Decisions

Mission: `mission-status-contract-v1-01M3WC5X` (issue #5558, part of #5528).

Rationale log, seeded at planning with the decisions made so far. Each entry: the decision, the
reason, what was rejected. The full register with alternatives is in `plan.md` (Decision
register) and `research.md`. Append at each decision point during implementation.

## DD-1: OQ-4 closed by operator ruling (2026-10-01); DEV-1 accepted

The reality check runs once, in the router's `tests-corpus` job, which a contracts-only change
selects through one added glob (`contracts/**`). The contracts workflow runs a resolver-parity
script instead of a second pytest run. Consequence: no duplicate-suite ledger row, no
`WORKFLOW_FILES` row, no deselection from `tests-corpus`, `.github/ci-module-registry.yml`
untouched. DEV-2 (the PR-green release dry run is a job of the contracts workflow) is planned as
written, because OQ-4 covers both deviations and the ruling closes OQ-4; the PR body still lists
both as confirmation items, and the plan asks once whether the ruling's scope includes DEV-2.

## DD-2: OQ-1 resolved: a Python resolver proven equal to the CI bundle

One resolution authority, `contracts/tools/contract_resolver.py`, used by the reality check, the
parity script and every Python check. Rejected: a JDK in the corpus jobs (edits two existing
jobs), a committed bundle (never committed), a test that downloads the CI artefact (cross-job and
network dependency, no local verdict), a second unproven resolver (excluded by the question's own
constraint).

## DD-3: Python checks read the resolved tree, not the bundle

Keeps ten checks JVM-free, local and fast; parity proves tree equals bundle, and parity is a
`needs` of the terminal gate. The bundle-based jobs are only validate, lint, breaking-change,
parity and the release dry run.

## DD-4: stable message codes and a three-valued exit status

0 pass, 1 violation, 2 could not do its job. Negative tests assert the code, so a check that fails
for the wrong reason is not counted as evidence (FR-021, silent-success rule D-15).

## DD-5: no committed Gradle wrapper jar

The pinned distribution archive is verified by sha256 from `pins.json` before it runs. FR-018's
parenthetical names `distributionSha256Sum`, a wrapper-only property; the manifest check gives
the same guarantee and honours R-10's preference for no committed binary. Departure recorded in
the PR body.

## DD-6: breaking-change baseline is rebuilt from the latest tag

Same build path for baseline and candidate, no release-host dependency. The first release is the
loud, single allowed "no baseline" state.

## DD-7: the contracts workflow triggers on `branches: [main]` with exactly three paths

Matches the repository's other path-filtered workflows and leaves the release-branch expectation
in `tests/ci/test_fleet_verdict.py` unchanged.

## DD-8: opening campsite commit is one test file

Hoist the repeated pair of path-filtered workflow names in
`tests/ci/test_fleet_verdict.py::test_all_existing_pr_workflows_are_registered` into one constant
the three assertions use. Chosen because that function is the one FR-017 must edit, and because
it avoids the pinning-inventory subjects so no new inventory rule appears. Rejected as grab-bag
items: the stale `_CORPUS_GLOBS` documentation (open PR #5557 rewrites the file), the `ruff.toml`
legacy baseline (unrelated), any `src/` debt (C-002).

## DD-9: a hidden byte-for-byte gate is part of the gate set

`tests/release/test_pinning_inventory_fresh.py` pins line numbers in three files the spec edits.
Regenerate with `scripts/ci/derive_pinning_inventory.py`; never hand-edit; keep new text free of
the inventory's three subjects.

## DD-10: `tests/ci/test_fleet_main.py` is edited only if a test turns red

The spec expects its conditional-gate expectations to gain the contracts workflow. On this
checkout `MainAPI` builds a run for every `PR_WORKFLOWS` member and the one conditional-gate test
pops only the drift workflow, so adding a member should not change it. Decide by running the file
red-first after the `PR_WORKFLOWS` edit.

## DD-11: citation resolution accepts annotated class attributes

The stream cursor's contract field `invariant` is the dataclass attribute `content_invariant`
(`TailCursor`, a bare annotation). Without accepting annotated targets, the spec's own citation
would not resolve.

## DD-12: the checks that need no source file are the ones that run on every contracts edit

All `contracts/tools/` checks run on any `contracts/**` change (the workflow's path filter), so a
README-only edit still runs the structure check, as D-19 requires.

## DD-13: dashboard references re-verified; corrections made in the plan, spec.md left unedited

Spec rows citing the removed dashboard scanner are replaced as follows (full table in `plan.md`):
lifecycle derivation, next action, workflow phases, mission count and the registry cross-check
become contract-owned `x-derived` rules with cited contract-field or status-domain inputs;
friendly name cites `MissionIdentity` in `specify_cli/mission_metadata.py`; title, phase label,
authored lists and prompt body cite `read_authored_wp_frontmatter` and `WPMetadata` in
`specify_cli/status/wp_metadata.py`; subtask progress is `x-derived` from `WPView.subtasks`;
accepted, merged and discarded stamps cite the metadata module. Not corrected here: stale
line-number cites inside the Proposed read-API ADR (history, C-011), and two spec mentions of
paths that do not exist on this checkout (`tests/ci/test_corpus_blocking_home.py`, from open PR
#5557; `.kittify/release/downstream-verified.json`, a documentation-only glob).

## DD-14: charter and CLAUDE.md drift on merge enforcement; charter wins

Probed read-only: no branch protection, no rulesets. "Enforced" in this plan means a red job the
fleet verdict reads, not a GitHub required check; CODEOWNERS review is advisory.

## DD-15: UI early-start is the end of IC-04; pin-grade is the end of IC-09

Earlier partial points exist at the end of IC-02 and IC-03. After the early-start point only
additive or nullability-relaxing changes are allowed, each logged in the module CHANGELOG.

- (append during implement and review)

## Assess at close

- (to be written at close)
