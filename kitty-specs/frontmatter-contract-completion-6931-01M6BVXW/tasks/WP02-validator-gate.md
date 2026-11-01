---
work_package_id: WP02
title: Contract validator gate (published sections only)
dependencies:
- WP01
requirement_refs:
- FR-007
- NFR-001
- NFR-005
- C-002
- SC-001
- SC-004
planning_base_branch: issue-6931-frontmatter-contract
merge_target_branch: issue-6931-frontmatter-contract
branch_strategy: Planning artifacts for this mission were generated on issue-6931-frontmatter-contract. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6931-frontmatter-contract unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
phase: Phase 2 - Gate
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Authored via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/docs/
create_intent:
- tests/docs/test_frontmatter_contract_corpus.py
execution_mode: code_change
model: ''
owned_files:
- tests/docs/test_frontmatter_contract_corpus.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Contract validator gate

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

---

## Objective

Turn the contract module into a runnable gate:

```bash
uv run python -m scripts.docs.frontmatter_contract --strict          # whole published tree
uv run python -m scripts.docs.frontmatter_contract --strict --changed-from origin/main
uv run python -m scripts.docs.frontmatter_contract --json
```

Rules of the gate:

- **Page set authority.** It must consume the existing resolver
  (`scripts.docs._published_pages.resolve_published_pages`), which reads
  `docs/docfx.json` and applies the enumerated exclusions. Do **not** add a second
  answer to "which pages are published", and do **not** read `site/` or
  `docs/_meta/sections.yaml` — neither exists on `main` (C-002).
- **Fail closed.** Coverage errors (resolver refusal, empty set, or a set below
  `MINIMUM_EXPECTED_PAGES`) exit `2`, mirroring `description_length_check`. A gate
  that validates zero pages must fail, not pass.
- **Exit contract.** `0` clean (warnings allowed); `1` `--strict` and at least one
  error; `2` coverage failure. Same shape as the sibling gates so CI wiring is
  uniform.
- **Severity parity.** Errors and warnings exactly as WP01 defines them from
  upstream: an absent required field is an error; an unknown `kind`/`doc_status`/
  `type` is a warning. Do not promote warnings to errors "for safety" — that would
  be a gate doc-kitty does not have.
- **`--changed-from`** is optional scope-limiting for PRs; it must not replace the
  whole-tree non-vacuity assertion (the corpus is still resolved and floored).

## Definition of done

- `--strict` on the current (pre-migration) tree exits `1` with a machine-readable
  report; that red output is the reproduction this mission is fixing and it is
  pasted into the PR body.
- `tests/docs/test_frontmatter_contract_corpus.py` asserts: the real tree resolves
  ≥ 500 pages, and after the migration (WP04) reports 0 errors and 0 warnings.
- A **gate-can-fail** test: a synthetic page missing `kind` in a temporary docs
  root makes the gate exit `1`; an empty/collapsed root exits `2`. No test asserts
  green over an empty set.
- Runtime over the whole published tree is measured and recorded (NFR-005, < 10 s).
