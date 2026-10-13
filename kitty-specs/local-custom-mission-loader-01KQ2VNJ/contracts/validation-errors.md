# Contract: Loader Validation Errors and Warnings

This is the closed enumeration of error and warning codes emitted by `mission_loader`. Wire spellings are stable: removal or rename is a breaking change requiring a deprecation cycle. Additions are non-breaking.

## Errors (exit code 2)

| Code | When | Required `details` keys |
| --- | --- | --- |
| `MISSION_YAML_MALFORMED` | Discovery scanned a file but failed to parse it as YAML, OR `MissionTemplate.model_validate` raised `ValidationError`. | `file`, `parse_error` |
| `MISSION_REQUIRED_FIELD_MISSING` | Top-level `mission.key`, `mission.name`, `mission.version`, or `steps[]` missing. (A specific subset of `MISSION_YAML_MALFORMED` surfaced separately for operator clarity.) | `file`, `mission_key` (best-effort), `field` |
| `MISSION_KEY_UNKNOWN` | The user invoked `spec-kitty mission run <key>` but no discovery tier produced a definition with that key. | `mission_key`, `tiers_searched` (list[str]) |
| `MISSION_KEY_AMBIGUOUS` | Two or more tiers produced the same key AND the resolver could not pick a single selected entry (extreme edge case; default precedence picks one). Reserved for future use. | `mission_key`, `paths` (list[str]) |
| `MISSION_KEY_RESERVED` | A non-builtin tier produced a definition whose `mission.key` is in `RESERVED_BUILTIN_KEYS`. | `mission_key`, `file`, `tier`, `reserved_keys` |
| `MISSION_RETROSPECTIVE_MISSING` | Validator R-001: the last step's `id` is not `"retrospective"`. | `file`, `mission_key`, `actual_last_step_id`, `expected: "retrospective"` |
| `MISSION_STEP_NO_PROFILE_BINDING` | Validator FR-008: a step with empty `requires_inputs` declares neither `agent_profile` nor `contract_ref`. | `file`, `mission_key`, `step_id` |
| `MISSION_STEP_AMBIGUOUS_BINDING` | Validator: a step declares both `agent_profile` AND `contract_ref`. | `file`, `mission_key`, `step_id` |
| `MISSION_CONTRACT_REF_UNRESOLVED` | A step's `contract_ref` does not resolve in the on-disk `MissionStepContractRepository`. | `file`, `mission_key`, `step_id`, `contract_ref` |

## Warnings (exit code unaffected; included in envelope)

| Code | When | Required `details` keys |
| --- | --- | --- |
| `MISSION_KEY_SHADOWED` | A definition was discovered in multiple tiers; the higher-precedence tier wins. Emitted for non-built-in keys (built-in shadow is an error per `MISSION_KEY_RESERVED`). | `mission_key`, `selected_path`, `selected_tier`, `shadowed_paths` |
| `MISSION_PACK_LOAD_FAILED` | A mission-pack manifest pointed at a `mission.yaml` that failed to load. | `pack_root`, `failed_path`, `parse_error` |

## Detail key conventions

- All paths are absolute strings.
- `mission_key` is the value of `template.mission.key` once known; `null` when unknown.
- `tier` ∈ `{"explicit", "env", "project_override", "project_legacy", "user_global", "project_config", "builtin"}`.
- `step_id` is the `PromptStep.id` value.

## Stability guarantees

1. The `result` field of the JSON envelope is exactly `"success"` or `"error"`. No third value.
2. `error_code` ∈ the codes above. Tooling MAY rely on string equality.
3. `details` is always an object. It MAY have additional keys beyond those required (forward-compatible). Tooling MUST NOT fail on unknown keys.
4. Warnings flow on success and on error envelopes. Tooling MUST surface them.
