# Approach: residue-safe-migration-sweep-01M5SS0F

- **[2026-10-25][specify] Red-first P0 first.** The `p0_repro(issue=6669)` landed in its own `pr:p0-repro` PR (#6672) before any fix, as the operator ruled for #6627.
- **[2026-10-25][specify] Scope grew after the adversarial review.** A narrow fix (the rule plus superseding 2.0.6) still left 3.1.1 and 0.9.0 writing into residue. The operator extended the supersession to 0.9.0, 0.9.1 and 3.1.1.
- **[2026-10-25][plan] Successor shape per predecessor.** Class-based migrations (0.9.x) are subclassed with per-folder overrides; module-function migrations (2.0.6, 3.1.1) are re-walked over the frozen helpers.
