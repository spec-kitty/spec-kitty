# Data Model: Skill surface and upgrade integrity

## Surface effect (existing)
Fields: `destination`, `owner`, `phase`, `action`, `before`, `after`, `logical_owners`, `surface_ids`, `ownership`.
**New merge invariant**: two effects at one destination merge iff `action == create`, `before` is absent, and `phase` and `after` (kind, mode) are equal; the result unions `logical_owners`, `surface_ids`, `ownership` and keeps a deterministic primary `owner` (lowest sort key). Any other difference raises a conflict naming destination, both owners and the differing field(s).

## Pack skill finding (existing, extended)
Kinds: `drift`, `stale`, `orphaned`, `unresolvable`, **`missing`** (new).
`missing` is emitted per (agent, skill) when the skill is in force, the agent accepts skill files, and either no pack manifest entry exists or the entry's installed file is absent.

## Tool surface finding (new)
`no_tool_folder`: emitted once when none of the configured agents' root folders exists. Lists the configured agents.

## Upgrade metadata snapshot (new, transient)
`{version, last_upgraded_at, schema_version}` captured before the runner; restored on any failure of the runner or `finalize_upgrade`; discarded on success.
