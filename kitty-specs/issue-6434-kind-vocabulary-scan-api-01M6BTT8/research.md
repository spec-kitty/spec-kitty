# Discovery — issue #6434 (kind_vocabulary scanning API)

Captured before the spec, at the `discovery` step. Facts below are from the mission
checkout at `issue-6434-kind-vocabulary-scan-api` (base `origin/main` = `287a226cfe`).

## Grounding the issue

- Issue spec-kitty/spec-kitty#6434 is **open, unassigned, unclaimed** at the start of this
  run (labels: `domain:charter`, `priority:P3`, `tech-debt`, `from:dev`). No PR, branch or
  commit on `main` addresses it: `gh pr list --search 6434` returns only the merged #6440
  (#6404's mission PR), and `git log -S"_scan_dir_matches"` shows only the parity work that
  introduced the helpers, nothing that promotes them.
- It is a **pre-PR review finding on the #6404–#6408 Mission**, whose PR #6440 added
  `src/charter/activation/identity_index.py`. The coupling therefore still reproduces on
  current `main`.
- The tracked issue text names the affected private names explicitly:
  `kind_vocabulary._scan_dir_matches`, `IdentityIndex._scan`,
  `_load_action_governance_bundle`, `compiler._direct_root_urns`, plus the module helpers
  the index calls (`_scan_roots`, `_read_id`, `_id_field_for`, `_config_stem`,
  `_iter_artifact_paths`).

## Reproduction (current main)

`IdentityIndex._scan` (`src/charter/activation/identity_index.py:250-269`) is written
entirely against private `kind_vocabulary` names:

```
kind_vocabulary._id_field_for(kind)
kind_vocabulary._scan_roots(kind, _offering_root=..., org_roots=..., layer_roots=...)
kind_vocabulary._scan_dir_matches(scan_dir, pattern, recursive=recursive)
kind_vocabulary._config_stem(path)
```

Tests reach for the same private surface to count scans and compute expected ids:

| Test file | Private coupling |
| --- | --- |
| `tests/charter/activation/test_identity_index.py` | `kind_vocabulary._scan_dir_matches`, `._parse_id`, `._id_field_for`, `._config_stem`, `._built_in_scan_dir` |
| `tests/charter/test_directive_resolution_memoization.py` | `kind_vocabulary._scan_dir_matches`, `._parse_id` |
| `tests/charter/activation/test_context_identity_reuse.py` | `IdentityIndex._scan` |
| `tests/charter/test_resolver_directive_activation_keying.py` | `IdentityIndex._scan` |
| `tests/charter/activation/test_compile_check_identity_6433.py` | `kind_vocabulary._iter_artifact_paths`, `._config_stem`, `._read_id`, `._id_field_for` |
| `tests/charter_offering/drg/test_recursion_parity_gate.py` | `kind_vocabulary._iter_artifact_paths` |
| `tests/charter_offering/test_owner_delivery.py`, `tests/charter_offering/drg/test_org_pack_node_inference.py`, `tests/charter/test_synthesized_in_force_snapshot.py`, `tests/charter/test_context_service_seams.py`, `tests/charter/test_action_governance_bundle_activation.py`, `tests/charter/synthesizer/test_styleguide_reach_only.py`, `tests/charter/synthesizer/test_reach_only_delivery.py` | `action_governance_bundle._load_action_governance_bundle` |
| `tests/charter/synthesizer/test_styleguide_reach_only.py`, `tests/charter/synthesizer/test_reach_only_delivery.py` | `compiler._direct_root_urns` |

## Decisions

1. **Scope = the four seams the issue names, not the whole charter layer.** The review
   finding lists exactly `kind_vocabulary`'s scanning helpers, `IdentityIndex._scan`,
   `_load_action_governance_bundle` and `compiler._direct_root_urns`. Every other
   underscore name in these modules (`_org_scan_dirs`, `_layer_scan_dirs`,
   `_directive_ids_by_stem`, `_resolve_action_bundle`, …) is a genuine implementation
   detail with no consumer outside its module, and stays private. Rationale: DIRECTIVE_024
   (locality of change) plus the issue's own scope.
2. **Promote, do not wrap.** Each helper is renamed in place and its call sites updated;
   no compatibility alias is kept. A private alias left behind would preserve exactly the
   coupling the issue reports, and these are internal `charter`-layer modules with no
   published contract (C-002 in the spec).
3. **Names.** `scan_roots`, `scan_dir_matches`, `iter_artifact_paths`, `built_in_scan_dir`,
   `artifact_id_field`, `read_artifact_id`, `parse_artifact_id`, `artifact_config_stem`;
   `IdentityIndex.scan`; `load_action_governance_bundle`; `compiler.direct_root_urns`.
   `artifact_` prefixes keep the id helpers from reading as generic YAML utilities, and
   `read_artifact_id` (memoised, `resolution_pass`-aware) vs `parse_artifact_id` (uncached
   full parse) preserves the distinction the scan-count tests rely on.
4. **`_load_action_governance_bundle` is already exported.** It sits in
   `action_governance_bundle.__all__` with a leading underscore — the rename fixes an
   existing inconsistency rather than widening the module's surface. `context.py` keeps
   re-exporting it under a private alias for its own use; only the defining name and the
   test imports change.
5. **The red test is an architectural ratchet, not a behaviour test.** A refactor has no
   failing behaviour to reproduce, so the mission's red-first proof is a new test that
   fails on `main` (the retired names are still reached) and passes only when every call
   site has moved. It also guards recurrence, which a one-off rename cannot.
6. **Behaviour must be provably unchanged.** The existing suites pin resolution: scan-count
   and memoization tests (NFR-001), the recursion/loader parity gate, the config-stem
   parity test, the identity-index suite and the governance-bundle suites. They run
   unmodified apart from the probe seam they wrap.

## Evidence

- `src/charter/activation/kind_vocabulary.py` module docstring already describes itself as
  "the single seam through which charter-layer consumers route two vocabularies"; the
  scanning half of that seam is private, which is the gap the issue reports.
- `tests/architectural/charter_activation_boundary_baseline.yaml` keys its ratchet on
  `(file, module)` pairs, not symbol names, so promoting symbols does not move a baseline.
- `tests/architectural/test_charter_facades_reexport_offering.py` and
  `test_charter_activation_api_reexport.py` assert specific public re-exports from
  `kind_vocabulary`; none of them names a promoted helper, so the additions are additive.
- Sibling precedent: `PROJECT_KIND_DIRS` was already promoted from `_PROJECT_KIND_DIRS` in
  the same module (comment above the alias), for the same reason — a consumer needed the
  mapping without a private name.

## Open questions

- None blocking. The one judgement call — whether to include the two governance-seam
  renames in this mission — is settled by decision 1 and recorded in the spec as FR-005 so
  a reviewer can drop it cleanly if they disagree.
