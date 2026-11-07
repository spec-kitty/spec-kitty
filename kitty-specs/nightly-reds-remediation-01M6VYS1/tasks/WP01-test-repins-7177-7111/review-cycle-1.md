---
affected_files: []
cycle_number: 1
mission_slug: nightly-reds-remediation-01M6VYS1
reproduction_command: spec-kitty agent tasks move-task WP01 --to approved --mission nightly-reds-remediation-01M6VYS1 --agent claude-opus-reviewer
reviewed_at: '2026-11-07T22:45:19Z'
reviewer_agent: claude-opus-reviewer
wp_id: WP01
---

Approved by claude-opus-reviewer: approval:WP01

# WP01 review (reviewer-renata, claude-opus-reviewer): APPROVED

Commit 37b68a50b4.

- #7177 `test_merge_cli_golden.py:98-101`: `--dependency-ref` added to `EXPECTED_PARSER_LONG_FLAGS`, citing #6771 / 9c2881c6 / ADR 2026-09-29-1 Amendment 2026-10-31. The flag is visible and repeatable on `consolidate` only. Strict set equality is kept, so the golden is exactly as strong as before.
- #7111 `test_wp_lifecycle_structured_actor_6400.py:178-219`: the caller-supplied `migration:` path through `start-implementation` is a retired contract (#6754, f22a7b6275). The refusal on all four verbs, plus a byte-identical log, is covered by `tests/specify_cli/orchestrator_api/test_caller_seed_refusal_6754.py`. The rewrite seeds two rows through the store primitive with `build_system_actor`, pins the full 4-key `role: system` dict, and keeps all three seed predicates. The expectation changed correctly from implementer to system.
- Nit (not blocking): the rewritten test no longer exercises the orchestrator-api surface at all. It is now a status/actor pin that sits in an orchestrator_api file and overlaps `tests/unit/migration/test_system_actor_6722.py`. That is acceptable because the orchestrator-api route it used to cover no longer exists.

Evidence (reviewer, foreground): golden + 6400 + both 6754 refusal files + test_system_actor_6722: 57 passed. Exact nodes green. ruff check/format clean.
