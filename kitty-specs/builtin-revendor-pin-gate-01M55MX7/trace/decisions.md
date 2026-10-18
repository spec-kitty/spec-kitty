# Decisions — builtin-revendor-pin-gate (#3504)

- **2026-10-17 Scope = Shape A (operator ruling).** Run #3504 exactly as ADR
  2026-08-16-2 (amended 2026-10-11) defines it: the committed `packs/built-in/`
  tree STAYS in place and read-only; add a pin lockfile + `charter pack vendor`
  command + per-PR/release drift gate. The operator's original "remove the core
  copies" steer was reconciled against the binding ADR (decisions 1/5/6 reject
  removal, keep internal, defer the authoring flip) by the §1 grounding squad and
  withdrawn in favour of Shape A. The committed tree becomes a *verified build
  cache* (like committed `uv.lock`), which fully delivers single-source-of-truth
  without removal. No new ADR amendment needed — this IMPLEMENTS the 2026-10-11 one.
- **Pin by SHA + digest, not tag, not `requires_core` range** (ADR decision 2;
  open-packs#39). `v0.1.0` is a human handle only.
- **Reuse landed primitives** (c3fc8aa349 / #6046/#6048): `core_compat`,
  `pack_clean_digest`, `regenerate-graph --pack-root`. Do not re-author.
- **Option B, not C.** Filesystem sibling + wheel force-include stay; no runtime
  fetch (that is #3022).
