# Existing public pack-validation contract — #5833

Audience: software-engineer. Updated: 2026-10-09.

No new CLI, REST endpoint or output field is introduced. Both `charter org validate <pack>` and `doctrine pack validate <pack>` already consume validate_pack. Only the doctrine command supports `--json`.

Canonical fragment findings preserve the existing ValidationIssue shape: severity `error`, category `drg_dangling_edge`, artifact_type `drg`, file naming authored `drg/fragment.yaml`, artifact_id naming the offending token/URN, and message carrying source/target role plus resolver cause where applicable. Tests compare structured fields and message role/token, not incidental terminal styling. Nonzero exit follows errors.

| Endpoint condition | Finding/message |
|---|---|
| Qualified valid URN absent from standalone universe | Missing role and URN; single-pack scope/remediation |
| Unresolved bare or unknown-prefix token | drg_dangling_edge with unresolved_edge_endpoint |
| Malformed known-kind URN | drg_dangling_edge with malformed_urn |
| Ambiguous built-in bare id | drg_dangling_edge with ambiguous_edge_endpoint and qualification guidance |
| Both sides broken | Two findings in source/target order; no source-failure short circuit |
| Valid explicit declaration / trusted file / built-in binding | No new dangling finding |

Unknown relation label does not suppress existence checks or become a new category. Authored augmentation can additionally retain unknown_target where current intent logic emits it; generated augmentation/governance edges receive no new fragment-attributed findings. Fragment/governance selection load failures preserve existing categories/file attribution and skip the endpoint pass. Artifact schema faults preserve their own finding, exclude file trust and do not skip a successfully loaded fragment.

Findings and order are deterministic: consecutive JSON outputs for the same pack must agree. Existing graph-document findings and order-sensitive snapshots remain unchanged. An intentional sibling identity requires explicit declaration here to pass standalone validation; doctor doctrine verifies configured assembled runtime context but does not substitute for standalone closure.
