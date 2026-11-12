# Quickstart: verify a lane runs its own code

1. `spec-kitty implement WP01 --mission <handle>` — note the "Lane test invocation" block:
   `cd <lane>`, the `export`/`unset` lines, the command, and `probe: verified`.
2. Plant a change: edit a function in `<lane>/src/<pkg>/…` so it returns a sentinel.
3. Run the printed invocation (or `env -u PYTHONPATH … PYTHONPATH=<lane>/src python -c
   "import <pkg>, sys; print(<pkg>.__file__)"`) and see the lane path and the sentinel.
4. Contrast: `<root>/.venv/bin/python -c "import <pkg>; print(<pkg>.__file__)"` from the lane
   prints the repository root checkout's path.
5. `spec-kitty agent tasks move-task WP01 --to for_review --mission <handle>` records
   `evidence_tree` in the transition; if the lane's own `.venv` points elsewhere, the move is
   refused with `EVIDENCE_TREE_MISMATCH` (re-run with `--force` to bypass, recorded).
