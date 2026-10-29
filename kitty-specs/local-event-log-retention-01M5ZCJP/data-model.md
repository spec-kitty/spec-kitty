# Data model: Local event-log retention

## RetentionRule (enum, `specify_cli.state.contract`)

| Value | Meaning | Allowed git class |
|---|---|---|
| `never` | Never pruned by the CLI; git (or the owner) keeps it. All tracked ledgers. | any |
| `ledger_retention` | Pruned by `doctor event-logs` under `ledger.retention` limits once the item's work is over (a run: its Mission merged or the run recorded `MissionRunCompleted`; a per-Mission log: its Mission completed). | `ignored` only |
| `rebuildable` | A cache rebuilt (or bypassed) on read; `doctor event-logs` may delete it at any time unless locked. | `ignored` only |
| `owner_lifecycle` | Removed by the command that owns it (named in `cleanup_command`). | any |
| `manual` | No automated cleanup; an operator removes it by hand if ever. | any |
| `retired` | A deprecated tombstone surface with no live writer. | any |

Pinned local tier: `ledger_retention` = the run family (`runtime_run_snapshot`, `runtime_run_event_log`, `runtime_frozen_template`) and `glossary_fallback_events`; `rebuildable` = `derived_mission_views` only. `op_invocation_index` is `manual` with no cleanup command (operator ruling 2026-10-28: `invocations list` trusts a partial index); `tracker_cache` is `manual`.

Invariants (tests): a `tracked` surface is never `ledger_retention` or `rebuildable`; a `ledger_retention` or `rebuildable` surface names `spec-kitty doctor event-logs --apply`; an `owner_lifecycle` surface names a command; a deprecated surface is `retired`.

## CleanupPolicy (frozen dataclass)

| Field | Type | Notes |
|---|---|---|
| `retention` | `RetentionRule` | required |
| `cleanup_command` | `str \| None` | the command that cleans the surface, or `None` |

`to_dict()` → `{"retention": "<value>", "cleanup_command": "<cmd>" \| null}`; `StateSurface.to_dict()` adds `"cleanup_policy"`.

`StateSurface.cleanup_policy` is keyword-only and has no default (FR-002).

## RetentionLimits (`specify_cli.core.ledger_retention`)

| Field | Default | Validation |
|---|---|---|
| `keep_runs` | 20 | `int`, not `bool`, ≥ 0 |
| `max_age_days` | 30 | `int`, not `bool`, ≥ 0 |

Missing file / missing `ledger` / missing `retention` → defaults. A non-mapping `ledger.retention`, an unknown key, or an invalid value → `RetentionConfigError` (exit 2). Unparseable YAML → `RetentionConfigError`.

## RetentionItem and verdicts (`specify_cli.state.retention`)

| Field | Meaning |
|---|---|
| `surface` | registry surface name that selected the item |
| `path` | repo-relative POSIX path (a run directory, a log file, a cache file or directory) |
| `kind` | `run`, `mission_log`, `cache` |
| `mission` | the Mission directory name under `kitty-specs/` when resolved, else `null` |
| `age_days` | float |
| `verdict` | `candidate` or `kept` |
| `reason` | see below |

Reasons — candidate: `past retention; Mission completed`, `rebuildable cache`. Kept: `within keep_runs`, `younger than max_age_days`, `Mission is open`, `Mission not found`, `lock held`.

A run's Mission is resolved from its run-index entry (`mission_id`, else `mission_slug` when the entry records no id); a run with no entry falls back to its snapshot's own fields under the same id-only rule. A `mission_slug`, `mission_id` or glossary log stem that maps to more than one Mission directory is ambiguous and resolves to none (`Mission not found`).

State transition on apply: `candidate` → `deleted` | `failed` (with error text). A `candidate` whose lock is found held at apply time becomes `kept: lock held`.
