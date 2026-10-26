---
work_package_id: WP01
title: In-force required ids reader in the activation layer
dependencies: []
requirement_refs:
- FR-002
- FR-007
- NFR-001
- NFR-003
- C-001
- C-002
planning_base_branch: issue-6417-charter-list-org-required
merge_target_branch: issue-6417-charter-list-org-required
branch_strategy: Planning artifacts for this mission were generated on issue-6417-charter-list-org-required. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6417-charter-list-org-required unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundation
history:
- at: '2026-10-26T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/activation/test_required_in_force.py
execution_mode: code_change
owned_files:
- src/charter/activation/activation_ledger.py
- src/charter/activation/api.py
- tests/charter/activation/test_required_in_force.py
- tests/architectural/test_charter_activation_api_reexport.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – In-force required ids reader in the activation layer

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission charter-list-org-required-in-force-01M5WZVP`). Address all feedback before the work is complete.

---

## Objective

Add `required_in_force(repo_root, *, strict=True) -> tuple[RequiredInForce, ...]` to
`src/charter/activation/activation_ledger.py`, next to `required_not_in_force` (FR-023). For every
org-requirable, activatable kind whose `activated_<plural>` key is **absent** from the activation
ledger, it returns the org-required ids that are in force: the floor intersected with
`PackContext.effective_ids(kind, available)`, where `available` is what the built-in, project and
every org layer provide. Re-export it (and `RequiredInForce`) from `charter.activation.api`.

This is the single in-force answer `charter list` (WP02) renders. Do not compute membership any
other way (operator ruling 1; `tests/architectural/test_no_raw_activation_membership.py`).

## Context

- Root cause and evidence: `kitty-specs/charter-list-org-required-research-01M5WZQH/research.md`.
- `PackContext` (`src/charter/activation/pack_context.py`): `admits`, `effective_ids`, `allow_for`,
  `from_config`. Effective deny already subtracts the required floor (`load_denied` /
  `_effective_deny`), so a denied-but-required id is admitted. For `skill`
  (`effective_when_absent == "required"`) `from_config` materialises the floor as the allow state.
- Floor with provenance: `read_org_required_provenance(repo_root, kind, strict=...)`
  (`src/charter/activation/org_pack_discovery.py`), already wrapped by `_required_provenance` in
  `activation_ledger.py` (lazy import). Stems are normalised there.
- Availability: `ActiveCharterManager().list_available_detailed(ctx, kind.operator_token,
  layer_roots=resolve_layer_roots(repo_root), org_root_chain=resolve_pack_chain(repo_root, strict=False))`
  (`src/charter/activation/pack_manager.py`, `src/charter/activation/layer_roots.py`) — the scan
  `charter list --all` renders. Use `entry.artifact_id` values.
- Import cycle: `pack_context` and `pack_manager` import `activation_ledger` at module scope. Import
  them lazily inside the function, with the short comment style this file already uses
  (`# identity_index imports this module`).
- Seam rules: `charter.activation.api` re-exports use `X as X`; every `__all__` entry needs an
  identity row in `tests/architectural/test_charter_activation_api_reexport.py`. `__all__` of
  `activation_ledger.py` must list the new public names (C-007; `test_no_dead_symbols` needs a
  `src/` caller — the api re-export plus WP02's `list_cmd` use).

## Subtasks

### T001 — Red-first unit tests

File: `tests/charter/activation/test_required_in_force.py` (new). Commit it alone, red, before
any implementation (ATDD, charter C-011). Mark `pytestmark = [pytest.mark.fast]`.

Fixture: reuse the pattern of `tests/specify_cli/cli/commands/charter/test_list_required_omitted.py`
— an org pack `acme` under `org-packs/acme` registered in `.kittify/config.yaml`
(`charter_packs.org.packs`), `org-charter.yaml` with `required_directives: [DIRECTIVE_001]`, and
`seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)` from
`tests._factories.activation_ledger`. `DIRECTIVE_001` is the built-in
`001-architectural-integrity-standard`.

Cases:

1. Absent directive key → one `RequiredInForce(kind=DIRECTIVE, artifact_id="001-architectural-integrity-standard")`
   with `pack_names == ("acme",)`.
2. Explicit `activated_directives=[...]` (even omitting the id) → nothing (that is FR-023's case).
3. Denied required id (`deactivated_directives=["001-architectural-integrity-standard"]`) with the
   key absent → still returned (floor beats deny). Check `seed_activation_ledger` supports deny keys;
   otherwise write `.kittify/charter/activation.yaml` directly.
4. A required id no layer provides (`required_directives: [999-nowhere]`) → not returned.
5. An org-pack-provided directive (`org-packs/acme/directives/team-rule.directive.yaml`, valid
   body: `schema_version: "1.0"`, `id: TEAM_RULE`, `title`, `intent`, `enforcement: required`;
   `required_directives: [team-rule]`) → returned as `team-rule`.
6. No org pack / empty floor → `()`, and availability is never scanned: monkeypatch
   `ActiveCharterManager.list_available_detailed` to raise and assert it is not called (NFR-001).
7. Unreadable `org-charter.yaml` (invalid YAML) with `strict=False` → `()` with no exception
   (NFR-003).
8. Skill: an org pack with `required_skills: [team-report]` and a skill file the pack provides
   (copy the shape from `tests/charter/activation/test_skill_projection_deny.py` or the
   `CharterSteps.java` `OFFERED_SKILL_BODY`) → returned exactly once. If building a valid skill
   fixture is disproportionate, assert at least that a required skill no layer provides is **not**
   returned (the materialised floor is still intersected with availability).

### T002 — `RequiredInForce` and a shared base

In `activation_ledger.py`, introduce a private frozen base (e.g. `_RequiredId`) holding `kind`,
`artifact_id`, `packs`, `pack_names`, `describe_packs()`; make `RequiredOmission` and the new
`RequiredInForce` subclasses (keep `RequiredOmission`'s public API and docstring). Docstring for
`RequiredInForce`: "An org-required id in force while its kind's allow key is absent (#6417)".

### T003 — The reader

```python
def required_in_force(repo_root: Path, *, strict: bool = True) -> tuple[RequiredInForce, ...]:
```

Steps:

1. `ledger = load_activation_ledger(repo_root, report_stray=False)`.
2. Kinds: `kind` from `ledger.allow` with `allow is None` and `kind.org_requirable`.
3. Floors: `_required_provenance(repo_root, kind, strict=strict)`; keep non-empty ones. If none,
   return `()` before building anything else (NFR-001).
4. `context = PackContext.from_config(repo_root)`; roots once; per kind
   `available = {e.artifact_id for e in manager.list_available_detailed(...)}`;
   `in_force = context.effective_ids(kind, available)`.
5. Emit `RequiredInForce(kind, stem, packs)` for floor stems in `in_force`, kinds in enum order,
   stems in floor order. Keep the function ≤ 15 complexity; extract a helper for the availability
   scan if needed.
6. With `strict=False`, an `ActiveCharterConfigError` from reading the floor must not escape (the
   provenance reader handles `strict`); do not add broad `except` blocks.

### T004 — Seam

- `activation_ledger.__all__`: add `RequiredInForce`, `required_in_force` (sorted as the file does).
- `charter/activation/api.py`: add both to the "Activation diagnostics" import block and to
  `__all__` (sorted).
- `tests/architectural/test_charter_activation_api_reexport.py`: add identity rows.

## Test strategy

```bash
uv run --frozen pytest tests/charter/activation/test_required_in_force.py -q
uv run --frozen pytest tests/architectural/test_charter_activation_api_reexport.py tests/architectural/test_no_raw_activation_membership.py tests/architectural/test_layer_rules.py -q
uv run --frozen pytest tests/charter/activation/test_activation_ledger.py tests/specify_cli/cli/commands/charter/test_list_required_omitted.py -q
uv run --frozen ruff check src/charter/activation/activation_ledger.py src/charter/activation/api.py tests/charter/activation/test_required_in_force.py
uv run --frozen ruff format --check --force-exclude src/charter/activation/activation_ledger.py src/charter/activation/api.py tests/charter/activation/test_required_in_force.py
uv run --frozen mypy src/charter/activation/activation_ledger.py src/charter/activation/api.py
```

## Definition of Done

- T001 committed red before T002–T004; green after.
- `required_in_force` is reachable as `charter.activation.api.required_in_force`.
- No change to `required_not_in_force` behaviour; FR-023 tests pass.
- ruff, format, mypy clean; no new `noqa` / `type: ignore`.

## Risks

- Spelling space: floors are stems; `list_available_detailed` returns ids from the file scan. Case 5
  pins that a declared id (`TEAM_RULE`) differing from its stem still matches by stem. If it does not,
  compare through `IdentityIndex` stems rather than raw ids.
- Cost: `PackContext.from_config` and the scans run only when a floor exists.

## Reviewer guidance

Verify red→green (T001 commit red on its parent), the single-authority rule (no allow-list membership
test outside `PackContext` accessors), floor-beats-deny and not-provided controls, and the api gate rows.

## Implementation command

```bash
spec-kitty agent action implement WP01 --agent claude --mission charter-list-org-required-in-force-01M5WZVP
```
