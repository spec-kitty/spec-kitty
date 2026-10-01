# Quickstart: asking git for paths

```python
from kernel.git import GitPath, status_entries, tree_paths

target = tree_paths(repo, new_sha)                       # frozenset[GitPath]
for entry in status_entries(repo, ignored=True):         # StatusEntry, NUL-safe
    if (entry.is_ignored or entry.is_untracked) and any(entry.path.overlaps(t) for t in target):
        print("would be clobbered:", entry.path)
```

Never build `["git", "status", "--porcelain", ...]` or split git output on newlines or NUL outside `src/kernel/git/`; `tests/architectural/test_git_path_listing_owner.py` fails the build if you do.
