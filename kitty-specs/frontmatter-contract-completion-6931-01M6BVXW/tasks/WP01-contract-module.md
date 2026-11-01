---
work_package_id: WP01
title: Frontmatter contract module + upstream parity
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-004
- C-001
- SC-002
planning_base_branch: issue-6931-frontmatter-contract
merge_target_branch: issue-6931-frontmatter-contract
branch_strategy: Planning artifacts for this mission were generated on issue-6931-frontmatter-contract. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6931-frontmatter-contract unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Contract
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Authored via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/docs/
create_intent:
- scripts/docs/frontmatter_contract.py
- tests/docs/test_frontmatter_contract.py
- tests/docs/test_frontmatter_contract_upstream_parity.py
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/frontmatter_contract.py
- tests/docs/test_frontmatter_contract.py
- tests/docs/test_frontmatter_contract_upstream_parity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Frontmatter contract module + upstream parity

## ⚡ Do This First: Load Agent Profile

Load the agent profile named in the frontmatter (`python-pedro`, role
`implementer`) before parsing the rest of this prompt and behave according to its
guidance.

---

## Objective

Create `scripts/docs/frontmatter_contract.py`: the single place that states the
doc-kitty frontmatter contract, plus the pure resolution functions the validator
(WP02) and the migration (WP04) both call.

The contract data is **mirrored from doc-kitty at the pinned commit `494f2d87`**,
not invented:

- `CANONICAL_REQUIRED = title, description, doc_status, updated, kind` (absent =
  error; `title` is the floor);
- `KINDS` (15) and `STATUSES` (5) exactly as `src/lib/vocabulary-core.mjs` declares
  them (a value outside the set = **warning**, matching the upstream gate);
- `DOC_TYPES` (18) for the advisory `type` check;
- `updated` is an RFC3339 UTC instant (`YYYY-MM-DDTHH:MM:SSZ`);
- description upper bound 180 (`DESCRIPTION_MAX` upstream).

Cite the upstream file and commit in the module docstring so the next reader can
re-verify; the constants are *mirrored*, and
`tests/docs/test_frontmatter_contract_upstream_parity.py` is what keeps them honest.

Also in this module (data only, so WP02/WP04 can consume them without duplicating a
vocabulary):

- `DOC_STATUS_ALIASES` — `closeout → durable`, `point_in_time → durable`,
  `proposal → draft` (ADR D-7);
- `ADR_STATUS_TO_DOC_STATUS` — `Accepted → active`, `Proposed → active`,
  `Superseded → superseded` (ADR D-7 + operator ruling 5);
- `DIVIO_TYPE_TO_KIND` — `tutorial → Tutorial`, `how-to → How-To`,
  `reference → Reference`, `explanation → Explanation`;
- `KIND_BY_PATH_PREFIX` — the ordered path-prefix table for the 201 pages with no
  Divio `type`, no index role and no ADR role (`plans/ → Planning`,
  `changelog/ → Changelog`, `api/ → Reference`, `architecture/ → Explanation`,
  `context/ → Explanation`, `configuration/ → Reference`,
  `development/reference/ → Reference`, `migrations/ → How-To`,
  `operations/ → How-To`); longest prefix wins;
- `DRAFT_SECTIONS` — `plans/engineering-notes/`, `plans/investigations/`,
  `plans/research/` (D-8), with the precedence documented in a comment: for those
  subtrees D-8's `draft` beats D-7's `point_in_time → durable`, because applying
  D-7 literally would publish pages the operator decided not to publish.

Pure functions (no filesystem, no `docs/` dependency):

- `resolve_kind(rel_path, frontmatter) -> str | None` — order: explicit `kind` →
  index page (`index.md`/`README.md`) `Hub` → `adr/` tree `ADR` → Divio `type`
  mapped → path prefix → `None` (unclassified, a hard error downstream);
- `normalise_doc_status(rel_path, frontmatter) -> str | None` — canonical value
  passes; alias table; ADR `status` mapping; `DRAFT_SECTIONS` override;
- `normalise_updated(rel_path, frontmatter) -> str | None` — an existing value is
  normalised to the instant shape (a date-only value becomes `T00:00:00Z`), an ADR
  with no `updated` takes its `date`, otherwise `None`;
- `remove_divio_type(frontmatter) -> bool` — whether the page's `type` carries a
  Divio value (and therefore must go, since upstream `type` names the section).

## Definition of done

- Module exists, imports only stdlib + no new dependency (NFR-004).
- Unit tests cover: every rule of `resolve_kind` in precedence order (including a
  page that matches no rule → `None`), the alias table, the ADR mapping's
  totality over the three observed statuses, the D-8 override on a synthetic
  engineering-notes page, the instant grammar (accept `2026-10-26T00:00:00Z`,
  reject `2026-10-26`, `2026-10-26T00:00:00+02:00`, `2026-13-01T00:00:00Z`).
- The parity test asserts the three sets equal the recorded doc-kitty values, and
  fails if the module drifts from them.
- `uv run pytest tests/docs/test_frontmatter_contract.py tests/docs/test_frontmatter_contract_upstream_parity.py -q` passes.
