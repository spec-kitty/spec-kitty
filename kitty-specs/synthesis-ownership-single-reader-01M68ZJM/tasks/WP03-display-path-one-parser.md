---
work_package_id: WP03
title: One sidecar parser and the display path that wraps it
dependencies:
- WP01
requirement_refs:
- FR-006
- FR-007
- FR-008
- SC-004
planning_base_branch: issue-6767-synthesis-ownership-single-reader
merge_target_branch: issue-6767-synthesis-ownership-single-reader
branch_strategy: Planning artifacts for this mission were generated on issue-6767-synthesis-ownership-single-reader. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6767-synthesis-ownership-single-reader unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 2 - Consumers
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/charter/_synthesis.py
create_intent:
- tests/specify_cli/cli/commands/charter/test_synthesis_envelope_sidecar.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/charter/_synthesis.py
- src/specify_cli/cli/commands/charter/__init__.py
- src/specify_cli/cli/commands/charter/_collision_remedy.py
- tests/specify_cli/cli/commands/charter/test_synthesis_envelope_sidecar.py
- tests/cli/test_charter_context_coded_error_6454.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – One sidecar parser and the display path that wraps it

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

Resolves the display half of #6767 (FR-006, FR-007, FR-008, SC-004).

- `specify_cli.cli.commands.charter._synthesis` contains no YAML parse of the provenance sidecar;
  its `artifact_id` comes from `manifest.sidecar_artifact_urn`, and a
  `SynthesisMembershipUnreadableError` degrades that field to `None` instead of raising.
- The `charter synthesize --json` envelope keeps its documented four-field shape on healthy and
  damaged fixtures alike.
- The collision remedy catches the one coded error (it may keep catching `ManifestIntegrityError` for
  the genuine content-hash mismatch) and still names the offending file and the remedy.
- No public name is lost: `specify_cli/cli/commands/charter/__init__.py` re-exports whatever the
  renamed helper becomes (C-004).

## Context & Constraints

- Spec: `.../spec.md` FR-006, FR-007, FR-008, C-004; plan IC-03; research decision D5.
- Read first: `src/specify_cli/cli/commands/charter/_synthesis.py:450-525`,
  `src/specify_cli/cli/commands/charter/__init__.py:70-95,180-195` and
  `src/specify_cli/cli/commands/charter/_collision_remedy.py:70-95`.
- The envelope is a **strict-JSON contract**: `_load_written_artifacts_from_manifest` never raises
  today and must not start. That is why the wrapper catches, and why the catch must be the coded
  error (not a bare `except Exception` around business logic).
- Only directive entries carry an `artifact_id` (the sidecar is the only surface that records it);
  non-directive kinds must still emit `null`.
- One deliberate narrowing: a sidecar whose `artifact_urn` kind does not match the manifest entry now
  yields `None` (the strict reader validates it). Same for a sidecar path outside the provenance
  root — the strict reader's containment check replaces the unchecked `repo_root / path`.

## Branch Strategy

- **Planning base branch**: `issue-6767-synthesis-ownership-single-reader`
- **Merge target branch**: `issue-6767-synthesis-ownership-single-reader`

```bash
spec-kitty agent action implement WP03 --agent python-pedro --mission synthesis-ownership-single-reader-01M68ZJM
```

## Subtasks & Detailed Guidance

### Subtask T012 – Red-first envelope tests

- **File**: `tests/specify_cli/cli/commands/charter/test_synthesis_envelope_sidecar.py` (new).
- Cases, all through `_load_written_artifacts_from_manifest` (the pre-existing entry point):
  1. healthy manifest + sidecar → `artifact_id` is the URN id segment for a directive entry;
  2. non-directive entry → `artifact_id is None`;
  3. missing sidecar → `artifact_id is None`, the rest of the entry intact, and **no exception**;
  4. corrupt sidecar YAML → same;
  5. sidecar whose `artifact_urn` is `tactic:X` for a directive entry → `artifact_id is None`;
  6. absent manifest → `[]`;
  7. corrupt manifest → `[]`.
- Assert the four-field shape (`path`, `kind`, `slug`, `artifact_id`) on every case.

### Subtask T013 – Wrap the strict reader

- **File**: `src/specify_cli/cli/commands/charter/_synthesis.py`.
- Replace `_extract_artifact_id_from_provenance(prov_path)` with
  `_artifact_id_from_sidecar(repo_root: Path, entry: ManifestArtifactEntry) -> str | None`:
  ```python
  try:
      urn = sidecar_artifact_urn(repo_root, entry)
  except SynthesisMembershipUnreadableError:
      return None
  return urn.partition(":")[2] if urn else None
  ```
  Import the two names from `charter.activation.api` (WP02 adds them) so the CLI does not reach into
  the synthesizer package directly.
  **Decide and document:** the ownership reader returns `None` for a `project-direct-write` sidecar,
  but the envelope answers "what did the manifest commit, and what is its id" — a direct-write
  registration's id must still appear. If `sidecar_artifact_urn` returning `None` there would change
  the envelope, add a `recorded_urn=True` (or equivalent) parameter on the strict reader rather than
  duplicating the parse, and keep the display contract; note the choice in the WP history.
- Update the call site (`_load_written_artifacts_from_manifest`) and the module's `__all__`.
- Delete the old function; do not leave it as a deprecated alias (SC-001).

### Subtask T014 – Collision remedy

- **File**: `src/specify_cli/cli/commands/charter/_collision_remedy.py`.
- Catch `(SynthesisMembershipUnreadableError, ManifestIntegrityError)` in
  `_project_directive_remedy`. For the coded error use its metadata (`offending_artifact or
  record_path`, `reason`) and keep today's sentence shape:
  "…is an activated project directive, and the synthesis ownership record is unreadable (<file>,
  listed by <manifest>), so its origin cannot be told. Restore <manifest> and its provenance
  sidecars from version control and re-run. Do not deactivate it…".
- Update the module docstring's "unreadable ownership record" bullet to name the one error.
- Do not change the built-in/org branch or the "synthesis did not create it" advice.

### Subtask T015 – Import sites and re-exports

- `src/specify_cli/cli/commands/charter/__init__.py`: follow the rename in the import block and
  `__all__` (lines ~80 and ~190).
- `tests/cli/test_charter_context_coded_error_6454.py`: import the error from its new home
  (`charter.activation.synthesizer.errors` or `charter.activation.api`) instead of `reach_only`; keep
  asserting the code and the rendered output.
- `grep -rn "_extract_artifact_id_from_provenance" src/ tests/ docs/` must return nothing when done.

## Test Strategy

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_synthesis_envelope_sidecar.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_synthesis_report_6404.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/charter/test_synthesize_charter_soundness.py -q
uv run --frozen pytest tests/cli/test_charter_context_coded_error_6454.py -q
uv run --frozen ruff check src/specify_cli/cli/commands/charter/
uv run --frozen mypy src/specify_cli/cli/commands/charter/_synthesis.py src/specify_cli/cli/commands/charter/_collision_remedy.py
```

## Risks & Mitigations

- The envelope suites are broad (`test_charter_synthesize_cli.py`, `test_synthesis_path_parity.py`,
  `test_charter_synthesize_fresh.py`); run them and fix fixtures, not contracts.
- `SynthesisError` catch sites elsewhere render panels; the coded error is a
  `KittyInternalConsistencyError`, not a `SynthesisError`, so check whether any synthesize command
  path now reaches `except SynthesisError` with the coded error and would render it as an
  "Unexpected error". If so, add the coded error to that renderer's catch (that file is then an
  out-of-map edit with a rationale in the history note).

## Review Guidance

- `grep -n "YAML(\|ruamel" src/specify_cli/cli/commands/charter/_synthesis.py` must show no sidecar parse left.
- Confirm the envelope still never raises and that `artifact_id` is populated for a direct-write
  directive registration exactly as before.
