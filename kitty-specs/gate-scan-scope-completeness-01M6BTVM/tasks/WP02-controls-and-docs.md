---
work_package_id: WP02
title: Adversarial controls and the operator-facing docs
dependencies:
- WP01
requirement_refs:
- FR-007
- NFR-001
planning_base_branch: issue-7000-gate-scan-scope-completeness
merge_target_branch: issue-7000-gate-scan-scope-completeness
branch_strategy: Planning artifacts for this mission were generated on issue-7000-gate-scan-scope-completeness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7000-gate-scan-scope-completeness unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
history: []
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent:
- tests/architectural/test_gate_read_scope_controls.py
execution_mode: code_change
owned_files:
- tests/architectural/test_gate_read_scope_controls.py
- docs/development/reference/ci-gate-mechanics.md
- docs/changelog/unreleased/
role: implementer
tags: []
tracker_refs:
- '#7000'
---

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` (`spec-kitty agent profile show python-pedro`) before reading anything else.

## Objective
Prove `_gate_read_scope` can fail for the right reason, and document the check where CI mechanics
live. **FR-007, NFR-001.**

## Context (grounded)
WP01 adds `tests/architectural/_gate_read_scope.py` (pure scanner) and
`tests/architectural/test_gate_scan_scope_completeness.py` (the live property). A property test
that cannot fail is worthless: the #6994 class was exactly a silently passing declaration. This WP
owns the mutation controls and the docs; it does not edit the gate file (no ownership overlap).

## Guidance
**T004 — controls** (`tests/architectural/test_gate_read_scope_controls.py`, markers
`architectural` + `fast`, tmp_path only):
- a synthetic gate file with `_REPO_ROOT / "planted-undeclared"`-style read → `uncovered_reads`
  reports it with the prefix; declaring `planted/**` in a tmp registry copy clears it;
- a partially dynamic read (`_REPO_ROOT / "kitty-specs" / mission` when the temp tree has no
  `kitty-specs/**` declaration) → fails naming `kitty-specs/**`, and passes once declared;
- dropping one row from a copy of the live registry → the live scan reds naming that gate;
- `validate_exemptions` rejects an empty reason, a `**` prefix, an unknown gate and a stale entry;
- a syntactically invalid gate file raises `ValueError` (or the scanner's own error) with its path;
- a non-vacuity control: an empty gate set is not "covered".
**T005 — docs**: add one paragraph to `docs/development/reference/ci-gate-mechanics.md` next to the
#6994 scan-scope bullet describing the completeness check and the exemption rules; make sure the
registry comment block names the new gate (WP01 edits the block, this WP only verifies the wording
mentions it); add `docs/changelog/unreleased/<pr>.internal.md` in the repo's fragment style
(bold impact-first lead, `(#7000)` reference, under 1,200 characters).

## Definition of Done
- Every control reds on its mutation with a message naming the mutated gate, glob or exemption, and
  greens when the mutation is removed.
- `uv run --frozen python -m scripts.docs.check_changelog_style` reports 0 errors;
  `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` errors=0.
- No ownership overlap with WP01; no change to the gate file or the scanner.
