# Contract: charter status / activate / deactivate JSON (local, schema 1.0.0)

Local CLI contract. Not the spec-kitty-charter activation contract (ADR-0020); the mapping onto it is held
by #6518 (#6520 fields, #6521 revision, #6524 refusal codes). See "Contract mapping deferred to #6520" below.

## Error envelope (all three commands)

```json
{"ok": false, "error": {"code": "ACTIVE_CHARTER_CONFIG_INVALID", "message": "..."}}
```

Only the error envelope carries `ok`, and it is always `false`. Success payloads have no `ok`: status keeps
`result: "success"`, the change report has neither. Consumers detect an error by the presence of `ok` / `error`.
Exit codes are those of the same invocation without `--json`. Text mode prints `Error (<CODE>): <message>`.

| Code | Command(s) | Cause | Exit |
|------|------------|-------|------|
| ACTIVE_CHARTER_CONFIG_INVALID | all | an unsound charter.yaml (unparseable, non-mapping, empty); a `charter:` pointer in `.kittify/config.yaml` naming a missing file (status gives the pointer remedy); an unreadable activation ledger; an unsound pack configuration (deactivate's strict required-floor read); `deactivate` of an artifact on an unmigrated project | 1 |
| CHARTER_CONFIG_SHAPE_INVALID | status | evidence reader's config shape error, reachable only after the soundness gate passes (a non-mapping `.kittify/config.yaml` is refused earlier as ACTIVE_CHARTER_CONFIG_INVALID) | 1 |
| CHARTER_STATUS_FAILED | status | repository/task resolution failure, or a charter bundle that is not compatible with this CLI | 1 |
| INTERNAL_ERROR | status | unexpected exception; the only message starting `Unexpected error:` | 1 |
| ACTIVATION_KIND_UNKNOWN | activate, deactivate | KIND not an activation kind | 1 |
| CASCADE_SCOPE_INVALID | activate, deactivate | bad `--cascade` value | 1 |
| CHARTER_WRITE_ROOT_INVALID | activate, deactivate | linked worktree / write root | 1 |
| DEACTIVATION_REFUSED_REQUIRED | deactivate | org-required id; `error.requiring_packs` lists the packs | 1 |
| ACTIVATION_FAILED | activate, deactivate | activation engine / DRG load error (unknown id, malformed `charter_packs` on activate, mission-type preflight); under `--json` also a failed pack-skill projection after the change (`error` carries the change report and `detail`) | 1 |
| RESYNTHESIS_FAILED | activate, deactivate (`--json`) | change written, post-write catalog refresh/resynthesis failed; `error` carries the change report and `detail` (the failed step's captured output) | 1 |

`charter status` may pass other internal-consistency codes through unchanged; consumers treat an unknown code
as an error. `ACTIVATION_STATE_UNREADABLE` is not a command refusal: it is the `error.code` of the status
`activation` block only (below).

A refusal writes nothing, except RESYNTHESIS_FAILED and the post-change ACTIVATION_FAILED. `charter status`
refusals never print "Nothing was written." (status is read-only). Usage errors (flag misuse) remain Click usage
errors, exit 2, not JSON.

## activate / deactivate success (`--json`, positional form)

```json
{
  "schema_version": "1.0.0",
  "command": "activate",
  "kind": "directive",
  "id": "DIRECTIVE_010",
  "changed": ["..."],
  "now_listed": [],
  "no_longer_in_force": [],
  "warnings": [],
  "notices": ["Catalog not recompiled (--no-compile): ..."],
  "referenced_not_cascaded": [],
  "referenced_kind_filtered": [],
  "cascade": {
    "source_urn": "directive:DIRECTIVE_010",
    "scope": "all",
    "cascaded": [{"kind": "tactic", "id": "...", "urn": "tactic:..."}],
    "reinstated": [], "failed": [], "skipped_out_of_scope": [], "skipped_deactivated": [],
    "unreached_behind_deactivated": [], "skipped_kind_filtered": [], "skipped_shared": [],
    "skipped_required": [], "still_active_unrestricted": []
  }
}
```

- `cascade` is `null` without `--cascade`; then `referenced_not_cascaded` lists what the `Warning: referenced ...`
  lines list and `referenced_kind_filtered` what the `Not cascaded: ...` lines list. Both are `[]` with
  `--cascade`, where `cascade.skipped_kind_filtered` carries the kind-filtered references.
- `now_listed`: `--only`'s written list (`[]` otherwise). `no_longer_in_force`: `--only`'s dropped ids, `null` when
  unknown (effective set unresolved; text footer "unknown (see the warning above)"), `[]` without `--only`.
- `warnings` order: mission-type step-removal warnings, registration + manager warnings (deactivate: the named
  profile's mission-step default warning), tension findings (activate), cascaded artifacts' advisory warnings.
- `notices`: the non-empty, whitespace-stripped, unstyled lines the post-change tail printed (catalog refresh:
  `--no-compile` notice, a degraded recompile; pack-skill projection: synced/preserved lines, skill warnings).
- Entry extras: `failed[].message`, `skipped_out_of_scope[].deactivated` (bool, on every entry),
  `skipped_deactivated[].required_by` (`[]` when reached only through `suggests`), `skipped_shared[].referenced_by`,
  `skipped_required[].packs`.

See data-model.md for field semantics.

## status (`--json`) — added `activation` block

```json
"activation": {
  "schema_version": "1.0.0",
  "source": "ledger",
  "path": ".kittify/charter/activation.yaml",
  "exists": true,
  "selected": {"directives": ["..."], "tactics": null},
  "deactivated": {"directives": ["..."]},
  "mission_types": null,
  "activated_kinds": null,
  "required": [{"kind": "directive", "id": "...", "in_force": true, "packs": ["acme"]}]
}
```

- `required` covers every org-requirable kind; a kind that is not charter-activatable (`asset`) is always
  `in_force: true`. `in_force` follows core's current rule (an explicit allow list can keep a required id out).
- `required_error: {code, message}` is added only when the strict org-charter read fails; `required` then holds
  the lenient read.
- On an activation read failure the block is `{"schema_version": "1.0.0", "error": {"code", "message"}}`:
  the typed code (e.g. ACTIVE_CHARTER_CONFIG_INVALID), or ACTIVATION_STATE_UNREADABLE for an OSError. Status
  still succeeds (exit 0).
- `null` in core today: `selected.<plural>` = every artifact of the kind (`skills`: org-required only);
  `mission_types` = none; `activated_kinds` = every kind.

## Contract mapping deferred to #6520

| Local name | ADR-0020 name | Note |
|------------|---------------|------|
| `selected.<plural>` | `selected.<kind>` | local `null` → key omitted (contract has no `null`); camelCase kind keys |
| `deactivated` | `deactivated` | both omit empty deny lists |
| `mission_types` | `missionTypes` | `null` → omitted; absent means none in both |
| `activated_kinds` | `activatedKinds` | `null` → omitted; absent means every kind |
| `required[]`, `in_force` | not stored; D7 read-time floor (`…/artifacts` `state` + `required`) | `in_force` expected always true under D7 |
| `required_error`, `source`, `path`, `exists`, `schema_version` | not in contract | contract carries `revision` (#6521) |
| `skipped_out_of_scope` | `skippedByScope` | |
| `skipped_deactivated[].required_by` | `skippedDeactivated[].requiredBy` + `viaRequires` | local empty `required_by` ≈ `viaRequires: false` |
| `unreached_behind_deactivated` | `unreachedBehindDeactivated` | |
| `skipped_shared[].referenced_by` | `skippedShared[]` (referencing active artifact) | |
| `skipped_required[].packs`, `error.requiring_packs` | `CharterRefusal.requiredBy` `[{packId, via}]` (D10) | local lists pack names only |
| `cascaded`, `reinstated`, `failed`, `skipped_kind_filtered`, `still_active_unrestricted`, `notices`, `now_listed`, `no_longer_in_force`, `referenced_not_cascaded`, `referenced_kind_filtered` | not in contract | |
| local error codes | `CharterRefusalCode` (#6524) | not mapped |

The mapping is semantic (null vs omitted, per-key absent meaning), not a rename.
