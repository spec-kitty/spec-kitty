---
work_package_id: WP02
title: One union spelling rule, pinned per kind and layer
dependencies: []
requirement_refs:
- FR-002
- FR-003
- SC-002
- SC-003
- SC-004
- NFR-002
- NFR-003
- C-003
planning_base_branch: issue-6435-effective-set-one-spelling
merge_target_branch: issue-6435-effective-set-one-spelling
branch_strategy: Planning artifacts for this mission were generated on issue-6435-effective-set-one-spelling. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6435-effective-set-one-spelling unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-effective-set-one-spelling-01M68ZYF
base_commit: b0b6694093c52abcc1a4bed4f4e1affb5076167d
created_at: '2026-10-31T13:07:18.019338+00:00'
subtasks:
- T005
- T006
- T007
- T008
- T009
- T010
phase: Phase 2 - The assurance
history:
- at: '2026-10-31T12:48:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/effective_set.py
- tests/charter/activation/test_effective_set.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – One union spelling rule, pinned per kind and layer

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

The effective-set seam spells the service half of its union as activation stems in
**two** places (`_resolve_one` and `_fallback_ids`). The resolved copy is pinned by
tests; the fallback copy is not — deleting it leaves the whole module green while
`fallback_ids` is what `activate` writes for an unresolvable key. Extract one
helper both paths call, and pin the mixed two-org-pack union per applicable kind,
in both pack orders and both spellings.

Behaviour must not change on the resolved path.

## Context

- `src/charter/activation/effective_set.py`:
  - `_scanned_ids` → `ActiveCharterManager.list_available` → already stems
    (`list_available_detailed` emits `_config_stem`).
  - `_service_ids` / `_service_keys` → the service mapping keys, which are
    **declared ids**.
  - `_as_stems(ids, kind, identity)` → `identity.stem(kind, item) or item`.
  - `_resolve_one` unions the two halves for every kind except `directive`
    (directives are scanned by stem already, so the service half is skipped).
  - `_fallback_ids` repeats the same union for the best-effort path.
- Mutation evidence (research.md D3): removing `_as_stems` from `_fallback_ids`
  keeps 19/19 tests in `tests/charter/activation/test_effective_set.py` green.
- Do **not** reimplement `list_available_detailed` (C-003) and do not change the
  unknown-token rule: an id the index does not know stays in the set as given, so
  a service-only artifact cannot vanish.

## Branch Strategy

- Planning / base branch: `issue-6435-effective-set-one-spelling`
- Final merge target: `issue-6435-effective-set-one-spelling`
- Execution worktrees are allocated per computed lane from `lanes.json`.

## Subtasks

### T005 — extend the shared fixture

`tests/charter/activation/test_effective_set.py` already builds **two** declared
org packs (`ORG1 = org-packs/acme`, `ORG2 = org-packs/acme-two`, ORG2
higher-precedence because it is declared last) plus a project tactic. Extend it
with an id≠stem artifact for every activatable kind the union resolves, splitting
them across the two packs so an id≠stem artifact sits in the **lower**-precedence
pack as well as the higher one:

- tactic, styleguide, toolguide, paradigm, procedure, agent-profile,
  mission-step-contract, glossary-pack, directive.

Use the schema shapes already used in the repo (`test_stored_spelling_6527.py`,
`tests/_factories/`) and keep each file minimal but valid enough that the kind's
scan and the doctrine service both load it. If a kind cannot be loaded by the
service in a plain temp project (e.g. glossary-pack needs `provenance`), keep it
in the fixture only if `list_available` still sees it; otherwise drop that kind
and say which and why in the PR body.

### T006 — mixed-union assertions

One test, table-driven over the kinds above:

```python
entry = _resolve(project, [key])[key]
assert entry.resolved
assert stem in entry.ids and declared_id not in entry.ids          # listed once, by stem
assert IdentityIndex.build(project, org_roots=[...]).stored_spelling(kind, declared_id) == stem
```

The second assertion is the "both spellings converge" pin (SC-004): the declared
id an operator may type maps to the same stem the set lists.

### T007 — fallback-path pin

Add a test where the same fixture is made unresolvable (a declared org root that
does not exist, as the existing `test_missing_declared_org_root_is_unresolved`
does) and assert:

- `entry.resolved is False` and `entry.reason` is set (NFR-003 unchanged),
- `stem in entry.fallback_ids` and `declared_id not in entry.fallback_ids`,
- every fallback id is a known stem for the kinds present (`IdentityIndex.knows`
  + `stem(kind, id) == id` where the index knows the id).

Prove it is non-vacuous: with `_as_stems` removed from the fallback half, T007
must go red. Record the mutation result in the PR's `## Tests run`.

### T008 — one helper

In `src/charter/activation/effective_set.py`, add one module-private helper that
owns the merge + mapping, e.g.

```python
def _union_ids(scanned: Iterable[str], service: Mapping[str, Any], kind: ArtifactKind, identity: IdentityIndex, *, include_service: bool) -> set[str]:
    """Scanned stems plus the service half spelled as activation stems (one rule, both paths)."""
```

and call it from `_resolve_one` and `_fallback_ids`. Keep the directive exclusion
as data (`include_service=False`) with the one-line reason in the docstring; keep
`_as_stems` (or inline it) so the unknown-token rule stays in exactly one place.
No behaviour change on the resolved path.

### T009 — half-by-half mutation check

1. Drop the helper's mapping (return the service keys unmapped) → T006/T007 red.
2. Restore → green.
3. Record both outcomes in the PR's `## Tests run` self-review block.

### T010 — targeted validation

```
uv run --frozen pytest tests/charter/activation/test_effective_set.py -q
uv run --frozen pytest tests/charter/activation/test_identity_index.py tests/charter/activation/test_stored_spelling_6527.py tests/charter/activation/test_preset_application.py -q
uv run --frozen ruff check src/charter/activation/effective_set.py tests/charter/activation/test_effective_set.py
uv run --frozen mypy src/charter/activation/effective_set.py
```

Plus the specific architectural gates for `src/charter` that exist (name them; do
not run the whole `tests/architectural/` directory).

## Definition of Done

- One union/mapping call site; `_resolve_one` and `_fallback_ids` both use it.
- T006/T007 fail when the mapping is removed and pass with it (recorded).
- Every applicable kind is covered with both spellings converging on one stem.
- Module runtime stays within NFR-002 (no second service build; extend the
  existing fixture rather than adding a new one).
- `ruff`, `mypy`, and the named architectural gates pass.

## Risks

- Fixture cost: building the doctrine service is the expensive part (the module's
  setup is ~20 s today). Extend the existing fixture once; do not add a second
  project fixture for the same kinds.
- Some kinds' service loaders validate strictly; a barely-valid file is skipped by
  the service but still scanned, which would hide a real difference. Assert
  against `list_available_detailed` and the service mapping on the same fixture
  where it matters.

## Reviewer guidance

- Confirm the resolved-path behaviour is unchanged (the existing 19 tests still
  pass unmodified except for the fixture extension).
- Confirm the unknown-token rule is documented once, not twice.
- Confirm no scanner reimplementation and no change to the directive half's
  observable output.
