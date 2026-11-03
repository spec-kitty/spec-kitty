# Quickstart: verify the create-claim refusal by hand

Mission: `owned-create-root-refuses-mission-worktree-01M6GRFM` · Issue: #6956

## 1. Build a repository with a coordination worktree

```bash
git init -q -b work /tmp/r && cd /tmp/r
git config user.email t@example.invalid && git config user.name T
mkdir .kittify && echo seed > README.md
git add . && git commit -qm seed
git worktree add -q -b codex/coord .worktrees/probe-01M6GRFM-coord
```

## 2. The claim is refused before anything is scaffolded

```bash
spec-kitty agent mission create probe --owned-checkout /tmp/r/.worktrees/probe-01M6GRFM-coord --json
echo "exit=$?"          # 1
```

Expected last JSON line:

```json
{"ok": false, "error": {"code": "OWNED_CHECKOUT_IS_MISSION_WORKTREE", "message": "--owned-checkout names a worktree registered to an existing mission ..."}}
```

Then confirm nothing happened in the claimed checkout:

```bash
git -C /tmp/r/.worktrees/probe-01M6GRFM-coord status --porcelain   # empty
ls /tmp/r/.worktrees/probe-01M6GRFM-coord/kitty-specs              # no probe-* directory
```

## 3. An ordinary linked owned checkout still works

```bash
git -C /tmp/r worktree add -q -b codex/owned /tmp/owned
spec-kitty agent mission create probe2 --owned-checkout /tmp/owned --json
echo "exit=$?"          # 0, scaffold_only
ls /tmp/owned/kitty-specs    # probe2-<mid8>
```

## 4. The read-only startup gates never follow a refused claim

```bash
spec-kitty agent context resolve --action plan --mission probe2 --owned-checkout /tmp/r/.worktrees/probe-01M6GRFM-coord --json
```

The startup gates then run against `/tmp/r` (the repository root), and the command's own leaf
refuses. `startup_project_checkout` returns the repository root for any claim the minter refuses.

## Automated coverage

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_mission_create_owned_worktree_refusal.py -q
uv run --frozen pytest tests/core/test_owned_mission_minter.py -q -k create_root
uv run --frozen pytest tests/specify_cli/cli/commands/test_owned_checkout_helper.py -q -k OpRecordRoot
```
