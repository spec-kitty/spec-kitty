---
work_package_id: WP01
title: 'Effective override policy: pack sanctions, scoping, revocation, decision table'
dependencies: []
requirement_refs:
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-013
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-003
- C-004
- C-005
- C-006
- SC-005
planning_base_branch: issue-replaceable-builtins-sanction
merge_target_branch: issue-replaceable-builtins-sanction
branch_strategy: Planning artifacts for this mission were generated on issue-replaceable-builtins-sanction. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-replaceable-builtins-sanction unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-shipped-builtin-override-sanction-01M45WB7
base_commit: ca59bbea59f4cb9b0113b5b4f97c2719c84cae3e
created_at: '2026-10-05T11:36:53.414609+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history: []
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/
create_intent:
- tests/doctrine/drg/test_override_policy_pack_sanctions.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/drg/override_policy.py
- src/charter/offering/drg/merge.py
- tests/doctrine/drg/test_override_policy_predicates.py
- tests/doctrine/drg/test_override_policy_pack_sanctions.py
- tests/architectural/test_builtin_override_policy.py
- tests/doctrine/test_drg_merge.py
role: implementer
tags: []
tracker_refs: []
---

# WP01: Effective override policy (pack sanctions, scoping, revocation, decision table)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP01 --agent claude`

## Objective

Make `charter.offering.drg.override_policy` the single authority for built-in override sanctions:
- Parse the consumer allowlist, including the new optional `revoked_pack_sanctions` key.
- Load each org pack's pack-root `replaceable-builtins.yaml`, with containment and per-pack isolation.
- Detect overrides together with their contributing pack.
- Adjudicate them with a pure function that implements the spec's sanction decision table.
- Switch the architectural gate to the same loader, and pin parity.

## Context

- Read first: `spec.md`, especially § "Sanction decision table", FR-002 to FR-007, FR-013 and the edge cases. Then `plan.md` § Design, `data-model.md`, `contracts/replaceable-builtins-file.md`, and `research/code-grounding.md` §1, §4, §5 and §9.
- Today `load_replaceable_builtins` (`override_policy.py:117`) reads only `.kittify/doctrine/replaceable-builtins.yaml`, and `find_overridden_builtin_urns` (`:182`) drops the pack from `org:<pack>` provenance.
- **Layer rule (C-004).** This module is in `charter.offering`. It must NOT import `charter.activation` or `specify_cli`. Pack roots come in as a `Mapping[str, Path]`, built from `OrgDRGFragment` objects (`charter.offering.drg.org_pack_loader`): `pack_name` and `source_ref`, as stamped at `org_pack_loader.py:562-564`.
- **Containment.** Use `charter.offering.drg.org_pack_config.resolve_relative_path_within_root` (`:172`). It raises `OrgPackSubdirEscapeError` on an escape.
- **Do not change merge behaviour (C-005).** You may only correct the misleading docstring at `merge.py:~1208` ("earlier fragments take precedence"). For built-in URNs the code makes the last pack win (`merge.py:927`).
- **Dead-symbol gate (blocker found by the post-tasks squad).** `tests/architectural/test_no_dead_symbols.py` checks EVERY public name, not just the ones in `__all__`. A name used only inside its own module also counts as dead. Today the only `src` caller of `load_replaceable_builtins`, `find_overridden_builtin_urns` and `find_unsanctioned_overrides` is `_doctrine_collect.py:880-890`, and WP02 replaces that caller. Therefore:
  - **Retire** `find_overridden_builtin_urns` and `find_unsanctioned_overrides`, so they cannot become a second authority (C-003). Migrate their tests (`tests/doctrine/drg/test_override_policy_predicates.py`, and the seam test in `tests/architectural/test_builtin_override_policy.py`) honestly to `find_overridden_builtins` + `adjudicate_overrides`.
  - **Make `load_replaceable_builtins` private** (`_load_consumer_policy`), called only by `load_effective_override_policy`. Migrate `tests/doctrine/test_drg_merge.py::TestReplaceableBuiltinsPolicy` to exercise the consumer file through `load_effective_override_policy(repo_root, {})`, keeping every existing assertion about messages and fail-closed behaviour.
  - New public names (`load_effective_override_policy`, `adjudicate_overrides`, `find_overridden_builtins`, `pack_roots_from_fragments`, `legacy_template_entries`, `load_pack_sanction`, `PACK_POLICY_FILENAME`) get `src` callers in WP02 and WP03. Inside this lane the gate is expected to be red between WP01 and WP02. Record that in the hand-off. The closeout history cleanup folds the caller in before landing, so that no intermediate commit is red on the gate.

### Subtask T001: Tidy-first seam (behaviour-preserving, separate commit)
- **Purpose**: Make parsing source-agnostic before any functional change (DIRECTIVE_025).
- **Steps**:
  1. Extract `_parse_policy_document(data: object, *, source_label: str, allow_revocations: bool) -> ReplaceableBuiltinsPolicy` from `load_replaceable_builtins`. Make `_parse_entry` take `source_label`.
  2. `load_replaceable_builtins(repo_root)` keeps its signature, return type and **byte-identical messages**. It passes `source_label=str(POLICY_RELPATH)`.
  3. Correct the `merge.py` docstring at lines 1208-1211. It currently says "earlier fragments take precedence" and "a built-in node always wins regardless". Both are false for same-kind overrides at built-in URNs: the org node substitutes in place, and the last org pack wins (`_resolve_builtin_collision`, :905-927). Change the docstring only.
- **Validation**: `pytest tests/doctrine/test_drg_merge.py tests/doctrine/drg/ tests/architectural/test_builtin_override_policy.py` passes unchanged. Commit as `refactor(doctrine): …` before any T002+ code.

### Subtask T002: Consumer revocations and pack loader
- **Steps**:
  1. Add defaulted fields `revoked_urns: frozenset[str] = frozenset()` and `revoked_packs: frozenset[str] = frozenset()` to `ReplaceableBuiltinsPolicy`. Existing constructions such as `ReplaceableBuiltinsPolicy(entries=...)` must keep working.
  2. Parse the consumer-only `revoked_pack_sanctions:` key: a list of mappings, each with exactly one of `urn` / `pack` (a non-empty string), and an optional string `reason`. Anything else raises `OverridePolicyError`. Ignore unknown top-level keys, as today.
  3. Add `PACK_POLICY_FILENAME = "replaceable-builtins.yaml"` and `load_pack_sanction(pack_name: str, pack_root: Path) -> ReplaceableBuiltinsPolicy`:
     - Resolve the file through `resolve_relative_path_within_root(pack_root, PACK_POLICY_FILENAME)`.
     - Absent file → an empty policy.
     - Raise `OverridePolicyError` with a message naming the **pack and the path** when the path escapes the root (catch `OrgPackSubdirEscapeError`), is not a regular file (for example a directory), raises an `OSError`, holds invalid YAML or the wrong shape, or contains `revoked_pack_sanctions` (that key is consumer-only).
- **Validation**: unit tests in T005.

### Subtask T003: Effective policy loader (FR-013)
- **Steps**:
  1. Add a frozen dataclass `EffectiveOverridePolicy(consumer: ReplaceableBuiltinsPolicy, packs: Mapping[str, ReplaceableBuiltinsPolicy], pack_errors: tuple[str, ...])`.
  2. Add `pack_roots_from_fragments(fragments: Iterable[OrgDRGFragment]) -> dict[str, Path]` (`Path(frag.source_ref)` keyed by `frag.pack_name`).
  3. Add `load_effective_override_policy(repo_root: Path, pack_roots: Mapping[str, Path]) -> EffectiveOverridePolicy`:
     - The consumer file is loaded through `_load_consumer_policy`. A malformed consumer file does NOT raise. It is recorded in a new `consumer_error: str | None` field, and the consumer policy is treated as empty, so the check fails closed. This is the spec edge case "malformed consumer allowlist".
     - Every `revoked_pack_sanctions.pack` that is not a key of `pack_roots` is recorded in a new `revocation_errors: tuple[str, ...]` field. Matching is exact and case-sensitive.
     - Every pack is read eagerly. An `OverridePolicyError` for a pack goes into `pack_errors`, and that pack is left out of `packs` (isolation).
     - When a pack's sanction path `.resolve()`s to the same file as the consumer allowlist (also `.resolve()`d, so that a symlinked `.kittify` still matches), skip that pack **before parsing**, so the file counts once, for the consumer only. Otherwise the consumer's legitimate revocation key would be reported as a pack error.
  4. `pack_roots_from_fragments(fragments, repo_root)` resolves a relative `source_ref` against `repo_root`. The loader always stamps an absolute effective root, including `subdir`, but test fragments may not.
- **NFR-001**: exactly one sanction-file read per pack. Pin this in tests with a counting monkeypatch.

### Subtask T004: Provenance-aware detection and the pure adjudicator
- **Steps**:
  1. Add `OverriddenBuiltin(urn, kind, pack)` and `find_overridden_builtins(merged, built_in_urns) -> list[OverriddenBuiltin]`, sorted by URN. Derive `pack` from `provenance.removeprefix("org:")`. Re-express `find_overridden_builtin_urns` on top of it, with an identical result.
  2. Add `SanctionedOverride(urn, kind, pack, source: Literal["consumer","pack"], reason)` and `OverrideAdjudication(sanctioned: list, unsanctioned: list[UnsanctionedOverride])`.
  3. Add the pure function `adjudicate_overrides(overrides, effective) -> OverrideAdjudication`. It implements the spec's decision table exactly:
     - A valid consumer entry wins, with source `consumer`.
     - Otherwise, a valid entry in **the same pack's** sanction counts, with source `pack`, unless the URN is in `consumer.revoked_urns` or the pack is in `consumer.revoked_packs`.
     - "Valid" means the URN is listed, and directives (`_is_directive_urn`) have a non-empty, stripped reason.
     - Every `why` text names `replaceable-builtins`. Use these:
       - not listed anywhere: `"not on .kittify/doctrine/replaceable-builtins.yaml or pack '<P>' replaceable-builtins.yaml"`
       - revoked: `"pack '<P>' sanction revoked by .kittify/doctrine/replaceable-builtins.yaml (revoked_pack_sanctions)"`
       - empty directive reason in the consumer file: `"directive override requires a non-empty reason"`
       - empty directive reason in the pack file: `"directive override requires a non-empty reason (pack '<P>' replaceable-builtins.yaml)"`
       - A revocation takes precedence over a reason finding whenever the pack would otherwise have sanctioned the override (see spec.md's decision table and the note below it).
     - Keep the function at complexity ≤ 15 by extracting a `_verdict_for(override, effective)` helper.
  4. Add `LEGACY_TEMPLATE_RELPATH = "templates/setup/replaceable-builtins.yaml"` and `legacy_template_entries(pack_root: Path, urns: Iterable[str]) -> dict[str, str]`. It is a tolerant probe: on any error (escape, malformed, absent) it returns `{}`. It returns `{urn: reason}` for the requested URNs that the template lists.
  5. Retire `find_unsanctioned_overrides` and `find_overridden_builtin_urns` (see Context). Pack names may contain `:`, so parse provenance with `removeprefix("org:")`, never with `split(":")`.

### Subtask T005: Focused tests (red-first)
- **Ordering:** right after T001, write the decision-table and loader tests against stub signatures (functions that raise `NotImplementedError`). Commit them RED as `test(doctrine): red-first decision table for pack sanctions (#5767)` and record the red run in your notes. Only then implement T002-T004.
- In `tests/doctrine/drg/test_override_policy_predicates.py` (pure; build `DRGGraph`/nodes as the existing tests do):
  - one test per decision-table row;
  - cross-pack: pack B's sanction cannot sanction pack A's node;
  - revocation by URN, and revocation by pack;
  - the consumer listing wins over a revocation;
  - a consumer directive entry with an empty reason plus a pack entry with a reason → sanctioned by the pack;
  - an inert entry for a non-overridden URN;
  - the cells the post-tasks squad flagged:
    - consumer valid + malformed pack → sanctioned by consumer (unhealthiness is WP02's concern);
    - invalid consumer entry + valid pack + revocation → the revocation `why`;
    - revocation of a URN the pack never sanctioned → the row-4 `why`;
    - revocation by pack `P'` while the node comes from `P` → still sanctioned;
    - pack empty-reason directive → the pack-reason `why`;
    - a pack name containing `:`.
- In the new `tests/doctrine/drg/test_override_policy_pack_sanctions.py` (use `tmp_path`):
  - absent pack file → empty;
  - valid file;
  - each malformed variant raises with the pack name and path in the message;
  - a symlink pointing outside the root → error;
  - a directory in place of the file → error;
  - `revoked_pack_sanctions` inside a pack file → error;
  - consumer revocation parsing, valid and invalid;
  - effective loader isolation: one bad pack and one good pack → the good pack is loaded and the error is recorded;
  - consumer-path dedupe;
  - read count, one read per pack (NFR-001);
  - legacy probe, tolerant;
  - **NFR-002 compatibility (non-vacuous):** load the merge-base module (`git show 14d653bb:src/charter/offering/drg/override_policy.py`, written to `tmp_path` and imported via `importlib`). Assert that its `load_replaceable_builtins` parses a consumer file carrying `revoked_pack_sanctions` with no error, and that it never reads a pack-root file. If `git` is unavailable, skip with a reason.
  - malformed consumer → `consumer_error` is set, the consumer is treated as empty, and pack sanctions still load;
  - unknown revoked pack (case mismatch `Acme` vs `acme`) → `revocation_errors`;
  - consumer-path dedupe through a symlinked `.kittify`;
  - a relative `source_ref`.
- Mark every test `pytest.mark.fast`.

### Subtask T006: Arch gate on the shared loader
- In `tests/architectural/test_builtin_override_policy.py`, make `test_builtin_overrides_are_sanctioned` use these:
  - `load_effective_override_policy(_REPO_ROOT, pack_roots_from_fragments(org_fragments, _REPO_ROOT))`
  - `find_overridden_builtins`
  - `adjudicate_overrides`
- Merge with `project=None`. Doctor merges without the project layer, and project-tier overrides are ungoverned (C-006). Merging the project layer would let a project node mask an org override in the gate but not in doctor, which breaks parity (FR-013).
- Also assert that `effective.pack_errors`, `consumer_error` and `revocation_errors` are empty for this repository.
- Migrate the seam test (`test_real_merge_override_is_detected_and_governed`) to the new API.
- The doctor/gate parity test (SC-005) is owned by WP02, in a new file. Do NOT add it here.

## Definition of Done
- T001–T006 are recorded with `spec-kitty agent tasks mark-status <Txxx> --status done`.
- T001 is a separate behaviour-preserving commit that comes first.
- These pass (`test_no_dead_symbols.py` is expected red only for the WP02/WP03 callers that have not landed yet; list the exact names in the hand-off):
  - `pytest tests/doctrine/drg/ tests/doctrine/test_drg_merge.py tests/charter/test_org_drg_cannot_override_shipped_invariants.py tests/architectural/test_builtin_override_policy.py tests/architectural/test_layer_rules.py tests/architectural/test_charter_offering_does_not_import_activation.py`
  - `make test-fast`
- `ruff check`, `ruff format --check --force-exclude` and `mypy` pass on the changed files. Complexity is ≤ 15. No new suppressions.
- Every commit carries `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`, and no commit names an AI model.

## Risks
- Breaking the byte-identical consumer messages pinned by `TestReplaceableBuiltinsPolicy`. Mitigation: T001 runs those tests first.
- The dead-symbol gate flagging names whose callers land in WP02/WP03. Mitigation: a minimal `__all__`, documented for the reviewer.
- A Windows symlink test. Mitigation: `pytest.skip` when `os.symlink` is unavailable.

## Reviewer Guidance
- Check that the decision table is implemented exactly, especially the cross-pack, revocation and consumer-first rows.
- Check that there is no I/O inside `adjudicate_overrides` or the `find_*` functions.
- Check that there are no `charter.activation` or `specify_cli` imports.
- Check that T001 is behaviour-preserving (diff its tests: they should have none).
- Re-run the named arch gates.
