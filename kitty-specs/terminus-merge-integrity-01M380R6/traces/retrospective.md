# Mission Retrospective — terminus-merge-integrity (Epic #5001)

## Outcome
Structural spine delivered + honestly verified. **7/12 children closed** (#4969 #4973 #4978 #4996
fully; #4945 #4977 #4981 under `--strategy merge`). 3 follow-up workstreams tracked
(#4982/#4997/#4985/#4991 resume-strategy/SHA; #4970 surface-write hardening; #5013
squash-content-soundness). Siblings #4990/#4972 out of scope. PR #5012.

## Approach (what worked)
- **Research/grounding squad first** (4 lenses, file:line) → found the single meta-root (no
  transaction boundary + no tree-vs-claim post-condition). This framing made the spine coherent.
- **Adversarial squads at every point-cut earned their tokens.** Post-plan caught the *vacuous
  verifier* (empty claim → PASS) before any code was written. Pre-merge caught the **default-squash
  gate bypass + fabricated success message** — a real invariant violation that would otherwise have
  shipped. Neither was visible to single-pass review.
- **Conflict-safe WP decomposition** (parallel fan + single serialized executor lane; scaffold WP
  owns all `executor.py` edits) let 5 WPs run in parallel with zero src collisions.
- **Red-first via `xfail(strict)` + honest reasons**; no green-washing. The final honest 7/12 (vs a
  fake 12/12) is the mission's integrity.

## Tooling friction (tracer — HIGH SIGNAL: this IS the Epic #5001 class, self-inflicted)
Running the mission on the WIP CLI, Spec Kitty repeatedly *fought its own operator* — the exact
"terminus command fights you" class this mission fixes:
1. **Lane auto-stacking vs kitty-specs/sparse-checkout.** `spec-kitty agent action implement WP##`
   merges planning INTO each lane, then its OWN `for_review` gate REJECTS `kitty-specs/` on the lane
   → a per-WP reconcile-and-commit dance. Every serial-stack `implement` hit `LANE_AUTO_REBASE_FAILED`
   on kitty-specs conflicts + sparse-dirty worktrees; recovery = manual dep-lane merge + restore
   kitty-specs from coord + `sparse-checkout disable && reset --hard && clean`. ~15 tool calls of git
   surgery per stack transition.
2. **Coordination-artifact-deletion guard (`R-STATUS-EVENTS-JSONL-UNION`)** refused my kitty-specs
   cleanup when it removed `status.json` — a good guard, but it fired against the operator doing
   legitimate lane hygiene.
3. **Every `implement` dirties mission planning state**, blocking the next `implement` until committed.
4. **Issue-matrix scaffold stubs** (`unknown` verdict, no issue ref) blocked WP approval until
   resolved; `issue-matrix.json.rows` is a dict keyed by `#NNNN` (undocumented shape).
Net: the mission's own thesis — terminus/merge/coord commands should never fight the operator or
require expert git recovery — is validated by how much they did during this mission. Worth its own
DX hardening pass.

## Design decisions (tracer)
- One `SurfaceAuthority` with read (loud-fallback) + write (fail-closed) entry points, not two classes.
- Verifier claim **Lamport-sourced inside `specify_cli`** (materialize wrapper), NOT `reduce_parsed` —
  closes #4990's green-washing risk for the merge read path WITHOUT crossing the `spec_kitty_events`
  boundary (C-002 intact).
- CAS: per-call entry-observed old value (not one transaction-start value threaded to all 4 sites —
  that would reject legitimate sequential advances under the serial lock).
- Squash: content-reachability deferred (squash loses SHAs) but claim-integrity enforced + reported
  honestly. Full squash-content axis = #5013.

## If done again
- Point the CLI at a checkout on upstream/main (not a sibling WIP branch) to avoid dogfooding
  half-built merge/lane code during the mission.
- Consider `git rm --cached kitty-specs` on lanes up front, or a helper, to avoid the reconcile dance.
