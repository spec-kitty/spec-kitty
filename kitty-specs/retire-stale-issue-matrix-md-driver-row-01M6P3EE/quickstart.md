# Quickstart: verify the retired merge-driver row

## Reproduce the defect (pre-fix tree)

```bash
git clone https://github.com/spec-kitty/spec-kitty /tmp/repro && cd /tmp/repro
make sync-packs && uv sync --frozen --all-extras
spec-kitty upgrade --yes
git status --porcelain          # M .gitattributes
git diff -- .gitattributes      # +kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix
```

## Verify the fix

```bash
cd /tmp/repro
git checkout -- .gitattributes                   # start from the committed file
sha_before=$(git hash-object .gitattributes)
spec-kitty upgrade --yes
[ "$sha_before" = "$(git hash-object .gitattributes)" ] && echo "untouched"
git status --porcelain                            # empty

# the live drivers are still installed
git config --local merge.spec-kitty-acceptance-matrix.driver
git config --local merge.spec-kitty-issue-matrix.name

# healing: a project that already carries the retired row
echo 'kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix' >> .gitattributes
git commit -qam "a project that upgraded under 3.2.6"
spec-kitty upgrade --yes
grep -c 'issue-matrix.md merge=' .gitattributes   # 0
```

## Targeted tests

```bash
uv run pytest tests/upgrade/test_issue_matrix_md_row_retirement_7217.py \
               tests/init/test_init_then_upgrade_is_noop.py \
               tests/upgrade/test_dry_run_sequenced_verdict.py \
               tests/upgrade/test_dry_run_sequenced_verdict_cli.py -q
uv run pytest tests/specify_cli/upgrade/test_gitignore_backfills_superseded_6589.py \
               tests/architectural/test_migration_order_manifest.py \
               tests/architectural/test_merge_reconciliation_class_guard.py -q
```
