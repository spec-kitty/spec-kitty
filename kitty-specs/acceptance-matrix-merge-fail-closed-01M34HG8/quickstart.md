# Quickstart: reproduce + verify (#4880)

## Reproduce the corruption (pre-fix, MUST fail closed after the fix)

Set up a repo with `.gitattributes` mapping `kitty-specs/**/acceptance-matrix.json`
to `merge=spec-kitty-acceptance-matrix`, then:

- **base**: `C1.pass_fail = "pending"`
- **branch A**: `C1.pass_fail = "fail"`
- **main (ours)**: `C1.pass_fail = "pass"`

```bash
git merge --no-edit A
```

**Pre-fix (bug):** exit 0, commits; the value becomes
`"<<<<<<< ours\n\"pass\"\n=======\n\"fail\"\n>>>>>>> theirs"` and
`AcceptanceMatrix.from_dict(...).overall_verdict == "fail"`.

**Post-fix (expected):** the driver exits non-zero, git leaves the conflict, the
merge aborts, nothing is committed.

## Verify (unit level)

```bash
# IC-2 red-first: pre-fix product file → the repro fails; post-fix → passes
PWHEADLESS=1 .venv/bin/python -m pytest \
  tests/specify_cli/cli/commands/test_row_aware_merge_driver.py \
  tests/merge/test_gate_artifact_merge_drivers_2804.py -q

# IC-3 read guard
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/acceptance -q
```

Run file-scoped (per the repo's narrow-run discipline), not a broad sweep.
