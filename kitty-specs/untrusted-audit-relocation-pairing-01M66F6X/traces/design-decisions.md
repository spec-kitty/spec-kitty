# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-agent-i · Spec+plan review round 1 (reviewer-renata squad): 3 major findings accepted and folded into spec.md/plan.md — (1) source comparand is the exact canonical machine string; prose/empty source cells never pair and emit a distinct non-pairing note; (2) path-level tripwires (KNOWN_CANDIDATE_FILES, FR-009) are a documented scope boundary — last-sink-out-of-a-known-candidate moves stay red; (3) truncated tokens never auto-pair (removal+new-sink prefix collision is indistinguishable from a move). Minors accepted: extended test matrix and a machine check for the rationale trim.

2026-10-30 · maintainer-agent-i · Tasks review round (reviewer-renata squad): 1 blocker + 2 majors accepted — (1) exact-equality source pairing would never fire for 6 live rows whose source cells are hand-tuned (resolved.mission_slug vs discovered mission_slug): added T009 source-cell canonicality check + one-time re-pin of the six cells (hand annotations move to rationale); (2) pair_relocations must dedupe to composite KEYS and exclude [inventory-only] rows before grouping (key-set semantics spelled out in the WP prompt); (3) the hand-kept Disposition summary counts are stale (41/36/5 vs live 45/39/6) — T006 now reconciles them and strips stale per-row locator citations. Minors accepted: NFR-002 runtime measurement added to T008; T005 monkeypatch harness specified (audit module's INVENTORY_PATH + discover_rows); chain guard extended to signed-shift prose (shifted −11); changelog subsection named (### Fixed under [Unreleased] - 4.0.0rc8).
