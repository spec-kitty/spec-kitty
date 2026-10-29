# Data Model: Charter CLI typed errors and JSON

All shapes are **local** to core (schema_version `1.0.0`), snake_case, and are not the spec-kitty-charter
`ActivationConfig` contract (#6520/#6521 held; see contracts/cli-json.md "Contract mapping deferred to #6520").

## CodedError

| Field | Type | Notes |
|-------|------|-------|
| code | str | local UPPER_SNAKE (see contracts/cli-json.md) |
| message | str | human text, includes remedy where one exists |
| extra | dict | optional, merged into `error` (e.g. `requiring_packs`; for a post-change failure the whole change report plus `detail`) |

Rendered: text `Error (<code>): <message>`; JSON `{"ok": false, "error": {"code", "message", ...extra}}`. Only
this envelope carries `ok` (always false).

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
| skipped_out_of_scope | list[ArtifactRef + deactivated] | `deactivated` (bool, on every entry): the node is itself deactivated and nothing behind it was walked |
| skipped_deactivated | list[ArtifactRef + required_by] | activate only; `required_by` `[]` when reached only through `suggests` |
| unreached_behind_deactivated | list[ArtifactRef] | activate only |
| skipped_kind_filtered | list[ArtifactRef] | |
| skipped_shared | list[ArtifactRef + referenced_by] | deactivate only |
| skipped_required | list[ArtifactRef + packs] | deactivate only |
| still_active_unrestricted | list[ArtifactRef] | deactivate: child of a kind with no allow list |

Invariant: every artifact the text renderer prints a cascade line for appears in exactly one list, in render order.

## ActivationChangeReport (activate / deactivate success payload)

| Field | Type |
|-------|------|
| schema_version | "1.0.0" |
| command | "activate" \| "deactivate" |
| kind, id | str (as given) |
| changed | list[str] (the manager's activated/deactivated entries) |
| no_longer_in_force | list[str] (activate `--only`; `[]` otherwise) |
| warnings | list[str]: step-removal warnings, registration + manager warnings, tension findings, cascaded advisories, in that order |
| notices | list[str]: non-empty, stripped, unstyled lines of the post-change tail (catalog refresh, pack-skill projection) |
| referenced_not_cascaded | list[ArtifactRef] (no `--cascade`: skipped + deactivated references the warning lists) |
| referenced_kind_filtered | list[ArtifactRef] (no `--cascade`: the `Not cascaded` kind-filtered references) |
| cascade | CascadeReport \| null |

## ActivationBlock (`charter status --json` → `activation`)

| Field | Type | Notes |
|-------|------|-------|
| schema_version | "1.0.0" | |
| source | "ledger" \| "legacy" | `ActivationSource` |
| path | str | file actually read, repo-relative when inside the repo |
| exists | bool | ledger file present |
| selected | {plural: list[str] \| null} | null = no allow list: every artifact of the kind (skills: org-required only) |
| deactivated | {plural: list[str]} | deny lists, present only |
| mission_types | list[str] \| null | null = no mission type in force |
| activated_kinds | list[str] \| null | null = every kind |
| required | list[{kind, id, in_force, packs}] | org-required floor of every org-requirable kind; non-activatable kinds always in force |
| required_error | {code, message} | only when the strict org-charter read fails; `required` is then the lenient read |

On an activation read failure: `{"schema_version": "1.0.0", "error": {"code", "message"}}` (a typed code, or
`ACTIVATION_STATE_UNREADABLE` for an OSError); status still succeeds for the other sections (the broken-charter
and dangling-pointer cases are refused earlier, FR-001).
