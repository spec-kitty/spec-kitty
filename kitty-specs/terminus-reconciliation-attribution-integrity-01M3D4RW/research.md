# Research: Terminus Reconciliation Attribution Integrity

Phase 0 decisions. Grounded by two opus lenses (alignment + scope) against HEAD `1409dc827f`; all four facets confirmed LIVE, none superseded.

## Decision 1 — #5022 squash deletion attribution (WP1)

- **Decision**: Add `authored_deletions: frozenset[str]` (repo-rel posix paths) to `ApprovedWpCommitSet`, produced by a new `_final_authored_deletions` collector wired through `_collect_authored` → `build_approved_wp_set`. In `_unattributable_content_squash`, stop skipping `D` paths: a squashed deletion is attributable only if the path is in `authored_deletions` **or** is mission bookkeeping (`_is_bookkeeping_path`); otherwise it is an unattributable deletion → FAIL → existing CAS-revert.
- **Rationale**: The soundness model already computes each approved lane's FINAL first-parent blob per path (`_final_authored_blobs`). A path whose newest first-parent touching commit deletes it currently just falls out (its `blob_id_at` raises, path marked seen, no blob recorded) — that is exactly the "approved lane's final state is a deletion" signal, captured with no new probe. Attributing deletions closes the data-loss escape while a legitimate approved deletion still PASSes.
- **Alternatives considered**: (a) infer a deletion is legitimate from a rev-parse failure — rejected (F1: never infer deletion from a probe error). (b) A separate whole-diff deletion pass — rejected (redundant; the first-parent spine already yields the authority).
- **Adversarial evidence**: rename under `--no-renames` (delete+add) attributes each half; a delete-then-re-add within one lane must NOT count as an authored deletion (final state is present); bookkeeping-path deletion tolerated. Disposition: **accepted** (folded into WP1 acceptance tests).

## Decision 2 — #5018 commit-level exclusion (WP2)

- **Decision**: In `_collect_excluded`, subtract the approved lanes' first-parent `authored_shas` / `authored_patch_ids` (from `_collect_authored`) from a mixed lane's excluded set. Thread those authored sets in as parameters (do not reorder `build_approved_wp_set`'s collector calls into shared mutable state). A commit that is an approved WP's own first-parent authorship is not excluded; a commit that is neither approved-authored nor otherwise attributable stays excluded.
- **Rationale**: Lanes collapse by write-scope; `_phase_merge_lanes` integrates a mixed lane's survivors wholesale. The gate must attribute at commit granularity to match. The first-parent spine already excludes second-parent-smuggled canceled code (`_collect_authored` uses `--first-parent`), so subtracting the authored set is safe against the #4977 class.
- **Risk asymmetry (C-001)**: A naive "approved lane wins → exclude nothing" reopens #4977 for second-parent-smuggled canceled code. The fix subtracts only the *first-parent-authored* commits, so smuggled canceled code (not on the survivor's first-parent spine) stays excluded.
- **Alternatives considered**: skip approved lanes entirely in `_collect_excluded` — rejected (would let a mixed lane's second-parent-smuggled canceled commit ride unflagged).
- **Adversarial evidence**: second-parent-smuggled canceled code still excluded + FAILs when reachable; cherry-picked canceled copy still patch-id caught; fully-canceled lane fully excluded. Disposition: **accepted**.

## Decision 3 — #5021 residual 1 resume tolerance (WP3)

- **Decision**: Make `merge --resume` recognise a completed-but-mid-teardown squash state (target already advanced + reconciliation already PASSed, teardown partially done) and complete teardown instead of re-running the content axis against a possibly-post-teardown-partial `authored_blobs` claim.
- **Rationale**: On resume, `_capture_reconciliation_claim` rebuilds the claim from persisted anchors; if a lane branch was already torn down, `_lane_first_parent_spine` tolerates the unresolvable range and yields empty authorship → the squash blob axis then REFUSEs (empty authored set with resolved approved WPs). The recovery path must not re-verify already-verified, already-landed content.
- **Alternatives considered**: persist the full authored_blobs set into merge-state and re-use verbatim on resume — heavier; deferred in favor of a completed-state short-circuit keyed on persisted PASS + advanced target.
- **Guard**: a genuinely incomplete merge (target not advanced / reconciliation not run) still runs the full gate — no tolerance leak.

## Decision 4 — #5038 projection proof precision (WP4)

- **Decision**: Make `_assert_squash_projected_content_landed` / `projected_content_matches_target` distinguish a coord-partition bookkeeping path the target legitimately does not carry (`coord_bytes` present but the target never received it under a legitimate ownership contract) from a genuine failed projection of approved content, and stop `--resume` dead-ending on `TARGET_BRANCH_CONTENT_CONFLICT` for a completed clean merge.
- **Rationale**: `projected_content_matches_target` returns False (→ REFUSE) whenever `coord_bytes is None` OR `target_bytes != coord_bytes` for any projected path. For a clean single-lane mission a coord-partition path (verdict/notes/trace) can legitimately not land, yet the proof demands byte-equality → false REFUSE; `--resume` re-hits it.
- **Precision, not weakening (C-001)**: the proof must still REFUSE a genuine failed projection of approved content. WP4's red-first repro pairs a legitimate-non-landing case (must PASS) with a genuine-divergence case (must still REFUSE). The exact root-cause boundary (which path classes legitimately do not land) is nailed by the WP4 repro.
- **Alternatives considered**: skip any missing projected path — rejected (would blind the proof to a genuine failed projection).

## Decision 5 — #5021 residual 2 (3-way) kept honest xfail

- **Decision**: KEEP `test_squash_three_way_merge_resolution_is_unattributable` as `xfail(strict=True)`. Do not attempt a fix this mission.
- **Rationale**: A true 3-way resolution blob equals neither parent's blob; attributing it requires either a git-merge-simulation probe or relaxing the disjoint-write-scope invariant the whole blob axis rests on — an architectural soundness-model change, not a line-level tweak. It is the SAFE direction (refuse a legitimate merge, never ship unattributed content).
- **Honest-red (Standing Order #9)**: WP1's deletion work must not silently un-strict this xfail; documented as a tracked Epic #5001 follow-up.

## Supply-chain

N/A — no dependency added, upgraded, or removed.
