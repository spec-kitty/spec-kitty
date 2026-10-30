# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-agent-p15 · Pin both packs to open-packs 72cb7dbc (the #74 merge commit), not to main tip: the tip carries an unrelated breaking sanitized-shape migration, and the diff old-pin..72cb7dbc is exactly the red-main move (6 built-in, 5 internal files).

2026-10-30 · maintainer-agent-p15 · Repoint this repository's own activation ledger in the same PR: the pin bump itself introduces the 'Charter catalog miss for procedure:red-main-release-discipline' warning and a DENY_UNKNOWN_ID finding, so leaving it out would ship a regression the issue's list did not enumerate.

2026-10-30 · maintainer-agent-p15 · Guard test scope: ledger_findings only reports the deny side, so the new module also probes the allow side through IdentityIndex.knows (the primitive the cascade and the doctor share), with a positive control on the same index so a blind probe cannot pass.

2026-10-30 · maintainer-agent-p15 · Deactivate-then-activate, then delete the deny entry by hand: the deactivation writes deactivated_procedures for an id no layer provides, so doctor charter-packs reports DENY_UNKNOWN_ID and its own remedy says to remove the entry. Leaving it would keep a doctor warning alive for a retired id.
