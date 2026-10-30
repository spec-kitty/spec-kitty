# Approach Evolution

> Track how your approach changed as the mission progressed.

## Entries

- **[2026-10-30][planning] Typed error at the shared seam, not per-verb CLI mapping.** Started
  from the issue's suggestion (raise a typed error for the unreadable registry). Grounding
  showed the deactivate side already converges through `ActiveCharterConfigError` raised by
  the strict required-floor read, while activate reads the same registry through
  `require_declared_org_roots` as a plain `ValueError`. The chosen approach types that one
  seam (research.md D1) so the CLI needs no change; the rejected alternative (mapping codes
  in the CLI by message text) is the fragility the issue names.
- **[2026-10-30][planning] Keep the `ValueError` base on the typed error.** A plain
  `ActiveCharterConfigError` (no `ValueError` base) would silently change three strict
  readers of the org-pack chain (effective set, preset application, requirement-kinds
  loader) whose `except ValueError` arms would stop firing. The dual base preserves their
  documented contracts (FR-004) and is pinned by a seam test.
