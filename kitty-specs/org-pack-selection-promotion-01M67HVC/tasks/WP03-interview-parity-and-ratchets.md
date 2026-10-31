---
work_package_id: WP03
title: Interview parity, ratchets and the user-facing record
dependencies:
- WP01
requirement_refs:
- FR-003
- NFR-002
- NFR-003
- SC-002
planning_base_branch: issue-6686-org-pack-selection-promotion
merge_target_branch: issue-6686-org-pack-selection-promotion
branch_strategy: Planning artifacts for this mission were generated on issue-6686-org-pack-selection-promotion. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6686-org-pack-selection-promotion unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 3 - One rule for both writers
history:
- at: '2026-10-30T23:00:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/interview.py
- tests/specify_cli/cli/commands/test_charter_interview_promotion.py
- tests/architectural/charter_activation_boundary_baseline.yaml
- tests/architectural/_baselines.yaml
- docs/changelog/CHANGELOG.md
- docs/architecture/activation-ledger-and-charter-contract.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Interview parity, ratchets and the user-facing record

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

---

## Objectives & Success Criteria

`charter interview` and the upgrade step now resolve a selection through the same resolver, so
the two writers cannot disagree about an org-pack id. The duplicate loop in
`_promote_interview_selections` is gone, the boundary ratchet loses the two rows that loop kept
alive, and the changelog records the fix for the operator.

Done when:

- `_promote_interview_selections` uses `SelectionResolver` with `refuse_ambiguous=True` (a
  collision is still refused before any write) and no longer builds its own `IdentityIndex`.
- A CLI test proves the interview stores the same stem the migration promotes for the same
  org-pack id.
- `tests/architectural/test_runtime_charter_activation_boundary.py` passes with the two
  `interview.py` rows removed and `boundary_baseline` lowered in `_baselines.yaml`.
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry for #6686 and the touched architecture
  doc describes the shared resolver.

## Context & Constraints

- Read `_promote_interview_selections` end to end before editing: its docstring carries several
  decisions (seeding an absent key, the `--narrow-activation` behaviour, the write target, the
  best-effort contract). Only the *resolution* changes.
- The interview's collision refusal is pinned by
  `tests/charter/activation/test_stored_spelling_6527.py::test_charter_interview_renders_the_collision_as_an_error`;
  that test must stay green unchanged.
- `charter.activation.api` is the only seam `specify_cli` may import. This WP **removes** reaches
  (`charter.activation.catalog`, `charter.activation.layer_roots`), it adds none.
- Docs: the changelog entry is impact-first, bold lead, `(#6686)`, before/after, under 1,200
  characters. Do not regenerate the whole docs reference (shared machine cache).

## Branch Strategy

- **Strategy**: single_branch — implement and land on the topic branch.
- **Planning base branch**: `issue-6686-org-pack-selection-promotion`
- **Merge target branch**: `issue-6686-org-pack-selection-promotion`

## Subtasks & Detailed Guidance

### Subtask T009 – CLI parity test

- **Purpose**: Prove the two writers agree through the production entry point (CLI), not only a
  helper.
- **Steps**: in `tests/specify_cli/cli/commands/test_charter_interview_promotion.py` add a test
  that, on a project with `write_identity_org_pack` and a git repo fixture (the module already has
  `_git_init`), runs `runner.invoke(charter_app, ["interview", "--defaults", "--profile", "minimal", "--selected-directives", "QA_003"])`
  and asserts the stored activation state contains `qa-003-no-fake-green` for
  `activated_directives` — the same stem the migration promotes in WP02's test.
- **Files**: `tests/specify_cli/cli/commands/test_charter_interview_promotion.py`
- **Notes**: Pair it with the existing unknown-id/`--defaults` behaviour so the fixture is not
  vacuous: the same run must store nothing for an id no layer knows.

### Subtask T010 – Rewire the interview onto the shared resolver

- **Steps**:
  1. In `_promote_interview_selections`, replace the `IdentityIndex.from_roots(...)` construction
     and the per-kind loop with `resolver = SelectionResolver.build(repo_root)` and
     `resolution = resolver.resolve(kind_to_selection, refuse_ambiguous=True)`.
  2. Keep the per-kind warning text exactly: `f"Could not resolve selected {kind.operator_token} id {raw_id!r}; skipped."`
     derived from `UnresolvedSelection` entries.
  3. Delete the now-unused imports (`resolve_layer_roots`, `resolve_pack_chain`,
     `resolve_offering_root`, `IdentityIndex`) from this function and adjust the docstring: the
     resolution is the shared, layer-aware one (#6686); the seeding/narrowing/write-target rules
     are unchanged.
  4. `_stem_spelled_config` (narrow mode) uses `resolver.stems(kind, current)` instead of building
     its own `IdentityIndex` — pass the resolver in rather than rebuilding it.
- **Files**: `src/specify_cli/cli/commands/charter/interview.py`
- **Notes**: `ActivationIdCollisionError` must still propagate to the command body that turns it
  into `TaskCliError("... The interview answers were saved; no activation list was written.")`.

### Subtask T011 – Drain the boundary ratchet rows

- **Steps**: remove the two `src/specify_cli/cli/commands/charter/interview.py` rows for
  `charter.activation.catalog` and `charter.activation.layer_roots` from
  `tests/architectural/charter_activation_boundary_baseline.yaml`, and lower
  `test_runtime_charter_activation_boundary.boundary_baseline` in
  `tests/architectural/_baselines.yaml` by the same count (234 → 232), keeping the justification
  text accurate (name #6686 as the drain).
- **Files**: `tests/architectural/charter_activation_boundary_baseline.yaml`, `tests/architectural/_baselines.yaml`
- **Notes**: The ratchet fails on stale rows as well as new reaches; run the gate, do not guess.

### Subtask T012 – Changelog and docs

- **Steps**:
  1. Add an `[Unreleased]` entry to `docs/changelog/CHANGELOG.md`: bold impact-first lead, `(#6686)`,
     before/after, under 1,200 characters. Say what an org-pack operator sees change: the upgrade no
     longer reports a valid org-pack selection as unresolved, it promotes it like the interview does.
  2. Update `docs/architecture/activation-ledger-and-charter-contract.md` where it describes selection
     resolution/promotion, so it names the one shared, layer-aware resolver.
  3. Run `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0). If the change
     needs an index update, regenerate only that surface.
- **Files**: `docs/changelog/CHANGELOG.md`, `docs/architecture/activation-ledger-and-charter-contract.md`
- **Notes**: Keep the docs prose in the repo's voice; do not restate the whole activation architecture.

## Test Strategy

```bash
uv run pytest tests/specify_cli/cli/commands/test_charter_interview_promotion.py -q
uv run pytest tests/charter/activation/test_stored_spelling_6527.py tests/architectural/test_runtime_charter_activation_boundary.py -q
uv run python -m scripts.docs.check_docs_freshness --ci
uv run ruff check src/specify_cli/cli/commands/charter/interview.py
uv run mypy src/specify_cli/cli/commands/charter/interview.py
```

## Risks & Mitigations

- **Refusal downgraded**: `refuse_ambiguous=True`; keep the CLI collision test unchanged.
- **Stale ratchet**: run the boundary gate after the edit; the count must match the file.
- **Docs churn on a shared machine**: verify with `check_docs_freshness --ci`, do not rebuild the
  whole reference.
- **Behaviour drift in narrow mode**: `_stem_spelled_config` keeps its stem-spelling rule, now from
  the resolver; run the `--narrow-activation` tests.

## Review Guidance

- Confirm the interview no longer has a resolution loop and no `layer_roots`/`catalog` imports.
- Confirm parity is asserted on the production CLI path, not only on the resolver helper.
- Confirm the changelog entry is impact-first, references #6686 and stays under 1,200 characters.

## Progress & Status

Record each subtask with `spec-kitty agent tasks mark-status T00x --status done`; append the
resolver/parity evidence to the mission tracer.
