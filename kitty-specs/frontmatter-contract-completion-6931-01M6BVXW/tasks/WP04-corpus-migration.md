---
work_package_id: WP04
title: Corpus migration + body immutability proof
dependencies:
- WP01
- WP03
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
- NFR-002
- NFR-003
- C-003
- SC-003
tracker_refs: []
planning_base_branch: issue-6931-frontmatter-contract
merge_target_branch: issue-6931-frontmatter-contract
branch_strategy: Planning artifacts were generated on issue-6931-frontmatter-contract. Completed changes merge back into that branch.
subtasks:
- T010
- T011
- T012
phase: Phase 4 - Migration
assignee: ''
agent: "claude:opus:python-pedro:implementer"
shell_pid: ""
history:
- at: '2026-11-01T15:40:00Z'
  actor: system
  action: Authored via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- scripts/docs/frontmatter_contract.py
- docs/
- tests/docs/test_frontmatter_body_immutability.py
- docs/_meta/immutable-body-hashes.json
role: implementer
tags: []
task_type: implement
---

# Work Package Prompt: WP04 – Corpus migration + body immutability proof

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` (role `implementer`) before parsing the rest of this prompt.

---

## Objective

Apply the D-7 mapping to the published corpus with a mechanical, idempotent,
**frontmatter-only** writer in `scripts/docs/frontmatter_contract.py`:

```bash
uv run python -m scripts.docs.frontmatter_contract --check   # print the plan, write nothing
uv run python -m scripts.docs.frontmatter_contract --write   # apply
```

Per published page: add `kind` (WP01 resolution), normalise `doc_status` (canonical
value, alias table, ADR `status`, D-8 subtree override), normalise `updated` to a
UTC instant (ADR `date` fallback), and remove a Divio `type`.

**Line surgery, not re-serialisation.** Rewrite only the frontmatter lines the
migration owns — in place for an existing key, appended at the end of the block for
a new one — and copy everything from the closing `---` onward verbatim. Do not run
the block through `ruamel` and re-dump it: that reformats 670 blocks and destroys
reviewability (NFR-003).

A page the resolution cannot classify is a **hard failure of the migration** (D-7:
"any page left unclassified is a migration failure") — never a guessed kind.

## Immutability (ADR D-7, C-003)

Bodies of ADRs, plans, reports and changelog entries are byte-immutable. Deliver
both halves:

1. **Baseline + test**: `docs/_meta/immutable-body-hashes.json` records the SHA-256
   of every immutable page's body (the text after the closing frontmatter fence);
   `tests/docs/test_frontmatter_body_immutability.py` fails on any difference and
   its failure message names the deliberate-update path.
2. **Transformer property test**: the migration function is asserted
   body-preserving over every file in the tree *and* over adversarial synthetic
   inputs (no frontmatter, CRLF, empty body, a body that itself contains `---`),
   so the guarantee is a property of the code, not a snapshot that decays.

## Definition of done

- Migration `--check` on the pre-migration tree, then `--write`; a second `--write`
  changes **0 bytes** (idempotence, NFR-002).
- `git diff -U0 origin/main -- docs/` shows every changed line inside a frontmatter
  block; paste the mechanical proof (a `grep`/`awk` one-liner over the diff) into
  the PR body (NFR-003).
- The corpus gate from WP02 is **green**: 0 errors, 0 warnings over 670 pages
  (SC-001), and every published page's `kind` is in the canonical set.
- The immutability baseline covers ≥ 380 files and the test passes (SC-003).
- `uv run pytest tests/docs -q` passes.
