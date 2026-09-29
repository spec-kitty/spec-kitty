# Quickstart: verifying the requirement-ID grammar

Use the repo's editable install: `SK=.venv/bin/spec-kitty`. A bare `spec-kitty` on PATH may be a stale install.

## 1. Authored refs survive finalize (#2991)

1. In a scratch mission, have the spec declare `FR-001`, `FR-006a`, `SC-001` and `SC-002b` (table rows or `- **SC-001**:` bullets).
2. Put `requirement_refs: [FR-001, FR-006a, SC-001, SC-002b]` on `tasks/WP01-*.md`.
3. Run `$SK agent mission finalize-tasks --mission <handle> --json`, without `--validate-only`.
4. Expected:
   - The WP file's `requirement_refs` is exactly the seeded list.
   - `planning_base_branch` was written.
   - `success_criteria_coverage.referenced` lists both SC IDs.

## 2. The suffixed-FR coverage hole is closed (#3519)

1. Remove `FR-006a` from WP01.
2. Run `$SK agent mission finalize-tasks --mission <handle> --validate-only --json`.
3. Expected: failure, with `FR-006a` unmapped and `parsed_spec_ids.functional` containing `FR-006a`.

## 3. Rejections explain themselves (#2066)

1. Add `C-007-mission`, `SC-009` and `other-mission-01KAAAAA#FR-013` to WP01's refs.
2. Expected output of `rejected_requirement_refs.WP01`:
   - `malformed`, `unknown_spec_id` and `foreign_qualified`, in that order.
   - Validation fails, because of the first two.
   - `FR-001` still counts.

## 4. Planning hand-off check (#2066)

1. Add a spec row `| C-007-mission | … |`.
2. Run `$SK agent mission setup-plan --mission <handle> --json`.
3. Expected: exit 1, with `error_code: SPEC_REQUIREMENT_IDS_INVALID`.
4. Fix the row and run it again. Expected: it proceeds.
5. Write the prose line "see FR-099" in a non-requirements section. Expected: a `requirement_id_warnings` entry, and no refusal.

## 5. map-requirements is append-only

Run `$SK agent tasks map-requirements --mission <handle> --wp WP01 --refs sc-001,FR-002 --json`.

Expected:
- The existing items are unchanged, in their original order.
- `FR-002` is added.
- `SC-001` is not duplicated, because deduplication is by canonical form.

## Targeted tests (C-007; never the whole directory)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest -q \
  tests/specify_cli/test_requirement_mapping.py tests/specify_cli/test_requirement_id_grammar.py \
  tests/architectural/test_requirement_id_grammar_single_source.py \
  tests/architectural/test_bare_prose_corpus_ratchet.py tests/architectural/test_layer_rules.py \
  tests/architectural/test_bridge_cores_import_boundary.py
```
