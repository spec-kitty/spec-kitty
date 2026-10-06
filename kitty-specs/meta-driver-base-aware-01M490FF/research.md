# Research: meta.json merge driver honours the merge base

## Decision: base-aware per-key three-way merge for ordinary merges, two-way opt-out for the lane-merge pipeline

- **Decision**: `reconcile_meta_payloads` gains an optional `base`; with a non-empty ancestor it merges per key (one-sided change/deletion wins, equal collapses, genuine conflict → today's precedence), with coupled key groups moved as a unit; the consolidation pipeline sets an opt-out so its own merges keep the two-way rule.
- **Rationale**: the #5460 merge has disjoint changes on the two sides (ancestor `8a24129`: A changed `coordination_branch`/`discarded_at`/`flattened`/`topology`, B changed `vcs`/`vcs_locked_at`), so a three-way rule yields the correct record with no conflict at all; a squash records no ancestry, so after a reopen its `%O` is the stale fork point and three-way would resurrect removed content (post-spec review MAJOR-3) — hence the opt-out (Decision `01M493BC3KPSC4FT6XSC7ESNDN`).
- **Alternatives considered**: three-way everywhere with the stale-ancestor residual pinned (rejected: a known wrong result on reopen + re-consolidate, and squash results would move); passing the previous squash commit as the ancestor (rejected: needs squash bookkeeping that does not exist); failing closed on genuine conflicts (out of scope, C-003).

## Decision: an explicit MISSING sentinel, not `_merge_field`

- **Decision**: a module-level sentinel distinguishes "key absent" from `null`; `_merge_field` (acceptance/issue matrices) is not reused.
- **Rationale**: `_merge_field` documents that it treats removed and `None` identically; the meta driver already distinguishes them (`key not in ours`), `mission_number: null` is a meaningful value, and NFR-001 needs deterministic key presence (review MINOR-3).
- **Alternatives considered**: reuse `_merge_field` (rejected for the reason above); treat `null` as absent (rejected: breaks the #4900 rule and byte stability).

## Decision: coupled key groups

- **Decision**: three groups merge as single units — flatten triple (`coordination_branch`, `topology`, `flattened`), merge bookkeeping (`merged_*`), acceptance stamps (`accepted_at`, `accepted_by`, `accepted_from_commit`, `acceptance_mode`, `accept_commit`). `vcs`/`vcs_locked_at` stay individual keys (independent provenance).
- **Rationale**: per-key merging can produce a half-flattened record (`flattened: true` with `topology` restored) or a half-deleted `merged_*` block (review MAJOR-2); the groups mirror the writers `flatten_coordination_metadata`, `_MERGE_FIELDS` and `record_acceptance` in `mission_metadata.py`.
- **Alternatives considered**: per-key only (rejected); deep-merging nested values (rejected: out of scope, values compared whole, NOTE-1).

## Decision: the `mission_number` guard applies regardless of ancestor

- **Decision**: after the per-key choice, if the chosen `mission_number` is unassigned and the other side's is assigned, the assigned value wins.
- **Rationale**: scoping #4900 to genuine conflicts lets `base 5 / ours null / theirs 5` resolve to `null` (review MAJOR-4); every #4900 test uses an absent or `{}` ancestor and would not catch it.

## Decision: red for the right reason

- **Decision**: the file-level red test calls `run_meta_driver(O, A, B)` (pre-existing signature) with a real ancestor file; the real-git test registers the driver as a recording wrapper around `sys.executable -m specify_cli merge-driver-meta` and asserts git exit 0 and the invocation marker before any content assertion; `git rebase` of the same branches is the positive control (green before and after); a squash-opt-out fixture proves two-way vs three-way differ and the pipeline env selects two-way.
- **Rationale**: a stale install or an unregistered driver makes git conflict (non-zero) and would red the test without a content defect; a new reconciler signature is red with a `TypeError` (review MAJOR-5, MINOR-5/6).

## Decision: goldens

- **Decision**: the five existing golden directories are left byte-identical (zero diff in the PR); three new cases (`base-one-sided-delete`, `base-both-changed-precedence`, `base-empty-file`) are hand-authored with the correct `expected_A` in the red commit and a `note` naming how the pre-fix driver differs; the `base-absent` note is reworded ("absent ancestor selects the two-way rule").
- **Rationale**: `_capture.py` regenerates `expected_A` from whatever driver is installed, so a post-fix capture would silently green-wash (review MAJOR-6, MINOR-2).

## Residuals recorded (not fixed here)

- `merge_history` is append-only but stays whole-value; a genuine both-sides append loses one side's entry (as today).
- `acceptance_history` union can exceed `HISTORY_CAP` by restoring a trimmed entry (as today).
- Safety-relevant booleans (`retain_*`, `commit_to_target`) resolve by precedence on a genuine conflict; failing closed is C-003 out of scope.
- A criss-cross merge whose virtual ancestor carries conflict markers fails loud (accepted).
- Merge vs rebase flip which side is "ours"; precedence therefore flips on a genuine conflict (documented, unchanged from today's two-way behaviour).

## Supersession check (grounding, 2026-10-06, origin/main 0d4c7583e)

Not superseded: the meta driver body is unchanged since #4900 (`d7b6450ce`); `5b5699e50` only added the decision-index driver; no `[Unreleased]` changelog entry, ADR or open PR touches the meta driver; #4933 is closed; #5292, #4316, #4169 are out of scope. The issue's reproducer gives `trigger: lost` / `nodriver: conflict` on current main.

## Supply-chain security check (DIRECTIVE_051)

No dependency is added, upgraded or removed; the `supply_chain_security_check` step is satisfied as not applicable. No adversarial pass needed on this axis; the adversarial pass that was run (post-spec, reviewer-renata) is recorded above through its dispositions.
