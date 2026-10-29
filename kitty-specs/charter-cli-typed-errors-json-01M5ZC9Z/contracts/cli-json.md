# Contract: charter status / activate / deactivate JSON (local, schema 1.0.0)

Local CLI contract. Not the spec-kitty-charter activation contract (ADR-0020); the mapping onto it is held
by #6518 (#6520 fields, #6521 revision, #6524 refusal codes).

## Error envelope (all three commands)

```json
{"ok": false, "error": {"code": "ACTIVE_CHARTER_CONFIG_INVALID", "message": "..."}}
```

Exit codes are those of the same invocation without `--json`.

| Code | Command(s) | Cause | Exit |
|------|------------|-------|------|
| ACTIVE_CHARTER_CONFIG_INVALID | all | charter.yaml / pack config unsound | 1 |
| CHARTER_CONFIG_SHAPE_INVALID | status | evidence reader's config shape error, reachable only after the soundness gate passes (a non-mapping `.kittify/config.yaml` is refused earlier as ACTIVE_CHARTER_CONFIG_INVALID) | 1 |
| RESYNTHESIS_FAILED | activate, deactivate (`--json`) | change written, post-write catalog refresh/resynthesis failed; `error` carries the change report | 1 |
| CHARTER_STATUS_FAILED | status | repository/task resolution failure | 1 |
| INTERNAL_ERROR | status | unexpected exception | 1 |
| ACTIVATION_KIND_UNKNOWN | activate, deactivate | KIND not an activation kind | 1 |
| CASCADE_SCOPE_INVALID | activate, deactivate | bad `--cascade` value | 1 |
| CHARTER_WRITE_ROOT_INVALID | activate, deactivate | linked worktree / write root | 1 |
| DEACTIVATION_REFUSED_REQUIRED | deactivate | org-required id; `error.requiring_packs` lists the packs | 1 |
| ACTIVATION_FAILED | activate, deactivate | activation engine / DRG load error | 1 |

Usage errors (flag misuse) remain Click usage errors, exit 2, not JSON.

## activate / deactivate success (`--json`, positional form)

```json
{
  "schema_version": "1.0.0",
  "command": "activate",
  "kind": "directive",
  "id": "DIRECTIVE_010",
  "changed": ["..."],
  "no_longer_in_force": [],
  "warnings": [],
  "referenced_not_cascaded": [],
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

`cascade` is `null` without `--cascade`; then `referenced_not_cascaded` lists what the text warning lists (empty with `--cascade`). See data-model.md for field semantics.

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
