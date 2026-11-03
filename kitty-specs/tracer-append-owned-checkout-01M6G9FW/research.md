# Discovery — issue #7081 (tracer-append loses an owned Mission checkout)

Mission `tracer-append-owned-checkout-01M6G9FW`. Findings captured on the mission branch
against `main` @ `d18c4f1d58`.

## Reproduction

`src/specify_cli/cli/commands/agent/tracer_append.py:105-125` on `main`:

```python
cwd_repo_root = locate_project_root()
...
repo_root = get_main_repo_root(cwd_repo_root)          # ← unconditional
policy = ProtectionPolicy.resolve(repo_root)           # ← R's protected set, R's hatch
target_branch = get_feature_target_branch(repo_root, mission)   # ← R's mission copy
result = append_tracer_finding(repo_root=repo_root, ...)        # ← R as the write root
```

Confirmed at the CLI surface: `spec-kitty agent tracer-append --help` on this checkout lists
`--mission`, `--category`, `--entry`, `--actor`, `--json` and nothing else. There is no
`--owned-checkout`, so the invocation the issue reports cannot be spelled even though
`next`, `plan`, `issue-verdict`, `finalize-tasks`, `record-analysis` and `move-task` all
expose it.

The consequence is exactly the reported one: from inside an owned checkout `P` whose
Mission lives in `P`, the command selects `R` (on protected `main`), the tag commit is
refused `PROTECTED_BRANCH_REFUSED`, and the `_stage` thunk has already written
`kitty-specs/<slug>/traces/<category>.md` into `R` — untracked residue on the primary
checkout, plus a lost tracer entry.

## Supersession check

- `git log -S "tracer_append"` shows four commits, all pre-dating the owned-checkout
  machinery (`5b5699e500`, `4c15bba2e2`, `42055719dd`, `b04da00e13`). None touches the
  root selection.
- `git log -S "owned_checkout" -- src/specify_cli/cli/commands/agent/tracer_append.py`
  is empty: the file was never visited by `owned-checkout-lifecycle-authority-01M3M2ZB`.
- `src/specify_cli/retrospective/tracer_writer.py` documents the gap in its own words:
  "``append_tracer_finding`` has no ``owned`` parameter (binding correction, brownfield
  scout round 3), so this never threads one through."
- No ADR or changelog fragment mentions tracer routing; no open PR references #7081.

Not superseded, still reproduces on `main`.

## Decisions

### D1 — Reuse the one owned CLI seam; do not add a second resolver

`specify_cli/cli/commands/_owned_checkout.py` is G2's designated sole CLI caller of
`resolve_owned_mission` / `adopt_owned_checkout`, policed by
`tests/architectural/test_owned_checkout_single_authority.py` with an **empty allowlist**.
`resolve_owned_or_refuse` already does exactly what this command needs: validate the
explicit claim once, otherwise attempt flagless adoption, render the C2 refusal and exit.

Adding any bespoke claim parsing would either fail that gate or require weakening it.
Rejected: calling `resolve_owned_mission` from `tracer_append.py` directly.

### D2 — Flagless adoption is the real fix; the flag is the explicit spelling

The issue's repro runs *from* the owned checkout with **no** flag. `adopt_owned_checkout`
already returns the fact for that case (it deliberately declines only lane worktrees), so
routing through `resolve_owned_or_refuse` fixes the reported invocation, and the new flag
covers the case where the caller wants to name `P` from elsewhere. Both paths land in the
same place.

Rejected: making `--owned-checkout` mandatory. It would force every owned caller to change
its command line and would leave the reported invocation broken.

### D3 — Derive all four inputs from the fact, not just the root

`repo_root` alone is not enough. `ProtectionPolicy.resolve(R)` folds `R`'s protected set
and `R`'s operator hatch; for an owned Mission the hatch and the branch set belong to the
fact (`ProtectionPolicy.resolve_for_owned`). Likewise `get_feature_target_branch(R, slug)`
reads `R`'s copy of the Mission — the exact stale copy this defect is about — while
`owned.write_branch` is the branch `P` is on and the write must land on.

Rejected: setting only `repo_root = owned.owned_root` and leaving the policy/target
computation on the old root (it would keep reading `R`'s meta and `R`'s config).

### D4 — Thread the fact into the writer rather than reconstructing it there

`write_artifact` already accepts `owned`, and `placement_seam(...)` accepts it too. The
tracer writer is the last Mission-scoped writer that does not thread it; its own docstring
records that as a known limitation. Passing the already-validated fact avoids a second
ownership interpretation below the CLI and keeps the coordination-surface materialisation
governed by the same fact.

## Risks observed while reading

- `_stage` writes the file before the commit is attempted, by design (read-before-write
  merge under the mission write lock). The refusal-before-write requirement is therefore
  about the **ownership** refusal only, which must fire before `append_tracer_finding` is
  reached; the writer's own post-probe refusals keep their existing shapes.
- `tests/mission_runtime/test_coord_read_seam_callers.py` binds `tracer_append` through
  `importlib.import_module` because the package attribute is rebound by `agent/__init__`;
  the new tests must do the same to exercise the real module.
