# Quickstart / Verification — Tool-surface projection honesty

## Reproduce (pre-fix)
```bash
# Seam A: stale GEMINI.md, no .gemini/
PYTHONPATH=src spec-kitty doctor tool-surfaces --tool gemini --fix   # exits 0, GEMINI.md unchanged
# Seam B (Windows): upgrade needs 3 runs; run 1 aborts "Completed command output changed: ...\.agents\skills"
```

## Verify the fix
```bash
# US1 / Seam A (FR-001..004)
PYTHONPATH=src spec-kitty doctor tool-surfaces --tool gemini --fix   # GEMINI.md refreshed, reported repaired
#   + LLXPRT.md refreshed by the same mechanism (FR-003)
# US2 / Seam B (FR-005,006; NFR-001) — Windows simulated in tests via monkeypatched observed mode
PYTHONPATH=src spec-kitty upgrade                                    # converges in ONE run, exit 0
PYTHONPATH=src spec-kitty upgrade                                    # second run: no changes
PYTHONPATH=src spec-kitty upgrade --dry-run                         # zero phantom repairs (FR-007)
```

## Test commands (ATDD, blast radius)
```bash
PWHEADLESS=1 PYTHONPATH=src .venv/bin/python -m pytest \
  tests/specify_cli/session_presence/ \
  tests/specify_cli/tool_surface/ \
  tests/specify_cli/skills/ -q
make test-fast
```

## Done when
SC-001 (GEMINI.md+LLXPRT.md refreshed by one --fix), SC-002 (one-pass Windows convergence), SC-003 (no phantom dry-run), SC-004 (detect==repair parity), SC-005 (honest failure), SC-006 (POSIX correctness preserved).
