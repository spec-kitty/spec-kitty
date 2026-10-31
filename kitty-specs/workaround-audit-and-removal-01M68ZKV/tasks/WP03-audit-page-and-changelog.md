---
work_package_id: WP03
title: The audit method and its ledger on one page
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-008
- C-002
- C-004
- SC-001
planning_base_branch: issue-6745-workaround-audit-and-removal
merge_target_branch: issue-6745-workaround-audit-and-removal
branch_strategy: Planning artifacts for this mission were generated on issue-6745-workaround-audit-and-removal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6745-workaround-audit-and-removal unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 3 - Documentation
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-31T12:50:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/development/how-to/
create_intent:
- docs/development/how-to/auditing-special-case-workarounds.md
execution_mode: planning_artifact
model: claude-sonnet-4-6
owned_files:
- docs/development/how-to/auditing-special-case-workarounds.md
- docs/development/how-to/index.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6745'
- '#6527'
- '#6898'
- '#6899'
- '#6900'
---

# Work Package Prompt: WP03 – The audit method and its ledger on one page

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
before parsing the rest of this prompt.

- **Profile**: `scribe-sally` (documentation writer)
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Issue #6745's acceptance criteria 1, 2 and 4 are documentation deliverables: the audit method is
written down, every suspect has a disposition, and a guard is proposed. This WP delivers them
as one maintainer how-to page plus the changelog entry.

Delivered state:

- `docs/development/how-to/auditing-special-case-workarounds.md` exists with the heuristics, the
  time-box, the four classifications, the ledger table, and an explicit "what this audit did
  **not** cover" section.
- The page states plainly that 327 `except Exception  # noqa: BLE001` sites are sampled, not
  reviewed one by one, and that the audit is not claimed complete (C-002).
- Every suspect without a removal cites an issue number: #6527 (activation-token refusal,
  existing), #6898 (`reenter_lane_self_heal` seam), #6899 (dependency-cycle refusal), #6900
  (the proposed process guard).
- The `[Unreleased] → Internal` changelog entry lands (FR-008), under 1,200 characters.
- `docs/development/how-to/index.md` links the page.

- **FR-001 / FR-002 / FR-003 / FR-008 / C-002 / C-004 / SC-001.**

## Context & Constraints

- **Source of truth for the ledger**: `kitty-specs/workaround-audit-and-removal-01M68ZKV/research.md`
  §4 (rows S1–S10) and §5 (decisions D1–D4). Copy the rows, not the prose around them, and keep
  each evidence pointer as `path:line`.
- **What landed in this PR**: S7 (the duplicated `DiscoveryContext` constructor — now one public
  `runtime.next.runtime_bridge_io.build_discovery_context`) and S8 (the composition's
  `getattr`/`len()` tolerance — now a direct read of the executor contract). Say "removed in this
  PR", not "fixed".
- **What was deliberately left**, with reasons, must be on the page: S1 (#6527 — a refusal
  reachable from real org-pack content needs an operator decision), S2 (`_best_effort_offering_root`
  — the swallow is the documented best-effort contract of three writers), S3 (legacy
  `coordination_branch` fallback — legacy missions in user repos still need it; only the comment
  is stale), S4 (`ensure_pack_identity` — a planned migration owns the backfill), S5 (#6898),
  S6 (the `BLE001` sample — the nine context-renderer sites are genuine "degrade, do not crash"
  constraints), S9 (#6899), S10 (the `should_auto_commit*` twins — two thin wrappers over one
  decision function, not a second authority).
- **Doctrine tier (C-004)**: no artifact is added to `packs/built-in/` (it ships to every
  consumer). The guard proposal is #6900, filed for the operator; the page points at it.
- **Style**: follow the neighbouring how-to pages (`pr-landing.md`, `review-gates.md`): frontmatter
  with `title`, `description` (50–180 chars), `doc_status: active`, `updated`, `audience`,
  `related`; short sections; tables where a table is clearer than prose.
- **Docs index**: after adding the page, run only the writes this tree needs and verify with
  `uv run python -m scripts.docs.check_docs_freshness --ci`. Do **not** rebuild the full CLI
  reference (`docs/api/cli-commands.md`) on this shared host.

## Branch Strategy

- **Strategy**: completed changes merge back into `issue-6745-workaround-audit-and-removal`.
- **Planning base branch**: `issue-6745-workaround-audit-and-removal`
- **Merge target branch**: `issue-6745-workaround-audit-and-removal`

## Subtasks & Detailed Guidance

### Subtask T009 – Author the audit page

- **Purpose**: make the audit repeatable and its outcomes auditable (FR-001, FR-002, FR-003).
- **Steps**: create `docs/development/how-to/auditing-special-case-workarounds.md` with:
  1. **Why** — one short paragraph on the bias and its cost (a second authority that drifts),
     quoting the issue's worked example only as a pointer to #6745/PR #6748, not restating it.
  2. **The method** — the six greppable heuristics, the per-subsystem time-box, and the sampling
     statement for `BLE001`.
  3. **The four classifications** — one line each, plus "what the fix looks like" for each.
  4. **The ledger** — one table row per finding (id, site, classification, disposition, evidence)
     covering S1–S10; "removed in this PR" rows name the new seam / the direct read.
  5. **What this audit did not cover** — the unsampled `BLE001` remainder, the four child issues,
     and the fact that the issue's worked-example family already landed in #6748.
  6. **Related** — #6527, #6898, #6899, #6900, `plan.md`, `research.md`.
- **Files**: `docs/development/how-to/auditing-special-case-workarounds.md`.

### Subtask T010 – Index row and docs freshness

- **Steps**: add one bullet to `docs/development/how-to/index.md` in the same style as its
  neighbours (`- [Auditing special-case workarounds](auditing-special-case-workarounds.md) — …`),
  bump the page's `updated:` if the index carries one, and run
  `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`). If the docs
  index needs a write, use `uv run python -m scripts.docs.docs_index --write` and commit only the
  files this page changes.
- **Files**: `docs/development/how-to/index.md`.

### Subtask T011 – Changelog entry

- **Steps**: under `## [Unreleased] - 4.0.0rc8` → `### Internal`, add one bullet: bold
  impact-first lead with `(#6745)`, then what changed and why it matters (one builder for the
  discovery context, and composition reading the executor contract instead of tolerating a test
  double), and a pointer to the new page. Keep it under 1,200 characters.
- **Files**: `docs/changelog/CHANGELOG.md` (the canonical file; root `CHANGELOG.md` is a symlink).

### Subtask T012 – Verify

- **Steps**:
  - `uv run pytest tests/docs/test_changelog_style.py -q`
  - `uv run python -m scripts.docs.check_docs_freshness --ci`
  - `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`
  - `uv run pytest tests/docs/ -q` (the docs suites are fast; skip anything heavy)
- **Never** run a full heavy suite.

## Definition of Done

- The page classifies S1–S10 and every non-removal row cites an issue number.
- The page says the audit is not complete and names the unsampled remainder.
- Changelog entry passes `test_changelog_style.py`; docs freshness `errors=0`.
- No file under `packs/` is touched.

## Risks & Mitigations

- **Duplicate issue**: S1 already has #6527 (open, claimed) — cite it, do not file another.
- **Docs churn on a shared host**: only run the freshness check and the narrow index write; a
  full `docs_index --write` that rewrites unrelated rows must be reverted and reported.

## Reviewer Guidance

- Check the ledger against `research.md` §4: every suspect present, no row overclaiming a fix.
- Check the page does not present the audit as complete, and that the "#6900 is a proposal"
  framing is explicit.
