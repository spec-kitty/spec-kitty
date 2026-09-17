# WP05 independent review — changes requested

Reviewer: codex:gpt-6:reviewer-renata:reviewer, freshly resolved via AgentProfileRepository.
Official review invocation: 9aec076be0ae400bbb47c61b91823f93.
Reviewed HEAD: a2aea67b0; dependency base: 105ef7167.
Full official prompt and primary-root mission contracts consulted. No product edits.

## R1 — HIGH: ambiguous mission handles escape adopted command boundaries

Locations: archive.py:69, materialize.py:80, verify.py:135 (via _existing_feature_dir:49).

Real temporary Git repository, .kittify/config.yaml containing {}, and two mission directories with valid meta.json identities sharing prefix 01KV0S99:
alpha-01KV0S99 (mission_id 01KV0S99AAAAAAAAAAAAAAAAAA), beta-01KV0S99 (mission_id 01KV0S99BBBBBBBBBBBBBBBBBB).

Actual registered callbacks invoked through CliRunner:

- `archive create 01KV0S99 --by review --reason review --json`
- `materialize --mission 01KV0S99 --json`
- `verify --mission 01KV0S99 --json`

Each returns exit 1 with raw MissionSelectorAmbiguous, stdout empty, stderr empty. Human mode also leaks that exception (verify first prints its ordinary tool report). These are not controlled SystemExit failures; an uncaught real process can expose a traceback, and JSON stdout cannot be parsed.

Resolution runs outside the new command error handlers. Adopted archive/materialize domain-error coverage and verify JSON boundary therefore remain incomplete (FR-005/007/010, NFR-002; C1/C2/C5). This is an existing failure class left uncovered by this adoption, not an alleged introduced regression.

Required correction: catch expected selector failures at each owned command boundary, emit one canonical error object in JSON mode, retain useful handle/candidate context, and preserve command-specific human/JSON exit fidelity. Add real ambiguous-handle regression fixtures. Do not alter shared resolver semantics or unrelated command families without ownership coordination. Verify diagnostics is a sibling path worth auditing at the same time.

## R2 — HIGH: status delegate errors bypass canonical shape and violate exit fidelity

Location: tasks_status_cmd.py:176 (_st_resolve_dirs delegates to _find_mission_slug); _do_status:876 rethrows the delegate's Exit without adaptation. Shared source tasks_shared.py:212 onward explains the emitted legacy payload; it is not owned by this WP.

Same real fixture, actual agent.tasks.app status registration:

| Invocation | JSON exit / output | Human exit |
|---|---|---|
| `agent tasks status --mission 01KV0S99 --json` | 1; success=false, error_code=MISSION_AMBIGUOUS_SELECTOR, error is string | 2 |
| `agent tasks status --mission missing --json` | 1; success=false, error_code=MISSION_NOT_FOUND, error is string | 2 |
| `agent tasks status --json` | 1; only error string '--mission <slug> is required' | 1 |

All three lack C2's ok=false and nested nonempty error.code/error.message. Missing/ambiguous handles additionally violate C4 because human mode exits 2 while JSON exits 1. The new _status_error builder never receives these paths.

Required correction: adapt these delegate failures within the owned status boundary (or explicitly coordinate necessary shared changes) without causing double JSON output or changing unrelated tasks commands. Preserve established human exit codes and match them in JSON. Add registered-command tests for absent, nonexistent and ambiguous mission selectors; assert exact exits and one parseable canonical object, preserving candidate metadata where relevant.

## Evidence and scoped compliance

- Durable reproducer: parent/WP05-review-repro.py; complete 12-case results: parent/WP05-review-repro.log. Real temporary filesystem/metadata and production callbacks; no product mocks, active-mission archive, hosted settings changes or source edits.
- Actual diff inspected across all 11 changed files. Red-only 51a46c5a9 precedes functional a2aea67b0. Implementer records initial 15 failed/2 passed plus corrected archive-exit red run. Functional commit combines builder extraction and adoption; there is no separate tidy commit, a process deviation from the requested separation. Future remediation should keep tests and functional corrections separately reviewable.
- Zero-WP status success is covered by real Git/mission/tasks fixtures, production tasks app, and root application registration. Empty collections, zero total, exit 0 and no error key asserted. Builder is live through show_kanban_status, which retains human presentation/legacy error behavior; builder raises instead of printing on expected missing inputs.
- Existing status seam assertion changes explicitly authorized. Successful aggregation remains sourced from original implementation; no success-schema redesign found.
- Glossary list/conflicts/validate use shared envelope authority; real malformed YAML, schema errors, empty lists, missing validation paths exercised. Dashboard preserves early registry JSON return without starting server. Human-only validate_encoding/research/validate_tasks interfaces untouched.
- Verified implementer logs: focused 75 passed; extra domain 10 passed; root registration 1 passed; architecture 44 passed. Distinct broad suite 1553 passed/8 skipped/33 failed. Those 33 were separately reproduced unchanged on baseline and tracked as #4671/#4672 by parent; this review does not waive the integrated hard gate.
- Independently reran ruff check and strict mypy over all 11 changed Python files: both exit 0, mypy 11 files. Integrated format log records 1934 files unchanged; no additional broad suite repeated because independent real probes already establish blockers.
- No issue-matrix terminal verdict or GitHub publication made. Shared integration validation remains root's responsibility.

## Eight mandatory anti-pattern checks

| Check | Verdict | Evidence |
|---|---|---|
| Dead code | PASS | New public build_kanban_status has production caller show_kanban_status; helpers reached from registered commands |
| Synthetic-fixture test | PASS | Regression cases invoke production commands/services with real temporary project state, including root registration |
| Silent empty return | PASS | Empty status is legitimate success; builder missing inputs raise; no new unexplained exception-empty return |
| FR coverage | FAIL | Adopted selector errors bypass promised machine boundary; R1/R2 |
| Frozen surface | PASS | Diff limited to owned source/new tests and explicitly authorized old status seam assertions |
| Locked decision | FAIL | C2/C4 remain unsatisfied for adopted status errors; no new forbidden framework or flags found |
| Shared ownership | PASS | Product diff does not modify another WP's files; shared resolver implicated but untouched |
| Production fragility | PASS | New builder raises have documented fail-loud role and wrapper adaptation; raw selector failures are existing gaps detailed above |

## Verdict

REQUEST CHANGES. Two high-severity findings. Keep green empty-status and glossary coverage; complete the owned error boundaries before approval. Do not mark unfinished convergence issues fixed.
