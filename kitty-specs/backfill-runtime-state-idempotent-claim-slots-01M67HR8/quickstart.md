# Quickstart — reproducing and verifying #6689

Commands assume the repository root of a spec-kitty checkout with `uv sync --frozen
--all-extras` and `make sync-packs` already run.

## 1. Reproduce on a pre-fix tree (red)

```bash
git checkout 512567eee7          # or any pre-fix commit
uv run python /tmp/repro6689.py  # the fixture builder below
```

Expected (pre-fix, reproduced on `512567eee7`):

```
--- run 1
wrote 3 None []
verify ok= False 1 ('WP01: claim mismatch (deterministic seed payload diverged)',)
--- run 2 (idempotency)
skip 0 nothing new to seed (idempotent)
verify ok= False ('WP01: claim mismatch (deterministic seed payload diverged)',)
DIFF 0RWXZFHX7REDZWCZC43GQB3SPF
    mission_id actual= 'cache-known-card-ceo-checks' expected= None
```

The seed id `0RWXZFHX7REDZWCZC43GQB3SPF` is the id quoted in the issue report, which is how
we know the fixture is the reporter's Mission and not a lookalike.

## 2. The fixture (the reported Mission shape)

- `kitty-specs/cache-known-card-ceo-checks/meta.json` with
  `"mission_id": "cache-known-card-ceo-checks"` (a slug, not a ULID), plus `accept_commit`,
  `accepted_at`, `accepted_by`.
- `kitty-specs/cache-known-card-ceo-checks/tasks/WP01-known-card-fast-path.md` with **no**
  `lane:` key, `assignee: root`, `agent: "codex"`, `shell_pid: "21224"` and no
  `shell_pid_created_at`.
- `kitty-specs/cache-known-card-ceo-checks/status.events.jsonl` whose history starts at
  `claimed -> in_progress` (no initial `planned -> claimed`).

## 3. Verify through the production entry point (green, post-fix)

```bash
# from a project whose kitty-specs/ holds that Mission
uv run spec-kitty migrate backfill-runtime-state --mission cache-known-card-ceo-checks
echo $?   # 0; summary reports the Mission under "Flipped"
grep cache-known-card-ceo-checks/status.events.jsonl | head -3   # claim row now carries mission_id
uv run spec-kitty migrate backfill-runtime-state --mission cache-known-card-ceo-checks
# second run: "Skipped"/skip action, 0 seeds, still exit 0
```

## 4. Verify the fail-closed posture is untouched

```bash
uv run pytest tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py -q
uv run pytest tests/unit/migration/test_backfill_runtime_state.py -q
uv run pytest tests/specify_cli/migration/test_runtime_state_cutover.py tests/migration/test_birth_cutover.py -q
```

Every refusal row in the new file is paired with a positive control built from the *same*
fixture, so a widened tolerance (rather than a real fix) fails the suite.

## 5. Local gates

```bash
uv run ruff check src/specify_cli/migration/backfill_runtime_state.py tests/specify_cli/migration/test_backfill_runtime_state_slug_identity_6689.py
uv run mypy src/specify_cli/migration/backfill_runtime_state.py
uv run python -m scripts.docs.check_docs_freshness --ci
```
