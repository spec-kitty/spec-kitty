# Data Model & Contract: Driver-Replay Attribution Probe

This mission adds no persisted data model. The one new logical contract is the **driver-replay
attribution proof**, replacing the byte-equality check in `projected_content_matches_target`.

## Entities / values

- **Projected path** `repo_rel: str` — a post-checkpoint coord-partition path (`kitty-specs/<slug>/…`,
  status byte-sets and PRIMARY artifacts excluded) as returned by `_post_checkpoint_mission_paths`.
- **Blob triple** for a path: `base = git show <checkpoint>:path`, `ours = git show <pre-merge-target>:path`,
  `theirs = git show <coord_ref>:path` — the `%O / %A / %B` inputs git passes to the merge driver.
  `pre-merge-target` is the target baseline captured before the squash (`target_baseline_sha` /
  `pre_mutation_*` on the merge run state), NOT the post-squash target.
- **Registered driver** — the `merge=<name>` attribute from `.gitattributes` for the path, mapped to
  its `spec-kitty merge-driver-<name>` implementation (reuse the existing registry; do not fork).
- **Expected blob** — the bytes the registered driver writes to `%A` when replayed on the triple.
- **Landed blob** — `git show <target>:path` after the squash.

## Proof contract (replaces `coord_bytes == target_bytes`)

For each projected path:

| Situation | Verdict |
|---|---|
| Target did NOT diverge from checkpoint (`ours == base`) and coord carried forward | PASS iff `landed == theirs` (existing behavior; no regression — FR-004) |
| Path is driver-governed and diverged: `landed == driver_replay(base, ours, theirs)` | **PASS** (legitimate lossless union — FR-001) |
| Path is driver-governed and diverged: `landed != driver_replay(...)` | **REFUSE** (genuine non-landing / dropped coord content / tampering — FR-002) |
| Diverged path has NO registered driver, OR an input blob is missing, OR a git/driver probe errors | **REFUSE** fail-closed (FR-003) — never silently PASS |

Determinism guarantee: the driver is the SAME code git invoked during the squash, and it is
deterministic/idempotent (verified in Phase R), so a legitimate squash's landed blob equals the
replay by construction; a divergence means the landed content is not the driver's output.

## Invariants (fail-closed floor)

- **INV-FLOOR-1**: a landed blob that is not the driver-replay output REFUSEs (re-grounded
  `test_5038_p2`).
- **INV-FLOOR-2**: an unevaluable probe REFUSEs, never PASSes (FR-003).
- **INV-FLOOR-3**: the product-content attribution axis (`_unattributable_content_squash`) and its 13
  guardian tests are unchanged and stay green (NFR-001) — the #4945/#4977/#4981/#5001/#5018/#5022
  data-loss class stays caught.
- **INV-NO-REGRESSION**: the `ours == base` non-diverged subset keeps PASSing exactly as today
  (FR-004).
