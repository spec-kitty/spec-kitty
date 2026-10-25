# Data Model: Residue-safe migration sweep and fabricated-identity audit

## Residue decision (value, computed)

| Input | Source |
|---|---|
| `path` | a `kitty-specs/<slug>/` child |
| `repo_root` | the parent of `kitty-specs/` unless given |
| `tracked` | optional batched `tracked_mission_paths(repo_root)`, computed once per walk |
| git-aware mode | git can run **and** `tracked` is non-empty |

| Mode | Residue when |
|---|---|
| git-aware | `not is_mission_dir(path)` **and** neither `spec.md` nor `meta.json` exists on disk |
| file-presence (fallback) | none of the Mission content files exist (`spec.md`, `meta.json`, `plan.md`, `tasks.md`, `tasks/`, `status.events.jsonl`, `status.json`, `lanes.json`) and `not is_mission_dir(path)` |

Invariants:
- A folder whose `meta.json` carries a `mission_id` is never residue, and the decision costs 0 git calls.
- A folder whose tracked `spec.md` or `meta.json` is deleted on disk is never residue.
- A folder outside `kitty-specs/` is never residue.

## Successor migration (class-level metadata)

| Field | Value |
|---|---|
| `migration_id` | `<predecessor version>_residue_safe_<name>` (e.g. `2.0.6_residue_safe_consistency_sweep`) |
| `target_version` | = predecessor's |
| order | immediately after the predecessor, `# tie:` |
| `runs_on_worktrees` / `requires_git_repository` / `clone_local_effect` | = predecessor's |
| `detect()` | False if the predecessor is settled (selection view); else the predecessor's detection over non-residue folders |
| `apply()` | the predecessor's repairs over non-residue folders; one `RESIDUE_NOTICE` warning per skipped folder |

Supersession table entry: `predecessor_id -> successor_id`; the registry registers a `SupersededMigration` substitute for the predecessor (content hash unchanged).

## Ledger states that decide a successor's work

| Predecessor record | Pending adoption settles predecessor? | Successor `detect()` |
|---|---|---|
| `success` | n/a | False |
| none, `skipped` or `failed` | yes | False (dry run and live) |
| none, `skipped` or `failed` | no | the predecessor's own detection, minus residue |

## Residue notice

`RESIDUE_NOTICE.format(slug=...)`: one constant in `mission_resolver`. It names the folder, says it is not a Mission, and gives the remedy: add a `spec.md` or `meta.json` to make it one, or remove the folder. The runner keys its collapse on `(folder, RESIDUE_NOTICE)` and passes every other warning through unchanged.

## Fabricated-identity finding

| Field | Value |
|---|---|
| code | `FABRICATED_IDENTITY_SUSPECTED` |
| severity | WARNING (not in `TEAMSPACE_BLOCKER_CODES`) |
| artifact_path | `meta.json` |
| detail | the three matched signals; the manual remedy; no run-varying values |

Flagged only when all hold:
1. `meta.json` is git-tracked, and the folder contains nothing outside the allow-list `{meta.json, status.json, status.events.jsonl, decisions/, *.lock}`.
2. `meta.json`'s slug-derived fields equal `baseline_slug_fields(slug)`: blank equals `""`, `null` or absent, and a numeric prefix matches as text or int.
3. `mid8_from_slug(slug)` is non-empty and differs from `mission_id[:8]`.
