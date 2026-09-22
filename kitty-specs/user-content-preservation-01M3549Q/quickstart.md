# Quickstart: User-content preservation for mutating flows

How to verify the mission end-to-end. Each defect ships a `@pytest.mark.regression`
repro that is RED on the mission base and GREEN on the fix.

## Prerequisites

- Editable install reflecting the checkout: `.venv/bin/spec-kitty` (already present).
- Do NOT `uv run` (it re-syncs and destroys the hand-built `.venv`). Use `.venv/bin/python -m pytest`.

## Per-defect smoke checks (isolated throwaway repos)

Each issue body carries a complete portable repro script (isolated HOME/XDG under
`mktemp`, `SPK_QA_SOURCE=<checkout>`). The mission's regression tests encode the same
scenarios. Expected AFTER the fix:

| # | Command | Expected |
|---|---------|----------|
| 4907 | `agent config remove claude` with a user `.claude/commands/my-deploy.md` | file preserved, exit 0, "Preserved …" (not "Removed") |
| 2691 | bare `agent config sync` with a user command file + pinned manifest | file preserved; manifest byte-identical; `--json` lists zero mutations |
| 4895 | `implement WP##` with a foreign `.git/hooks/pre-commit` | foreign hook backed up to `pre-commit.<ts>`, backup path printed, user hook restorable |
| 4910 | `intake <doc>` (and `--auto`) with a brief present, no sidecar | exit non-zero, `Use --force`, brief byte-identical |
| 4896 | `validate-encoding --fix` over mixed/binary/CRLF `.md` | UTF-8 intact, binary skipped, CRLF preserved, "Fixed" only on faithful repair |
| 4890 | `agent tasks finalize-tasks` with a frontmatter-only cycle | exit non-zero, no status seeded, payload == persisted graph |
| 4888 | any auto-commit / `upgrade` with an unrelated file partially staged | `git diff --cached` + `git stash list` unchanged; on residual failure stash ref + SHA surfaced |

## Targeted test surfaces (run per WP, not the whole suite)

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/agent/cli/commands/test_agent_config.py -q      # WP-B (#4907/#2691)
PWHEADLESS=1 .venv/bin/python -m pytest tests/policy/ tests/lanes/ -q                           # WP-C (#4895)  [adjust to real mirror]
PWHEADLESS=1 .venv/bin/python -m pytest tests/specify_cli/cli/commands/ -k intake -q            # WP-D (#4910)
PWHEADLESS=1 .venv/bin/python -m pytest tests/ -k text_sanitization -q                          # WP-E (#4896)
PWHEADLESS=1 .venv/bin/python -m pytest tests/ -k tasks_finalize -q                             # WP-F (#4890)
PWHEADLESS=1 .venv/bin/python -m pytest tests/ -k "commit_helpers or autocommit" -q             # WP-G (#4888)
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_mutation_ownership_routing.py -q # WP-H closure
PWHEADLESS=1 .venv/bin/python -m pytest tests/asset_preservation/ -q                             # WP-A helper
```

(The exact mirror dirs are confirmed by the brownfield scout per WP — `tests/` mirrors
`src/`; when the mirror is not obvious use `grep -rl "<module>" tests/ --include=*.py`.)

## Definition of done

- All 7 red-first repros GREEN on the fix (were RED on base) — SC-001.
- Owned-delete / faithful-success anchors stay green — SC-004.
- The widened census gate fails on a planted un-routed op and on a narrowed routed set
  (self-mutation both directions) — SC-003.
- 7 issue-matrix rows moved from `in-mission` to `fixed` with evidence refs — SC-005.
- One non-draft PR to upstream `main`; operator merges.
