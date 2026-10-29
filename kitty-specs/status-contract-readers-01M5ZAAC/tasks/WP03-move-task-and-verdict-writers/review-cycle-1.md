---
affected_files: []
cycle_number: 1
mission_slug: status-contract-readers-01M5ZAAC
reproduction_command:
reviewed_at: '2026-10-27T21:38:49Z'
reviewer_agent: claude-reviewer
wp_id: WP03
---

# WP03 review feedback (cycle 1) -- reviewer-renata

## Blocking

**[MAJOR] Architectural gate red: direct `specify_cli.status.actor` submodule imports.**
`tests/architectural/test_status_module_boundary.py::test_ast_scan_no_direct_status_imports_repo_wide` fails on this branch with exactly two violations, both introduced by WP03:

- `src/specify_cli/cli/commands/agent/tasks_move_task_hops.py:38` -- `from specify_cli.status.actor import build_status_actor, compose_status_actor, role_for_hop`
- `src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py:103` -- `from specify_cli.status.actor import ActorRole`

The gate requires `from specify_cli.status import X`. `specify_cli.status.__init__` does not re-export `ActorRole`, `build_status_actor`, `compose_status_actor` or `role_for_hop` today. Fix: re-export them from `specify_cli/status/__init__.py` (add to `__all__`) and import them from the package in both files. Do not add the files to `_WP10_DEFERRED_FILES`. Re-run the gate file.

## Verified OK (no change needed)

- Red -> green: test commit 39143b90 is 8/8 red on its own; HEAD 8/8 green.
- `agent=st.agent or hop_actor`: `_mt_hop_actor` returns `st.agent` whenever it is set, so the parsed identity is the one the hop chose; the compact string never lands in `tool` on a parseable identity (#2861). An unparseable identity (empty tool segment) is caught and kept whole as `tool`, so no new refusal (base raised ValueError on a binding hop for such an `--agent`; base wrote the raw string on non-binding hops).
- `_implementer_of_record_label`: a legacy string actor goes through `actor_identity_str`, byte-identical to base `latest_implementer_actor`.
- `ReviewOverride.actor` stays the string; event actor via `event_actor=`.
- Complexity <= 15 (ruff C901), ruff check/format clean, no new mypy errors on changed lines.

## Non-blocking (note, no rework required)

- [MINOR] `work_package_lifecycle.py:281-282`: for an EXISTING log whose implementer event already carries a dict actor (written by the base's binding hops), the refusal message now names `tool:model:profile` instead of the bare tool. Message-only; mention it in the PR.
