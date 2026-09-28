# Tracer: approach and reasoning

## What was already decided before spec authoring started

The dispatch carried three binding operator decisions (remedy = (d) + a real nightly; auth = a
named, fail-loud dedicated PAT/App-token secret; scope = charter-only) plus a fully-verified
readiness report. Spec authoring therefore was not a discovery exercise for *what* to build — it
was: (1) re-verify every load-bearing factual claim in the readiness report against the live
checkout rather than trust it, (2) translate the three operator rulings into a `## Clarifications`
section using the canonical decision-record format already established in this repo
(`kitty-specs/up-mission-type-seam-01KZY1JB/spec.md`'s `CL-00N` pattern), and (3) turn the
readiness report's "what breaks if unresolved" language for both open questions into concrete,
testable FRs/ACs so a review squad has something falsifiable to check, not prose to trust.

## Re-verification performed

- Read `tests/architectural/test_module_length_agreement.py` in full: confirmed
  `test_charter_is_not_allowlisted_and_agrees` is `@pytest.mark.slow`, asserts hard equality, and
  that `charter` is deliberately excluded from `_MISMATCH_ALLOWLIST` with an inline comment
  explaining why (a count-preserving swap must not mask a regression). Confirmed the three other
  ratchet tests (`test_allowlist_does_not_exceed_baseline`,
  `test_allowlisted_modules_still_genuinely_mismatch`,
  `test_allowlist_entries_are_real_registry_modules`) exist and are unrelated to the charter-only
  assertion — the demotion can be scoped to exactly one test function.
- Read `.github/workflows/module-tests.yml`'s "Select this shard's tests" step directly: confirmed
  the positional-pairing fallback to uniform weights on `len(durations) != len(node_ids)`, with no
  warning emitted today — this is the basis for NFR-001 (the gate protects shard balance, not
  correctness) and for the "no correctness regression risk" framing throughout the spec.
- Read `.github/workflows/ci-stale-running-sweep.yml` and `.github/workflows/ci-nightly.yml`:
  confirmed neither runs `capture_shard_timings.py`, confirmed the schedule+workflow_dispatch-only
  pattern with no `pull_request`/`push` trigger that `ci-stale-running-sweep.yml` uses (the
  closest existing precedent for the new workflow's trigger shape), and confirmed it only posts a
  PR *comment*, never opens a PR — so there is genuinely no in-repo precedent to copy verbatim for
  the PR-opening step; that is left as a plan-time design choice, not prescribed here.
- Read `.github/workflows/release.yml`'s `nightly-gate` job: confirmed the
  `RELEASE_NIGHTLY_DISPATCH_TOKEN` secret name and its documented rationale (a
  `workflow_dispatch` issued with the default `GITHUB_TOKEN` does not start a new run) — the
  precedent CL-002 cites.
- Read `.github/workflows/protect-main.yml`: confirmed it runs on `push: branches: [main]` and
  inspects the pushed commit for PR provenance — the mechanism behind "main is PR-only" in this
  spec's C-003.
- Ran `grep -rn "capture_shard_timings" .github/workflows/`: zero hits, confirming no workflow
  recaptures timings today (readiness report's claim, now independently confirmed).
- Read the SK-247 ledger entry in full: confirmed the 20-vs-21 mismatch figures match what's
  currently frozen in `_MISMATCH_ALLOWLIST`, confirmed the prior mission's scope ruling (charter
  only), and confirmed SK-247 itself proposes per-module CI-config-path gating and a
  `SELECTION_MARKER_EXPR` alignment fix that this mission deliberately does not attempt (kept as
  open follow-up, cited in the spec's Ledger Cross-Reference section so this mission cannot be
  misread as closing SK-247).
- Read the charter (`.kittify/charter/charter.md`) in full for Standing Order #5's exact wording
  (non-vacuous gate, shrink-only allowlist, self-mutation test, never disable a gate to get green)
  to write the Charter Tension section against the rule's actual text, not a paraphrase.

## Design choices deliberately left open for the plan phase

- The exact mechanism for "visibly distinct from a genuine pass" (FR-004): `xfail(strict=False)`,
  `warnings.warn` plus a captured-output assertion, or a GitHub Actions `::warning::` annotation
  are all viable; pytest.ini carries no `-W error`, so a plain warning would not itself fail the
  suite. The spec pins the *observable* requirement, not the mechanism, per the
  smallest-viable-diff / locality-of-change reconciliation the charter itself directs (mechanism
  choice belongs to whoever is closest to the code at plan/implementation time).
- The exact name of the new workflow file and the new secret: named illustratively in the spec's
  Key Entities / CL-002 sections as "a dedicated PAT / GitHub App token, named explicitly by the
  plan" rather than inventing a name here, since the operator explicitly said the design "must
  NAME the secret" (plan-time responsibility) and the dispatch did not hand down a fixed name.
- Duplicate-PR and no-drift detection mechanisms (FR-006/FR-007): specified as observable
  acceptance criteria (no PR when no drift; no second PR when one is already open), not as a
  prescribed implementation (e.g., `gh pr list --state open --label ...` vs. matching a
  branch-name prefix vs. a bot commit-author check) — again a plan-time choice among the three
  markers Key Entities names. Note this is narrower than it may first look: the spec's Key
  Entities section now specifies the recapture branch is freshly generated per run (a
  timestamp/run-id suffix, mirroring `generate_run_id()`), so checking for a single fixed,
  reused branch name is **not** a viable option any plan may pick — a branch-based check, if
  chosen, must match the fixed prefix portion of the name, never the full (per-run-varying)
  branch name.
