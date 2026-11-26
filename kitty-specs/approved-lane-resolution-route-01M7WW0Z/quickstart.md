# Quickstart: the approved-lane conflict route

## Operator walkthrough (the #5604 shape)

Two approved lanes, `lane-a` (WP01) and `lane-b` (WP02), edit adjacent hunks of one file.

1. Run `spec-kitty consolidate --mission alpha`. `lane-a` lands. `lane-b` is refused as stale. The refusal:
   - names `lane-a` and the conflicted path;
   - says the auto-rebase stopped on a conflict;
   - prints the route.
   The run rolls back, and so does the auto-rebase merge on `lane-b`.
2. Follow the printed commands (option (b) shown):
   ```bash
   spec-kitty agent tasks move-task WP02 --to in_progress --mission alpha ...
   spec-kitty agent action implement WP02 --mission alpha --incorporate lane-a   # exits non-zero on a conflict: expected
   # resolve the conflict in the checkout it names, then commit
   spec-kitty agent tasks move-task WP02 --to for_review --mission alpha
   ```
3. An independent reviewer reviews WP02. The review context lists the resolution merge as `git show --remerge-diff <sha>`. The reviewer approves.
4. Run `spec-kitty consolidate --mission alpha` again. It exits 0.

If you skip the review in step 3, consolidate refuses before anything moves with `RESOLUTION_MERGE_UNREVIEWED`, naming the merge and the route.

## Targeted test commands (no full heavy suites)

Run these in addition to `make test-fast`. The exact file list is fixed per work package in the tasks.

```bash
uv run --frozen pytest -q tests/lanes/test_stale_check*.py tests/lanes/test_stale_remediation_cli_command.py tests/lanes/test_auto_rebase*.py
uv run --frozen pytest -q tests/consolidation/test_approved_bound*.py tests/consolidation/test_dependency_merge_attribution_7307.py \
  tests/consolidation/test_rollback_authority.py tests/consolidation/test_single_rollback_authority.py \
  tests/consolidation/test_git_probes*.py tests/consolidation/test_resume_frozen_anchors.py
uv run --frozen pytest -q tests/review/ -k "wp_range or context_block"
uv run --frozen pytest -q tests/orchestrator_api/ -k "envelope or consolidat"
uv run --frozen pytest -q tests/terminus/<new route test>.py
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py tests/architectural/test_layer_rules.py
uv run --frozen ruff check <changed files> && uv run --frozen ruff format --check --force-exclude <changed files> && uv run --frozen mypy <changed files>
```
