---
work_package_id: WP02
title: Both ownership consumers read only through the one reader
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-010
- SC-001
planning_base_branch: issue-6767-synthesis-ownership-single-reader
merge_target_branch: issue-6767-synthesis-ownership-single-reader
branch_strategy: Planning artifacts for this mission were generated on issue-6767-synthesis-ownership-single-reader. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6767-synthesis-ownership-single-reader unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 2 - Consumers
history: []
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/reach_only.py
create_intent:
- tests/charter/synthesizer/test_reach_only_delivery.py
execution_mode: code_change
owned_files:
- src/charter/activation/synthesizer/reach_only.py
- src/charter/activation/api.py
- tests/charter/synthesizer/test_reach_only_delivery.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – Both ownership consumers read only through the one reader

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

Resolves the delivery half of #6767 (FR-004, FR-010, SC-001).

- `reach_only.py` no longer reads the synthesis manifest or the created-artifacts record itself:
  `reach_only_ids` asks `manifest.synthesized_slugs`, and the first-time diff asks
  `manifest.manifest_slugs`.
- `SynthesisMembershipUnreadableError` is no longer defined in `reach_only`; consumers catch the
  taxonomy class.
- The reach-only delivery suite still proves every governance outcome it proves today, on fixtures
  that describe a real synthesis tree (a provenance sidecar per manifest entry).
- `charter.activation.api` re-exports the one reader and the one error, so CLI code has one import
  surface.

## Context & Constraints

- Spec: `.../spec.md` FR-004, FR-010, C-003, C-004; plan IC-02; research decision D1.
- WP01 must be approved first: it adds `synthesized_slugs`, `manifest_slugs`,
  `read_created_record`, `write_created_record`, `CREATED_ARTIFACTS_PATH` and the coded error to the
  record module.
- **Documented behaviour change (keep it, do not "fix" it back):** an artifact the manifest records
  with a `project-direct-write` sidecar is a registration, not synthesis ownership, so a
  hand-authored tactic that some synthesized-shape edge points at is a root again. That matches
  `reach_only_ids`' own docstring and #6510's rule; the changelog (WP04) records it.
- **Must not change:** the lazy read (no overlay / no synthesized-shape edge → empty set and no
  record read), the org-required exclusion, the activation-list policy (absent key stays absent, a
  deactivated artifact is recorded but not appended), the unreadable-record *warning* on the write
  path, and the synthesis lock around the record read-merge-write.
- `tests/charter/synthesizer/test_reach_only_delivery.py` is the red-first surface: it builds a
  manifest with no sidecars today. Update `_write_manifest` (one helper) to write a sidecar per
  entry with `adapter_id="test"`, then additionally pin the direct-write case.

## Branch Strategy

- **Planning base branch**: `issue-6767-synthesis-ownership-single-reader`
- **Merge target branch**: `issue-6767-synthesis-ownership-single-reader`

```bash
spec-kitty agent action implement WP02 --agent python-pedro --mission synthesis-ownership-single-reader-01M68ZJM
```

## Subtasks & Detailed Guidance

### Subtask T008 – Red-first fixtures and the new case

- **File**: `tests/charter/synthesizer/test_reach_only_delivery.py`.
- Extend `_write_manifest` to write `.kittify/charter/provenance/tactic-<slug>.yaml` for each entry
  (top-level `artifact_urn: tactic:<slug>`, `artifact_kind: tactic`, `artifact_slug`, and the keys
  the `ProvenanceEntry` model requires — copy the shape from
  `tests/charter/synthesizer/test_manifest.py::_write_ownership_record`). Assert RED on the base:
  the fixtures must still exercise the same delivered/not-delivered pairs after the change.
- Add `test_hand_authored_registered_tactic_is_not_reach_only`: the manifest records the tactic with
  a `project-direct-write` sidecar and the overlay carries the synthesized-shape edge → the tactic
  is **not** in `reach_only_ids` and is delivered even with the directive deactivated (positive
  control: the synthesized tactic on the same fixture still drops).
- Add `test_missing_sidecar_falls_back_to_the_created_record`: manifest readable, the reach-only
  tactic's sidecar removed, `synthesized-artifacts.yaml` lists it → still reach-only, with the
  warning; remove the record too → the coded error (proves the unified fallback reaches delivery).
- Keep every existing absence assertion paired with its positive control.

### Subtask T009 – Adopt the one reader

- **File**: `src/charter/activation/synthesizer/reach_only.py`.
- Delete `_synthesized_slugs`, `_recorded_slugs`, `_registered_slugs`, `_manifest_slugs`,
  `_UNREADABLE_MEMBERSHIP`, `_UnreadableRecordError`, `SynthesisMembershipUnreadableError`, and the
  record IO that moved in WP01.
- `reach_only_ids` → `registered = {f"{prefix}{slug}" for slug in synthesized_slugs(repo_root, kind)}`.
- `_first_time_slugs` / `append_synthesized_activations` → `manifest_slugs(...)` and
  `read_created_record(...)`; keep `_UNREADABLE_RECORD_WARNING` and its formatting (it is activation
  policy, not record IO).
- Module docstring: say the ownership answer comes from the record module's one reader, and that
  `reach_only.py` owns delivery policy only.

### Subtask T010 – API re-exports

- **File**: `src/charter/activation/api.py`.
- Re-export `synthesized_urns`, `synthesized_slugs` and `SynthesisMembershipUnreadableError`
  alongside the existing `ManifestIntegrityError` / `synthesis_owned_directive_ids` imports; add to
  `__all__`. Keep the re-export's source module the synthesizer `manifest` / `errors` module so
  `tests/architectural/test_charter_activation_api_reexport.py` can pin it (add the rows there only
  if that test enumerates every re-export — check before touching it, it may not be owned).

### Subtask T011 – Verify no governance outcome changed

- Run and record:
  ```bash
  uv run --frozen pytest tests/charter/synthesizer/test_reach_only_delivery.py -q
  uv run --frozen pytest tests/charter/synthesizer/test_manifest.py -q
  uv run --frozen pytest tests/charter/test_action_governance_bundle.py -q
  uv run --frozen pytest tests/charter/test_compiler*.py -q
  uv run --frozen pytest tests/cli/test_charter_context_coded_error_6454.py -q
  ```
- Also run the delivery-table / context renderers suites that consume `reach_only_ids`:
  `tests/charter/test_context_*.py`. Fix only real regressions; a fixture that now needs a sidecar is
  a fixture fix, not a behaviour change.

## Test Strategy

```bash
uv run --frozen pytest tests/charter/synthesizer/ -q
uv run --frozen pytest tests/charter/ -q -x -k "context or delivery or compiler or governance"
uv run --frozen ruff check src/charter/activation/synthesizer/reach_only.py src/charter/activation/api.py
uv run --frozen ruff format --check --force-exclude src/charter/activation/synthesizer/reach_only.py src/charter/activation/api.py
uv run --frozen mypy src/charter/activation/synthesizer/reach_only.py src/charter/activation/api.py
```

## Risks & Mitigations

- Dropping the direct-write exclusion's counterpart (entry-derived URNs) changes one reachable
  behaviour; it is documented and pinned by T008's new test. Do not "restore" the old rule.
- `_eligible` calls `reach_only_ids` inside the activation write path — an unreadable record now
  raises there instead of silently appending. Confirm `append_synthesized_activations` still returns
  the warning (not a raise) for an unreadable *created-artifacts record*, and that a raise can only
  come from the ownership reader. If the write path can now raise, stop and report: that would be a
  gate change beyond the spec.

## Review Guidance

- `grep -n "load_yaml\|MANIFEST_PATH\|read_created_record" src/charter/activation/synthesizer/reach_only.py` must show no manifest read.
- Confirm the lazy-read ordering in `reach_only_ids` is unchanged and the org-required exclusion still runs last.
