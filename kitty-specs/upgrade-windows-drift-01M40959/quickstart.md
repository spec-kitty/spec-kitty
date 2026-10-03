# Quickstart: reproduce and verify

Run from the mission checkout with the synced environment (`uv sync --frozen --all-extras`).

## #5574 and #5575 — command skills

```bash
uv run pytest tests/specify_cli/skills/test_command_installer.py \
  tests/specify_cli/skills/test_crlf_skill_render_4998.py \
  tests/specify_cli/tool_surface/providers/test_command_skills.py \
  tests/specify_cli/tool_surface/test_drift_policy.py -q
```

Manual check in a scratch project:

1. `spec-kitty init` with the `codex` agent, then rewrite one entry's `content_hash` in the command-skill manifest to an older value without touching the file. `spec-kitty upgrade --yes` must exit 0 and the manifest hash must equal the file's SHA-256.
2. Append a line to `.agents/skills/spec-kitty.plan/SKILL.md`. `spec-kitty upgrade --yes` must exit non-zero and leave the file byte-identical. `spec-kitty doctor tool-surfaces` must name `--fix`; `spec-kitty doctor tool-surfaces --fix` must restore the canonical bytes.

## #5576 — CRLF planning artifacts

```bash
uv run pytest tests/specify_cli/cli/commands/test_implement_coord_idempotency.py \
  tests/specify_cli/cli/commands/test_implement_cores.py \
  tests/architectural/test_trio_seam_only.py -q
```

Manual check: in a repository with `.gitattributes` `* text=auto eol=crlf`, re-check out the files so `git status --porcelain` is empty, then `spec-kitty implement WP01 --no-auto-commit` must not ask to commit planning artifacts.
