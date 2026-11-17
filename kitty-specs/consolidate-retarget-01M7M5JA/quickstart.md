# Quickstart: retarget a Mission at consolidation

```bash
git checkout develop            # the new target, cut from the old one after the Mission was created
spec-kitty consolidate --mission <m> --dry-run --json --target develop --retarget   # forecast
spec-kitty consolidate --mission <m> --target develop --retarget --retarget-reason "release train moved"
git show develop:kitty-specs/<m>/meta.json | jq '.target_branch, .retarget_history'
```

If anything fails after the retarget commit, the run restores `develop` (and the Mission branch) to its pre-run tip. `spec-kitty consolidate --resume` re-applies the retarget, and `spec-kitty consolidate --abort` drops it.
