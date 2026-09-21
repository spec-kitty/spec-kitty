# WP07 cycle-2 — fold FR-011 root-hardening (operator-directed)

WP07 was approved. The operator directed folding in the FR-011 root-hardening residual the
WP06 reviewer flagged. Confined to `src/runtime/next/_tmp_namespace.py` + its test (no owned_files change).

## The residual
WP07 currently does `mkdir(parents=True, exist_ok=True)` for the prompt dir and chmods only the
**leaf** subdir to 0700. If `prompt_tmp_dir()` runs FIRST on a fresh machine (before any credential
write), `mkdir(parents=True)` creates `~/.spec-kitty` at the ambient umask (0755). It self-heals to
0700 on the next credential write (WP06's `ensure_runtime_root`), but a prompt-only workload leaves
the runtime **root** at 0755 — a narrow FR-011 gap.

## Layer constraint (important)
`_tmp_namespace.py` is in the `runtime` package and MUST NOT import `specify_cli.paths.ensure_runtime_root`
(that is a `runtime → specify_cli` layer violation — the enforced direction is
`kernel <- ... <- specify_cli`; runtime is below specify_cli). So do NOT call WP06's helper.

## Required fold
In `prompt_tmp_dir()` (or a small local helper), after resolving `kernel.paths.get_runtime_state_root()`,
ensure the **runtime root itself** is created and chmod'd `0700` (via `kernel.paths` + stdlib `os`),
not just the leaf prompt subdir. This is idempotent with WP06's `ensure_runtime_root` (both chmod the
same root to 0700 — redundant but not divergent; document the one-line rationale that this closes the
prompt-first-run window without a cross-layer import). Keep the existing leaf-0700 + no-follow behavior.

## Test
Add a red-first test: on a fresh isolated HOME with no prior credential write, call `prompt_tmp_dir()`
and assert the **runtime root** (`get_runtime_state_root()`) is mode 0700 (not 0755). Red before the
fold (root left at umask), green after.

Keep everything else (per-user resolution, symlink-safe writer, ≤0600 files) unregressed. Re-run the
WP07 test set + `ruff format --check` (keep it green).
