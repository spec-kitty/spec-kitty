# Research: Terminus Projection Driver-Replay Attribution (#5038, #5021-r2)

Phase R ran BEFORE specify (charter research-first). Three profile-loaded opus lenses (R1
approach-adjudication, R2 data-loss/fail-closed, R3 scope/boundary), each grounded in real
`merge-driver-traces` / `spec-kitty merge` CLI runs on the post-#5040 base (`main` @ `ae0ff2fbf2`).
Every claim below was witnessed in a real run; no claim rests on code-reading alone.

## Decision 1 — Fix #5038 via driver-replay attribution (candidate a, driver-governed form)

**Decision**: Replace the projection proof's `coord_bytes == target_bytes` byte-check with a
driver-replay attribution proof: for each post-checkpoint coord-partition path, reconstruct the
EXPECTED landed blob by replaying the path's registered `spec-kitty merge-driver-*` command on
`(%O = checkpoint blob, %A = pre-merge-target blob, %B = coord blob)`, and PASS iff the actual
landed target blob byte-equals that expected blob. REFUSE otherwise (including when the probe cannot
be evaluated).

**Rationale**:
- `traces/*.md` resolves via `.gitattributes` → `merge=spec-kitty-traces` →
  `spec-kitty merge-driver-traces %O %A %B` → `merge_driver_traces` (`merge_driver.py:525`), a
  DETERMINISTIC, order-preserving, lossless append-union (`_drop_stale_theirs_trace_blocks` +
  `union_trace_texts`) that never conflicts and always exits 0 (INV-3: every non-empty line of both
  inputs survives). It is replayable in-process.
- Empirically (R1/R2 both ran the real driver): P1 (additive) and P2 (same-line) triples BOTH
  produce a lossless union containing the coord block verbatim. The current byte-equality proof
  therefore FALSE-REFUSEs both — including any real mission that edits a tracer/verdict/notes file
  on both target and lane during merge. This is the true (previously-unreproducible-as-filed) #5038.
- Driver-replay is a genuinely SOUND proof: it certifies the landed blob is exactly the deterministic
  driver's output from the three inputs, so a landed blob that is NOT the driver's output (genuine
  non-landing / dropped coord section / tampering — the #4981/#4970/#4973 projection job) still
  REFUSEs.

**Alternatives considered**:
- *Symmetry fix* (assert only over `ProjectionResult.projected_paths`, i.e. exclude target-diverged
  paths): REJECTED. `project_post_checkpoint_commits_to_target` (line 556) skips a path when the
  target diverged from checkpoint — true for BOTH P1 and P2 — so this green-washes P2 AND verifies
  nothing on the diverged path (strictly fail-OPEN). Worse than the disease.
- *Naive driver-replay described as "landed == driver output" with no fail-closed on unevaluable*:
  refined into FR-003 (missing input / no registered driver / probe error → REFUSE).

## Decision 2 — There is NO discriminator that flips P1 while keeping P2-as-codified REFUSE

**Decision**: Accept that P1 and P2 are informationally identical at the projection gate; therefore
adopting the sound fix (Decision 1) necessarily flips P2 to PASS, and `test_5038_p2` must be
**re-grounded** onto a genuinely-lossy scenario.

**Rationale**: Every signal over `(checkpoint, target, coord)` gives the same verdict for P1 and P2
(`coord != target`; stock-git would conflict on both; the union driver losslessly merges both). The
`test_5038_p2` module docstring itself concedes "BOTH shapes present identically". R1 and R2
independently concluded the same. P2-as-written asserts a byte-equality REFUSE on a **non-lossy union
of a bookkeeping path** — its "unresolvable divergence" premise is empirically FALSE for the union
driver.

**Fail-closed analysis (R2)**: The genuine data-loss floor lives on the ATTRIBUTION axis
(`_unattributable_content_squash`), which SKIPS bookkeeping paths (`_is_bookkeeping_path`, line 640)
and is untouched by a projection-axis change. The 13 guardian tests
(`test_repro_4945/4977/4981/5001/5018/5022` + `test_squash_fails_when_superseded_v1_blob_ships`,
`test_squash_fails_on_second_parent_smuggled_blob`, `test_squash_unattributed_deletion_fails`,
`test_squash_authored_deletion_union_across_two_lanes_passes`, `test_squash_passes_clean_no_false_fail`)
stay GREEN. Driver-replay is strictly STRONGER than today's `coord==target` for detecting real loss
(it validates the whole blob against the deterministic driver output, not just against coord alone).

**Operator ruling**: Option B, decision `DM-01M3EC2FMWKCKGSBX1QHC7GFCJ` — the P2 byte-equality
premise is disproven for union-driver paths; re-grounding onto genuine loss is authorized. This is a
sanctioned floor re-adjudication, NOT a green-wash: the re-grounded P2 must REFUSE a landed blob the
driver replay does not reproduce.

## Decision 3 — #5021-r2 is soundly unfixable; keep honest strict-xfail, split to its own issue

**Decision**: Do NOT attempt to flip `test_squash_three_way_merge_resolution_is_unattributable`.
Keep it `xfail(strict=True)` with a narrowed reason and file a dedicated follow-up issue.

**Rationale (R1/R2, real stock-git runs)**: `src/shared.py` has no merge driver → stock
`git merge-file` / `git merge-tree --write-tree` return rc=1 with conflict markers on the alpha-vs-beta
case; the manually-resolved `resolved\n` third blob equals neither parent and is reconstructable by
NO deterministic function. Merge-tree simulation cannot attribute it (git conflicts); union-of-parents
attribution still fails (`resolved ∉ {alpha, beta}`); the only acceptance (skip attribution for
multi-authored paths, or union ALL intermediate blobs) green-washes the #4945 canceled-content class
or breaks the superseded-`v1` guardian. Honest xfail is the only sound disposition.

## Decision 4 — ONE mission, TWO file-disjoint slices (R3)

**Decision**: Fold both issues into ONE mission with two file-disjoint slices (WP01 code fix for
#5038; WP02 doc/disposition for #5021-r2). They share one root phenomenon (target blob != either
parent) but distinct code seams (projection vs attribution axis), distinct paths (bookkeeping
`traces/` vs product `src/shared.py`), and distinct determinism (deterministic union vs stock-git
conflict). #4997 (staged-deletion `LOCAL_CHANGES` window, PR #5031) is a DISTINCT class and stays OUT;
do not touch its files.

## Grounded seam map (verified line numbers, post-#5040 base)

- `src/specify_cli/merge/executor.py:2307` `_assert_squash_projected_content_landed` — re-derives the
  candidate set from `_post_checkpoint_mission_paths` (FULL set) and demands
  `projected_content_matches_target`. Call-site to rewire.
- `src/specify_cli/merge/bookkeeping_projection.py:569` `projected_content_matches_target` — the
  `coord_bytes is None or target_bytes != coord_bytes → False` byte-check to replace with the probe.
  Line 501/556 `project_post_checkpoint_commits_to_target` skips target-diverged paths (why the
  assertion's re-derived FULL set is the bug).
- `src/specify_cli/merge/git_probes.py` — probe layer; candidate home for the registered-driver-replay
  helper (`_git_show_blob_bytes` already reads blobs by ref; `target_baseline_sha`/`pre_mutation_*`
  provide the pre-merge `%A`).
- `src/specify_cli/cli/commands/merge_driver.py:525` `merge_driver_traces` (+ the driver registry in
  `src/specify_cli/lanes/merge.py`) — the deterministic drivers to replay; reuse, do not fork.

## Adversarial-evidence disposition

No dependency changes → supply-chain section N/A. Phase R itself was the pre-spec adversarial pass
(3 independent lenses). All contested points were resolved to `accepted` (driver-replay for #5038;
honest-xfail for #5021-r2) with real-run evidence; none dropped silently. A post-tasks adversarial
lens and a pre-merge data-loss lens will re-challenge the re-grounded `test_5038_p2` (the sole
green-wash-risk artifact).
