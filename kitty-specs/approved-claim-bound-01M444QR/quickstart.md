# Quickstart: verifying the mission

## Reproduce the defect (before the fix)

The reproducer script is in the body of issue 5668. From an empty directory with a throwaway `HOME`:

```bash
bash repro.sh <repo>/.venv/bin/spec-kitty lanes squash   # exit 1 = defect present
```

Run it for `lanes|coord` x `squash|merge`. After the fix every combination exits 0.

## Targeted tests

```bash
.venv/bin/python -m pytest tests/terminus/test_post_approval_commit_refused.py -q
.venv/bin/python -m pytest tests/consolidation/test_approved_bound.py -q
.venv/bin/python -m pytest tests/consolidation tests/terminus -q -n auto --dist loadfile
.venv/bin/python -m pytest tests/consolidation/test_single_rollback_authority.py tests/status/test_lane_head.py -q
make test-fast
```

## What an operator sees

- A lane with a commit after approval: `LANE_MOVED_AFTER_APPROVAL`, the commit named, no branch moved.
- A mission approved before 4.0.0rc5: `APPROVAL_STAMP_MISSING`; re-review, or attest with `--attest-approved-reviewed`.
