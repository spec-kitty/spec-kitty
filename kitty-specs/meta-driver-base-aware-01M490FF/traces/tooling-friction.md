# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-06 · claude · Seed: the specify prompt's create example omits --topology, so the first scaffold came up coord; recreated with --topology lanes (worktree, coord branch and scaffold commit had to be removed by hand). spec-commit leaves status.events.jsonl modified after decision open/resolve.

2026-10-06 · claude · record-analysis refuses on ANY untracked file in the checkout, including unrelated .kittify/evidence/ and kitty-ops/ Op records left by earlier governance Ops; parked them with git stash -u (restore after the mission). The /spec-kitty.plan and .tasks prompts never mention this precondition.

2026-10-06 · python-pedro · Red-first fixture trap: a 'git merge discard' on main (ours=teammate, theirs=discard) PASSES on the pre-fix driver because two-way takes vcs/vcs_locked_at from ours and the rest from theirs; the #5460 loss only reproduces from the discarding clone (ours=discard, theirs=upstream), i.e. the git pull shape. Also base-both-changed-precedence and base-empty-file goldens are green pre-fix by design (they pin unchanged behaviour); only base-one-sided-delete is red. The e2e reproducer needs the wrapper binary to be literally named spec-kitty (git driver command resolves it by name on PATH); check_docs_freshness needs PYTHONPATH=. from a worktree.
