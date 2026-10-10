# Contract: refusal codes

| Code | Raised by | Exit | Meaning | Remedy printed |
|---|---|---|---|---|
| `COORD_TEARDOWN_KEPT_ONLY_COPY` | `consolidate`, `consolidate --abort` teardown | 76 (defined in `coordination/teardown.py`) | The landing is done; the coordination worktree holds the only copy of the listed files, so the coordination branch, worktree and marker were kept | Commit the files on the coordination branch, or move them out, then `spec-kitty consolidate --resume` |
| `DESTRUCTIVE_OP_ONLY_COPY` | any guard entry point | caller-defined (consolidate: 1, after rollback) | A destructive op would discard files that exist nowhere else | Commit, stash or move the listed files, then re-run |
| `BRANCH_HAS_UNIQUE_COMMITS` | `guarded_branch_delete` | caller-defined | The branch holds commits no other ref reaches | Merge or keep the branch; nothing was deleted |
| `TOOL_OWNED_PATH_UNPROVEN` | `remove_tool_owned_tree` | caller-defined | The path is not under a tool-owned root | Programming error; nothing was deleted |

Every refusal names each kept file (first 20 plus a count) and one recovery step (NFR-002). Nothing is mutated before a refusal.
