# Contract: `replaceable-builtins.yaml` (consumer and pack)

| Location | Keys honoured | Owner |
|---|---|---|
| `<repo>/.kittify/doctrine/replaceable-builtins.yaml` | `replaceable_builtins`, `revoked_pack_sanctions` | consumer |
| `<org pack root>/replaceable-builtins.yaml` | `replaceable_builtins` only | org-pack author |

- **Entry grammar:** `{urn: <kind>:<id>, reason: <str>}`. `reason` is required and must be non-empty when `<kind>` is `directive`.
- **Pack scope:** a pack entry is effective only for an override whose surviving node has provenance `org:<registry name of that pack>`.
- **Compatibility:** CLIs that predate this contract ignore the pack file and the `revoked_pack_sanctions` key.
- **Transitional:** `<pack root>/templates/setup/replaceable-builtins.yaml` is never a sanction. Doctor reads it only to print remediation hints, and the read goes away with #2594.
