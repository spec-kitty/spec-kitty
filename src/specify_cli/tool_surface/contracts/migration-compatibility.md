# Migration Compatibility Contract

This contract freezes the **external interfaces** that the ToolSurfaceContract
registry (WP01) and its providers (WP03-WP09) must not break. It is enforced by
the integration tests under
`tests/specify_cli/tool_surface/integration/`:

- `test_migration_compat.py` -> `spec-kitty doctor skills --json`
- `test_agent_config_compat.py` -> `spec-kitty agent config list/status/sync`

Those tests are a **compatibility gate**: they must stay GREEN for every
subsequent WP PR. If a WP breaks a frozen interface, that WP cannot merge.

The tests are deterministic. They run the **checkout-local** package
(`python -m specify_cli`, never the globally-installed `spec-kitty` script)
against a controlled `.kittify` fixture in a temp directory, so the result
never depends on which agents or tools the developer has configured.

## Frozen interfaces

### `spec-kitty doctor skills --json`

This command emits a JSON object. The **schema shape** (keys + value types, not
content) is captured in `fixtures/doctor_skills_baseline.json` and asserted by
`test_doctor_skills_json_schema_matches_baseline`.

Frozen success-path fields:

| Field | Type | Notes |
|-------|------|-------|
| `ok` | bool | Overall health (false when agents are uninstalled, drift exists, etc.) |
| `configured_agents` | list[str] | Agents from `.kittify/config.yaml` |
| `manifest_agents` | list[str] | Agents recorded in the command-skills manifest |
| `entries` | int | Manifest entry count |
| `canonical_commands` | int | Count of canonical command skills |
| `drift` | list[str] | Skills whose content drifted |
| `gaps` | list[str] | Missing skills |
| `orphans` | list[str] | Unexpected skills |
| `stale` | list[str] | Stale skills |
| `unsafe` | list[str] | Unsafe skill paths |
| `uninstalled_agents` | list[str] | Configured but not installed |
| `vibe_config_missing` | bool | Vibe skill-path config absent |
| `repaired_agents` | list[str] | Agents repaired by `--fix` |
| `repaired_paths` | list[str] | Pack-skill paths projected or retired by `--fix` (additive, #5801) |
| `pruned` | list[str] | Entries pruned by `--fix` |
| `repaired_vibe_config` | bool | Vibe config repaired by `--fix` |
| `repair_errors` | list[str] | Errors during `--fix` |
| `pack_skills` | list[object] | Pack-skill drift / stale / orphaned findings, each naming its pack `source_ref` (additive, #5193) |
| `slash_commands` | object | Nested report: `configured_agents`, `gaps`, `repaired`, `errors`, `ok` |

Frozen **error envelope** (asserted by `test_doctor_skills_json_error_schema_stable`):

```json
{ "ok": false, "error": { "code": "<stable-identifier>", "message": "<human-readable>" } }
```

Known error `code` values include `not_in_project`, `config_error`, and
`manifest_error`. The error path exits with code `2`. The success path exits `0`
(healthy) or `1` (schema healthy but action needed, e.g. uninstalled agents).

### `spec-kitty agent config list / status / sync`

These subcommands have **no `--json` flag**; their external interface is the
command surface, exit codes, and stable human-readable markers, captured in
`fixtures/agent_config_list_schema.json` and asserted by
`test_agent_config_compat.py`.

Frozen facts:

- `agent config list` exits `0` and prints the markers `Configured agents:` and
  `Auto-commit:`.
- `agent config status` exits `0` and prints a table titled `Agent Status` with
  columns `Agent Key`, `Directory`, `Configured`, `Exists`, `Status`.
- `agent config sync --keep-orphaned` is idempotent on a fixture with no
  orphans: it exits `0`, prints `No changes needed`, and makes **no** state
  changes to the project tree.
- None of the three subcommands expose `--json` today. Adding it later is an
  *additive* change (see below) and must update both the descriptor fixture and
  this contract.

## Additive vs. breaking changes

**Additive (allowed) -- the gate stays green or is updated in the same PR:**

- New top-level keys added to `doctor skills --json`.
- New finding/list entries or new `code` values in the error envelope.
- New fields added to nested objects (e.g. `slash_commands`).
- A new `--json` flag added to an `agent config` subcommand.

**Breaking (forbidden) -- the gate must fail and block merge:**

- Removing or renaming any frozen field above.
- Changing a frozen field's value type (e.g. list -> object).
- Removing a frozen text marker or changing a frozen exit code.
- Removing an `agent config` subcommand.
- `agent config sync --keep-orphaned` mutating state when there are no orphans.

## How to update baselines (intentional additive change)

If an intentional **additive** change causes baseline drift:

1. Regenerate the schema shape. From the checkout, run the helper used by the
   tests against a controlled fixture:

   ```python
   from tests.specify_cli.tool_surface.integration._compat_support import (
       run_spec_kitty, schema_shape, write_controlled_project,
   )
   ```

   Capture `schema_shape(result.json())` for `doctor skills --json` into
   `fixtures/doctor_skills_baseline.json` (shape only -- never raw content,
   paths, or counts).
2. For `agent config`, update `fixtures/agent_config_list_schema.json`.
3. Document the change in `CHANGELOG.md`.
4. The PR must include Codex sign-off confirming the change is **additive**, not
   breaking, before the updated baseline is accepted.
