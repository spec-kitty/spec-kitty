# Research — agent-string-parser-hardening-01M6699F

Discovery findings for issue spec-kitty/spec-kitty#6755, captured before planning.

## Reproduction on current `main` (512567eee7, verified live 2026-10-30)

```python
>>> from specify_cli.status.models import parse_agent_boundary_string as p
>>> p("claude: :")      # issue row 1 — whitespace segment
('claude', ' ', None, None)      # BUG: model is " ", expected None
>>> p("claude\n")        # issue row 2 — unstripped segment
('claude\n', None, None, None)   # BUG: tool is "claude\n", expected "claude"
>>> p("a:b:c:d:e")       # issue row 3 — more than four segments
('a', 'b', 'c', 'd')             # BUG: "e" dropped silently; expected refusal
```

## Call-site survey (blast radius)

Direct callers of `parse_agent_boundary_string` (all under `src/specify_cli/`):

| Call site | Path | Effect of the hardening |
|---|---|---|
| `build_status_actor` | `status/actor.py:128` | Strips/normalizes the explicit `--agent` value on `mark-status` (via `_ms_status_actor`, `cli/commands/agent/tasks_mark_status.py:206`) and any other builder consumer. A `ValueError` already funnels to the clean `Invalid --agent value: ...` refusal (exit 1) before any write. |
| `actor_from_option` (lenient) | `status/actor.py:162` | Pre-checks `len(actor.split(":")) > 4` BEFORE parsing (line ~156), so >4-segment free text never reaches the parser and keeps being stored whole (#6400 contract). Unaffected. |
| `actor_full_identity` | `status/models.py:321` | Wraps the parser in `try/except ValueError` and falls back to the whole string; a >4-segment recorded value becomes opaque text instead of silently truncated — strictly better for identity comparison. Unaffected in behavior for ≤4-segment values. |
| `_actor_key` | `status/work_package_lifecycle.py:143` | Wraps the parser in `try/except ValueError`, falls back to the projected string whole. Unaffected. |
| `_refuse_unparseable_agent` | `cli/commands/agent/tasks_shared.py:376` | The shared pre-write refusal for explicit `--agent` on `move-task` (`tasks_move_task.py:533`) and `add-history` (`tasks.py:1171`); catches `ValueError` → `Invalid --agent value: <reason>` + exit 1. A parser-level `ValueError` for >4 segments flows through unchanged. |
| re-exports | `status/emit.py:65`, `status/__init__.py` | Name-only; no behavior. |

The frontmatter parser `wp_metadata._resolve_agent_from_colon_string` is a
separate authority (persisted frontmatter) and is deliberately NOT touched
(single canonical authority; C-002 of #2861's thin-parser contract).

## Decisions

1. **Fix inside `parse_agent_boundary_string` only.** All three rows are parser
   defects; every explicit `--agent` path already funnels through it and already
   converts `ValueError` into the clean refusal. No call-site changes are needed
   for the refusal to appear on move-task / mark-status / add-history — raising
   `ValueError` for >4 segments reaches all three through the existing seams
   (verified: `build_status_actor` → `_ms_status_actor` refusal;
   `_refuse_unparseable_agent` on the other two).
2. **Segment semantics.** Strip each segment; a segment that is blank after
   stripping is `None` (model/profile/role) or the existing empty-tool
   `ValueError` (tool). `""` already behaves this way — the fix extends the same
   rule to whitespace.
3. **>4 segments raises `ValueError`** with a message that names the segment
   count, so the refusal text stays in the existing `Invalid --agent value:
   <reason>` envelope. The lenient paths are safe: `actor_from_option`
   pre-checks the count; `actor_full_identity` and `_actor_key` catch
   `ValueError` and fall back to the whole string.
4. **#2861's bare-tool rule untouched.** No synthetic defaults are introduced;
   absent stays `None`.

## Evidence

- Issue #6755 body (three-row table, "Done when" list).
- PR #6774 / mission `status-contract-readers-01M5ZAAC` (#6400): introduced the
  structured actor and the lenient/strict split; changelog line 103 documents
  "A free-text `--actor` with over 4 segments, or starting with `migration:`, is
  stored whole".
- `tests/status/test_actor_boundary_normalize.py` pins the parser contract
  (bare tool, full compact form, partial segments, empty tool raises).
- `tests/specify_cli/cli/commands/agent/test_move_task_structured_actor_6400.py`
  and `test_structured_actor_annotations_6400.py` pin the CLI refusals.

## Open questions

None blocking. The refusal wording for >4 segments follows the existing
envelope; exact message text is an implementation detail reviewed in-loop.
