# Quickstart: verify the change

```bash
uv run --frozen pytest -q tests/policy/test_merge_gates_issue_matrix.py
uv run --frozen pytest -q $(git grep -l "_issue_matrix_approval_blocker\|read_issue_matrix_ref_content" -- 'tests/*.py')
make test-fast
```

Manual check: in a Mission with `merge_gates.mode: block`, add an `in-mission` row for an
issue cited nowhere (`spec-kitty agent issue-verdict --issue '#5678' --verdict in-mission ...`).
`spec-kitty consolidate --dry-run` should then report the terminality gate as failing and
name `#5678`.
