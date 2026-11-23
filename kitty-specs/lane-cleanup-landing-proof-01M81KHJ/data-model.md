# Data Model: One landing proof for lane cleanup

No persisted data changes. The proof reads git objects only.

## Value objects

- **Lane tip** (`str`, commit SHA): the claim-validated tip cleanup proves (consolidate), or the worktree `HEAD` (doctor).
- **Landing ref** (`str`): `refs/heads/<target>` at the PASS anchor (consolidate) or `refs/remotes/<remote>/<primary>` (doctor, pr-mode).
- **Mission slug** (`str`): the lane's own Mission directory name under `kitty-specs/`; consolidate reads it from `lanes.json`, doctor from the released Mission's directory matched by the lane branch.
- **Lane-own commits** (`frozenset[str]`): first-parent commits of the tip reached by neither the landing ref nor any branch the lane merged in.
- **Authored paths** (`frozenset[str]`): paths a lane-own commit changed, a merge counting only when its result is none of its merged-in parents' versions.
- **Bookkeeping kinds** (closed set): `kitty-specs/<slug>/status.events.jsonl` (containment rule), `kitty-specs/<slug>/status.json`, `kitty-specs/<slug>/meta.json`, `kitty-specs/<slug>/tasks/WP*.md` (never-authored rule).

## Invariants

- The proof is `True` only if no lane content can be lost: outside `kitty-specs/`, merging the tip changes nothing on the landing ref; under `kitty-specs/`, every differing path matches one rule of research R3.
- A merge result is never evidence for a `kitty-specs/` path.
- Any git error makes the proof `False`.

## Kept code

- `LANDING_PROOF_UNAVAILABLE`: cleanup had no usable landing proof for the lane; the worktree and branch are left as they are.
