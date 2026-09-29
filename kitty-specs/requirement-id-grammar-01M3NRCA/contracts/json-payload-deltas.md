# Contract: JSON payload deltas (additive, NFR-002)

Every key that exists today is kept, with the same type. The changes are listed below; each one also goes in the changelog.

## `spec-kitty agent mission finalize-tasks --json`

Added keys, present on both success and requirement-mapping failure:

```json
{
  "parsed_spec_ids": {
    "functional": ["FR-001", "FR-006a"],
    "non_functional": ["NFR-001"],
    "constraint": ["C-001"],
    "success_criteria": ["SC-001", "SC-002b"]
  },
  "rejected_requirement_refs": {
    "WP02": [
      {"ref": "C-007-mission", "reason": "malformed"},
      {"ref": "SC-009", "reason": "unknown_spec_id"},
      {"ref": "other-mission-01KAAAAA#FR-013", "reason": "foreign_qualified"}
    ]
  },
  "success_criteria_coverage": {
    "referenced": {"SC-001": ["WP01"]},
    "unreferenced": ["SC-002b"]
  }
}
```

- `unmapped_*` and all other existing keys keep their name and type. Two existing keys change meaning (pre-PR squad finding, recorded here and in the changelog):
  - `requirement_refs_parsed` now lists each WP's refs as authored (raw tokens, case preserved, including malformed and foreign ones), where it previously listed the uppercase-normalised subset the old parser recognised.
  - `unknown_requirement_refs` now lists every ref whose verdict fails (`malformed` or `unknown_spec_id`), not only undeclared well-formed IDs.
- `requirement_extraction_warnings` no longer contains the "SC … DROPPED, not traced" entry. The key stays.
- Pass/fail: the command fails if any `rejected_requirement_refs` entry has a reason in `{malformed, unknown_spec_id}`, or if any declared functional ID is unmapped. It never fails on `success_criteria_coverage.unreferenced`.

## `spec-kitty agent tasks map-requirements --json`

- **Input tokenisation:** each `--refs` value and each `--batch` list item is split with the grammar's ref tokenizer (commas and/or whitespace), the same split used for stored items, so `"FR-001, FR-002"` is two refs.
- **Pre-write refusal** (`--refs` or `--batch` holding an unusable ID): the existing `malformed_refs` / `unknown_refs` keys are kept, and `parsed_spec_ids` (flat list, as on the stale gate) is added to both the malformed and the unknown-ID refusal. The hint names the grammar: kinds FR/NFR/C/SC, a digit string, an optional lowercase letter, and an optional `<mission-slug>#` prefix for another mission's ID.
- **Stale gate:** `stale_ref_reasons` gains a `foreign_qualified` bucket next to `malformed` and `unknown_spec_id`. Foreign-qualified refs are reported only there: they never appear in `stale_refs` (which the hint tells the operator to `--replace`), and a WP whose only offenders are foreign is not listed.
- **Byte-contract fixture flips** (`byte_contracts.json`):
  - `map_requirements_malformed_ref_error`: `FR-001a` is no longer malformed. If it is undeclared in the fixture spec it becomes `unknown_spec_id`; the fixture is re-pinned to a genuinely malformed token.
  - `map_requirements_stale_frontmatter_error`: `FR-002a` moves from `malformed` to `unknown_spec_id`.
  - `map_requirements_unknown_spec_ref_error`: gains `parsed_spec_ids` (additive).
  - Hint text: re-pinned.
- **Success:** added refs are written in canonical form and existing items stay byte-identical, in their original order.
- **`--replace` success (FR-005):** `--replace` is the explicit, operator-invoked overwrite. Its success payload gains one additive key, `replaced_refs_removed: {WP: [item, …]}`: for every WP the run replaced, the previously stored items that the replacement dropped, raw as they were on disk and in their original order (an empty list when nothing was dropped). The key appears only on `--replace` runs, so the default-mode `map_requirements_success` byte contract does not move.

## `spec-kitty agent mission setup-plan --json`

- **New refusal** (exit **1**):

  ```json
  {"result": "error", "error_code": "SPEC_REQUIREMENT_IDS_INVALID",
   "error": "spec.md declares requirement IDs that do not match the requirement-ID grammar",
   "invalid_requirement_ids": [{"token": "C-007-mission", "line": 142, "rule": "<kind>-<digits>[<lowercase letter>]"}]}
  ```

- **New additive key on every non-error payload:** `"requirement_id_warnings": [{"token", "line", "message"}]`. The list is empty when clean.

## Orchestrator-api `plan` verb

The envelope `error_code` is **`PLAN_SETUP_FAILED`**, which is already registered in `core/upstream_contract.json` and needs no contract change. The data carries:

```json
{"reason": "SPEC_REQUIREMENT_IDS_INVALID", "invalid_requirement_ids": [ ... ]}
```

The shared `_classify_delegate_error` is not changed for the `tasks` and `specify` verbs.

**Contract version (NFR-002):** `CONTRACT_VERSION` (`orchestrator_api/envelope.py`) is bumped once, `1.7.0` → `1.8.0`, covering the additive `tasks` data keys (finalize's `parsed_spec_ids`, `rejected_requirement_refs`, `success_criteria_coverage`), the additive `plan` key `requirement_id_warnings`, and the `plan` remap to `PLAN_SETUP_FAILED` with `data.reason`. WP06 makes the bump. `core/upstream_contract.json` is not changed.

## Runtime (`spec-kitty next`) readiness findings

The findings reuse the same reason vocabulary. For one fixture, the list is non-empty if and only if finalize-tasks `--validate-only` fails on requirement mapping (SC-007).
