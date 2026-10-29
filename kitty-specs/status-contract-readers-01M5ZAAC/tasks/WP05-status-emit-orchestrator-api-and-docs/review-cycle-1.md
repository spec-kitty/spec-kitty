---
affected_files: []
cycle_number: 1
mission_slug: status-contract-readers-01M5ZAAC
reproduction_command:
reviewed_at: '2026-10-27T20:46:47Z'
reviewer_agent: claude-reviewer
wp_id: WP05
---

# WP05 review feedback (cycle 1) - reviewer-renata

## Blocking: unrequested behaviour change - an empty-tool `--actor` is now refused

Verified on both surfaces by driving the real Typer apps on the mission base (`kitty/mission-status-contract-readers-01M5ZAAC`) and on this lane's HEAD:

| Surface | Base | HEAD |
|---|---|---|
| `orchestrator-api start-implementation --actor ":x"` | exit 0, `success: true`, events stored with actor `":x"` | exit 1, `USAGE_ERROR` "Invalid --actor ':x': Empty agent tool ...", no event |
| `agent status emit WP01 --to claimed --actor ":x"` | exit 0, event stored with actor `":x"`, output `"actor": ":x"` | exit 1, `{"error": "Empty agent tool in --agent value: ':x'"}` |

The WP prompt's line "A value that `parse_agent_boundary_string` rejects (empty tool) is already invalid today" is wrong for `agent status emit`: the base passes `--actor` through verbatim and never parses it. The mission brief forbids unlisted behaviour changes, so both surfaces must keep accepting such values.

Required fix:
1. `src/specify_cli/orchestrator_api/wp_lifecycle.py:71-85` (`_status_actor`): when the compact parse fails (`ValueError` from `build_status_actor`), do NOT `_fail(... USAGE_ERROR ...)`. Store the raw `--actor` value as `tool`, with `profile`/`model` null and the hop's `role`, i.e. `{"tool": actor, "role": role, "profile": None, "model": None}`. Update the docstring (drop "fails with USAGE_ERROR").
2. `src/specify_cli/cli/commands/agent/status.py:309-323` (`_emit_actor`): the same fallback. Today the `ValueError` escapes and the command exits 1.
3. Keep this fallback in one place if you can. For example, a small helper in the WP05-owned code that both call. Do not change `build_status_actor` / `parse_agent_boundary_string` (WP02/WP03 territory, and other writers rely on the raise).
4. Tests (add them to the two `*_6400.py` files):
   - orchestrator: `start-implementation --actor ":x"` succeeds (exit 0, `success: true`). The envelope matches the one for a normal actor with the same keys and values: echoed values stay `":x"`, `contract_version` is unchanged. The stored actors are `{"tool": ":x", "role": "implementer", "profile": None, "model": None}`.
   - status emit: `--to claimed --actor ":x"` exits 0, output `"actor": ":x"`, and the stored actor is the structured dict with `tool` `":x"`.
   Both must be red on the current HEAD.

## Verified OK (no action needed)
- Red-first: at `0933360a` (tests only), all 8 new tests fail. At HEAD they pass.
- Envelopes: `requesting_actor` echoes `--actor` verbatim. That is byte-identical to base, because base `actor_identity_str(str)` returned the string verbatim. The emit JSON `actor` output is unchanged. The history line stays a string.
- Role: `transition` calls `role_for_hop` through `_transition_role` (reads the current lane). `start-implementation` is implementer, `start-review` is reviewer, `append-history` is implementer, and `status emit` uses `role_for_hop`. This matches the data-model table.
- `status/emit.py`: the `emit_inner_state_changed(actor: ActorField)` widening is type-only (the body only forwards `actor`).
- The out-of-map test edits only change expected values. Exception: `_emit_via_legacy_direct_path` in `tests/status/test_agent_status_emit_aggregate_wiring.py` changes the *input* actor so the parity test still compares like with like. That is acceptable; mention it in the commit/PR.
- Docs describe the 4-key shape, the profile order without the frontmatter fill, and `profile_source` as planned. The changelog #4941 citation now reads "spec-kitty-events PR #102, fixing issue #101". The new entry passes the style gates.
- ruff, `ruff format --check --force-exclude`, C901: clean. mypy on the touched src plus `status/actor.py` and the two new test files: clean.

## Minor (non-blocking, optional)
- Mixed-version logs: a WP last claimed on base with a compact string actor (`"claude:opus:p"`) keeps that string as the snapshot `current_actor`. The review-claim predicate (`review_claim_predicate.py`, `current_actor == requesting_actor`) now compares it against a requester projected to `"claude"`. This is a narrow edge that WP03 shares. Consider noting it in the PR rather than fixing it here.
