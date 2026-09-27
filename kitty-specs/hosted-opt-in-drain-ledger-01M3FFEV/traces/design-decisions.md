# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

## 2026-09-26 — architecture checkpoint (operator)
- D-1 drain = repo `.kittify/config.yaml hosted.drain` AND personal global activation; either off ⇒ off. Alternative (repo-only, per issue text) rejected: one committed `true` would opt in every clone.
- D-2 ledger flag = auto-refresh of the gitignored derived projection (option c). (b) rejected: the coord transaction commits events+status.json atomically; gating the commit breaks lane state and #4311.
- D-3 no endpoint ⇒ guidance error on explicit commands, silence on automatic paths.
- D-4 keep `[sync].server_url` (rename is a follow-up).
- D-5 (operator): personal drain activation in runtime-root config.toml `[hosted] drain`, co-located with `[sync].server_url`.
- Post-spec squad (HOLD→folded): R-1 no env var can enable drain; R-2 saas-auth.json/.kitty.env are explicit endpoint config; R-3 drain gates all relay traffic incl. operator-typed sends; R-4 already-migrated team.spec-kitty.ai values stay explicit.
