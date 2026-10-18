# Surprises — builtin-revendor-pin-gate (#3504)

- **The operator directive contradicted the binding ADR.** "Remove the committed
  copies" is exactly what ADR 2026-08-16-2 amended decision 1 rejects (breaks
  offline dev + nightly exact-SHA gate). Surfaced as a STOP; operator chose Shape A.
- **open-packs#31 blocker was already materially cleared** by the re-seed +
  `v0.1.0` tag done earlier this session — so #3504 is now buildable despite its
  stale `status:blocked` label.
- **c3fc8aa349 already landed the plumbing** (pack_level, requires_core,
  core_compat, pack_clean_digest, regenerate-graph --pack-root). The mission wires
  these into a pipeline; it does not author the digest/compat logic.
- **No `built-in.source.yaml`/lockfile/vendor command/drift gate exists in core
  today** — this is net-new construction, not modification of an existing seam.
