# Contract — `agent tracer-append --owned-checkout`

Mission `tracer-append-owned-checkout-01M6G9FW`, issue #7081. This is the CLI contract the
mission pins.

## Surface

```
spec-kitty agent tracer-append
  --mission <handle>            (required)
  --category <approach|design-decisions|tooling-friction>   (required)
  --entry <text>                (required)
  --actor <text>                (required, non-blank)
  --owned-checkout <path>       (optional, NEW)
  --json
```

`--owned-checkout` is declared as `OwnedCheckoutOption` from
`specify_cli.cli.commands._owned_checkout` and carries that module's help text verbatim; it
satisfies the `CLI_CLAIM_INPUT_RULE` (G5) with no new exemption.

## Resolution order (exactly one validation per invocation)

1. `locate_project_root()` → `cwd_repo_root`; missing → the existing error payload + exit 1.
2. `repo_root = get_main_repo_root(cwd_repo_root)`.
3. `resolve_owned_or_refuse(repo_root, --owned-checkout, mission,
   cwd=Path.cwd(), allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES, json_output=--json)`.
   - An explicit claim is validated by the minter; any refusal renders the C2 owned refusal
     and exits 1 **before** step 4.
   - Without a claim, flagless adoption applies when the invocation is made from an owned
     checkout of the named Mission; otherwise the fact is `None`.
4. With a fact: `repo_root = owned.owned_root`, `target_branch = owned.write_branch`,
   `policy = ProtectionPolicy.resolve_for_owned(owned, mission)`, and `owned=owned` is
   passed to the writer. Without one: `target_branch = get_feature_target_branch(repo_root,
   mission)` (best-effort, as today) and `policy = ProtectionPolicy.resolve(repo_root)`.

## Guarantees

| # | Guarantee |
| --- | --- |
| G-1 | With a fact, the tracer file is written under `owned.owned_root/kitty-specs/<slug>/traces/`, committed on `owned.write_branch`; the repository root gains no `traces/` file and no commit. |
| G-2 | An ownership refusal exits 1 without calling the writer: no file, directory, worktree or commit is created under either checkout. |
| G-3 | The non-owned invocation's JSON keys (`ok`, `kind`, `destination_surface`, `row_or_entry_ref`, `status`, `commit_ref`, `commit_hash`, `surfaces`, …), refusal shapes and exit codes are byte-identical to `main`'s. |
| G-4 | No new caller of `resolve_owned_mission` / `adopt_owned_checkout` appears outside `specify_cli/cli/commands/_owned_checkout.py`. |
| G-5 | The writer's existing structured refusals (unmaterialised coordination worktree, corrupt UTF-8 traces file, blank actor) keep their current payloads on both paths. |
