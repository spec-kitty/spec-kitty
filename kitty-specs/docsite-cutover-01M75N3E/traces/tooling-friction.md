# Tooling friction

- **[2026-11-11][setup] Topic branch tracked `origin/main`.** `git checkout -b <topic> origin/main` set the topic branch's upstream to `origin/main`; unsetting it before `mission create` keeps a later push from targeting main. Disposition: workaround, no gap.
- **[2026-11-11][implement] Slow targeted pytest runs.** A single test file of `tests/release` takes about 95 s, mostly collection and session fixtures, which pushed the first red run past the 120 s foreground limit. Disposition: ran it in the background; no gap filed.
- **[2026-11-11][implement] actionlint not installed.** The container has no `actionlint`; installed v1.7.7 with `go install` into `~/go/bin`. Disposition: workaround.
- **[2026-11-11][review] `move-task` reported "NOT committed (--no-auto-commit)" without the flag.** The reviewer's approval left `status.events.jsonl`, `status.json` and `review-cycle-1.md` uncommitted. Disposition: committed by hand; candidate gap, noted in the PR.
- **[2026-11-11][close] Assess.** Candidate gap: `move-task` left review status files uncommitted without `--no-auto-commit`. The rest were workarounds (topic upstream, slow collection, missing actionlint). The live switch and first smoketest are deferred to #6938 after merge.
