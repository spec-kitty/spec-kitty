# REASONS Canvas — Agent String Parser Hardening

> Mission: agent-string-parser-hardening-01M6699F
> Generated: 2026-10-30
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: the compact `--agent` parser fabricates whitespace identity (`" "` model, `"claude\n"` tool) and silently drops every segment past the fourth, corrupting the structured actor stored on agent/operator status writes since #6400 ([research.md](research.md)).
- Acceptance: [spec.md](spec.md), FR-001 through FR-004 and SC-001 through SC-004; each row of #6755's table pinned by a failing-first test, refusal on the three explicit `--agent` paths, lenient whole-value storage preserved.
- Definition of done: red-first test commit ahead of the production fix, targeted test surface green, mypy --strict clean, changelog entry, independent aggregate review, draft PR flipped to ready for review. The implementer never merges.

## Entities
- Compact agent string (the `tool:model:profile:role` CLI value), structured actor (`{tool, role, profile, model}`), lenient builder (`actor_from_option`) all keep their #6400/#2861 meanings; see [spec.md](spec.md#key-entities-include-if-the-mission-involves-data).
- The parser stays a thin, non-synthesizing boundary parser: absent segments stay `None`, never a tool-derived synthetic default (#2861). No new entity is introduced.

## Approach
- Fix all three rows inside `parse_agent_boundary_string` only: strip each segment, blank-after-strip is `None` (or the existing empty-tool `ValueError` for the tool), and more than four segments raises `ValueError`.
- No call-site changes: every explicit `--agent` path already converts `ValueError` into the existing clean `Invalid --agent value: <reason>` refusal; the lenient paths pre-check the segment count or catch `ValueError` and keep the value whole.
- Tradeoff: parser-level refusal over per-command checks — one authority, no second segment-count source (NFR-001, C-003).

## Structure
- Candidate production surface: `src/specify_cli/status/models.py` (`parse_agent_boundary_string`).
- Tests: `tests/status/test_actor_boundary_normalize.py` (parser rows), plus the CLI refusal tests for mark-status / move-task / add-history alongside the existing #6400 ones under `tests/specify_cli/cli/commands/agent/`.
- One work package; implementer owns product/tests, reviewer is independent, planner owns this reasoning and sequencing only.

## Operations
1. Opening campsite check of the touched surfaces; record the no-enabler conclusion (the function is small and already isolated).
2. Write failing-first tests through the pre-existing entry points (parser + CLI commands); run and commit RED before production edits.
3. Apply the bounded parser hardening; keep the docstring contract truthful.
4. Run the targeted status/CLI test files and mypy --strict; record commands and counts; verify red→green.
5. Changelog entry under [Unreleased]; draft PR; follow CI to green; flip to ready for review. No merge, no auto-merge, no push to main.

## Norms
- Canonical sources and CLI commands only; explicit mission handle on every spec-kitty command; targeted staging only.
- Python typing/lint standards; no new dependencies; no version numbers in scope.
- New/changed-line coverage ≥90% (diff-cover gate); independent review of the aggregate diff before the PR flips.

## Safeguards
- The lenient free-text paths (`agent status emit`, `orchestrator-api`) keep storing over-4-segment and unparseable values whole (#6400 contract, C-001).
- The bare-tool rule stays intact: no synthetic defaults; a whitespace-only tool is refused as an empty tool.
- No full heavy-suite runs locally; CI owns the full sweep. No credentials or machine-local paths in commits.
- All code work on the mission lane worktree; planning artifacts on `issue-6755-agent-string-parser-hardening`; never push `main`.

## Deviations (append-only)

(none yet)
