# Contract: what an operator-time writer may store into an absent `activated_<kind>` key

Governing ruling: #6629 (merged for the upgrade promotion) and #6683 (its pin). Applies to the two
writers #6685 names: `charter interview` (`_promote_interview_selections`) and the first
`charter activate <kind> <id>` (`plan_activation` via `ActiveCharterManager.activate`).

## Invariants

| ID | Invariant |
| --- | --- |
| C1 | An absent `activated_<kind>` key is never *filled*. Not writing keeps the unrestricted state; writing a list narrows it to that list. |
| C2 | Zero drop: every artifact in force before a writer runs is in force after it, and a resolving, non-deactivated selection stays in force. |
| C3 | `--narrow-activation` / `--only` are the only paths that write an absent key, and they name what stops being in force. |
| C4 | A present list is appended to, never narrowed, and no writer changes a deny list except `charter deactivate` and an explicit activation that clears its own exclusion (D-09). |
| C5 | A kind whose absent key does **not** put the artifact in force still materialises: `mission-type` (nothing in force while absent) and a `required`-when-absent kind such as `skill` (only the org-required set). |
| C6 | An unresolved effective set never produces a bare restrictive list: the interview writes nothing, and an activation keeps today's tolerant materialisation of the readable chain. |
| C7 | No new key, no schema change: writes still go through `resolve_activation_write_target` and `plan_activation` + `commit_plan` / `promote_activations`. |

## Observable contract

- `charter interview` on absent keys: exit 0, no `activated_*` key on the activation surface, one
  message per skipped key naming the key and `--narrow-activation`.
- `charter activate <kind> <id>` on an absent key of an `all` kind, artifact in force: exit 0, no
  allow list written, `Activated: <id>` plus a warning that nothing in force was deactivated,
  nothing was written, and `--only` writes a list.
- `charter synthesize --dry-run --json` after either writer reports `fresh_project_seed_dry_run`,
  and `_catalog_is_established` stays `False`.
- A second identical run changes no byte on `.kittify/config.yaml`, `.kittify/charter/charter.yaml`
  or `.kittify/charter/activation.yaml`.
