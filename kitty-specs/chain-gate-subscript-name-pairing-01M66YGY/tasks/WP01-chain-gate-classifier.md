---
work_package_id: WP01
title: Classify subscript collectors and name-paired dict comprehensions
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
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
- T007
- T008
- T009
- T010
history:
- at: '2026-10-30T17:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/architectural/
create_intent: []
execution_mode: code_change
owned_files:
- tests/architectural/test_org_pack_chain_single_authority.py
- docs/changelog/CHANGELOG.md
tags: []
task_type: implement
tracker_refs:
- '6732'
---

# Work Package Prompt: WP01 – Classify subscript collectors and name-paired dict comprehensions

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objective

Fix the two misclassifications in the chain single-authority class gate
(`tests/architectural/test_org_pack_chain_single_authority.py`, issue #6732):

1. **False negative** — `for i, p in enumerate(reg.packs): roots[i] = p.effective_root(r)`
   assembles a ROOTs-only chain by hand and the gate is silent, because (a) the iteration
   is wrapped in `enumerate(...)` and `_is_packs_iter` does not see through it, and (b) only
   `append`/`add`/`extend` call arguments count as collectors, never an `ast.Assign` to an
   `ast.Subscript` target.
2. **False positive** — `{p.name: p.effective_root(r) for p in reg.packs}` is name-paired,
   which the gate's docstring explicitly permits, but `_comprehension_collects_bare_roots`
   flags it and #6418 had to rewrite a `for` loop to get past it.

The rule the gate states is: only a ROOTs-only collection over `<registry>.packs` is a
violation; anything carrying `pack.name` is name-paired and legitimate. The classifier must
match that rule for both idioms, and every new rule gets a planted violation and a planted
non-violation so a fix in one direction cannot silently undo the other.

## Context

- Spec: `kitty-specs/chain-gate-subscript-name-pairing-01M66YGY/spec.md`
- Plan: `plan.md` (classifier design and fixture table), research: `research.md`
  (Decisions 3–5 explain how the subscript key joins the loop's pairing evidence and why the
  `DictComp` exemption keys on the key only).
- The live tree contains the name-keyed subscript idiom at
  `src/charter/activation/drg_activation.py::_org_pack_roots_by_name`
  (`roots[pack.name] = pack.effective_root(repo_root)`), so over-widening the subscript
  rule reds the real census, not only a fixture.
- The empty allowlist, the offering-tier scan exclusion, the scanned-file floor (1200) and
  the owner-bypass control are invariants: do not touch them, and do not add a scan
  exclusion or allowlist entry for any real file.

## Subtasks & Detailed Guidance

### T001 – Record the pre-fix red
Run the two new violation fixtures and the new non-violation fixtures through the gate's
own scanner `_scan_source` **before** editing it, and capture the output for the PR:
the subscript loop must show no hit, the name-keyed `DictComp` must show a hit.

### T002 – Plant the violation fixtures
Add to `test_planted_violation_is_reported`:
- `enumerate(...)` + `roots[i] = p.effective_root(r)` → `registry.packs iteration assembling roots`
- `{p.effective_root(r): p.name for p in ...packs}` → `registry.packs comprehension assembling roots`

### T003 – Plant the non-violation fixtures
Add to `test_non_violations_are_not_flagged`:
- `by_name[p.name] = p.effective_root(r)` inside the same `enumerate(...)` loop → no hits
- `{p.name: p.effective_root(r) for p in ...packs}` → no hits

### T004 – See through a wrapping call in `_is_packs_iter`
Unwrap a single-argument call whose sole argument is the `packs` attribute (e.g.
`enumerate(<registry>.packs)`) so an indexed iteration is still recognised.

### T005 – Subscript assignment is a collector
Return the collected values plus each subscript key from the loop body, and decide pairing
over the loop's collections and keys — never over the whole loop body, so a loop that merely
mentions a name elsewhere stays a violation, and the existing loop-wide pairing (the
`paired-loop` fixture) keeps its meaning.

### T006 – Name-keyed `DictComp` is exempt
Exempt a `DictComp` whose **key** carries a `*.name` attribute; a `DictComp` whose key is a
bare `effective_root(...)` stays a violation even when its value carries a name.

### T007 – Docstring matches behaviour
Update the module docstring's Rule 2 paragraph to state subscript collection and the
name-keyed `DictComp` exemption.

### T008 – Re-run and confirm the invariants
`uv run pytest tests/architectural/test_org_pack_chain_single_authority.py` must pass, the
live census over `src/` must report zero hits, and the allowlist/floor/owner-control tests
must pass unchanged.

### T009 – Prove the fix half by half
Revert each half in turn (the `enumerate` unwrap, the subscript collector, the `DictComp`
key rule) and confirm a fixture reds each time; restore.

### T010 – Changelog
Add an `[Unreleased]` `### Fixed` entry for #6732: bold impact-first lead with `(#6732)`,
before/after, under 1,200 characters.

## Validation

```bash
uv run pytest tests/architectural/test_org_pack_chain_single_authority.py -q
```

Do not run the full `tests/architectural/` sweep (NO_FULL_HEAVY_SUITES_IN_MISSION).
