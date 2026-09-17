---
affected_files: []
cycle_number: 1
mission_slug: cli-boundary-robustness-01M2NQCB
reproduction_command:
reviewed_at: '2026-09-16T21:27:35Z'
reviewer_agent: codex:gpt-6:reviewer-renata:reviewer
wp_id: WP03
---

# WP03 independent review — changes requested

Reviewer: codex:gpt-6:reviewer-renata:reviewer, freshly resolved through AgentProfileRepository.
Official invocation: 0936e5ea41004b46b1e42c71a6921a11.
Reviewed HEAD: 24ef6acf7; dependency base: 105ef7167.
No implementation edits. Canonical root mission contracts and full stable review prompt consulted.

## Finding R1 — HIGH: corrupted token bytes escape the adopted JSON boundary

Location: src/specify_cli/cli/commands/context.py:320–327 (mission_show_command), reached through the registered `context mission-show` command.

A real `.kittify/runtime/contexts/ctx-broken.json` containing bytes `FF FE` causes:

```
context mission-show --context ctx-broken --json
exit_code=1
exception=UnicodeDecodeError
stdout=""
stderr=""
```

Human mode also leaks the raw exception. CliRunner catches that Python exception rather than receiving a controlled SystemExit; normal uncaught execution can expose a traceback. This is not a successful machine error because stdout cannot be parsed as JSON.

`load_mission_context` reads UTF-8 at context/store.py:71 but wraps only JSONDecodeError/TypeError/KeyError. The newly adopted command boundary catches only ContextNotFoundError/ContextCorruptedError, so invalid encoding bypasses both handlers. The added corrupt-token test covers syntactically invalid UTF-8 JSON (`{bad`) only.

Required correction: translate non-UTF-8 token read failures at the owned command boundary (or coordinate any necessary domain-layer change), preserving human/JSON exit fidelity and a named canonical JSON error. Add a real-file regression through the registered command that asserts parseable stdout, nonempty stable code/message, and a controlled SystemExit rather than a raw UnicodeDecodeError. Keep malformed JSON and missing-token coverage intact. Consider the adjacent unreadable-token OSError boundary while auditing this same load site.

This finding concerns an existing failure class left unhandled by the explicitly adopted boundary, not an introduced decode regression. It blocks the promised WP03 missing/corrupted-token JSON behavior (FR-005, FR-007, NFR-002; C1/C2/C5).

Reproducer: parent/WP03-review-repro.py; output: parent/WP03-review-repro.log. Uses only temporary files, real loader, real registered command; no product mocks or environment sync changes.

## Evidence and coverage assessment

- Actual diff: only context.py and the new boundary test; owned scope preserved.
- Red-only 339bcb15a precedes tidy16cfcf8e2 and functional24ef6acf7. Read original WP03-red.log:11failed2passed, including original #4597 OptionInfo default leak and #4601 JSON parse failures.
- Real default values via Annotated fix no-subcommand delegation without sentinel framework. Four JSON siblings (info/list/mission-resolve/mission-show) wired to existing shared builder/console; cleanup retains non-JSON interface. Missing mission exit2 retained.
- Existing success workspace data, empty/orphan lists and token roundtrips covered through production filesystem/services. Root application registration test exercises actual command route.
- Implementer logs verified:239passed broad context/seam suite and44passed supplemental callers. No blanket integrated mission test approval inferred.
- Independently reran ruff check, strict mypy and explicit-file format on both changed files: all pass. No repeated broad suite needed to establish the concrete failing boundary.
- Failing independent two-mode token probe described above. No source edits, no test weakening, no dependency or hosted changes.

## Anti-pattern checklist

| Check | Verdict | Evidence |
|---|---|---|
| Dead code | PASS | _emit_error called by all four JSON sibling error handlers; no new production module/public API |
| Synthetic-fixture test | PASS | Real Typer commands, WorkspaceContext persistence and token files; root registration covered |
| Silent empty return | PASS | No new exception-swallowing empty-return branch |
| FR coverage | FAIL | Corrupted-token byte failure escapes adopted FR-005/FR-007/NFR-002 boundary; R1 |
| Frozen surface | PASS | Only two owned files changed; shared JSON authority and frozen doctor tests untouched |
| Locked decision | PASS | No sentinel framework, success-shape redesign, exit homogenization, flags or scope expansion |
| Shared ownership | PASS | No overlap with other WPs' product files |
| Production fragility | PASS | New explicit Exit branches correspond to existing domain failures; no new race-sensitive raise |

## Disposition

REQUEST CHANGES, one high-severity finding. Preserve existing green coverage and remediate R1 with red/green evidence. Do not mark #4601 terminally fixed or approve this work package until the owned context boundary is complete.
