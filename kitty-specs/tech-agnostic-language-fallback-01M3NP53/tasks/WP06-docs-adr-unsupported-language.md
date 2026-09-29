---
work_package_id: WP06
title: Consumer docs, ADR, reserved-token reference
dependencies:
- WP01
- WP04
- WP05
- WP07
requirement_refs:
- C-005
- FR-016
planning_base_branch: issue-5283-tech-agnostic-language-fallback
merge_target_branch: issue-5283-tech-agnostic-language-fallback
branch_strategy: Planning artifacts for this mission were generated on issue-5283-tech-agnostic-language-fallback. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5283-tech-agnostic-language-fallback unless the human explicitly redirects the landing branch.
subtasks:
- T031
- T032
- T033
- T034
phase: Phase 5 - Documentation (lane B)
history:
- at: '2026-09-29T06:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/guides/how-to/governance/
create_intent:
- docs/guides/how-to/governance/extend-charter-for-unsupported-language.md
- docs/adr/3.x/2026-09-29-1-catalog-languages-states-and-reserved-unknown.md
execution_mode: planning_artifact
model: claude-sonnet-5-5
owned_files:
- docs/guides/how-to/governance/extend-charter-for-unsupported-language.md
- docs/guides/how-to/governance/index.md
- docs/guides/how-to/governance/troubleshoot-charter.md
- docs/guides/toc.yml
- docs/adr/3.x/2026-09-29-1-catalog-languages-states-and-reserved-unknown.md
- docs/adr/3.x/index.md
- docs/architecture/doctrine-kinds.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP06 – Consumer docs, ADR, reserved-token reference

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (canonical: `spk-doctrine-profile-load`) to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Reviewers load `reviewer-renata` (reviewer ≠ implementer).

---

## ⛔ HARD RULE — NO_FULL_HEAVY_SUITES_IN_MISSION (verbatim, binding for implementer AND reviewer)

During implement and every WP review, you must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission (closeout) or to CI.

---

## ⚠️ Post-tasks squad corrections (BINDING — supersede any conflicting guidance further below)

- Code-WP dependencies clear at `approved`, not at consolidation: read every string you quote from the code WPs' lane branches (`git show kitty/…-lane-<x>:<path>`) or wait until the lanes are consolidated.
- DoD: the how-to page's frontmatter `title` equals the title quoted inside `CHARTER_EXTENSION_ADVISORY` (verify by reading the constant).
- `docs/architecture/doctrine-kinds.md:95` is inside the agent-profile schema YAML block that `tests/docs/diagram_drift/binding_table.py` binds — do not alter the block; add a prose note near it and run `uv run --frozen pytest tests/docs/diagram_drift/ -q` (named, docs-only).
- The ADR also records the tactic de-scoping (WP07, operator directive 2026-09-29) under Consequences, and the how-to states that built-in tactics are language-neutral while language-specific guidance lives in explicitly language-specific styleguides/toolguides/profiles or the local charter.
- Now also depends on WP07.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks and use language identifiers in code blocks.

---

## Objectives & Success Criteria

FR-016 + DIRECTIVE_003/042. Docs mirror SHIPPED behaviour — write after WP01/WP04/WP05 land and copy exact strings from the code (advisory constant, diagnostic codes, tool message), never from this prompt.

1. **How-to** `docs/guides/how-to/governance/extend-charter-for-unsupported-language.md`, titled exactly "Extend your charter for an unsupported language" (the advisory constant names this title — verify). Audience: a tech lead running Spec Kitty on a Zig/Go/other project. Content: what `Languages: unknown` means (Spec Kitty has no specialist guidance for the declared language; only language-neutral doctrine applies; language-scoped guides/profiles such as Python ones stop applying); how Spec Kitty decides (the languages/frameworks interview answer; languages that installed doctrine is scoped to count as recognised; placeholders and the default answer mean "not declared"); how to extend the local charter with tech-specific guidelines (project doctrine overlay / org pack — link the existing "create an org doctrine pack" and "setup governance" guides; do not invent commands — verify every command with `spec-kitty … --help`); regenerating: `charter generate --from-interview` (the default) re-derives languages and replaces a hand-edited `catalog.languages`; `--no-from-interview` keeps it; what `spec-kitty review` reports for non-Python missions (dead-code gate not applicable, `MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE`, verdict `pass_with_notes`) and how to supply your own analyzer/test command via the local charter. Never suggest Python layouts/files/tools.
2. Cross-link from `troubleshoot-charter.md` (a short section: "Context says `Languages: python` (or `unknown`) for a non-Python project" → correct the answer, regenerate from the interview) and add the page to the governance `index.md` and `docs/guides/toc.yml`.
3. **ADR** `docs/adr/3.x/2026-09-29-1-catalog-languages-states-and-reserved-unknown.md` (status Accepted, date 2026-09-29, deciders: operator Stijn Dejongh; squad lenses): context (#5284/#4614/#2395/#3292), decision (four states: absent/None admit-all, `[]` admit-none, recognised list, reserved `[unknown]` admit-none-scoped + advisory; doctrine-derived vocabulary; regenerate-only precedence bypass; `unknown` reserved in artifact scopes, stripped both sides), consequences (Go/C# keep scoped tactics when doctrine declares them; framework-only answers become unknown; plain regenerate replaces hand edits), alternatives rejected (status field; reuse `[]`; mtime; reset flag; per-language table growth). Add to `docs/adr/3.x/index.md`.
4. `docs/architecture/doctrine-kinds.md` (~`:95`, the `applies_to_languages` description): list reserved tokens — `any`/`all` (rejected at authoring, treated unscoped at runtime) and `unknown` (rejected at authoring, ignored at runtime; reserved for unrecognised project languages).

## Context & Constraints

- Charter (binding): `.kittify/charter/charter.md` — ATDD/red-first (C-011): the failing test is committed as its own commit BEFORE the fix; reviewer verifies red on the planning base and green at the WP tip.
- Mission docs: `kitty-specs/tech-agnostic-language-fallback-01M3NP53/{spec.md,plan.md,research.md,data-model.md,contracts/cli-outputs.md,quickstart.md}`; tracer files under `traces/` — append a dated 1–3 sentence entry for any tooling friction, approach change, or design decision you make.
- Operator policy (#2330 decision): Spec Kitty doctrine is tech-agnostic; default implementation profile `implementer-ivan`; unknown languages → advise extending the local charter; NEVER fix by adding languages one by one; NEVER suggest Python files/layouts/tools to a non-Python project.
- Sibling-owned, do NOT edit: `src/specify_cli/consolidation/**`, `tests/integration/**`, golden/snapshot fixtures (`tests/specify_cli/skills/__snapshots__/**`, `tests/cli/__snapshots__/**`, `tests/consolidation/merge_driver_goldens/**`, `tests/contract/snapshots/**`), doctor/decision surfaces, `review/arbiter.py`, move-task override, built-in software-dev guidelines (#5202).
- Code quality: `ruff check`, `ruff format --check`, `mypy` (strict) clean on touched files; cyclomatic complexity ≤15; no new `# noqa`/`# type: ignore`; every new branch/helper gets a focused test in the same commit; modules under `src/charter/**` keep `__all__` and every exported name needs a caller in `src/` (dead-symbol gate).
- Terminology canon: Mission, never "feature", in any new prose/identifier.
- In a lane worktree always run tools via `uv run --frozen ...` or the worktree's own interpreter so the LANE `src/` is imported (bare `python`/`pytest` may import the primary checkout).

### House style (binding)

- Every page: frontmatter with `title`, `description` (≤ the length the description check allows — run `scripts/docs/description_length_check.py` if present), `doc_status: active`, `updated: '2026-09-29'`, `audience:` (pick an existing persona file under `docs/context/audience/`), `type: how-to` (one Divio quadrant per page), `related:` list — mirror `troubleshoot-charter.md`'s frontmatter shape. ADRs mirror the neighbouring ADR frontmatter (`title`, `description`, `status`, `date`).
- Descriptive alt text for any diagram; Mission (never feature); no repo-local paths presented as something the consumer has (this is published docs for consumers — `src/...` paths must not appear in the how-to).

## Branch Strategy

- **Strategy**: lanes (no coordination branch)
- **Planning base branch**: issue-5283-tech-agnostic-language-fallback
- **Merge target branch**: issue-5283-tech-agnostic-language-fallback

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`. Execution worktrees are allocated per computed lane from `lanes.json`; prepare yours with `spec-kitty agent action implement WP06 --agent claude`.

## Subtasks & Detailed Guidance

### Subtask T031 – How-to page (+ index/toc)

- Write the page per Objectives 1; add it to `docs/guides/how-to/governance/index.md` (same bullet style) and `docs/guides/toc.yml` (next to troubleshoot-charter). Verify every CLI flag/command you mention with `--help` and every string against the code.

### Subtask T032 – troubleshoot-charter cross-link

- Add the short section per Objectives 2; bump its `updated:` date.

### Subtask T033 – ADR (+ index)

- Write the ADR per Objectives 3; add it to `docs/adr/3.x/index.md` following the existing entry format. If `scripts/docs/freshen_adr_inventory.py` or `docs_index.py --write` regenerates index content, run it and keep only changes caused by the new pages.

### Subtask T034 – doctrine-kinds reserved tokens

- Update the `applies_to_languages` paragraph per Objectives 4; bump `updated:`.

## Test Strategy

- `uv run --frozen python scripts/docs/docs_index.py --write` (then review the diff; keep only entries for the new/changed pages) and `uv run --frozen python scripts/docs/check_docs_freshness.py --ci` → errors = 0.
- `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q` (named gate).
- Any docs link/related validator the repo ships for touched pages (`scripts/docs/related_validator.py`, `description_length_check.py`) — run on the touched files only if they accept paths.

## Risks & Mitigations

- Docs drifting from shipped strings → copy from code after the code WPs merge.
- Index regeneration touching unrelated pages → revert unrelated hunks.

## Definition of Done

- [ ] How-to exists with the exact advisory-referenced title; linked from index, toc, troubleshoot-charter.
- [ ] ADR accepted + indexed; doctrine-kinds lists reserved tokens.
- [ ] Freshness/index checks and terminology guard green.

## Review Guidance

Verify every command/flag/string against the code; verify no Python advice to non-Python users; verify one Divio quadrant per page and frontmatter completeness. Targeted commands only (HARD RULE).

## Activity Log

> Append entries at the END, oldest first: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <action>` (UTC now: `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-29T06:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status; record subtasks with `spec-kitty agent tasks mark-status <Txxx> --status done`.
