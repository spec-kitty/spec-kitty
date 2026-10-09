# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

- 2026-10-06 — Decision: the naming contract is ADR 2026-10-06-1 (owner ruling): charter offering vs active charter; a Charter Pack bundles charter components with activation presets; `charter activate --pack --preset` (--pack defaults to built-in); presets are pack data; spk-doctrine-* → spk-charter-*/spk-practice-*; `doctrine-daphne` kept; full cutover, no aliases/shims; persisted state rewritten once by an upgrade migration. Alternatives (aliases with a removal milestone; keeping `charter pack apply`) were rejected by the owner because earlier compatibility layers left mixed names that confuse agents, contributors and users' harnesses.
- 2026-10-06 — Decision: bulk-edit classification ON (`change_mode: bulk_edit`). The occurrence map deliberately departs from the skill's default posture for cli_commands and serialized_keys (default do_not_change): the owner ruled a full cutover, so those categories rename, and the migration is the consumer-protection mechanism instead of a deprecation cycle.
- 2026-10-06 — Decision: #4400 is under robertDouglass's lease; the preset change empties `load_default_pack_activation_ids()`, which collides with its three callers. Asked on #4400 for (a) Robert lands it first or (b) the mission implements his recorded design; planning assumes (a) until answered.
- 2026-10-06 — RULING (Stijn): #4400's lease is stale; the mission takes it and implements robertDouglass's recorded design (effective-set seed via the #4399 seam) as a requirement, landing no later than the preset change. Claimed on #4400 with credit.
