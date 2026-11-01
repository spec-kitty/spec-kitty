# Research: Audit and remove special-case workarounds (#6745)

Grounding date: 2026-10-31, `origin/main` at `dfe9efb0e8` (clone `/home/exedev/work/sk-6745`).

## 1. What the issue asks, and what the operator added

Issue #6745 (P0, `tech-debt`) proposes an audit method (heuristics, time-box,
four-way classification), a disposition per suspect, a child issue per confirmed
workaround, and a process guard; its "Out of scope" line says fixing them is the
child issues' job. The operator's instruction for this Mission extends that: **remove a
bounded, well-evidenced set in this PR**, and state which suspects were audited and
deliberately left, with reasons. The audit is explicitly *not* claimed complete.

## 2. Grounding: is the issue still live?

Yes, but the family the issue was written from has moved.

- The worked example (mission `activate-output-and-identity-01M5ZA9X`, branch
  `issue-6457-activate-output-identity`) shipped as PR #6748 (state MERGED):
  "[#6457] charter activate says what it wrote; skill freeze warning; one stored
  activation spelling". `IdentityIndex.stored_spelling` is now the one spelling
  authority (`src/charter/activation/identity_index.py:345`), and
  `org_charter._normalize_required_ids` (`src/charter/activation/org_charter.py:290-330`)
  routes through it instead of a hand-rolled variant.
- So this Mission does not re-litigate the activation/identity family. That family's
  residual — "an unknown token is logged and kept best-effort"
  (`src/charter/activation/resolver.py:216-224`) — is a *refusal* change reachable from
  real org-pack content, i.e. an operator decision, and is deferred to a child issue.
- The six suspects are all still present at `dfe9efb0e8` (verified by reading each site;
  see §4).

## 3. Audit method adopted (time-boxed, repeatable)

Heuristics (each is a greppable shape, not a vibe):

1. Names and comments: `compensat`, `tolerat`, `workaround`, `fallback`, `legacy`,
   "for now", "best-effort", "kept as written", "defensive".
2. Broad `except` that yields an empty value or a default instead of surfacing.
3. A second construction of an object another module already builds (a copy kept
   alive because the original builder is private).
4. Production code shaped by a test double (`getattr(..., default)`,
   duck-typed `len`/`in`, `try/except TypeError` around a read).
5. Shrink-only allowlists and baselines that are still carrying entries.
6. Docstrings that describe "residuals" or "carve-outs".

Time-box: one pass per subsystem touched, ~20 minutes each; the sweep is *sampling*
`except Exception  # noqa: BLE001` (327 sites in `src/`), not a one-by-one review.

Classification (one per finding, from the issue):

- **genuine constraint** — keep; the branch is the contract (and say why).
- **workaround for bad data** — the fix is to refuse/report the input where it enters.
- **workaround for a missing seam** — add the seam, delete the branch/copy.
- **dead compensation** — the cause is already gone; delete it.

## 4. Dispositions (the ledger — the docs page in this PR is the durable copy)

| # | Site | Finding | Classification | Disposition |
|---|------|---------|----------------|-------------|
| S1 | `src/charter/activation/resolver.py:216-224` (`_gated`) | Unknown activation token is logged and kept best-effort; the final filter then silently drops it (no item has that key). | workaround for bad data | **left** — converting the log into a refusal is reachable from real org-pack content and needs an operator decision (child issue). |
| S2 | `src/charter/activation/org_charter.py:333-341` (`_best_effort_offering_root`) | Broad `except Exception: return None` around `resolve_offering_root()`. | genuine constraint (weak) | **left** — `resolve_offering_root()` already owns its own three-step fallback chain and returns a `Path`; the wrapper's `None` arm is unreachable in practice but swallowing is the documented "normalization is best-effort" contract of three writers. Tightening it is a refusal change, not a removal (folded into the S1 child issue's scope note). |
| S3 | `src/specify_cli/lanes/worktree_allocator.py:1135-1142` | Legacy missions without `coordination_branch` fall back to `mission_branch`; "WP08 will harden the legacy path further; for now we preserve existing behaviour." | genuine constraint (stale comment) | **left** — legacy mission state in user repos still needs the fallback; only the comment is stale. Not worth a diff on its own; noted for the allocator owner. |
| S4 | `src/charter/offering/drg/org_pack_config.py:649-651` (`ensure_pack_identity`) | Non-built-in packs returned without a `pack_id`; "Q2 backfill will mint them". | workaround for missing data (planned migration owns it) | **left** — the docstring at `:196-206` says load-without-`pack_id` is expected to raise a structured error only once the pack_id-keyed readers land; removing the pass-through today breaks readers. Child issue not needed: the planned migration is the owner. |
| S5 | `src/specify_cli/lanes/implement_support.py:602` (`reenter_lane_self_heal`) | Calls the allocator's private `_merge_recorded_planning_commit` / `_merge_dependency_lane_tips` to skip the allocator's clean-worktree check. | workaround for a missing seam | **left here** — a real seam (`adopt_recorded_planning_commit(...)`) is a larger allocator refactor than this P0-audit PR should carry. Child issue filed. |
| S6 | 327 `except Exception  # noqa: BLE001` in `src/` | Sampled: 9 in `src/charter/activation/context_renderers/`. | mixed | **sampled** — the context_renderers ones are **genuine constraints** (doctrine rendering must degrade, not crash a prompt build: `profile_sections.py:202,401,480`, `selection_block.py:179,676`, `activation_block.py:65,187`, `bootstrap_text.py:80`, `catalog_diagnosis.py:111`, each with a diagnosis or fallback). The rest of the 327 are unreviewed and the PR says so. |
| S7 | `src/specify_cli/mission_loader/command.py:206-235` (`_build_discovery_context`) | Byte-identical copy of `runtime.next.runtime_bridge_io._build_discovery_context`; the docstring says "the runtime bridge's helper is module-private; we duplicate the construction here". Mission `up-org-template-fsm-01M06F9K` then had to wire the org tier into both copies by hand (its DEC-006 calls them "independently-duplicated production wiring sites"). | workaround for a missing seam | **REMOVED HERE** — publish one builder, delete the copy. |
| S8 | `src/runtime/next/runtime_bridge_composition.py:615-645` | `getattr(result, "invocation_ids", ())`, `try: len(...) except TypeError`, `getattr(result, "steps", ())` — comment: "so test mocks (MagicMock) and real instances both flow through cleanly". `StepContractExecutionResult` (`mission_step_contracts/executor.py:145-163`) always carries both. | workaround for a test double | **REMOVED HERE** — read the contract; rewrite the tolerance-pinning test to assert the contract. |
| S9 | `src/specify_cli/ownership/validation.py:150` | `continue  # defensive: ignore cycles (validated elsewhere)` — the named authority does not exist: no dependency-cycle validator is reachable from `OwnershipManifest` loading. The guard is load-bearing (it bounds the recursion). | workaround for bad data (phantom authority comment) | **left** — the clean fix is to refuse a cyclic `depends-on` graph where it enters, which is new behaviour + a new refusal surface. Child issue filed. |
| S10 | `src/specify_cli/upgrade/autocommit.py:221-231` vs `:233-245` | `should_auto_commit_for_worktree` is a documented twin (D-10) of `should_auto_commit` — same body, same shared `get_auto_commit_default` authority. | not a second authority | **left** — both are two-line wrappers over one decision function; collapsing them is taste, not debt. |

## 5. Decisions taken

- **D1.** Scope the removals to S7 and S8: both are provable, small, and each is a
  different class (missing seam, test-double shaping), which makes the PR a
  demonstration of the method rather than a cherry-pick.
- **D2.** Do not touch a tolerance that is reachable from user-supplied pack content
  (S1) or that a planned migration owns (S4): those need an operator decision, which
  the issue's own "Out of scope" line respects.
- **D3.** Do not add a new architectural gate. The repo's ADR
  `2026-09-30-1-allowlist-ratchets-are-priced-debt` prices every new gate; instead
  extend the *existing* seam non-vacuity test (`tests/runtime/test_bridge_io.py`,
  `_SEAM_OWNED_NAMES`) to own the new public name and add one patch-point test proving
  `mission run` observes the seam.
- **D4.** The proposed process guard (a "workaround lens" / reviewer checklist item)
  goes to the operator as a tracker issue, not into `packs/built-in/` (that would ship
  in-house doctrine to every consumer).

## 6. Open questions (resolved by plan/tasks)

- Q1. Where does the audit page live? Chosen: `docs/development/how-to/` next to
  `review-gates.md` and `pr-landing.md`, because it is a how-we-work page for
  maintainers, not an architecture explanation. (Resolved in plan.)
- Q2. Does renaming `_build_discovery_context` to a public name trip a census or
  allowlist? Checked: `grep -rn "_build_discovery_context"` hits only
  `src/runtime/next/runtime_bridge_io.py`, `src/specify_cli/mission_loader/command.py`
  and `tests/runtime/test_bridge_io.py`; no YAML/JSON allowlist, census or baseline
  mentions it. (Resolved.)
- Q3. Does the composition change alter a test's premise? Yes: one test
  (`test_dispatch_handles_non_sized_invocation_ids_and_returns_guard_failures`) pins
  the tolerance with `fake_result.invocation_ids = object()`. It is rewritten to assert
  the contract (a real tuple → the emitted count) while keeping its guard-failure
  coverage — not deleted.
