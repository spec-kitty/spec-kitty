# Approach

## Initial (planning)

Three independent seams, one WP each, red-first through the real entry point. Grounding squad (researcher-robbie, paula-patterns, debugger-debbie) confirmed the seams and reproduced #5576 on a real repository. Implementers python-pedro / implementer-ivan on Sonnet 5.5 high; reviewer-renata on a high-reasoning model; pre-PR squad reviewer-renata + architect-alphonso.

Order: WP01 (canonical fresh) before WP02 (consent) because both touch `CommandInstaller.preserve`; WP03 in parallel.

## 2026-10-03 — Landing folds queued

- WP03 review (minor): `_working_object_ids` encodes the `--stdin-paths` payload with `str.encode()`; a non-UTF-8 filename raises instead of failing closed. Fold: `os.fsencode()`, plus a test.
- `contracts/planning-artifact-staging.md` still says `git hash-object --path`; correct to `--stdin-paths` (the `--path` + `--stdin-paths` combination is invalid).
- WP03 reviewer recorded issue-matrix rows: #5576 fixed (WP03); #5574/#5575 in-mission; #2527/#5281/#702 not-applicable.

## 2026-10-03 — Codegraph clause for all remaining subagent prompts (operator request)

Paste verbatim into every subagent prompt from here on (WP02 review, pre-PR squad, folds):

> **Codegraph (use it, and report on it).** A CodeGraph index is available: run `codegraph explore "<symbols or question>"` from `/home/stijn/Documents/_code/SDD/fork/spec-kitty`. Use it FIRST for callers, call paths and blast radius of the symbols you touch or review, before grep/read.
> **Caveat — it describes mainline, not this mission.** The index is of the primary checkout at the base commit (`fb7c92d6f0`, `skupstream/main`), not of this clone or its lane worktrees. It does not contain any WP01–WP03 change. Use it for "who calls X / what does X affect on main"; read the lane worktree files (or `git diff kitty/upgrade-windows-drift...HEAD`) for the current state of the work. Never treat a codegraph body as the reviewed code.
> **Report:** end your report with one line `Codegraph: used N calls / not used — <what it saved or why not>`.

WP01/WP03 implementers and reviewers did not get this clause (WP02 implementer was dispatched before it); their reports carry no codegraph signal.

## 2026-10-03 — Implementation evidence (red-first and counts)

| WP | Red-first commit | Red result | After | Review |
|----|------------------|------------|-------|--------|
| WP01 #5574 | `1ba9526b07` | real `upgrade --yes` exit 1 "Unresolved tool-surface drift"; 3 unit tests failed, 4 ratchets green | WP list 310 passed / 1 xfail; test-fast 2169 passed | APPROVED (replayed red) |
| WP02 #5575 | `39261ac2c6` | 3/3 failed (`--fix` left edit, `repair_command=None`, canonical bytes reported drift) | WP list 300 passed / 1 xfail; skills+tool_surface 1571 passed; dead-symbol gate 37 passed | APPROVED (replayed red) |
| WP03 #5576 | `ba232393f3` | 4 failed / 2 passed (ratchet green) | WP set 112 passed; trio gate 14 passed; test-fast 2169 passed | APPROVED (replayed red) |

Codegraph usage: orchestrator 4 calls during planning; WP02 reviewer 1 call (C-003 call-site census). Earlier subagents had no clause.

## 2026-10-03 — Closeout

- Consolidated, rebased on `skupstream/main`, three landing folds (`c709f13140`, `9df9955d48`, `c63841d2fa`), changelog `2dbdd00423`.
- Pre-PR squad: reviewer-renata LAND; architect-alphonso HOLD (listing-owner gate) → folded → LAND.
- PR: https://github.com/spec-kitty/spec-kitty/pull/5593 (ready for review; operator merges).
- Codegraph (with mainline caveat): pre-PR Renata 1 call, Alphonso 2 calls then 0; the gate failure was found by running the gate, not the index.
