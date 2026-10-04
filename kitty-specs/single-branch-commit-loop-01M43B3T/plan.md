# Implementation Plan: single_branch implement/review loop + commit-message hygiene

**Branch**: `ccr-ba04d8aa-fx98ee` | **Date**: 2026-10-04 | **Spec**: [spec.md](spec.md)

## Summary

Four defects, three code seams and one doc:

1. **#5459** — `agent action implement` (`cli/commands/agent/workflow.py`) resolves the workspace once and, for an existing workspace, only re-enters the lane self-heal. A single_branch WP's workspace is the repository root checkout, which always exists, so the write-checkout refusals and `record_claim_base` in `lanes/implement_support.py::create_lane_workspace` never run. Fix: extract the repo-root arm of `create_lane_workspace` into one helper (`guard_repo_root_claim`) and call it from both `create_lane_workspace` and the action path before materialization. One guard authority (C-001).
2. **#5655** — `coordination/status_transition.py::emit_inner_state_changed_transactional` commits annotations only for coord and stored-LANES missions; SINGLE_BRANCH falls back to an uncommitted write. `move-task` writes its implementer-identity annotation after the transition commit, and `mark-status` (non-owned) calls the uncommitted `emit_inner_state_changed` directly. Fix: let the annotation predicate admit stored SINGLE_BRANCH missions, and route single_branch `mark-status` through the transactional emitter.
3. **#5647** — `-m/--message` is a scalar typer option in `safe_commit_cmd.py` and `spec_commit_cmd.py`. Fix: `list[str]`, joined with blank lines via one shared helper.
4. **#5648** — rewrite the paragraph in `docs/development/reference/ci-gate-mechanics.md`.

## Technical Context

Python 3.11, typer, pytest. No new dependencies.

## Charter Check

Single canonical authority (one repo-root guard helper); red-first issue-pinned regression tests; no suppressions.

## Risks

- Annotation commits on single_branch run inside a `BookkeepingTransaction` on the write branch; protected-target single_branch missions already commit status transitions there, so the annotation follows the same policy.
- The action path must not refuse a genuine resume: the helper keeps the resume exemption.
