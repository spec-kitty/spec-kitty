# Data Model: Repo-relative retrospective record_path (#5868)

No new entities. One field's *form* changes on an existing entity.

## `RetrospectiveCaptured` event (`src/specify_cli/retrospective/lifecycle_events.py`)

| Field | Type | Before | After |
|-------|------|--------|-------|
| `record_path` | `string` | Absolute filesystem path (`/home/<user>/.../kitty-specs/<slug>/retrospective.yaml`) | Repository-relative POSIX path (`kitty-specs/<slug>/retrospective.yaml`) |

All other envelope fields unchanged (NFR-001).

### Invariant

`record_path`, when joined onto the repository root, resolves to the same
`retrospective.yaml` written by the record writer (`canonical_record_path`).
The on-disk `Path` used for the write is unchanged — only the *recorded string*
becomes relative.

### Derivation

```
feature_dir   = resolve_retrospective_home(repo_root, record.mission_slug)   # repo_root / kitty-specs / <slug>
canonical_path = feature_dir / RETROSPECTIVE_FILENAME                        # absolute Path (unchanged, used for I/O)
record_path   = canonical_path.relative_to(repo_root).as_posix()             # "kitty-specs/<slug>/retrospective.yaml"
```
