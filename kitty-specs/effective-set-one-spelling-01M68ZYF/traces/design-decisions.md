# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · Required-only floor: kept org_required_stems (the validated policy set + IdentityIndex.stored_spelling) as the one source, rather than PackContext.allow_for mapped separately, so the collision refusal and the floor come from one call with no extra scan. Verified against the extends: chain that both readers agree for every valid config (probe + a pinned chain test); the only divergence is a pack whose document fails schema validation, which the policy merge skips and doctor charter-packs reports.
