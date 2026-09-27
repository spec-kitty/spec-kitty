# Quickstart: reproduce & verify

How to witness the bugs (RED) and confirm the fix (GREEN). Mirrors the reproductions in #5171 and
#4943. Use an isolated HOME/XDG and a disposable repo (see #4943's `lib.sh`).

## 1. #5171 — mission-review false hard FAIL (coord topology)

```bash
# coord mission; spec cites an issue so finalize-tasks scaffolds a matrix row
spec-kitty agent mission create demo --mission-type software-dev --topology coord ...
# ... implement, review, then finalise the verdict on the coordination surface:
spec-kitty agent issue-verdict --mission <slug> --issue '#11' --verdict fixed --actor qa
#   -> OK #11 -> fixed (committed, surface=kitty/mission-<slug>)

# RED (today): the documented Gate 4 reads the PRIMARY residue
cat kitty-specs/<slug>/issue-matrix.json      # shows #11: in-mission (stale) -> false FAIL
# GREEN (fix): mission-review resolves the coord partition and reports #11: fixed -> PASS
```

Verify: mission-review PASSes when the coord surface is terminal (SC-001); still FAILs when the coord
surface itself is genuinely `in-mission` (positive control).

## 2. #4943 leg 1 — merge false PASS (coord husk discovery)

```bash
# coord mission citing #1234 in spec.md, no matrix row, mode: block
# RED (today): merge -> "No gating issue references discovered — nothing to enforce", exit 0
# GREEN (fix): merge discovers #1234 from the PRIMARY spec dir and FAILs (matches the lanes arm)
spec-kitty merge --mission <slug>
```

Verify parity: coord and lanes arms of the same fixture both FAIL on the missing row (SC-002).

## 3. #4943 leg 2 — merge lands an unresolved verdict

```bash
# gating row at in-mission, mode: block
# Control: hand-merge lane then `move-task WP01 --to done` -> exit 1 "Still 'in-mission'"
# RED (today): spec-kitty merge -> exit 0, row on target still in-mission, WP done
# GREEN (fix): merge refuses (block) naming the row; warn prints the same list
spec-kitty merge --mission <slug>
```

Verify: block refuses before the target advances (SC-003); the same mission with a terminal verdict
lands cleanly (positive control).

## 4. Deep — verdicts readable post-consolidation

```bash
# consolidate the coord mission so the worktree is removed but the branch is retained,
# then author #11 -> fixed on the coordination branch, then run mission-review AND merge.
# GREEN (fix): both resolve #11 from the branch ref (git show <coord-branch>:...) -> fixed (SC-004)
# A genuinely deleted coord branch fails closed (does not read the primary residue).
```

## 5. Guard & regression

```bash
# non-vacuous guard: injecting a raw `cat kitty-specs/.../issue-matrix.*` into a review/merge
# consumer or the Gate-4 doctrine must trip the architectural test (SC-005 self-mutation check).
pytest tests/architectural/ -k issue_matrix -q
```

## Targeted test surface (blast radius)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/policy \
  tests/specify_cli/cli/commands/review \
  tests/mission_runtime tests/unit \
  tests/integration -k "issue_matrix or coord or verdict or merge_gates" \
  tests/architectural -k "issue_matrix or layer or terminology" -q
ruff check . && ruff format --check .
pytest tests/architectural/test_no_legacy_terminology.py -q   # before pushing doctrine/prose
```
