# Decision Moment `01M6699SHBBV3FNV7XDV8VS2E6`

- **Mission:** `glossary-residue-three-senses-01M66977`
- **Origin flow:** `specify`
- **Step id:** `specify`
- **Input key:** `intent_summary`
- **Status:** `resolved`
- **Created:** `2026-10-30T11:32:10.923669+00:00`
- **Resolved:** `2026-10-30T11:32:18.254938+00:00`
- **Resolved by:** `pi`
- **Opened by:** `pi`
- **Other answer:** `false`

## Question

Intent Summary (confirmed by operator brief, issue #6759): add a docs/context/ glossary entry for 'residue' naming its three live senses (write-seam is_kitty_specs_residue; audit-engine RESIDUE_DIRECTORY / not is_mission_dir; read-side not is_selectable_mission_dir) with 'do NOT use when' guards, link it from the three owning docstrings, and gate it with a red-first structural test. Primary actor: maintainer/agent reader. Trigger: issue #6759. Desired outcome: one disambiguation entry discoverable from code and the Terminology Canon. Invariant: code stays the source of truth; no behavior change. Boundary: docs + docstrings + generated Contextive YAML + test + changelog only. Confirm this scope?

## Options

_(none)_

## Final answer

Confirmed: scope as stated in the Intent Summary (docs/context entry with three senses + guards, three docstring links, Terminology Canon bullet, regenerated Contextive YAML, red-first structural test, changelog entry; no behavior change)

## Rationale

Operator brief (maintainer-agent task for issue #6759) and the issue body fix the scope; discovery minimized per the non-interactive run, findings recorded in research.md.

## Change log

- `2026-10-30T11:32:10.923669+00:00` — opened
- `2026-10-30T11:32:18.254938+00:00` — resolved (final_answer="Confirmed: scope as stated in the Intent Summary (docs/context entry with three senses + guards, three docstring links, Terminology Canon bullet, regenerated Contextive YAML, red-first structural test, changelog entry; no behavior change)")
