# Tooling friction

Tooling touched: `spec-kitty dispatch` / `profile-invocation complete`
(the Op executor), `safe_commit`, `doctor ops --close-stale`.

- **[2026-10-18][specify] `agent mission create --pr-bound --json` refuses without `--branch-strategy already-confirmed`.** The refusal names the remedy, so the fix took one retry. Disposition: working as designed.
- **[2026-10-18][specify] This repository tracks Op records, so this Mission's own Op closes commit onto the topic branch.** That is the bug under fix. Disposition: workaround: drop any `op(...)` commit from the branch before opening the PR.
- **[2026-10-18][implement] No .venv; the repo's pytest needs a built test venv.** There was no `.venv`, the global pytest tool env lacks project deps, and the first pytest run builds `.pytest_cache/spec-kitty-test-venv` (`pip install -e`), taking about 3 minutes per cold run. Disposition: used a scratchpad venv with `--system-site-packages` plus pytest, xdist and pytestarch; ran with `-n 4 --dist loadfile`.
- **[2026-10-18][implement] Red-first test passed on first run.** The repro commit was silently refused with "Author identity unknown" because `safe_commit` shells out to a plain `git commit` and the fixture only used `-c` identity flags. Disposition: the fixture sets repo-local `user.email`/`user.name`; the test then failed on the base as required.
- **[2026-10-18][implement] Red-first run was contaminated by in-progress edits.** The first slow run imported modules after the fix was already on disk and passed. Disposition: re-ran the test against `git stash push -- src/` to get a clean RED.
- **[2026-10-18][closeout] `move-task --to approved` refused until the issue matrix row had a verdict.** The remedy is `agent issue-verdict`, and the refusal named it. Disposition: working as designed.
- **[2026-10-18][closeout] A git-path-listing gate went red that only the pre-PR boundary lens caught.** The WP01 reviewer ran the gates named in the WP prompt, not the gates the diff implicates. Disposition: candidate gap: WP prompts should ask for an architectural gate grep of the touched call sites (`ls-tree`, `check-ignore`).
