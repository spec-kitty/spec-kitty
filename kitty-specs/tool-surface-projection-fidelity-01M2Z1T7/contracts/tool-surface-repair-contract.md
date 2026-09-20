# Contract — tool-surface repair honesty

<!-- round-trip: skip: illustrative CLI-behavior contract, not mission frontmatter -->

## `doctor tool-surfaces --tool gemini --fix` (Seam A)
- GIVEN a stale `GEMINI.md` and NO `.gemini/` → the block is refreshed; surface reported `repaired`. (was: exit 0, unchanged)
- GIVEN a stale `LLXPRT.md` and NO `.llxprt/` → refreshed (latent twin).
- GIVEN a selected, stale, truly-unwritable surface → reported `failed` (named), non-zero. Never silent `not_applicable`.
- GIVEN an unselected harness → `not_applicable` (legitimate).

## `upgrade` (Seam B, Windows-mode condition)
- GIVEN the freshly-created `.agents/skills` observes mode ≠ 0o755 (Windows) → `upgrade` converges in ONE run (all command + doctrine skills applied), exit 0; no `Completed command output changed` raise.
- Second `upgrade` → zero changes (idempotent).
- `upgrade --dry-run` after convergence → zero repairs (no phantom `chmod`).

## Invariants
- OUT-1 (parity): detect-applicable == repair-applicable for every supported selected surface.
- OUT-2 (host-aware, POSIX-safe): mode compared only where the host can represent it; POSIX correctness unchanged off-Windows.
- OUT-3 (honest failure): residual drift → non-zero/`failed`, never exit-0 silent.
- OUT-4 (single-pass): one invocation converges; a second is a clean no-op.
