# Tooling friction

- **[2026-10-20][specify] Antigravity docs host unreachable.** `antigravity.google` fails DNS from the build container, so the workflows-to-skills guide could not be re-read; the spec records the Antigravity dotted-name behaviour as unverified (#6470). Workaround: rely on the issue's quoted guide and the spec-valid name.
- **[2026-10-20][specify] Container restart mid-planning.** A worker restart dropped one scout's delivered report; recovered from the task transcript. Disposition: workaround, no tracker item.
- **[2026-10-20][plan] Occurrence-map template vs schema.** The documented schema in docs/api/bulk-edit-gate.md shows `schema_version`/`mission` keys that the validator rejects as additional properties. Candidate gap (docs drift).
- **[2026-10-20][implement] Approval leaves status uncommitted.** On single_branch, `move-task --to approved` left status.events.jsonl/status.json and review-cycle-1.md uncommitted, so the next `implement` refused WRITE_CHECKOUT_DIRTY; committed with safe-commit. Candidate gap.
