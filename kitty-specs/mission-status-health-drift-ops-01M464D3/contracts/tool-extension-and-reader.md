# Contract: the tool extension (FR-027), the reference reader, the mutation catalogue and the test map

Internal contract between the work packages of Mission `mission-status-health-drift-ops-01M464D3`. It fixes names, signatures and stable messages so every work package works from one agreed set. An implementer may refine a name but keeps every rule here, or reports the change in the hand-off report; the orchestrator records it in `tracer-design-decisions.md` (a work package never writes under `kitty-specs/`). Plain text fences only (the corpus round-trip gate collects `yaml` fences of this directory). The names of the reader modules and functions are the plan's call (spec FR-025); the rules are the spec's.

## A. The tool files of FR-027 (the whole edit set under `contracts/tools/`)

### `fixture_builder.py`

- `STRICT_FIELDS` gains six names through a second tuple beside `_NEW_STRICT_NAMES` (the names are matched by exact property name in `leak_scan.py`, `str(child) in STRICT_FIELDS`): `specKittyVersion`, `currentBranch`, `profileId`, `action`, `invocationId`, `sourceCode`. The existing `profile` entry does not cover `profileId`. `title` and `value` stay out (human text). Measured at plan time: none of the six names occurs as a key anywhere under `contracts/` today, so `leak_scan.py --root contracts` still exits 0; IC-02 re-runs it.
- `KINDS` gains one `strict-<name>` kind per new name (34 kinds become 40: eight old, sixteen strict, twelve artifact-path forms, the reference kind, three regression kinds). The plant is the existing generic one for strict names (a leading-tilde path under that key, which is a host path only in the strict class) with its clean control on the same root; the plants are built from fragments at run time, no leaking text in the source. **All six are red-first**: the unchanged scanner does not report them (the key is not strict, and a leading-tilde path is not a human host path).
- `tests/contract/test_fixture_builder.py` moves its exact `KINDS` set; the existing test that the eight old kinds still build byte-identically stays (it passes before and after by design, so it is not a red-first claim).

### `leak_scan.py` (not expected to change)

The scanner derives `STRICT_FIELDS` from the builder and judges `artifactPath` as an artifact-path key already, so the new properties need no scanner edit. IC-02 edits it only if a red-first plant shows the unchanged scanner blind to a new case (plan PQ-4, Departs 7), in the same commit, with the file added to the allowed data. A planted `profileId` example holding a bare absolute path must fail the scan and its clean control pass (`tests/contract/test_leak_scan.py`); a committed test asserts each of the six names is in `STRICT_FIELDS`.

### `negative_cases.json`

Six cases appended in one block, in the existing shape: `{"id": "leak-scan-strict-<name>", "tool": "leak_scan.py", "build": "leak:strict-<name>", "plant": {"args": ["--root", "{root}"], "code": "HOST_PATH"}, "control": {"args": ["--root", "{root}"]}}`. No case needs a new file under `contracts/tools/fixtures/`. The slice adds no lint rule, so it adds no JVM-, vacuum- or oasdiff-tagged case (the existing lint plants, including `enum-case`, cover the new enums); the camel-case enum plant is run once at J-1 on a scratch copy.

### `enum_pins.json`

Under `mission-status`: `ProjectHealth` (IC-03); `DriftKind`, `DriftSeverity`, `DriftAuthority`, `DriftSide`, `DriftRemedy`, `DriftRefusalCode` (IC-04); `OpsModeOfWork`, `OpsInvocationStatus`, `OpsOutcome`, `OpsClosedBy`, `OpsEvidenceKind`, `OpsRefusalCode` (IC-05). `enum_pin_check` fails `ENUM_UNREADABLE` for a pinned title absent from the module, so each pin lands in the same work package as its schema; `test_enum_pin_check.py` moves its pinned line at each of the three (`enums=8 values=45`, then `enums=14 values=57`, then `enums=20 values=72`). Every value is snake_case; a planted camel-case value fails the pin check and, in J-1, the JVM lint.

## B. Reader modules (test tree, `tests/contract/`; none is a test module; every name holds `mission_status`)

| Module | Holds | Imports from |
|---|---|---|
| `_mission_status_memo.py` | `ResolverMemo` (created per run), `MemoEntry` (raw outcome: a directory or the exception; the subprocess count of the call), `memo_resolve(memo, repo_root, name)` (the one place the resolver is called), the counting context (a `pytest.MonkeyPatch` around `subprocess.Popen.__init__`), the marker the FR-007 stub tests for ("the resolver call is on the stack") | `specify_cli.status.aggregate` (`MissionStatus`), `specify_cli.coordination.surface_resolver` (the exception classes) |
| `_mission_status_project.py` | `build_project(repo_root, memo, *, source=...) -> ProjectOutcome`; `project_version`, `schema_version_of`, `health_of`, `read_head`, `current_branch_of`, `last_activity_of`; the four v1 fallbacks on the raw outcome | the memo, `ProjectMetadata`, `get_project_schema_version`, the schema constants, `_mission_status_payloads` (`load_source` only for the equality control in the tests, never in the builder) |
| `_mission_status_drift.py` | `scan_drift(repo_root, memo, *, mission_id=None, clock, listing=...) -> DriftOutcome(status, body, fallbacks, legacy_manifests)`; `resolve_scan_dir` (the strict sibling); `completion_of`; `kind1`, `kind2`, `kind3`; `classify_manifest`; `fixed_summary`; `sort_and_cap`; the file-system seam | the memo, `materialize_snapshot`, `materialize_to_json`, `read_lanes_json`, `LanesManifest`, `load_meta_fail_closed`, `derive_mission_lifecycle`, `code_lane_branch_name`, `now_utc`, `leak_scan.malformed_artifact_path` (by file path through the loader) |
| `_mission_status_ops.py` | `list_ops(repo_root, *, profile, page_size, cursor, fs) -> OpsOutcome(status, body, skipped_ids)`; `candidates_of`, `read_op`, `closure_of`, `classify_evidence`, `redact_evidence`, `keyset_cursor`; the validator of the open/closed invariants | `parse_op_event`, `LegacyRecordError`, `read_op_closures`, `closed_invocation_ids`, `normalise_ref` (classification input), `redact_emails`, `SECRET_PATTERNS`, the v1 projector (page info) |
| `_mission_status_oracles.py` | independent oracles: `oracle_kind12`, `oracle_kind3`, `oracle_fallbacks`, `oracle_ops`, `oracle_evidence`; the `UnicodeDecodeError` wrapper of the classifier | the memo (raw outcome only), `classify_status_json`, `is_mission_completed`, `materialize_snapshot`, `derive_mission_lifecycle`, `parse_op_event`; **never** the project, drift or ops reader |

Entry points return an outcome (a status and a body, or a typed refusal), never raise for a refusal. Public readers only; the one private name in the test tree is `_reset_remote_branch_lookup_cache` (the offline fixture, FR-026). The reader's own code never calls `materialize`, `InvocationWriter` or `append_to_index`; the tests replace each by a function that raises.

## C. Mutation catalogue (the proof kind M of the plan's test strategy)

A mutation is a context manager in the test module that replaces one reader function or branch by its defective twin; the rows named in the right column must go red, else the test fails with `the mutation was not killed: <name>`. Each reader work package ships the whole catalogue of its reader.

| Reader | Mutation (name) | Rows that must go red |
|---|---|---|
| project | `wrap-cli-version` (call `get_project_version` instead of the metadata reader) | AC-PROJECT 1, 2 |
| project | `unguarded-load` (call `ProjectMetadata.load` without the shape pre-check and without catching `AttributeError` or `TypeError`; plan D-P4) | AC-PROJECT 1 |
| project | `equality-health` (healthy only when the schema equals the minimum) | AC-PROJECT 4 |
| project | `invent-branch` (null on unborn, or a subprocess for HEAD) | AC-PROJECT 5, 7 |
| project | `string-max-activity` (maximum by text) | AC-PROJECT 6 |
| project | `no-fallback-outside-root` | AC-PROJECT 7 (equality with v1) |
| drift | `variant-confusion`, `no-generation-gate` (replay at the current generation) | AC-DRIFT 1, 20 |
| drift | `read-lanes-before-completion` | AC-DRIFT 10 |
| drift | `expect-both-branches`, `expect-mission-branch-only`, `remote-ref-counts` | AC-DRIFT 7, 8 |
| drift | `per-branch-subprocess`, `list-without-expected-lane` | AC-DRIFT 13 |
| drift | `fallback-on-any-exception` (the v1 helper's catch list) | AC-DRIFT 14, 17, 18 |
| drift | `completion-from-read-directory` | AC-DRIFT 19 |
| drift | `forward-source-text` (a summary or a branch name from the source) | AC-DRIFT 24 |
| drift | `unsorted`, `cap-off-by-one` | AC-DRIFT 23 |
| drift | `call-materialize` | AC-DRIFT 27 |
| ops | `ascending-order`, `index-profile-filters` | AC-OPS 1, 5 |
| ops | `cli-closure-gap` (read only the Op's own file) | AC-OPS 6 |
| ops | `drop-skipped-record-from-count`, `count-follows-filter` | AC-OPS 3, 4 |
| ops | `redact-before-credential-check`, `mask-credential`, `skip-url-userinfo` | AC-OPS 10, 11 |
| ops | `eager-500-on-legacy`, `empty-on-oserror` | AC-OPS 8, 9 |
| ops | `quadratic-redaction` (the pre-fix pattern) | AC-OPS 14 |
| ops | `cache-the-result` (the entry point memoises its result across calls; plan D-P16) | AC-OPS 14, AC-CROSS 4 (the 30 s listing case in the ops module; the real 5 s listing case in the reality module, where the same mutation is applied as a context manager; plan-round ruling 9) |

## D. Test map (three new modules; the existing modules edited)

| Concern | Home | Run by | Markers |
|---|---|---|---|
| Project builder, memo, v1 equality, description checks, metadata and HEAD matrices | `tests/contract/test_mission_status_project.py` (new, IC-03) | `tests (contract tools)` | `contract`, `corpus`, `git_repo` (not `fast`); module-level `pytestmark` |
| Drift reader: kinds 1 to 3, read directory, fallback, strict sibling, offline row, 500 matrix, order and cap, summaries, no dead value | `tests/contract/test_mission_status_drift.py` (new, IC-07) | `tests (contract tools)` | `contract`, `corpus`, `git_repo`; module-level `pytestmark` |
| Ops reader: order, cursor, candidate set, closure, skipped, evidence, credentials, timed cases, no dead value | `tests/contract/test_mission_status_ops.py` (new, IC-08) | `tests (contract tools)` | `contract`, `corpus`; module-level `pytestmark` |
| Contract-level proofs: frozen-copy pair, path keys and tags, CHANGELOG sections and qualified names, scope data, dependency check | `tests/contract/test_mission_status_contract_1_1.py` (edited, IC-01, IC-03, IC-06) | `tests (contract tools)` | unchanged (`contract`, `fast`, `corpus`) |
| Examples, required cases, path keys | `tests/contract/test_mission_status_examples.py` (edited, IC-03 to IC-05) | `tests (contract tools)` | unchanged |
| Tool extension | `test_fixture_builder.py`, `test_leak_scan.py`, `test_run_negative_cases.py`, `test_enum_pin_check.py` (edited) | `tests (contract tools)` | unchanged |
| The ratchet edits of v1 tests | `test_mission_status_payloads.py` (the five-property `derive_project` check), `test_mission_status_reality.py` (the Project build) (edited, IC-03) | `tests (corpus-blocking)` | unchanged |
| Corpus reality check: oracles, named lists, floors, offline skip (resolver-dependent assertions only), fingerprints; **every corpus-sized case**: AC-DRIFT 19's completion equality and AC-CROSS 4's real-directory, Project-build and scan bounds, each with a discovered-count guard (plan-round ruling 4) | `tests/contract/test_mission_status_reality.py` (edited, IC-09) | `tests (corpus-blocking)` | unchanged |

The three new modules above are **fixture-built only**: they read no corpus directory (the tool job is documented as reading none) and carry their own controls. Their `pytestmark` is one single-line list holding `pytest.mark.corpus` (plan D-P5), the form `_CORPUS_MARK_APPLICATION_RE` of the registry gate matches.

Registrations (outside the spec's file set, plan PD-2): each new module needs one `--deselect tests/contract/<module>` in the `built-in-corpus-suite` command of `.github/workflows/packs.yml` and one row in `_CORPUS_MARKED_MODULES` of `tests/architectural/test_ci_corpus_trigger_completeness.py`, written in the commit that creates the module, in sorted position. The modules carry no `fast` marker: the nightly `fast or unit` selection runs on a checkout without tags and expects sub-second pure tests (R-10), which these are not. A module without a module-level `pytestmark` is a defect even when its tests carry a marker each (a corpus reader never marked is silently never run by the corpus lanes).

## E. Fixtures: the families of FR-026 and where each is built

Fixture repositories use real git where git matters (the resolver, the branch listing, HEAD states) and `write_fixture_mission` otherwise (it writes `meta.json`, `status.events.jsonl` from `rows`, `lanes.json` from `lanes`, and any other file through `files`, so `status.json` and invalid-UTF-8 bytes are written through `files`).

| Family | Built in | Notes |
|---|---|---|
| Metadata shapes of FR-002; schema versions around the range including a float and a boolean; every HEAD state; a strict host-path branch name; activity at different offsets | project module | linked worktree through `git worktree add` in a scratch repository |
| One Mission per drift kind plus a clean control; the `status.json`, `meta.json` and `lanes.json` shapes of AD-10, each on a completed and on a non-completed Mission; generation pair; invalid UTF-8 in each of the four files | drift module | each plant has a same-fixture control |
| The coordination pairs (branch present, branch absent, `mission_branch` absent with the coordination branch present; primary copy stale beside coordination copy stale; `merged_at` in the own copy only beside the coordination copy only) | drift module | real git; the memo's two-repository test lives in the project module |
| The fallback and every other resolver outcome; the offline row (a remote whose URL is a non-existent local path; the probe cache reset between control and plant) ; one fixture per resolver arm the derivation does not mirror (a reopened Mission, a stored topology that does not use the coordination surface, a branch present only as a remote-tracking ref, one present only on a reachable remote) | drift module | the patched-resolver fixtures raise the other three exceptions and the outside-root case |
| 1001 and exactly 1000 findings | drift module | shuffled creation order |
| Every `kitty-ops/` shape of FR-017 to FR-020: absent; with and without index; own and spine closures; legacy lines; unreadable files beside a readable one; a vanished file; an index entry naming no file; an index line whose profile differs from its file's; invalid UTF-8 in an Op file and in the spine; an unreadable spine; equal `startedAt`; `mission_id` and `wp_id` present; each `modeOfWork` | ops module | unreadable files through a fault-injecting seam, never a permission change |
| Every evidence class and credential shape; three 256 KiB shapes; a 10,000-file directory | ops module | planted values assembled at run time from fragments |

## F. Floors in code and pinned fixtures

The frozen pre-slice tree `tests/contract/fixtures/mission_status_pre_slice/` mirrors the contract layout (`schemas/Project.yaml`, `examples/Project.example.yaml`, `paths/project.yaml`), so no two names in one directory differ only by letter case. `FLOORS` gains (IC-09, where the reality check consumes them, and never re-pinned): `drift_missions` 540, `ops_served` 440, `ops_spine_closed` 5, `evidence_none` 330, `evidence_absolute` 28, `evidence_text` 50, `evidence_relative` 25, `kind1_findings` 39, `kind2_findings` 27, `completion_non_coord` 490 (the guard of AC-DRIFT 19: Missions declaring no coordination branch compared). The existing floors stay. No kind-3 floor and no fallback floor exist. A new fixture `tests/contract/fixtures/mission_status_health_drift_ops_expected.json` lists the seven Op ids with a legacy completion and no spine record and the one legacy-shaped manifest Mission by name; each named entry must still be present and behave as stated (a subset check; an unnamed new anomaly is printed, never a failure).

## G. Stable test-failure messages

Every new corpus-level assertion states its examined and discovered counts in its failure text and fails when either is zero. A fault-injection test fails with `the injected fault did not fire` when its counter is zero. A mutation test fails with `the mutation was not killed: <name>`. The offline skip reads `skipped: no configured remote is reachable (git ls-remote --heads failed); resolver-dependent assertions only; offline runs are not evidence for SC-002 or SC-007` (the Ops walk, `skippedCount` equality, the Ops floors, the AC-DRIFT 19 completion equality, the real `kitty-ops/` listing bound and the fingerprints run and do not carry it; the one-`Project`-build, one-scan and combined timing cases do carry it). A timing failure states the minimum over the repeats, the repeat count and the bound (`min of 5 = 0.13 s > 0.1 s`). A corpus-condition failure names the Mission (`declares a coordination branch present only on a remote: <name>`).
