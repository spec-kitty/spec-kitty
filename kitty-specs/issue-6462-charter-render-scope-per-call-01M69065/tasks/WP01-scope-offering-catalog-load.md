---
work_package_id: WP01
title: Scope the offering-catalog load to the domains a caller reads
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- FR-006
- NFR-001
- NFR-003
- NFR-004
- C-001
- C-002
- C-003
- C-004
- SC-001
- SC-003
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Scoped catalog read
history:
- at: '2026-10-31T13:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/_render_census.py
- tests/charter/test_charter_render_scope_6462.py
- tests/charter/activation/test_offering_catalog_scope_6462.py
execution_mode: code_change
model: glm-5.3
owned_files:
- src/charter/activation/catalog.py
- src/charter/activation/resolver.py
- src/charter/activation/interview.py
- tests/charter/_render_census.py
- tests/charter/test_charter_render_scope_6462.py
- tests/charter/activation/test_offering_catalog_scope_6462.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Scope the offering-catalog load to the domains a caller reads

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match
for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

A persona render — `spec-kitty charter context --action <step>`, and the prompt build
behind `next` / `agent action` — must stop parsing doctrine domains whose ids its
governance resolution never reads, while producing byte-identical output.

Done when:

- `load_offering_catalog()` accepts an explicit, validated domain scope and its default
  (no argument) behaviour is unchanged.
- `resolve_project_governance()` reads exactly paradigms, directives and template sets;
  `default_interview()` reads exactly paradigms and directives.
- A census test fails on unmodified `main` (265 documents parsed, tactic/styleguide/
  toolguide/procedure/agent-profile documents present) and passes after (≤ 60 catalog
  documents, zero from the five unused domains).
- Rendered charter context and resolved governance selections are byte-identical for
  `specify`, `plan`, `tasks`, `implement`, `review`, `merge`.

## Context & Constraints

Read first:

- `kitty-specs/issue-6462-charter-render-scope-per-call-01M69065/spec.md` (FR-001,
  FR-002, FR-003, FR-005, FR-006; NFR-001, NFR-003; C-001, C-003, C-004)
- `.../research.md` (D-1..D-6, the measured baselines)
- `.../contracts/offering-catalog-scope.md` (S-1..S-7)
- `.../contracts/render-scope-census.md` (C-1..C-6)
- `.../data-model.md` (the scoped `OfferingCatalog` shape)

The measured facts you are acting on (`main` @ `dfe9efb0e8`): a persona render parses
**265** shipped documents; `resolve_project_governance` reads only 54 of them
(paradigms 14 + directives 38 + template-set derivation); `GovernanceResolution` hard-codes
`tactics/styleguides/toolguides/procedures` to `[]`, so 123 documents are provably unused
on every call.

Constraints:

- **No cache, no flag** (spec C-001). The only memoisation in play is the existing
  in-process `parse_shipped_yaml` seam (#5526). Do not add a TTL, an on-disk cache, or a
  `--no-charter-render` path.
- **One authority** (C-002): the scope is a parameter of the one loader. No second
  catalog, no per-domain loader module.
- **Warnings unchanged** (C-003): do not touch `_catalog_miss.py`, `CharterCatalogMissWarning`
  or the scope-filtered warning behaviour.
- **Compat** (C-004): `load_offering_catalog()` with no arguments keeps today's result
  for every existing caller, including `charter validate` and the JSON context surfaces.

## Branch Strategy

- **Planning base branch**: `kitty/mission-issue-6462-charter-render-scope-per-call-01M69065`
- **Merge target branch**: `main` (via PR from `issue-6462-charter-render-scope-per-call`)
- Execution worktrees are allocated per computed lane from `lanes.json`; never pick a
  base branch by hand. Claim with:
  `spec-kitty agent action implement WP01 --agent <name> --mission issue-6462-charter-render-scope-per-call-01M69065`

## Subtask Guidance

**T001 / T002 — the guard first (red before green).** Create
`tests/charter/_render_census.py`: a context manager that patches
`charter.offering.yaml_utils.parse_shipped_yaml` and records one entry per *actual*
parse (memo hits are not counted — a fresh CLI process pays the parse). Key entries by
document kind from the file suffix (`*.tactic.yaml`, `*.graph.yaml`, `*.agent.yaml`, …).
Then `tests/charter/test_charter_render_scope_6462.py` asserts, for
`charter.activation.context.build_charter_context(repo_root, action="implement")` and for
`"plan"`, that: (a) zero tactic/styleguide/toolguide/procedure/agent-profile documents
are parsed, (b) at most 60 catalog documents are parsed, (c) the same call with an
unscoped catalog parses strictly more (positive control, contract C-3). Run it against
unmodified `src/` and record the real numbers in the trace — that red is the proof the
guard observes the defect.

**T003 — the scope.** In `src/charter/activation/catalog.py`:

- Add `domains: Collection[str] | Collection[ArtifactKind] | None = None` to
  `load_offering_catalog`, plus `domains_scanned: frozenset[str]` on `OfferingCatalog`.
- Resolve each token through the existing domain vocabulary (`paradigms`, `directives`,
  `template_sets`, `tactics`, `styleguides`, `toolguides`, `procedures`,
  `agent_profiles`), accepting an `ArtifactKind` too. Unknown token → `ValueError`
  naming the token and the known set, raised **before** any file read.
- Guard each of the eight scan blocks on membership; `domains_present` only ever names
  scanned-and-present domains.
- `None` → all eight, exactly as today (S-1).

**T004 — loader contract tests.** Cover S-1..S-5 directly: default equals the pre-change
result for the same inputs, a scoped call parses only that domain (use the census
helper), `domains=()` reads nothing, unknown token raises, absent directory keeps its
old semantics, and an `ArtifactKind` token is accepted.

**T005 — call sites.** `resolve_project_governance` passes paradigms/directives/
template_sets; `default_interview` passes paradigms/directives. Leave every other caller
(the `charter validate` path, JSON context surfaces) on the default. Verify with the
census guard and the existing charter suites.

**T006 — parity and the scope-equals-reads pin.** Add a test that (a) compares the
rendered text and the resolved `GovernanceResolution` for all six actions against the
same render with an unscoped catalog (byte-identical), and (b) fails if a call site's
declared scope stops covering the fields it reads — implement (b) by asserting the
declared scope constant used by each caller equals the documented field set, so a future
edit that reads tactics must widen the scope or fail.

## Definition of Done

- The census guard and the loader contract tests pass; both were red on `main` for the
  documented reason.
- `uv run --frozen pytest tests/charter -q -n 4 --dist loadfile -m "not performance and not stress"` is green.
- `uv run --frozen ruff check src/charter tests/charter` and
  `uv run --frozen mypy src/charter/activation/catalog.py src/charter/activation/resolver.py` are clean.
- `spec-kitty charter context --action <each of the six>` output is unchanged (parity
  test), and the census shows ≤ 60 documents for the persona render.
- No new public symbol without a caller; no `specify_cli` import inside `charter`.

## Risks & Review Guidance

- Review the `domains_present` semantics hardest: an unscanned domain must never be
  mistaken for a deployed-but-empty domain by a caller that asked not to scan it.
- Review the fail-closed path: a typo in a domain name must raise, never yield an empty
  catalog that silently disables validation.
- Review that no warning text, order or count changed.
