# Quickstart: verify the two fixes by hand

Prerequisites: a repository with an owned checkout `P` of an owned-only Mission `M`
(see `tests/integration/test_explicit_checkout_commands.py::checkouts` for a scripted
setup).

## Owned legacy migration

```bash
cp legacy-issue-matrix.md P/kitty-specs/M/issue-matrix.md   # one legacy row, e.g. #1
spec-kitty agent issue-verdict --mission M --issue '#2' --verdict fixed \
  --actor me --evidence-ref 'PR #1' --owned-checkout P --json
# exit 0; P/kitty-specs/M/issue-matrix.json holds #1 and #2;
# the repository root checkout holds no kitty-specs/M
```

## Owned refusal shape

```bash
spec-kitty agent issue-verdict --mission no-such-mission-01ZZZZZZ --issue '#2' \
  --verdict fixed --actor me --evidence-ref 'PR #1' --owned-checkout P --json
# exit 1; stdout: {"ok": false, "error": {"code": "MISSION_CONTEXT_UNRESOLVED", "message": "..."}}
```

Repeat the refusal with any in-scope command (for example `agent tasks status`,
`agent tasks move-task`, `spec-commit`, `next`) and the payload has the same core.
