---
title: 'Tracer: design decisions'
updated: 2026-10-13
type: explanation
mission: declaration-first-repo-root-resolution-01M4TB21
---

# Design-decisions tracer

Appended as the mission progresses. Each entry: decision · rationale · alternatives rejected.

- **D1 (placement): the typed entry lives in `specify_cli`, not `mission_runtime`.**
  Rationale: it depends on `core.paths` (`read_target_branch_from_meta`,
  `get_feature_target_branch`, `get_main_repo_root`, `resolve_canonical_root`) and
  `core.git_ops` (`resolve_primary_branch`); the enforced chain forbids `mission_runtime`
  importing `specify_cli`. The ADR's `mission_runtime` `WriteLocation`-dual is the
  **Increment-2** handle, explicitly deferred. Alternative rejected: placing it in
  `mission_runtime` (would invert the chain) or duplicating the meta readers there.

- **D2 (build on existing resolvers, add no new checkout-HEAD grammar).** The branch
  half is declaration-first (`read_target_branch_from_meta` → explicit validated
  `resolve_primary_branch` fallback), **never** the ambient-HEAD bias. This is exactly
  the fix `test_no_write_side_rederivation.py` prescribes, so the ratchet stays green by
  construction rather than by allowlist.

- **D3 (scope is bounded and surfaced, not silently widened).** Increment 1 introduces
  the entry + routes the *mission-scoped* ambient root/branch seeds that are safe now;
  it **files-and-links** the merge-target (consolidation non-goal), the `implement_claim`
  guard (#2453-deferred, ratchet-allowlisted), create-time, project-scoped, and
  honest-identity-input sites. This matches the ADR's "degrades gracefully; Increment 1
  valuable standalone" and the escalation discipline (don't widen scope silently).

- **D4 (fail-closed preserved, not generalised).** #3128 `enforce_checkout_identity` and
  #3328 `resolve_checkout_identity` are kept verbatim; the entry *feeds* them, it does
  not replace or widen them (that generalisation is Increment 2). Negative tests prove it.

- **D5 (final routed set, after per-site reading).** Per-site reading showed the
  command-entry `locate_project_root() or Path.cwd()` prologues (verify, issue_verdict,
  decision, context) are mission-AGNOSTIC root discovery resolved BEFORE the mission slug
  is known, with the branch/placement already declaration-first downstream — so they carry
  no ambient-BRANCH defect (their canonical form is `get_project_root_or_exit`). The
  genuine declaration-first-branch consumers are the command-entry callers of
  `get_feature_target_branch(repo_root, slug)`, whose fallback carries the ambient-HEAD
  bias (`resolve_primary_branch(..., bias=True)`). **Routed:** `mission_record_analysis.py`
  (record-analysis, ADR-named), BOTH target-branch sites — they pass a full canonical slug
  (`feature_dir.name`), so the declaration case is byte-identical and only the fallback is
  corrected to non-ambient; a tight, provably-safe, single-command routing. **Filed-and-
  linked (not routed):** `mission_accept_merge.py` (merge-target — consolidation non-goal,
  C-001), `mission_create.py` (create-time), `mission_branch_context.py` (display
  recommender, already `bias=False`), `tasks_parsing_validation.py` (DI-injected
  `get_feature_target_branch` — higher-risk surface), `tracer_append.py` (fuzzy
  `--mission` handle — needs the canonicalization the entry deliberately omits),
  `implement_claim.py:81` (#2453-deferred ratchet-allowlisted guard), and the root-discovery
  prologues above. The single declaration-first entry is now established as the canonical
  producer a NEW mutating command calls; routing the remaining consumers is mechanical
  follow-up (Increment 2 / the filed follow-up issue).

- **D6 (pre-PR adversarial review folds).** An independent adversarial reviewer (reviewer ≠
  implementer) confirmed the routed-site behaviour is genuinely behaviour-preserving in the
  declaration case, and surfaced two real overclaims in the new module's own docstrings
  (not routed-site regressions). Both folded while still a draft:
  (1) the "non-ambient fallback … never the ambient HEAD, by construction" claim was false
  in a cornerstone-less repo, because `resolve_primary_branch(bias=False)`'s last resort
  recurses into the ambient-biased cascade — hardened with `_validated_fallback_branch`,
  which coerces that one hole to the conventional default so the ambient checked-out branch
  is never returned; docstrings re-scoped to the truth;
  (2) the entry dropped the `assert_safe_path_segment` traversal guard the old
  `get_feature_target_branch` applied — restored (a `../x` slug now refuses rather than
  composing a path outside `kitty-specs/`), and the contract made explicit (callers pass the
  resolved dir name, not a fuzzy handle — handle canonicalization is deferred to #6152).
  Added coverage for the cornerstone-less fallback edge, the unsafe-slug guard, and the
  explicit-`repo_root` non-git path (the gaps that let the overclaims slip through).
