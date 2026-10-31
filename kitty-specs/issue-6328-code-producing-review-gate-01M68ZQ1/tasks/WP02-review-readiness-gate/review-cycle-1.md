---
affected_files: []
cycle_number: 1
mission_slug: issue-6328-code-producing-review-gate-01M68ZQ1
reproduction_command:
reviewed_at: '2026-10-31T16:02:01Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

# WP02 review — cycle 1

## Finding R1 (blocking, readability in the crux test)

`tests/specify_cli/cli/commands/agent/test_ready_for_review_code_producing_gate.py`,
`_run_custom_type_preflight(..., with_commit: bool)`.

The parameter is inverted relative to its name at the call sites:

```python
    review_base_ref = base_sha if with_commit else head_sha
```

`with_commit=True` means "the lane HAS a commit beyond the gate's base" and
`with_commit=False` means "it does not" — but every fixture already contains a
real implementation commit; the only thing that varies is the ref. A reader
skimming `_run_custom_type_preflight(declared=True, with_commit=False)` will read
"no commit" and then find a commit in `_make_repo`, which is exactly the kind of
ambiguity that lets a vacuous test look meaningful later.

Required change: rename the parameter to `commit_beyond_base` (and invert the
docstring/comment to match), so the call sites read
`commit_beyond_base=True/False` and the two pre-flight cases are unambiguous.
Keep the fixture itself unchanged — the "same fixture, one differing ref" property
is the point and must not be traded away.

## Non-blocking notes (no change requested)

- The positive control does reach `_check_implementation_commit_present` rather
  than short-circuiting: the worktree exists, the health check passes on the real
  repo, `HEAD..base_sha` is 0 commits (currency pass), the tree is clean, and the
  refusal case asserts that check's own wording — so the same call path is proved
  to be the one that produces the verdict. Good.
- `_is_code_producing` correctly mirrors
  `mission_check_prerequisites._requires_substantive_spec`: api-seam import,
  `bool`-annotated local, no `# type: ignore`, no second fallback. Correct.
- `main_repo_root` (not `repo_root`) is passed — correct, the charter config lives
  on the primary partition.
- The `#6715`/`#5939` empty-diff proof was run and is empty. Correct.

## Verdict

REJECT — one blocking readability finding (R1). No behavioural change requested.
