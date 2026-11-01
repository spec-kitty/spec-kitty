---
work_package_id: WP01
title: The record module owns both records and the one reader
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-005
- NFR-003
- SC-001
- SC-002
planning_base_branch: issue-6767-synthesis-ownership-single-reader
merge_target_branch: issue-6767-synthesis-ownership-single-reader
branch_strategy: Planning artifacts for this mission were generated on issue-6767-synthesis-ownership-single-reader. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6767-synthesis-ownership-single-reader unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-synthesis-ownership-single-reader-01M68ZJM
base_commit: 949db9911011b019c0da3557815dd66a944a4698
created_at: '2026-10-31T12:45:44.008796+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Foundations
history: []
agent_profile: python-pedro
authoritative_surface: src/charter/activation/synthesizer/manifest.py
create_intent:
- tests/charter/synthesizer/test_synthesis_ownership_reader.py
execution_mode: code_change
owned_files:
- src/charter/activation/synthesizer/manifest.py
- src/charter/activation/synthesizer/errors.py
- tests/charter/synthesizer/test_synthesis_ownership_reader.py
- tests/charter/synthesizer/test_manifest.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – The record module owns both records and the one reader

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

---

## Objectives & Success Criteria

Resolves the convergence half of #6767 (FR-001, FR-002, FR-003, FR-005, SC-001, SC-002).

- `charter.activation.synthesizer.manifest` exposes exactly one reader of the synthesis ownership
  record: `synthesized_urns(repo_root, kind)`, plus its slug projection `synthesized_slugs`.
- `synthesized_urns` applies one fallback policy (spec FR-002) and raises exactly one error.
- `errors.SynthesisMembershipUnreadableError` is that error: code `SYNTHESIS_MEMBERSHIP_UNREADABLE`,
  carrying the record path, the offending file and the reason.
- `_synthesized_urns`, `_SynthesisOwnershipUnreadableError` and `_ownership_unreadable` no longer
  exist; `synthesis_owned_directive_ids` reads through the public reader.
- The created-artifacts record's read/write primitives now live with the manifest they sit beside,
  and `reach_only.py`'s **behaviour is untouched by this WP** (WP02 adopts the new reader there, so
  WP02's lane stays independent).

## Context & Constraints

- Spec: `kitty-specs/synthesis-ownership-single-reader-01M68ZJM/spec.md` (FR-001..FR-003, FR-005, C-001..C-004); plan IC-01 and "Phase 1 design notes"; research decisions D1–D4.
- Read first: `src/charter/activation/synthesizer/manifest.py:308-535` (path validation, `verify`, `_SynthesisOwnershipUnreadableError`, `_synthesized_sidecar_urn`, `synthesized_node_urns`) and `src/charter/activation/synthesizer/reach_only.py:96-190` (record IO + the reach-only reader being unified).
- Do **not** rename the error code. `SYNTHESIS_MEMBERSHIP_UNREADABLE` is documented in `docs/changelog/CHANGELOG.md:131`, rendered by `charter context` (`src/specify_cli/cli/commands/charter/context.py:241-246`) and asserted by two suites. Renaming it is out of scope and user-facing churn.
- Do **not** change the created-artifacts record's on-disk shape, key names or header comment (C-001). `.kittify/charter/synthesized-artifacts.yaml` keeps `created_tactics` / `created_styleguides` and the legacy `synthesized-tactics.yaml` stays read-only-forever.
- Keep the read lazy (NFR-003): `reach_only_ids`' overlay check stays before the reader, and this WP does not add a read to any new path.
- `manifest.py`'s `__all__` is authoritative (`__all__` declaration convention); add the new public names, do not export the retired privates.

## Branch Strategy

- **Planning base branch**: `issue-6767-synthesis-ownership-single-reader`
- **Merge target branch**: `issue-6767-synthesis-ownership-single-reader`

```bash
spec-kitty agent action implement WP01 --agent python-pedro --mission synthesis-ownership-single-reader-01M68ZJM
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first test module

- **File**: `tests/charter/synthesizer/test_synthesis_ownership_reader.py` (new; `pytestmark = [pytest.mark.fast]`).
- **Fixtures to build** (reuse `tests/charter/synthesizer/test_manifest.py`'s `guard` fixture and `_write_ownership_record` shape; copy the helper into the new module rather than importing a private):
  1. a manifest + one synthesized entry (`adapter_id="test"`) + its sidecar → owned URN;
  2. the same entry with `adapter_id="project-direct-write"` → not owned;
  3. two entries, one direct-write, one synthesized, same URN → owned (re-registration);
  4. no manifest → `frozenset()`, and assert no read of the created-artifacts record (patch `read_created_record`);
  5. corrupt manifest + record listing the kind's ids → those ids, and a `caplog` warning;
  6. corrupt manifest + record absent / unparseable / wrong shape / no id of the kind → `SynthesisMembershipUnreadableError`, `.code == "SYNTHESIS_MEMBERSHIP_UNREADABLE"`, body names the manifest and the record;
  7. corrupt manifest + `kind="directive"` (record does not track directives) → the same error;
  8. readable manifest + missing sidecar for a directive entry → the error names the sidecar; for a tactic entry with a usable record → the record's ids;
  9. dangling manifest symlink → treated as unreadable, not absent;
  10. sidecar whose `artifact_urn` kind mismatches the entry, or has an empty id → the error;
  11. sidecar `provenance_path` outside `.kittify/charter/provenance/`, or escaping the repo → the error.
- Every absence assertion needs a positive control on the same fixture (tactic `acceptance-criteria-non-vacuity`).
- Confirm RED before T002–T005: run the module on the untouched base and record the failing output in a history note.

### Subtask T002 – The one coded error

- **File**: `src/charter/activation/synthesizer/errors.py`.
- Add:
  ```python
  class SynthesisMembershipUnreadableError(KittyInternalConsistencyError):
      """..."""
      def __init__(self, body: str, *, record_path: str, offending_artifact: str | None = None,
                   reason: str = "", kind: str | None = None) -> None:
          super().__init__("SYNTHESIS_MEMBERSHIP_UNREADABLE", body)
  ```
- Import `KittyInternalConsistencyError` from `kernel.errors`. Add the name to `__all__`.
- Docstring: this is the one refusal for an unreadable synthesis ownership record (manifest, a listed provenance sidecar, or the created-artifacts record); fail closed; name the file and the remedy. Note that the body is the operator-facing message and `str(error)` is only the code.
- The body must keep the substance of both retired messages: what could not be read, which file, why, and "restore from version control (`git checkout -- <path>`) — do not delete the record, synthesis would forget which artifacts it created".

### Subtask T003 – Move the created-artifacts record primitives

- **From** `reach_only.py` **to** `manifest.py`: `CREATED_ARTIFACTS_PATH`, `_LEGACY_CREATED_TACTICS_PATH` → `LEGACY_CREATED_ARTIFACTS_PATH`, `_CREATED_ARTIFACTS_HEADER`, `_record_key` → `created_record_key`, `_UnreadableRecordError` → `UnreadableCreatedRecordError`, `_load_record_file`, `_ids_under`, `_read_record` → `read_created_record`, `_write_record` → `write_created_record`.
- Keep the behaviour identical: absent file → `{}`; malformed YAML / non-mapping / wrong value shape → `UnreadableCreatedRecordError(path)`; the legacy tactics record is unioned into `tactic`; unknown top-level keys are preserved on write; the header comment and `atomic_write(..., mkdir=True)` are unchanged.
- `read_created_record(repo_root) -> tuple[dict[str, set[str]], dict[str, Any]]` (per-kind ids for `REACH_ONLY_KINDS`, plus foreign keys). `write_created_record(repo_root, recorded, foreign)`.
- Leave `reach_only.py` importing these from `manifest` **in this WP** (its activation policy is WP02's file; a mechanical import swap here keeps the tree green without owning WP02's behaviour change). If that creates an import cycle, note it in the history and move the swap into WP02 instead.

### Subtask T004 – The one strict sidecar reader

- **File**: `manifest.py`. Rename `_synthesized_sidecar_urn` → `sidecar_artifact_urn` (public), keeping: `_validate_manifest_path(..., required_prefix=_PROVENANCE_PATH_PREFIX)`, `_resolve_under_repo`, `provenance.load_yaml` (Pydantic-validated), the `urn_kind == entry.kind` and non-empty id check, and `None` for `adapter_id == "project-direct-write"`.
- On `(OSError, ValueError, YAMLError)` raise `SynthesisMembershipUnreadableError` naming `entry.provenance_path` and the reason — this is the single raise site for a sidecar.
- Docstring: the one parser of the sidecar shape; the display path wraps it and catches this error.

### Subtask T005 – The one ownership reader

- **File**: `manifest.py`.
  ```python
  def synthesized_urns(repo_root: Path, kind: str) -> frozenset[str]: ...
  def synthesized_slugs(repo_root: Path, kind: str) -> frozenset[str]: ...  # URN id segment
  ```
- `synthesized_urns` steps (plan §Phase 1): absent manifest (and not a symlink) → `frozenset()`; `load_yaml` failure → `_recorded_urns`; per-entry `sidecar_artifact_urn`, `None` filtered out → union; any `SynthesisMembershipUnreadableError` from the sidecars → `_recorded_urns`.
- `_recorded_urns(repo_root, kind, cause)`: `read_created_record`; unreadable → `record_state="unreadable"`; ids present → log the existing warning and return `{f"{kind}:{id}"}`; no ids → `record_state="absent or lists no <kind>"`; a kind the record does not track (anything outside `REACH_ONLY_KINDS`) → `record_state="not tracked by the record"` and no record read at all. Then raise the one error with `from cause`.
- Delete `_synthesized_urns`, `_SynthesisOwnershipUnreadableError`, `_ownership_unreadable`.
- `__all__` gains `synthesized_urns`, `synthesized_slugs`, `sidecar_artifact_urn`, `read_created_record`, `write_created_record`, `manifest_slugs`, `created_record_key`, `CREATED_ARTIFACTS_PATH`, `LEGACY_CREATED_ARTIFACTS_PATH`, `UnreadableCreatedRecordError`.

### Subtask T006 – Consumers inside this module

- `synthesis_owned_directive_ids` calls `synthesized_urns(repo_root, ArtifactKind.DIRECTIVE.value)`; its docstring says it raises `SynthesisMembershipUnreadableError` (not `ManifestIntegrityError`).
- Add `manifest_slugs(repo_root, kind) -> frozenset[str]`: the lenient write-side helper moved from `reach_only._manifest_slugs`, docstring stating it answers "what the manifest listed before this run" for the first-time diff and is **not** an ownership answer (so it never raises).

### Subtask T007 – Update the ownership assertions

- `tests/charter/synthesizer/test_manifest.py`: `_synthesized_urns` → `synthesized_urns`; `_SynthesisOwnershipUnreadableError` → `SynthesisMembershipUnreadableError` with `.code` assertions; replace `test_ownership_unreadable_is_a_manifest_integrity_error` with a test that pins the one code and the metadata attributes; update the two `synthesis_owned_directive_ids` `pytest.raises(ManifestIntegrityError ...)` cases to the coded error, keeping the `synthesis-manifest.yaml` body assertion.
- New cases in the new module: `synthesized_urns` for `tactic` with a usable record after a missing sidecar (fallback), and the directive counterpart (raise).

## Test Strategy

```bash
uv run --frozen pytest tests/charter/synthesizer/test_synthesis_ownership_reader.py -q
uv run --frozen pytest tests/charter/synthesizer/test_manifest.py -q
uv run --frozen pytest tests/charter/test_charter_context_coded_error_6454.py tests/cli/test_charter_context_coded_error_6454.py -q 2>/dev/null || true
uv run --frozen ruff check src/charter/activation/synthesizer/manifest.py src/charter/activation/synthesizer/errors.py
uv run --frozen ruff format --check --force-exclude src/charter/activation/synthesizer/manifest.py src/charter/activation/synthesizer/errors.py
uv run --frozen mypy src/charter/activation/synthesizer/manifest.py src/charter/activation/synthesizer/errors.py
```

## Risks & Mitigations

- The record IO move is the breakage risk: every importer in `reach_only.py` must be updated in the same commit. Grep for `_read_record|_write_record|_record_key|CREATED_ARTIFACTS_PATH|_UnreadableRecordError` afterwards.
- `synthesis_owned_directive_ids` currently raises `ManifestIntegrityError`; the collision remedy catches it (WP03). Do not leave a caller raising into a catch that no longer matches — WP03 owns that file, so land WP01 and WP03 together before the PR is declared green.
- Do not make `synthesized_urns` read the record when the manifest is healthy: that would double the I/O on the hot path and mask a real inconsistency.

## Review Guidance

- `grep -n "synthesized_urns\|sidecar_artifact_urn\|read_created_record" src/` must show one definition of each.
- Check the reader's four branches against spec FR-002's table, and that a directive slate still refuses when the manifest is unreadable.
- Confirm no record-format byte changed: `tests/charter/synthesizer/test_reach_only_delivery.py` and the record round-trip tests pass unmodified in this WP.
