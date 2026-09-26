# Tracer: Tooling Friction
## Planning
- The slicing squad's `owned_files` sketch mis-located #4388 (`_PYTHON_FILE_PATTERNS` is in `test_module_shard_registry.py`, not `_dead_path_scan.py`) and #4408 (`_gate_coverage.py`, not `test_marker_job_completeness.py`) — re-verified per finding; all six own disjoint files, so no cross-file WP sequencing is needed. Always re-grep the real anchor before locking a no-overlap map.
- `spec-kitty agent mission branch-context --json` output was not clean JSON to pipe (global-agent-command rebuild noise) — non-blocking; branch state known from the explicit checkout.
## Implementation
- (append during implement)
## Review / consolidation
- (append during wrap-up)
