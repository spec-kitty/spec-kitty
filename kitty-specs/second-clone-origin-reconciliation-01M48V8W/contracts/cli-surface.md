# Contract: CLI surface

| Surface | Addition |
|---|---|
| `spec-kitty consolidate` | `--origin-check [enforce\|warn]` (default from `SPEC_KITTY_ORIGIN_CHECK`, else `enforce`) |
| `spec-kitty accept` | `--origin-check [enforce\|warn]`; `--no-commit` / `--diagnose` always warn |
| `orchestrator-api accept-mission` | `--origin-check`; refusal `MISSION_NOT_READY`, `data.preflight_error_code`, `data.origin_freshness` |
| `orchestrator-api consolidate-mission` | `--origin-check`; refusal `PREFLIGHT_FAILED`, `data.preflight_error_code(s)`, `data.origin_freshness` |
| envelope | `CONTRACT_VERSION` 1.10.0 → 1.11.0 |
| `agent action review` | no flag; prints `Updated <lane> from <remote>/<lane> (<n> commits)` or `Created review workspace from <remote>/<lane>`; refuses `ORIGIN_LANE_DIVERGED`; warns on unreachable |
| `spec-kitty init` (already initialized) | installs merge-driver config; still exit 0 "Already initialized" |
| `spec-kitty upgrade` | installs merge-driver config, reported in its outcome |
| environment | `SPEC_KITTY_ORIGIN_CHECK=enforce\|warn` documented in `docs/api/environment-variables.md` |
