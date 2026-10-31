# Quickstart: see the dry run report the work the real run does (#6552)

## What changed

A `spec-kitty upgrade --dry-run` no longer reports a migration as
`not needed (project already in target state)` when an earlier migration in the same run
would have made it needed. A migration that declares the predecessors its `detect()` reads
(`BaseMigration.sequenced_after`) is reported as applied, with the line
`dry-run: would apply after <migration id>`, so `Migrations applied:` matches what the real
run then does. An unpredicted dry-run skip now says `not needed on the current tree`, which
is the only claim a preview can support.

## Reproduce the original defect (on a build before the fix)

```bash
mkdir -p /tmp/sk6552/home /tmp/sk6552/proj && cd /tmp/sk6552/proj
git init -q -b main
HOME=/tmp/sk6552/home CI=1 spec-kitty init --ai claude --non-interactive
git add -A && git -c user.name=t -c user.email=t@e.invalid commit -qm fresh
# Drop the repoint's clone-local record: the state of a project upgraded from a build
# that predates that migration.
python3 - <<'PY'
import json, pathlib
p = pathlib.Path(".kittify/migrations/clone-local.jsonl")
keep = [l for l in p.read_text().splitlines() if l.strip() and json.loads(l)["id"] != "3.2.6_issue_matrix_driver_repoint"]
p.write_text("\n".join(keep) + "\n")
PY
cp -a . ../dry && cp -a . ../real
(cd ../dry  && HOME=/tmp/sk6552/home CI=1 spec-kitty upgrade --project --dry-run --no-worktrees)
(cd ../real && HOME=/tmp/sk6552/home CI=1 spec-kitty upgrade --project --yes     --no-worktrees)
```

Before the fix the dry run prints `○ 3.2.6_issue_matrix_driver_repoint` and
`! Migration 3.2.6_issue_matrix_driver_repoint not needed (project already in target state)`
while the real run prints `✓ 3.2.6_issue_matrix_driver_repoint`, and the two
`Migrations applied:` lists differ by that entry. After the fix both list it as applied.

## Run the tests

```bash
uv run pytest tests/upgrade/test_dry_run_sequenced_verdict.py -q
uv run pytest tests/compat/test_dry_run_parity.py tests/upgrade/test_runner_status_classification.py -q
```

## Declare the relationship in a new migration

```python
class MyMigration(BaseMigration):
    migration_id = "3.2.6_my_followup"
    # The migrations whose writes this migration's detect() reads. Detect-input
    # metadata only: order_manifest.txt still owns execution order.
    sequenced_after = ("3.2.6_gate_artifact_merge_drivers",)
```

Declare it only when `detect()` genuinely reads state the predecessor writes. Without a
declaration the preview still cannot predict the verdict — it just no longer claims the
project is already in its target state.
