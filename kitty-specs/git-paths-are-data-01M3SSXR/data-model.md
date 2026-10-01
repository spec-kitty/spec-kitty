# Data model: Git paths are data, not text

## GitPath (value object, `kernel.git.paths`)
- **Fields**: `parts: tuple[str, ...]` — repository-relative components, no empty, `.` or `..` component.
- **Construction**: `GitPath.parse(text)` strips one trailing `/` (git's directory marker) and splits on `/`; rejects absolute paths and `..`; `GitPath.parse("")` is the root (`parts == ()`).
- **Relations** (component-wise): `==`, `is_ancestor_of(other)` (strict prefix), `contains(other)` (== or ancestor), `overlaps(other)` (either contains the other). Root overlaps nothing (an empty path never obstructs).
- **Rendering**: `str(p)` / `p.as_posix()` → `"/".join(parts)`; `p.name`.
- **Invariant**: `GitPath.parse(str(p)) == p`.

## StatusEntry (`kernel.git.listing`)
- `xy: str` (two chars), `path: GitPath`, `orig_path: GitPath | None` (renames/copies only), `is_directory: bool` (git reported a trailing slash).
- Derived: `is_untracked` (`??`), `is_ignored` (`!!`), `is_conflicted` (unmerged codes), `index`, `worktree`.
- `line` — a display rendering `XY path` (with ` <- orig`) for messages; never parsed back.

## NameStatusEntry (`kernel.git.listing`)
- `status: str` (e.g. `M`, `A`, `D`, `R100`), `path: GitPath`, `orig_path: GitPath | None`.

## GitResult / GitCommandError (`kernel.git.runner`)
- `GitResult(returncode: int, stdout: bytes, stderr: bytes)`.
- `GitCommandError(RuntimeError)`: `argv`, `cwd`, `returncode`, `stderr` (decoded text); raised for a non-zero exit when `check=True`, or when git cannot be executed.
- **IndexEntry** (`kernel.git.listing`): `mode: str`, `oid: str`, `stage: int`, `path: GitPath`, `tag: str | None` (the `ls-files -v` tag, filled only when `tags=True`).
- **NumstatEntry** (`kernel.git.listing`): `added: int | None`, `deleted: int | None` (`None` for a binary file), `path: GitPath`.
- **TreeEntry** (`kernel.git.listing`): `mode: str`, `type: str` (`blob`, `tree`, `commit`), `oid: str`, `path: GitPath`.
- **GitCommandError** also carries `timed_out: bool`.
