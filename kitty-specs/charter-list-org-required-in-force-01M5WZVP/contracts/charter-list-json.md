# Contract: `spec-kitty charter list --json` (schema_version "2")

Change class: OP-CONTRACT-003 (key presence is unconditional). Version 1 had no
`schema_version` key.

```json
{
  "result": "success",
  "schema_version": "2",
  "kinds": [
    {"kind": "directive", "activated": ["team-rule"], "allow_list_present": false, "available": null, "deactivated": []},
    {"kind": "tactic", "activated": null, "allow_list_present": false, "available": null, "deactivated": []},
    {"kind": "mission-type", "activated": ["software-dev"], "allow_list_present": true, "available": null, "deactivated": null}
  ],
  "templates": null
}
```

Rules:

1. `allow_list_present` is on every row: `true` when the project has its own allow list for the
   kind (an empty list counts), `false` otherwise.
2. `allow_list_present: true` → `activated` is that list, sorted (unchanged from version 1).
3. `allow_list_present: false` → `activated` is the sorted org-required ids in force, or `null`
   when there are none. For an `"all"` kind every available, non-excluded artifact is also in
   force; `activated` names only the required ones.
4. `required_not_in_force` (FR-023) is unchanged and only concerns rows with
   `allow_list_present: true`.
5. Migration for consumers: test `allow_list_present` instead of `activated is null`.
