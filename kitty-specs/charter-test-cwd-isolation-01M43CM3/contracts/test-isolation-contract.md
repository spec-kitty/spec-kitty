# Contract: charter working-directory isolation for tests

## `charter_cwd_isolation` (opt-in fixture)

- Returns a callable `isolate(project_root: Path | None = None) -> Path`.
- Effect: process working directory = `project_root`; the charter command package's `find_repo_root` returns `project_root`. `None` means `tmp_path`.
- Returns the root it used. Undone at test teardown.
- Must not patch, wrap or replace `resolve_charter_write_root`.
- Exactly one definition in the test tree.

## Tripwire (autouse)

- Watches the guard at every charter command module that calls it: `generate`, `synthesize`, `resynthesize`, and `activate` (which also serves `deactivate`).
- Always calls through; never changes the guard's result.
- Violation: the probed path resolves inside the invoking checkout (the checkout containing the running `tests/` tree). A pytest base temp directory configured inside the checkout is not counted as inside; this is a correctness rule for tmp paths, not an opt-out.
- On violation the test fails at teardown with one message containing the test's node id and the name `charter_cwd_isolation`.
- No exemption marker, no allowlist. A suite check fails if any test file redefines the tripwire's fixture name.
- Blind spots: guard calls made from module- or session-scoped fixtures, and commands started as a separate process.

## Invariants (each has a test)

| # | Invariant | Evidence |
|---|-----------|----------|
| 1 | Without the helper, a guarded write from a linked worktree is refused with the product's message. | reproduction, unisolated arm |
| 2 | With the helper, the same start succeeds and writes under the test tmp project. | reproduction, isolated arm |
| 3 | With the helper active, moving into a linked worktree is still refused. | refusal control |
| 4 | A test reaching the guard from the invoking checkout fails, whatever its patch spelling. | tripwire self-mutation tests |
| 5 | Every caller of the guard in the charter commands package is watched. | tripwire coverage test |
| 6 | The existing guard test files are unchanged. | diff |
