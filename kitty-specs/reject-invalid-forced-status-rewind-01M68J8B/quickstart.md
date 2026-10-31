# Quickstart: verify the forced-rewind refusal (#6514)

Run from the repository root of this mission's clone.

## 1. The failing behaviour (before the fix)

```bash
# fixture: a mission whose WP01 sits in for_review
uv run pytest -q tests/status/test_forced_rewind_requires_review_ref.py -k invalid_forced_rewind
```

Expected before the fix: **red**. `agent status emit` exits 0, the log grows by one row,
and `agent status validate` then exits 1 with `for_review->in_progress without review_ref`.

## 2. The behaviour after the fix

```bash
uv run pytest -q tests/status/test_forced_rewind_requires_review_ref.py
```

Expected: **green**, covering

- the pointerless forced rewind exits non-zero and appends nothing (SHA-256 of
  `status.events.jsonl` and `status.json` unchanged);
- the same fixture then validates clean;
- the same rewind with `--review-ref` appends and validates clean (positive control);
- the same refusal through `orchestrator-api wp transition`.

## 3. The neighbouring contracts still hold

```bash
uv run pytest -q \
  tests/status/test_validate.py \
  tests/status/test_wp_state_force_free_contract.py \
  tests/status/test_agent_status_emit_cli.py \
  tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py
```

Expected: green, and specifically `move-task`'s forced `for_review → in_progress` rewind
(which supplies `review_ref="force-override"`) still records the rewind.

## 4. By hand, through the CLI

```bash
# 1. put WP01 in for_review (any mission with a live WP)
spec-kitty agent status emit WP01 --to in_progress --actor codex --force \
  --reason "source boundary changed"; echo "exit=$?"
#    -> non-zero, and the message names review_ref + --review-ref

# 2. the ledger is untouched and still valid
spec-kitty agent status validate --mission <slug>       # exit 0

# 3. the legal override still works
spec-kitty agent status emit WP01 --to in_progress --actor codex --force \
  --reason "source boundary changed" --review-ref "review-cycle://WP01/1"; echo "exit=$?"
#    -> 0, and `status validate` still exits 0
```

## 5. The documentation surface

```bash
rg -n "review_ref" docs/architecture/status-model.md | head
uv run python -m scripts.docs.check_docs_freshness --ci   # expect errors=0
```
