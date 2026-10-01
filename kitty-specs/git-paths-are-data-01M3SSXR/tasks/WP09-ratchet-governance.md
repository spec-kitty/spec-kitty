---
work_package_id: WP09
title: Ratchets are priced debt
dependencies: []
requirement_refs:
- FR-010
- FR-011
- FR-012
- SC-004
- C-005
- C-004
planning_base_branch: claude/git-path-remediation-rnrzfz
merge_target_branch: claude/git-path-remediation-rnrzfz
branch_strategy: Planning artifacts for this mission were generated on claude/git-path-remediation-rnrzfz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/git-path-remediation-rnrzfz unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-git-paths-are-data-01M3SSXR
base_commit: b99f6f41b251862ea70c120c90299665579178ab
created_at: '2026-09-30T19:02:57.631772+00:00'
subtasks:
- T038
- T039
- T040
- T041
phase: Phase 2 - Governance
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- docs/adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md
- docs/adr/4.x/index.md
- .kittify/charter/charter.md
- packs/built-in/tactics/frozen-baseline-shrink-only-ratchet.tactic.yaml
- packs/built-in/tactics/architectural-gate-non-vacuity.tactic.yaml
- packs/built-in/pack-manifest.yaml
- packs/built-in/tactic.graph.yaml
- packs/internal/**
role: architect
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP09 – Ratchets are priced debt

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `architect`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission git-paths-are-data-01M3SSXR`).
- Address every feedback item before handing back.

---

## Objectives & Success Criteria

- New ADR `docs/adr/4.x/2026-09-30-1-allowlist-ratchets-are-priced-debt.md` (Status: Accepted; Decider: Stijn, 2026-09-30) recording: shrink-only allowlist ratchets are priced debt — every allowlist entry is re-scanned on every CI run and keeps a known defect alive; a ratchet must be time-boxed, owned (issue + owner), and drained; the default closing state of a defect-class gate is an empty-allowlist invariant; a new gate is added only when it can start empty, or together with a mission that drains it. Relates to (does not supersede) `docs/adr/3.x/2026-09-14-1-census-floor-ratchet-adjudication.md`. Cites this mission as the first application (gate ships empty).
- Charter `.kittify/charter/charter.md`: standing order 5 no longer names "shrink-only allowlist" as the fix; it says close by construction with a non-vacuous gate, prefer an empty-allowlist invariant, and treat any transient allowlist as priced debt (time-boxed, owned, drained). Burn-down Policy (a) adds that a baseline/allowlist is debt with an owner and a drain date, and a gate with no allowlist needs no baseline entry. Update the header `Updated:` line; keep version bump rules of the charter itself (minor bump to 1.5.0 if the file's convention requires; read its header).
- Packs: generic caveat in `packs/built-in/tactics/frozen-baseline-shrink-only-ratchet.tactic.yaml` ("a ratchet carries recurring cost on every run; prefer draining to an empty-allowlist invariant; a ratchet needs an owner and exit date") — consumer doctrine; the CI-money rationale goes in `packs/internal/` (a short directive or note per `packs/internal/README.md` shape — single `drg/fragment.yaml` + `org-charter.yaml`). Then `spec-kitty doctrine regenerate-graph`.

## Context & Constraints

- Spec: `kitty-specs/git-paths-are-data-01M3SSXR/spec.md`; plan: `plan.md` (Design §1–10); API contract: `contracts/kernel-git-api.md`; data model: `data-model.md`; research: `research.md` (R1–R9).
- Charter: `.kittify/charter/charter.md` — campsite first (standing order 2), red-first (4), gate discipline (5), no heavy suites in mission (run targeted tests + the named gate files only).
- CLAUDE.md code style: ruff, `ruff format --check`, mypy zero issues on changed files; complexity ≤ 15; no new `# noqa` / `# type: ignore`.
- **C-007**: never move a destructive git command (`reset --hard`, `update-ref`, `worktree remove`, `stash`, `clean`) into `kernel.git`; only path *listings* move.
- **FR-013**: when a site today treats git failure as "no paths" (`check=False` then parse stdout, or a helper returning `()`/`None`), decide: a guard (it protects data or gates a transition) lets `GitCommandError` propagate; an advisory/display site catches `GitCommandError` at the call site with a one-line comment giving the reason. Record every decision in the tracer `kitty-specs/git-paths-are-data-01M3SSXR/research/design-decisions.md` (orchestrator appends; list them in your hand-off).
- **Boolean dirtiness** (`bool(stdout.strip())`) becomes `bool(status_entries(...))`; keep the same `untracked`/`ignored` options and pathspecs as the original argv.
- **Paths**: callers that need `str` use `str(entry.path)` / `p.as_posix()`; never re-parse a rendered line.
- Tests: use real temporary git repos (no git mocks) for at least one quoted-path case per migrated guard. Put new test files where listed in `owned_files`; small edits to existing tests of the migrated module are allowed with a one-line rationale in the hand-off.

## Branch Strategy

- **Strategy**: lanes (one worktree per computed lane from `lanes.json`)
- **Planning base branch**: `claude/git-path-remediation-rnrzfz`
- **Merge target branch**: `claude/git-path-remediation-rnrzfz`

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP09 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T038 – ADR

- Follow the ADR template used in `docs/adr/4.x/` / `docs/adr/3.x/` (read two recent ADRs for headings). Sections: Context (CI cost per run; allowlists outlive their missions; the 2026-09-14 census ruling), Decision, Consequences, Alternatives (keep shrink-only ratchets; ban allowlists entirely), References (this mission, #5392/#5400, Stijn's ruling 2026-09-30).
- Add it to `docs/adr/4.x/index.md`.

### Subtask T039 – charter

- Edit standing order 5 and Burn-down Policy (a) as in Objectives. Keep wording tight; do not restate the ADR.

### Subtask T040 – packs

- Built-in tactic caveat; check `architectural-gate-non-vacuity.tactic.yaml` and DIRECTIVE_043 wording for "shrink-only allowlist" as *the* fix and align (minimal edit; DIRECTIVE_043 is `packs/built-in/directives/043-close-defect-class-by-construction.directive.yaml` — if it needs editing, add it as an out-of-map edit with rationale).
- Internal pack: add the CI-cost rationale. Run `uv run --frozen spec-kitty doctrine regenerate-graph` (or `.venv/bin/spec-kitty`) and commit regenerated manifests.

### Subtask T041 – checks + follow-up issue

- `uv run --frozen python scripts/docs/docs_index.py --write`, `uv run --frozen python scripts/docs/check_docs_freshness.py --ci` (errors = 0), `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q`, and the pack/doctrine tests: `uv run --frozen pytest tests/doctrine -q -k "pack or manifest or graph"` plus `tests/cross_cutting/packaging/test_packaging_safety.py`.
- The follow-up issue (plain non-listing git runners + `worktree list` parsing, ~65 files) is filed by the orchestrator, not by this WP; leave a placeholder sentence in the ADR's References that the orchestrator fills with the number.

## Test Strategy

- As in T041.

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- Pack tier: CI-money rationale must NOT land in `packs/built-in/` (it would ship to consumers).
- Pack edits trip the manifest regen gate.

## Review Guidance

- ADR under 4.x; charter both sections amended; pack tiers respected; regen committed.
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
