# Tooling friction

- `agent tasks move-task` refuses in the minimal terminus fixture (no `.kittify/config.yaml`, target `main` protected); recovery tests drive the reopen through the production status shell instead.
- `git log --since=90.days` is meaningless in the shallow cloud clone (51 commits).
- Each pytest session in this container spends ~100 s in setup (conftest bootstrap), so single-file runs are slow; batch them.
- `git commit` with a model-identifier trailer and `gh` issue assignment were refused by the session permission layer.
- LOW-1 (run the printed `move-task` literally in the recovery test): tried with an unprotected `work` target; `move-task` then runs as printed, but the terminus fixture is the non-canonical bare-slug coordination shape (#5651), so the review-cycle file lands in the composed directory and the landing refuses `ALIAS_FILE_NOT_PRESERVED`; `implement` also needs an analysis report the fixture lacks. Not folded: needs a canonical-shape real-CLI fixture.
