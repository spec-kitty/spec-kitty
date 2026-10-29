# Data Model: Charter CLI typed errors and JSON

All shapes are **local** to core (schema_version `1.0.0`), snake_case, and are not the spec-kitty-charter
`ActivationConfig` contract (#6520/#6521 held).

## CodedError

| Field | Type | Notes |
|-------|------|-------|
| code | str | local UPPER_SNAKE (see contracts/cli-json.md) |
| message | str | human text, includes remedy where one exists |
| extra | dict | optional, merged into `error` (e.g. `requiring_packs`) |

Rendered: text `Error (<code>): <message>`; JSON `{"ok": false, "error": {"code", "message", ...extra}}`.

## ArtifactRef

| Field | Type | Notes |
|-------|------|-------|
| kind | str | operator token (`directive`, `agent-profile`, …) |
| id | str | stored spelling (config-stem id written to the activation files) |
| urn | str \| null | DRG URN when resolvable |

## CascadeReport

| Field | Type | Notes |
|-------|------|-------|
| source_urn | str | cascade source |
| scope | list[str] \| "all" | parsed `--cascade` value |
| cascaded | list[ArtifactRef] | activated / deactivated by the walk |
| reinstated | list[ArtifactRef] | exclusion cleared (`--include-deactivated`) |
| failed | list[ArtifactRef + message] | per-target failure; command continues |
| skipped_out_of_scope | list[ArtifactRef] | |
| skipped_deactivated | list[ArtifactRef + required_by] | activate only |
| unreached_behind_deactivated | list[ArtifactRef] | activate only |
| skipped_kind_filtered | list[ArtifactRef] | |
| skipped_shared | list[ArtifactRef + referenced_by] | deactivate only |
| skipped_required | list[ArtifactRef + packs] | deactivate only |
| still_active_unrestricted | list[ArtifactRef] | deactivate: child of a kind with no allow list |

Invariant: every artifact the text renderer prints a cascade line for appears in exactly one list.

## ActivationChangeReport (activate / deactivate success payload)

| Field | Type |
|-------|------|
| schema_version | "1.0.0" |
| command | "activate" \| "deactivate" |
| kind, id | str |
| changed | list[str] (the manager's activated/deactivated messages' entries) |
| no_longer_in_force | list[str] (activate `--only`) |
| warnings | list[str] (manager/registration warnings and tension findings, as the text lines say) |
| referenced_not_cascaded | list[ArtifactRef] (no `--cascade`: the artifacts today's no-cascade warning lists) |
| cascade | CascadeReport \| null |

## ActivationBlock (`charter status --json` → `activation`)

| Field | Type | Notes |
|-------|------|-------|
| schema_version | "1.0.0" | |
| source | "ledger" \| "legacy" | `ActivationSource` |
| path | str | file actually read, repo-relative when inside the repo |
| exists | bool | ledger file present |
| selected | {plural: list[str] \| null} | null = no allow list (unrestricted / kind default) |
| deactivated | {plural: list[str]} | deny lists, present only |
| mission_types | list[str] \| null | |
| activated_kinds | list[str] \| null | |
| required | list[{kind, id, in_force, packs}] | org-required floor |

On an activation read failure: `{"schema_version": "1.0.0", "error": {"code", "message"}}`; status still succeeds for the other sections (the broken-charter case is refused earlier, FR-001).
