# Quickstart: Reproduce & Verify — Charter Activation Catalog Coherence (#4785)

**Isolation rule (critical)**: charter write commands mutate tracked files and resolve to the
PRIMARY checkout. Do all write-reproduction in an isolated `git clone` of this repo under a
scratch dir — NOT a git worktree (worktrees do not isolate charter writes; that is Finding 3).
Never `git stash` in a shared clone.

```bash
git clone <this-repo-path> /tmp/repro && cd /tmp/repro
python -m pip install -e .            # editable; do NOT use a bare `uv run` that re-syncs a hand-built .venv
```

## F1 — activate leaves the catalog stale (RED today)

```bash
PYTHONPATH=src python -m pytest tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent -q   # GREEN baseline
spec-kitty charter activate directive 051-supply-chain-install-safety   # a built-in absent from the baseline catalog
PYTHONPATH=src python -m pytest tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent -q   # now RED: reference_id_divergences=['directive/051-...']
```
**After the fix**: the activate step leaves the guard GREEN (catalog recompiled by default).

## F2 — the suggested remediation cannot recompile (RED today)

```bash
spec-kitty charter synthesize   # prints "Charter synthesis (fresh project): minimal .kittify/doctrine/ materialized." and leaves the divergence
```
**After the fix**: the coherence-guard suggestion + `--resynthesize` help name `generate`, and
`synthesize` on this established store does NOT report "fresh project".

## F3 — charter writes hit the PRIMARY checkout from a worktree (RED today)

```bash
git worktree add /tmp/repro-wt -b wt-charter-test HEAD
cd /tmp/repro-wt && spec-kitty charter generate --from-interview
cd /tmp/repro && git status --porcelain .kittify/charter/charter.yaml   # PRIMARY shows 'M' — the write landed here, not in the worktree
```
**After the fix**: the command fails closed from the worktree (non-zero + "use a
repository-root checkout or dedicated clone"); the primary store is untouched.

## F4 — over-render + placeholder summaries (RED today)

```bash
git -C /tmp/repro reset --hard HEAD
spec-kitty charter generate --from-interview
grep -c "Definition unavailable in bundled doctrine." /tmp/repro/.kittify/charter/charter.yaml   # > 0 directive entries
spec-kitty charter generate --from-interview   # second run
git -C /tmp/repro diff --stat -- .kittify/charter/charter.yaml   # catalog.references churns/reorders (should be zero after fix)
```
**After the fix**: zero placeholder summaries for directives with a bundled definition; a second
recompile is a zero-line diff of the `catalog.references` section.

## Full verification (post-implement)

```bash
make test-fast
PYTHONPATH=src python -m pytest tests/charter tests/doctrine tests/specify_cli/cli/commands/charter tests/specify_cli/charter_runtime -q
```
