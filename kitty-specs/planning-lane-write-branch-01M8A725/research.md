# Research: Planning lane writes to the Mission branch before landing

## R-01 Root cause (verified on real git, `main` @ e6b18eeb)

- Fixture: a default Mission with 3 code work packages and 1 planning work package. It settles `lanes_with_coord`. The root checkout goes back to `main`, and the Mission branch is checked out in `.worktrees/<slug>-coord`.
- Before this change, `implement` named the root checkout, on `main`, as the planning workspace.
- Evidence results:
  - an owned commit on `main` passed `move-task --to for_review`;
  - an owned commit on the Mission branch was refused with `IMPLEMENTATION_MISSING` (#7860).
- Two documented rules disagreed:
  - FR-061 (ADR 2026-11-06-3 Decision 5): the PRIMARY partition is on the topic branch before landing;
  - ADR 2026-11-06-3 Amendment 2026-11-22: "lane-planning, whose branch is the target branch".
- Evidence: `tests/integration/test_7860_planning_evidence_window.py` (commit f1ecef5d).

## R-02 Decisions

| Decision | Choice | Rationale | Alternatives rejected |
|---|---|---|---|
| Rule | A': the Mission branch is the planning write branch before landing (operator ruling) | One rule, consistent with FR-061 and the review range | A (window only; refuses agents who follow `implement`), B (union of target and Mission branch; a second rule), D (no change) |
| In-flight Missions | Guidance only (operator ruling) | No second evidence rule. The refusal names the commits and the remedies | A transition window; a migration that moves commits |
| Window start | The commit on the Mission branch that introduced the work package's window-opening status event (operator ruling) | Durable in branch history (works across clones), fails closed, same derivation as the review range (Q10/Q12) | The claim-base ref (clone-local); moving the planning pin (still counts pre-claim content, and moves code-lane bases) |
| Write-branch reader | A new raising `planning_write_ref` in `mission_runtime` on `default_mission_primary_ref` | `_default_mission_facts` silently gives the target on an unreadable `meta.json` (NFR-002) | Reusing the non-raising reader |
| Checkout locator | `coordination/planning_commit.py::primary_partition_checkout` | Already the shared answer for the planning, claim and bookkeeping commits (#7372) | A third check in `workspace/context.py` |
| Workspace kind | A distinct resolution kind | 14 readers take `"repo_root"` to mean the root checkout | Overloading `"repo_root"` |

## R-03 Post-spec squad findings and dispositions

Squad: `architect-alphonso`, `reviewer-renata`, `doctrine-daphne` (profile-loaded, read-only, 2026-11-25).

| # | Finding | Disposition | Evidence location |
|---|---|---|---|
| 1 | The window start is the target pin (`lanes/planning_base.py:69`), so a hollow work package that owns an existing Mission file would pass | accepted | spec FR-010, User Story 2.2; plan IC-04 |
| 2 | The claim base is recorded from the repository root (`implement_support.py:370`, `orchestrator_api/wp_lifecycle.py:332`) | accepted | spec FR-011; plan IC-03 |
| 3 | There are three planning workspace arms, and 14 readers of `resolution_kind == "repo_root"` | changed (a distinct kind) | plan IC-02 |
| 4 | The reconciliation authorship walk attributes the planning lane against the target (`reconciliation_authorship.py:766`, `approved_attestation.py:203`) | accepted (E2E test; fix if red) | spec FR-012, SC-006; plan IC-05 |
| 5 | The agent and the CLI share the coordination worktree | accepted | spec FR-013, User Story 6 |
| 6 | The red test's control contradicts A', and its bookkeeping helper can fake evidence | accepted (owned by a work package; the Mission branch is not edited outside work packages) | plan IC-05 |
| 7 | FR-004 is [build], not [ratchet]; the remedy texts name the target | accepted | spec FR-004 |
| 8 | The FR-007 probe range is unbounded and checked by substring only | accepted (bounded to owned files; negative control) | spec User Story 3.2 |
| 9 | A landed control done by clearing `mission_branch` is vacuous | accepted (a recorded landing) | plan IC-04 risks |
| 10 | Per-caller coverage, and a pin for the one authority | accepted | plan IC-04, Charter Check |
| 11 | `_default_mission_facts` swallows an unreadable `meta.json` | accepted | spec NFR-002; plan IC-01 |
| 12 | FR-005 does not name its authorities | accepted | spec FR-005 |
| 13 | The glossary entries `orchestration.md:178`, `topology.md:77,155`; the "main repository" docstrings | accepted | spec FR-014; plan IC-02 / IC-05 |
| 14 | "Topic branch" was listed as a term to avoid, against the glossary | accepted (softened) | spec Domain Language |
| 15 | The ADR 11-06-3 amendment must answer #7759 | accepted | plan IC-01 |
| 16 | In-flight refusal is a breaking change, so a `docs/migrations/` note is needed | accepted | spec FR-009 |
| 17 | `wp_range` reads `landed=False` | deferred_with_rationale: C-001 (operator ruling, #5604), recorded in the ADR amendment and pinned by a ratchet test | spec C-001 |
| 18 | A PR-landed Mission without a local consolidate | deferred_with_rationale: the existing `--merge-commit` route (#6780) is unchanged | spec Edge Cases |
| 19 | No packs/built-in change needed | accepted (none) | n/a |

## R-04 Supply chain

No dependency is added, upgraded or removed, so DIRECTIVE_051 is not triggered.
