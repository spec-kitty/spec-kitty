# Contract — `kernel.ancestor_walk`

Owner: `src/kernel/ancestor_walk.py`. Every repo/project-root ancestor walk in the
stack goes through this module. It is the single reading of
`GIT_CEILING_DIRECTORIES` and the single ancestor-walk loop.

## Why it lives at the `kernel` floor

`charter` and `runtime` need the walk and may not import `specify_cli`
(`tests/architectural/test_layer_rules.py`). The module therefore imports only the
standard library, and it must stay cheap enough to import from
`specify_cli.bootstrap.env_file`, which runs at bare `import specify_cli` time and
must emit no stderr.

## Public surface

```python
GIT_CEILING_ENV: Final[str] = "GIT_CEILING_DIRECTORIES"

def git_ceiling_dirs(environ: Mapping[str, str] | None = None) -> frozenset[Path]: ...

def iter_ancestors(start: Path, *, ceilings: frozenset[Path] | None = None) -> Iterator[Path]: ...

def find_ancestor(
    start: Path,
    predicate: Callable[[Path], bool],
    *,
    ceilings: frozenset[Path] | None = None,
) -> Path | None: ...
```

- `git_ceiling_dirs` — the resolved absolute entries of the variable, in the given
  environment (default `os.environ`). Relative entries are ignored; empty entries are
  ignored. Read **per call**; never cached.
- `iter_ancestors` — yields `start.resolve()` and each parent, in order. When a
  candidate is in `ceilings`, it is yielded and the iteration stops after it. With no
  ceiling ancestor, the iteration ends at the filesystem root.
- `find_ancestor` — the first candidate for which `predicate` is true, else `None`.
  `predicate` receives resolved candidates and must be free of side effects the
  caller cannot afford to repeat; the walk stops at the first acceptance.

`ceilings` on both walk functions is an injection seam for tests and for callers that
must use a specific environment; production callers omit it and get
`git_ceiling_dirs()`.

## Ceiling semantics (issue #7056 item 2)

The shipped reading is kept deliberately, because matching git exactly would change
`resolve_canonical_root`'s observable behaviour:

| Case | git | this primitive |
| --- | --- | --- |
| A ceiling directory that is an ancestor of the start path | not examined | **examined**; the walk stops after it |
| The search starts at a ceiling directory | examined | examined; the walk stops after it |
| A relative ceiling entry | ignored | ignored |
| Absolute entries after an empty entry | left unresolved | **resolved** |

Evidence and reasoning: `kitty-specs/ceiling-aware-ancestor-walk-01M6EJNY/research.md`
D-3. Pinned by `tests/kernel/test_ancestor_walk.py`.

## Invariants

1. No caching of the environment (a monkeypatched value takes effect on the next call).
2. No upward import; no `specify_cli`, `charter`, `runtime` or `mission_runtime` import.
3. No decision logic: the predicate is the caller's, so this module never decides what
   a repository marker is.
4. Resolved comparison: the start is resolved once and ceiling entries are resolved
   when read, so a symlinked temp root compares equal to its resolved parents.
5. `specify_cli.core.paths.git_ceiling_dirs` stays importable and returns exactly
   `kernel.ancestor_walk.git_ceiling_dirs()`.

## Gate

`tests/architectural/test_no_hand_rolled_root_walks.py` rejects a new inline
`[p, *p.parents]`, `(p, *p.parents)` or `[p] + list(p.parents)` walk under `src/`
outside this module, except for file+function exemptions recorded with a reason in
`tests/architectural/_hand_rolled_root_walk_scan.py`. The list is shrink-only: an
exemption that no longer matches a scan hit fails the gate.
