# Research: Truthful verdicts and gates

## R1 — Approval body shape (#6652)

- **Decision**: approval line `Approved by <reviewer>: <approval-ref>`, a blank line, then the feedback file verbatim. Operator decision `01M5X10ZEECFYBHF3S7WNEWWCC`.
- **Rationale**: `_mt_finalize_plan` relies on the approval token staying in the committed body once the event's review reference is replaced by the review-cycle pointer; the review text is the traceability evidence.
- **Alternatives considered**: file verbatim only (loses the token from the record); refuse the flag on approvals (operator ruled the content must persist).
- **Mechanism**: pass the file as `feedback_source` with a `body_preamble`, so `_guard_feedback_source_provenance` still refuses a prior review-cycle artifact (#990/#2996(b)). The synthesized no-file body stays on `body=` (M1, PR #3156).

## R2 — Already-approved and damaged-slot edges (#6652)

- **Decision**: a supplied file on an approval whose latest verdict is already approved writes a new approved cycle (operator decision `01M5X114KD7XHKESE6Z2B25P5F`); a supplied file with a damaged verdict slot refuses (exit 1, nothing written) rather than being dropped.
- **Rationale**: the no-op exists to avoid fabricated duplicates; a reviewer-supplied file is not fabricated. A damaged slot stays fail-closed for the write decision, so the honest outcome is a refusal.

## R3 — Replay command quoting (#6654)

- **Decision**: `shlex.join([...])` over the argv list.
- **Rationale**: quotes every interpolated value; a bare-word reviewer renders unchanged.

## R4 — Terminality scope (#6653)

- **Decision**: at `done`, every `in-mission` row counts; with zero gating references an existing matrix is evaluated whole (operator decision `01M5X11A3G8YR6JA7ZE5YCGTQ3`).
- **Rationale**: `docs/development/reference/issue-matrix-verdicts.md` — classification decides whether a row is required, the verdict decides whether an existing row is resolved.
- **#5222 F1**: in the gate's zero-reference arm, a matrix that cannot be located (`IssueMatrixRefReadError`, unmaterialized coordination worktree) is treated as absent and the PASS message says "no gating issue references and no issue matrix".

## R5 — safe-commit ignored files (#6649, #5393)

- **Decision**: `status_entries(..., ignored=True)` in `_has_candidate_changes`.
- **Rationale**: `git status --ignored -- <file>` reports `!! <file>` for a named untracked ignored file; the helper's `git add --force` then stages it, matching the mixed-call behaviour and `test_safe_commit_can_commit_explicitly_ignored_file`.
- **#5393**: verified fixed on `main` (`status_entries` is NUL-safe; `test_cli_git_paths.py` covers `_expand_arguments`); add a command-level test.

## Related issues triage

Pulled in: #5393 (same false no-op class in `safe-commit`, already fixed, needs only a regression test).
Left out: #6632 (rejection feedback file left untracked — rejection path, different root cause); #5815 (orchestrator-api rejection review-ref, different surface); #3044/#5227 epics (parents, not fixable here); #5069, #4625, #5319 (`safe-commit` branch policy, not false success); #1742/#1741 (mission-card wiring, unrelated to row scope).
