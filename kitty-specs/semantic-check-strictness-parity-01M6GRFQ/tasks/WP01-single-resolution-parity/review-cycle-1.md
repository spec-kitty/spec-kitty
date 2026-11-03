---
affected_files: []
cycle_number: 1
mission_slug: semantic-check-strictness-parity-01M6GRFQ
reproduction_command: spec-kitty agent tasks move-task WP01 --to approved --mission semantic-check-strictness-parity-01M6GRFQ --agent reviewer-renata
reviewed_at: '2026-11-03T13:35:58Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

Approved by reviewer-renata: approval:WP01

## Review round 1 — WP01 (#7065)

Reviewed the integrated diff of `src/glossary/{strictness,events,middleware,pipeline}.py`
plus the new parity tests, against the mission spec and the issue's acceptance
criteria ("the persisted event's `effective_strictness` and `blocked` match the values
the generation gate applies").

### Verdict

Approve. The defect is fixed at its source: there is now exactly one strictness
resolution path (`resolve_context_strictness`), the emitter no longer substitutes a
policy value, and `blocked` is derived from the gate's own `should_block` predicate.

### Findings raised and resolved in this round

1. **`blocked` was scoped ambiguously in the docstring** — it reflects the conflicts
   passed to *this* check, while the gate evaluates the context's aggregate list. The
   docstring now says "the conflicts passed to this check", and the mission spec records
   the same limitation. No code change: the difference only arises when a context carries
   conflicts from an earlier layer, which the standard pipeline does not produce.
2. **The emitter's `runtime_override` parameter had no direct test** — added
   `test_a_direct_caller_can_pass_the_runtime_override`, so the seam the issue asked for
   ("pass the resolved strictness into the emitter") is exercised without the middleware.
   Fixed in `9e5747792e`.
3. **`or`-chained enum resolution** — checked: `Strictness` values are non-empty strings,
   so `coerce_strictness(...) or ...` cannot skip a real value; an unrecognised value
   returns `None` and falls through to the policy chain, which is the documented
   NFR-002 behaviour. Left as is, with a test for the malformed-value case.

### Checks run by the reviewer

- `uv run pytest tests/agent/glossary -q` → 583 passed, 9 skipped (the skips are
  pre-existing).
- `uv run pytest tests/agent/glossary/test_strictness_parity.py -q` → 14 passed; the same
  module fails on the pre-fix tree with `'medium' == 'off'` and `blocked True is False`.
- `uv run pytest tests/charter_offering/missions/test_glossary_hook.py -q` → green.
- `uv run pytest tests/specify_cli/cli/commands/test_cli_boundary_glossary.py
  tests/specify_cli/cli/commands/test_glossary_show.py
  tests/specify_cli/cli/commands/test_glossary_validate.py -q` → 40 passed.
- `uv run ruff check src/glossary tests/agent/glossary` and `ruff format --check` → clean.
- `uv run mypy src/glossary/{strictness,events,middleware,pipeline}.py` → clean.
- Confirmed the removed test (`test_unresolved_strictness_is_written_as_medium`) asserted
  the defect itself; its replacement pins resolution from config, not a constant.
