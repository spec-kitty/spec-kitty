# Data model: Charter governance resolution

## IdentityIndex (new, per invocation)

| Field | Type | Notes |
|---|---|---|
| roots | canonical layer chain | project (if dir) → org packs (reverse declaration order) → built-in |
| entries[kind] | ordered `IdentityEntry(kind, stem, declared_id, layer)` | built lazily, one scan per kind |
| by_stem / by_id | first-match maps | same precedence as `kind_vocabulary._scan_roots` |

Invariants: stem match wins over declared-id match; unknown activation tokens fall back to today's normalisation with a warning; unknown selections are reported, never raised.

## Activation keys (unchanged storage)

`activated_<plural>` in `.kittify/config.yaml` (or `charter.yaml` when the config points there). Absent = every effective artifact (ADR 2026-10-06-2). Present = allowlist. New writers: `--only` (selection + org-required stems), `--narrow-activation`, and `charter synthesize` (appends synthesized tactic slugs to a present `activated_tactics`).

## Project DRG overlay edge (changed)

Before: `tactic:how-we-apply-X --applies--> directive:X`.
After: `directive:X --suggests--> tactic:how-we-apply-X` (X = declared id). Owner for reconcile: the tactic.

## JSON payloads (additive)

- `charter context --json`: new top-level `diagnostics: list[str]`; `schema_version` 1.3.0 → 1.4.0.
- `charter interview --json`: new `narrowed: {activation_key: [dropped ids]}` (`{}` when not narrowing).

## CLI flags (new)

- `charter activate <kind> <id> --only` (refused with `--preset`, exit 2).
- `charter interview --narrow-activation`.
