# Quickstart: reproduce at base, verify after the fix

**Audience:** the implementer and reviewer of this Mission. Base revision: `ecb5dd914a`. Every command runs in a throwaway repository, never in this checkout.

## 0. Throwaway fixture

```bash
S=$(mktemp -d) && cd "$S"
git init -q -b main && git config user.email t@t && git config user.name t
echo x > README.md && git add . && git commit -qm init
spec-kitty init . --ai claude --non-interactive && git add -A && git commit -qm "spec-kitty init"
git checkout -qb topic
spec-kitty agent mission create demo --topology coord --branch-strategy already-confirmed --json > create.json
M=$(python3 -c 'import json;print(json.load(open("create.json"))["mission_slug"])')
C=$(python3 -c 'import json;print(json.load(open("create.json"))["coordination_branch"])')
```

Run the same steps with `--topology lanes_with_coord`, and with `--pr-bound --start-branch topic` from `main`.

## 1. #5440: create commits status to the target branch (US1, FR-001/002)

```bash
git show --stat HEAD                              # base: lists kitty-specs/$M/status.events.jsonl
git ls-tree -r --name-only "$C" | grep "$M"       # base: empty (coordination branch born without the Mission dir)
git worktree list                                 # base: no coordination worktree
```

**After the fix:**
- the target scaffold commit has `meta.json` and `tasks/*` but no `status.events.jsonl`;
- `$C` carries `kitty-specs/$M/status.events.jsonl` holding `MissionCreated` and `SpecifyStarted`;
- the coordination worktree exists;
- `spec-kitty doctor coordination --json` reports no `COORDINATION_BRANCH_DIVERGED_VS_TARGET`.

Tests: R1, R1b, R1c, R20.

## 2. #5519: fork and clock restart (US2)

```bash
spec-kitty agent decision open --mission "$M" --flow specify --slot-key s.a --input-key a --question "A?" --json
# append a tracer entry through the tracer writer (retrospect tracer append, or the
# library append_tracer_finding), which creates the coordination Mission dir at base
spec-kitty agent decision open --mission "$M" --flow specify --slot-key s.b --input-key b --question "B?" --json
wc -l kitty-specs/$M/status.events.jsonl .worktrees/*/kitty-specs/$M/status.events.jsonl
```

- **At base:** two logs. The second `event_lamport` restarts.
- **After the fix:** one log on the coordination surface, and `lamport2 > lamport1`.

Pre-fix healing: run the base CLI to create the Mission and open the first decision, then run the fixed CLI for the tracer append. The root records are carried over exactly once, and the root copy is restored.

Tests: R4, plus the seed tests in IC-03.

## 3. #5519: destructive repair (US4)

Build the fork fixture from step 2 (at base), then:

```bash
python3 -c 'import json;print(len(json.load(open("kitty-specs/'"$M"'/decisions/index.json"))["entries"]))'
spec-kitty doctor decisions --mission "$M" --repair --json
python3 -c 'import json;print(len(json.load(open("kitty-specs/'"$M"'/decisions/index.json"))["entries"]))'
spec-kitty agent decision verify --mission "$M" --json; echo "exit=$?"
```

- **At base:** the entry count drops, and verify exits 0.
- **After the fix:** the count is unchanged, the output has `forked: true` and the reconcile steps, and verify exits 1 with `DECISION_LOG_FORKED`.
- **Fresh clone:** `git clone "$S" c2 && cd c2 && spec-kitty doctor decisions --mission "$M" --json` reports the fork from refs.

Tests: R3, R14, R15, R16.

## 4. #5513: router reports "unchanged" for a dirty coordination copy (US3)

```bash
# make the status log dirty ONLY in the coordination worktree, then:
python3 - <<'EOF'
from pathlib import Path
from specify_cli.coordination.commit_router import commit_for_mission
# call with files=(repo_root/"kitty-specs"/M/"status.events.jsonl",), kind=STATUS_STATE
EOF
```

- **At base:** `status == "unchanged"`, `reason == "no_op_already_committed"`.
- **After the fix:** `committed` on `$C`, `surfaces` lists the coordination outcome, and the clean-copy control still reports `unchanged`.

Tests: R2, R2b.

## 5. #5501: spec-commit drops the status log (US3.4)

```bash
spec-kitty spec-commit --mission "$M" -m "spec batch" \
  kitty-specs/$M/spec.md kitty-specs/$M/decisions/index.json kitty-specs/$M/traces/approach.md kitty-specs/$M/status.events.jsonl --json
```

- **At base:** `success: true`; the status log is silently dropped and `decisions/` is re-routed to the coordination branch.
- **After the fix:** `arguments[]` names every path's fate. The ledger and `spec.md` are on the target; traces and the status log are on `$C`.

Test: R5.

## 6. accept (US3.5-3.7)

Create two fixtures: a COORD record dirty in the root checkout, and one dirty only in the coordination worktree. Run `spec-kitty accept --mission "$M" --json` against each.

- **At base:** the first fixture's record is committed to `topic`; the second fixture's record is skipped or overwritten.
- **After the fix:** the first is reported `COORD_RECORD_IN_ROOT_CHECKOUT` (never on `topic`); the second is committed on `$C`.

Tests: R7, R8, R9.

## 7. finalize, planning pin, receipts (US3.8, US5, US6)

- `finalize-tasks` with coordination-only dirt: at base "no changes"; after the fix, committed on `$C` (R10).
- `finalize-tasks`, then a planning commit, then `finalize-tasks` again: `lanes.json` `planning_commit_sha` is refreshed with no flag (R17).
- `spec-kitty agent action implement WP01 --json`: every `commits[].sha` is non-null and contained in its `destination_ref` (R18).

## 7b. Consolidation and `materialize` writers (IC-18, ruling Q4)

- **Pre-fix EMPTY Mission plus `spec-kitty consolidate`.** At base, the `done` events land in the repository root checkout's log. After the fix: one seed commit on `$C` lands before the merge, and the `done` events are in the coordination log (R22).
- **UNMATERIALIZED with a local branch.** Remove the coordination worktree (`git worktree remove`), then run `spec-kitty consolidate`. At base it exits 1 with "Merge aborted before any state change". After the fix it materializes the surface and proceeds. A remote-only branch still aborts (R23).
- **`spec-kitty materialize`** (no `--mission`), on a MATERIALIZED coordination Mission whose root copy is stale. At base, `status.json` is written in the root dir from the stale log. After the fix it is written on the coordination surface (R24).
- **Guards.** Run the consolidation guard files listed in plan IC-18, each by name.

## 8. Gate and end-to-end

```bash
pytest tests/architectural/test_no_write_side_rederivation.py -q            # R19: red at base on real offenders
pytest tests/integration/test_coord_single_home_workflow.py -q              # FR-015, both topologies + moved merge base
```

## 9. NFR-001 timing

```bash
scratchpad/nfr001/bench.sh coord topic; scratchpad/nfr001/bench.sh lanes_with_coord prbound
```

The baseline medians are about 2.64 s (`research.md`). After the fix, record the medians in the PR. Each must stay within baseline + 1.0 s; there is no absolute bound (ruling Q2).

## Test policy (C-006)

Run the targeted test files above, the owning-module test directories of each changed file, and the named architectural gate files:
- `test_no_write_side_rederivation.py`
- `test_write_surface_placement_guard.py`
- `test_merge_reconciliation_class_guard.py`
- `test_layer_rules.py`
- `test_status_events_writes_gate.py`
- `test_status_state_read_dir_single_authority.py`

Never run the full `tests/architectural/`, the e2e suite as a whole, or `make test-full` locally.
