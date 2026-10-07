---
affected_files: []
cycle_number: 1
mission_slug: mission-status-health-drift-ops-01M464D3
reproduction_command:
reviewed_at: '2026-10-07T05:48:51Z'
reviewer_agent: user
wp_id: WP08
---

# WP08 review cycle 1: changes requested (operator rulings, 2026-10-07)

The review found no defect against the spec text. It found two genuinely open points, and the operator ruled both. See the tracer section "Operator rulings at WP08: closure instants and credential-shaped handles". The full review is in the scratchpad file `c12-wp08-review.md`.

1. **F1, a bad closure instant: skip and count.** When the record that would close an Op (its own `completed` line or a spine record) has a `completed_at` that is not RFC 3339, skip the Op and count it in `skippedCount` with a named skip reason. Today a bad spine record is ignored and the Op is served open. Add red-first plants for both sources (own and spine), each with a clean twin, plus a revert experiment.
2. **F2, a credential-shaped handle: never served.** A `profileId`, `action` or `actor` value matching the contract tools' `SECRET_PATTERNS` skips the record as a field defect (`SKIP_FIELD` or equivalent named reason). Do NOT null `actor`: it is required and non-nullable in the contract. Add red-first plants, one per field per credential kind used in the existing credential plants (at least 3 fields × the 4 kinds), each with a clean twin. The check runs on the stored value. A new mutation goes in the catalogue ("credential handle served").
3. Write the matching spec and plan sentences as ONE patch file, `scratchpad/c12-wp08r-kitty-specs.patch`, against the planning branch. The orchestrator applies it. Change only what these two rulings need (FR-019/FR-020 or the Ops skip rules and AC-OPS rows), citing "operator ruling at WP08, 2026-10-07".

No contract change. Keep everything else unchanged and green, including the battery fast leg (ruling 14), the ten tools, the ruff pair and `mypy --strict`.
