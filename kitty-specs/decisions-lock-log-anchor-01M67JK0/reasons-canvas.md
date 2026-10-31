# REASONS Canvas — Decisions lock log anchor

> Mission: decisions-lock-log-anchor-01M67JK0
> Generated: 2026-10-30
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: the Decision Moment write lock is keyed on the per-checkout ledger directory, while the row it protects is appended to the Mission event log; two checkouts that write one log therefore take two locks and can both open the same explicit `decision_id` ([research.md](research.md), D-2/D-3).
- Acceptance: [spec.md](spec.md) FR-001 through FR-004 and SC-001 through SC-004 — the anchor lock derived from the event log, both locks held in one order by every forward write, distinct logs never serialized, the ledger-dir sidecar contract untouched.
- Definition of done: failing-first test through `open_decision`, scoped production change in `decisions/service.py`, targeted green evidence plus the pre-existing decision suites, independent review, draft PR only. No merge by the implementer.

## Entities
- Log anchor: the resolved `status.events.jsonl` write path; the identity every writer of a decision row shares. Its lock path is owned by `kernel.event_log_append.event_log_lock_path`.
- Ledger-dir sidecar lock: `kitty-specs/<mission>/decisions/index.json.lock`; unchanged, guards the index RMW against the reconciler and the repair command.
- Decision index, decision id, terminal status, Mission status lock keep their existing decisions/status meanings. No new entity or model is introduced.

## Approach
- Reuse the one existing anchor→lock contract (`kernel.event_log_append.event_log_lock_path`) instead of inventing a second digest/placement scheme.
- Widen, do not move: hold the log anchor lock *and* the existing ledger-dir sidecar, in one global order (anchor → sidecar → Mission status lock). Moving the sidecar would orphan the `repair-runtime-lock`, gitignore-provisioning, coherence-screen and reconciler machinery that all key on that exact file (C-002).
- Acquire both through the existing `_decisions_lock` helper so no new refusal type, code or envelope appears and the timeout surface stays #6841's (C-001, NFR-003).

## Structure
- Production: `src/specify_cli/decisions/service.py` only — `_decisions_lock_path` stays for the sidecar, a new anchor-path helper and a two-lock context manager are added, and `open_decision` / `_terminal_command` use it with the `events_path` they already pre-resolve.
- Reused, not edited: `src/kernel/event_log_append.py` (`event_log_lock_path`), `src/kernel/locks.py` (`machine_file_lock`).
- Tests: one new focused module under `tests/specify_cli/decisions/` plus the pre-existing decision suites as the ratchet.

## Operations
1. Opening campsite check of the touched surfaces; record the no-enabler conclusion rather than broadening scope.
2. Write the failing-first test through `open_decision`: two checkouts whose decision writes share one event log and whose ledger dirs differ must not enter the open critical section concurrently. Run it, commit RED.
3. Add the anchor lock helper and the two-lock context manager; wire both forward write paths; keep the sidecar and its callers untouched.
4. Run the targeted decision suites, the new test and the quality checks; record commands and results. Cover the new branches (shared anchor, distinct anchors, non-git fallback).
5. Wrap up: accept, issue verdict, independent review of the aggregate diff, consolidate/compact/rebase, changelog entry, draft PR. The operator merges.

## Norms
- Canonical command surfaces and the resolved mission handle; targeted staging only.
- Python typing/lint standards, no broad suppressions, no new dependencies.
- New-code coverage ≥90% on changed lines; the reviewer checks the real diff and live evidence, not a summary.
- Terminology: Mission (not feature), event log (not ledger) for `status.events.jsonl`, ledger for `decisions/index.json`.

## Safeguards
- Do not change decisions lock-timeout reporting, retryability or the orchestrator-api refusal envelope (#6841 owns that surface).
- Do not retire `decisions/index.json.lock`, its `.gitignore` provisioning, `repair-runtime-lock`, or the `is_decisions_runtime_lock` coherence screen.
- No lock path may be taken in the reverse order (sidecar before anchor); a `dry_run` resolves no lock.
- Keep the non-git sibling-lock fallback working and never swallow `EventLogLockUnavailableError` into an unlocked write.
- No full heavy suite in-mission; no main push; no merge.

## Deviations (append-only)
