# Agent Boundary Parser Contract Facts

Audience: software-engineer. Updated: 2026-10-30.

This Mission changes the compact `--agent` parser's segment handling only, not any stored schema or CLI surface. Authority: `src/specify_cli/status/models.py` and [spec.md](spec.md).

## Facts

- The compact agent string is `tool:model:profile:role`, at most four `:`-separated segments; the bare `tool` form is valid.
- `parse_agent_boundary_string` is a THIN, non-synthesizing boundary parser (#2861): an absent segment stays `None`, never a tool-derived synthetic default. The persisted-frontmatter parser (`wp_metadata._resolve_agent_from_colon_string`) is a separate authority and is untouched.
- Explicit `--agent` paths (`move-task`, `mark-status`, `add-history`) parse through `build_status_actor` / `_refuse_unparseable_agent` and convert any parser `ValueError` into the clean refusal `Invalid --agent value: <reason>` with exit 1, before any write.
- The lenient builder `actor_from_option` (free-text `--actor` on `agent status emit` / `orchestrator-api`, and recorded identities) stores a value with more than four segments, a `migration:` prefix, or an unparseable tool whole as `tool` (#6400).
- Identity projections (`actor_full_identity`, `_actor_key`) catch a parser `ValueError` and fall back to the whole recorded string.

## Invariants (this mission's delta)

1. Every segment is stripped before use.
2. A segment that is blank after stripping is `None` (model/profile/role) or raises the existing empty-tool `ValueError` (tool).
3. A value with more than four segments raises `ValueError` naming the count; the explicit `--agent` paths refuse it before any write; the lenient paths never see it (pre-check) or store it whole (fallback).
4. The refusal envelope stays exactly `Invalid --agent value: <reason>`; no new error surface.
5. No event envelope field, snapshot schema or CLI flag changes.
