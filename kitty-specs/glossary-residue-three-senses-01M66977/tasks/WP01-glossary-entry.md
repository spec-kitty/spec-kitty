---
work_package_id: WP01
title: Residue glossary entry, docstring links and structural test
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-6759-glossary-residue
merge_target_branch: issue-6759-glossary-residue
branch_strategy: Planning artifacts for this mission were generated on issue-6759-glossary-residue. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6759-glossary-residue unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
owned_files:
- docs/context/orchestration.md
- AGENTS.md
- docs/changelog/CHANGELOG.md
- src/specify_cli/context/mission_resolver.py
- src/specify_cli/audit/models.py
- src/specify_cli/.contextive/orchestration.yml
create_intent:
- tests/docs/test_glossary_residue_entry.py
authoritative_surface: docs/context/
execution_mode: code_change
agent_profile: python-pedro
role: implementer
agent: pi
history:
  - timestamp: "2026-10-30T11:35:00Z"
    agent: "pi"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP01 – Residue glossary entry, docstring links and structural test

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Issue #6759: "residue" (a `kitty-specs/` child that is not a Mission) has three live meanings in code and no `docs/context/` glossary entry — the same footgun class as `primary`, `merge` and `routing`. Add the entry, link it from the three owning docstrings, flag it in the Terminology Canon, regenerate the Contextive YAML, add the changelog entry, and pin it all with a red-first structural test. **No runtime behavior change**: only markdown, docstring comments, a generated glossary YAML, a test and the changelog change.

## Context

- The three senses, quoted from the live code on `main`@512567ee (do not reinvent them; the code is the source of truth, C-001):
  1. **Write-seam residue** — `is_kitty_specs_residue` in `src/specify_cli/context/mission_resolver.py` (#6627/#6668/#6669; #6680 is the issue's reference for this seam): whether a write seam (upgrade sweep, migration runner) must leave a `kitty-specs/` child untouched. A `spec.md` on disk keeps a folder out of residue, so the upgrade sweep can still repair it.
  2. **Audit-engine residue** — `RESIDUE_DIRECTORY` in `src/specify_cli/audit/models.py`, emitted by `src/specify_cli/audit/engine.py` when `not is_mission_dir` (#5812): reported as one INFO finding, not classified. The engine keeps this looser rule deliberately (`mission-walker-residue-rule-01M5ZC0X#FR-008`, issue #5875).
  3. **Read-side / `doctor identity` residue** — `not is_selectable_mission_dir` in `src/specify_cli/context/mission_resolver.py`, consumed by `src/specify_cli/status/identity_audit.py` (#5875, operator ruling 2026-10-27): no `meta.json` on disk; a git-untracked id-less `meta.json` in a repository; an unreadable `meta.json`. Mission selection never lists these folders.
- Sibling disambiguation entries to model: `### Routing` and `### The drain` in `docs/context/orchestration.md`; the AGENTS.md Terminology Canon bullets for `primary`/`merge`/`routing`.
- Entry schema: `docs/context/glossary-conventions.md` (Definition / Context / Status / Applicable to rows; optional `Do NOT use when`, `Note`, `Related terms`). Style: `spec-kitty charter context --include styleguide:kitty-glossary-writing` (clear not clever; functional over compositional; name owning code symbols like the sibling entries do; never "user" for the HiC).
- Docstring link form (precedent `src/specify_cli/state/contract.py:137`): ``Glossary: ``docs/context/orchestration.md#residue``.``

## Detailed Guidance

### Subtask T001 – Red-first structural test

Create `tests/docs/test_glossary_residue_entry.py`, modeled on the Routing-disambiguation tests in `tests/docs/test_artifact_placement_seam_page.py` (`pytestmark = [pytest.mark.unit]`, structural assertions only — presence, sense names, guards, links; never prose wording). Assert:
- `docs/context/orchestration.md` has a `### Residue` heading; its section body names the senses "write-seam residue", "audit-engine residue" and "read-side residue", names the owning symbols `is_kitty_specs_residue`, `RESIDUE_DIRECTORY` and `is_selectable_mission_dir`, and carries a `Do NOT use when` row.
- The docstrings of `is_kitty_specs_residue` and `is_selectable_mission_dir` in `src/specify_cli/context/mission_resolver.py`, and the `RESIDUE_DIRECTORY` doc in `src/specify_cli/audit/models.py`, each reference `docs/context/orchestration.md#residue`.
- AGENTS.md Terminology Canon links `docs/context/orchestration.md#residue`.
Run it on the planning base and confirm it is RED (record it); it goes green only after T002–T004.

### Subtask T002 – The glossary entry

Add `### Residue` to `docs/context/orchestration.md` after `### The drain` (keeps the disambiguation cluster together). One table row set: Definition (umbrella statement: three live senses, extends the Mission entry the way Routing extends the partitions), Context `Orchestration`, Status `canonical`, Applicable to `4.x` (match the page's convention — check neighboring entries), then a row per sense (like Routing's "Governed senses" row) naming sense, owning symbol+module, the rule, the provenance issue, and a per-sense *do NOT use when* guard steering to the neighboring sense. Add a `Do NOT use when` umbrella row ("never write bare 'residue' in governed prose; name the sense") and `Related terms` ([Mission](#mission), [Routing](#routing), [The drain](#the-drain)). Bump the page frontmatter `updated:` date. Update the sense rules ONLY from the code docstrings cited above.

### Subtask T003 – Docstring links

Add one short glossary-reference line to each of the three docstrings (comments only, no logic):
- `is_kitty_specs_residue` (mission_resolver.py) — after the mode description.
- `is_selectable_mission_dir` (mission_resolver.py) — after the rule list.
- `RESIDUE_DIRECTORY` `#:` doc (audit/models.py).
Use the exact anchor `docs/context/orchestration.md#residue`. ruff and `ruff format --check --force-exclude` must stay clean on the touched files.

### Subtask T004 – Terminology Canon bullet

AGENTS.md, Terminology Canon section, after the `routing` bullet: one bullet naming "residue" as overloaded with its three senses in one line, linking `docs/context/orchestration.md#residue`, in the voice of the sibling bullets.

### Subtask T005 – Contextive regeneration and docs gates

Run `python scripts/generate_contextive_glossaries.py generate` (regenerates `src/specify_cli/.contextive/orchestration.yml`) and `python scripts/generate_contextive_glossaries.py check` (must exit 0). Then the docs gates: `uv run python -m scripts.docs.docs_index --write` (only if the index output changes), `uv run python -m scripts.docs.freshen_adr_inventory`, `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0), and `uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py`.

### Subtask T006 – Changelog

`docs/changelog/CHANGELOG.md` under `[Unreleased]`: bold impact-first lead with `(#6759)`, before/after, under 1,200 characters.

## Branch Strategy

Planning branch `issue-6759-glossary-residue`, final merge target the same branch. The topology is `single_branch`, so you work in the repository root checkout; there is no lane worktree. Commit with the mission-aware entry point on that branch. Never push.

## Test Strategy

Red first (T001, on the planning base). Then: `uv run --frozen pytest tests/docs/test_glossary_residue_entry.py -q`, the T005 gates, `ruff check` and `ruff format --check --force-exclude` on the touched Python files, and `make test-fast` as the shared baseline. Record commands and counts in the Activity Log. Do NOT run any full heavy suite (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

## Definition of Done

- SC-001–SC-004 hold: the entry exists with three senses and guards; the three docstrings link it; the test was red on the base and is green at the tip; the Contextive check exits 0.
- Docs gates green; changelog entry present; no behavior change (`git diff` touches only the owned files).

## Risks & Mitigations

- Prose drift from the code rules → definitions quoted from the live docstrings; the test pins sense names and links, not wording.
- Contextive staleness → generator `check` mode must exit 0.
- Docs-freshness gate → bump `updated:` on the edited context page.

## Review Guidance

Reviewer: verify the three sense definitions match the code docstrings exactly in meaning (no invented rules), the guards steer to the right neighboring sense, the test asserts structure not prose, and no runtime file changed behavior.

## Activity Log

- 2026-10-30T11:35:00Z – pi – Prompt created.
- 2026-10-30T11:45:00Z – pi (python-pedro) – T001 red first: `uv run --frozen pytest tests/docs/test_glossary_residue_entry.py -q` → 5 failed (entry, three docstring links, canon bullet), 1 passed (the positive control on the known target-owned-bookkeeping link, proving the probe is non-vacuous). Red on the planning base as required.
- 2026-10-30T12:20:00Z – pi (python-pedro) – T002-T006 green: entry `### Residue` in docs/context/orchestration.md (three senses + guards + related terms, page `updated` bumped); glossary links added to `is_kitty_specs_residue`, `is_selectable_mission_dir` docstrings, the `RESIDUE_DIRECTORY` `#:` doc-comment, and (analysis finding C1, extension of the issue's three) the `identity_audit.py` module docstring; AGENTS.md Terminology Canon bullet after `routing`; Contextive regenerated (orchestration gains `Residue`; execution/governance also freshen — main's committed YAML was stale); docs gates green (docs_index 0 drift, ADR inventory unchanged, check_docs_freshness --ci exit 0, no-legacy-terminology 98 passed); changelog `[Unreleased]` Added entry. `uv run --frozen pytest tests/docs/ -q` → 1810 passed incl. the 6 new; residue/status suites green; ruff+mypy clean.
