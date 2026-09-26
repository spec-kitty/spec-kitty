---
work_package_id: WP04
title: Non-vacuous drain arch gate + NFR-001/NFR-004 posture matrix integration walk
dependencies:
- WP02
- WP03
- WP05
requirement_refs:
- NFR-001
- NFR-002
- NFR-004
- FR-010
planning_base_branch: claude/spec-kitty-mission-impl-8u6zmc
merge_target_branch: claude/spec-kitty-mission-impl-8u6zmc
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-mission-impl-8u6zmc. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-mission-impl-8u6zmc unless the human explicitly redirects the landing branch.
subtasks:
- T017
- T018
- T019
- T020
history: []
agent_profile: python-pedro
authoritative_surface: tests/
create_intent:
- tests/architectural/test_hosted_drain_gate.py
- tests/integration/test_hosted_posture_matrix.py
execution_mode: code_change
model: claude-opus-5-5
owned_files:
- tests/architectural/test_hosted_drain_gate.py
- tests/architectural/test_egress_consent_boundary.py
- tests/integration/test_hosted_posture_matrix.py
role: implementer
tags: []
tracker_refs: []
---

# WP04: Non-vacuous drain arch gate + NFR-001/NFR-004 posture matrix integration walk

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

**Hard lens for this WP**: this is a *gate-authoring* WP, not a feature WP. Every test you write must be provably non-vacuous — a floor that can be zero is not a floor, and a self-mutation test that has never been observed to fail is decoration (see `packs/built-in/tactics/architectural-gate-non-vacuity.tactic.yaml` and `packs/built-in/tactics/frozen-baseline-shrink-only-ratchet.tactic.yaml`, both under `packs/built-in/tactics/`). Read both tactic files before writing `test_hosted_drain_gate.py`.

---

## Objective

Prove, structurally and end-to-end, that "drain off" really means "zero hosted network attempts" (NFR-001) and that the gate proving it cannot pass vacuously (NFR-002), and prove that flipping ledger/drain posture never perturbs lane-FSM state or its committed artifacts (NFR-004, FR-010). This WP is the mission's verification capstone: it depends on WP02 (relay edges), WP03 (gateway + fan-out + producer + live_work + routes edges) and WP05 (ledger projection + hook sites) all being landed, because it tests their combined behavior rather than adding new production code of its own.

## Context

The plan (`plan.md`, Post-plan squad folds F-1..F-8) placed the drain gate at specific, narrow points rather than at module boundaries:

- **F-1 — relay gate placement**:
  - `transport.ZeitgeistClient.offer` gates *before* `run_with_deadline`.
  - It returns a new `OfferOutcome.DRAIN_DISABLED` — no worker thread spawned.
  - It is never misclassified as `DROPPED_UNREACHABLE`.
  - `filtered_stream.py`'s snapshot/watch methods and `history.py`'s fetch call `NoRedirects.build()` directly and raise `DrainDisabled`.
  - `operability.timeout_drill` reports `skipped: drain off`.
  - Relay CLI/MCP commands map `DRAIN_DISABLED`/`DrainDisabled` to one guidance line.
- **F-2 — gateway gate placement**:
  - `SaasCapabilityGateway.check_repo_admission` and `.mint_capability` gate individually.
  - The gate is not in `__init__`, so the `_http=` test seam stays intact.
  - `resolve_credentials`/`resolve_focus_capability` return `None` **before any cache read**, logging a distinct debug reason `drain-off`.
  - `spec-kitty routes` is drain-gated (it mints) and prints "Live drain is off…".
- **F-3 — projection hook sites** (background for T019, not something T017/T018 change):
  - Flat path: `refresh_execution_projection` is called directly next to `emit.py`'s `_saas_fan_out` sites.
  - Transactional path: it is registered as a post-commit deferred outbound (`txn.defer_outbound`) next to every `_defer_fan_out`/`queue_saas_emission` site in `coordination/status_transition.py` (~5 sites).
  - This is the path this WP's NFR-004 test must exercise, not just the flat path.
- **F-4 — single derived-view writer** (background): `write_derived_views`/`generate_progress_json`/`generate_lifecycle_json` take an optional `snapshot:` parameter so the refresh never rewrites tracked `status.json`.

**The concrete floor.** From `spec.md` NFR-002: *"relay opener used by the control POST, stream GET ×2 and history GET, plus the capability-gateway HTTP client"* — i.e. at least 5 named, currently-gated edges. Before writing the registry:

- Read `src/specify_cli/zeitgeist_client/transport.py::ZeitgeistClient.offer`.
- Read `src/specify_cli/zeitgeist_client/filtered_stream.py` for the snapshot and watch methods.
- Read `src/specify_cli/zeitgeist_client/history.py` for the fetch method.
- Read `src/specify_cli/zeitgeist_client/resolution.py::SaasCapabilityGateway.check_repo_admission` and `.mint_capability`.
- Trust the merged WP02/WP03 code over this prompt if the two disagree — WP02/WP03 land before this WP starts, and their real method names are authoritative.

**Relationship to the existing #3030 sink-scan gate.** `tests/architectural/test_egress_consent_boundary.py` (read in full before touching it) is the sibling gate:

- It classifies HTTP/urlopen/websocket/transport calls by **file**, not by "is this gated."
- It is allowlisted per file with a named consent seam (`AllowanceKind.SEAM`/`NOT_PROJECT_DATA`/`LOOPBACK_CONTROL`/`TRANSPORT_ONLY`/`UNREACHABLE`).
- The relevant existing row is `specify_cli/zeitgeist_client/resolution.py` (`NOT_PROJECT_DATA`, inventory id `E3-#9`); its `note` currently explains only the *credential-exchange* reasoning (team membership over Bearer auth), predating drain.
- T018 is a **documentation-only** update to that row's `note` — do not change `kind`, `seam_symbol`, or remove the row — plus a docstring cross-reference.
- Drain is a *narrower* precondition layered in front of the same consent answer, not a replacement for it.
- `test_hosted_drain_gate.py`'s sink vocabulary (only the relay/gateway openers) is deliberately narrower than `test_egress_consent_boundary.py`'s (every HTTP/urlopen/websocket/transport-call shape across all of `src/`).
- The two gates check different, complementary things; neither subsumes the other.

## Subtask T017: `tests/architectural/test_hosted_drain_gate.py` — non-vacuous drain gate

**Purpose**: Build a new AST-scan architectural gate proving every hosted relay/gateway network edge calls `require_drain`/`drain_posture` (or is a documented gated entry) before it can reach the network, with a concrete floor, a shrink-only allowlist, and a red-first self-mutation test — following `architectural-gate-non-vacuity` exactly.

**Steps**:

1. Model the new file on `tests/architectural/test_egress_consent_boundary.py`'s shape:
   - AST scan.
   - Allowlist.
   - Meta-tests.
   - `TestGuardBites`-style negative controls.
   - Scope it narrowly to `src/specify_cli/zeitgeist_client/**` plus the relay/gateway call sites named in D2/F-1/F-2 of `plan.md`.
   - Do not re-implement the sink-vocabulary scanner from `test_egress_consent_boundary.py` — this gate is a *gate-call* scan (does the function call `require_drain`/consult `drain_posture` before its relay-opener/`httpx` call), not a sink scan.
2. Define the gated edges as an explicit, named registry (a `frozenset[str]` or a `dict[str, GatedEdge]`) keyed by fully-qualified function (module + qualname). Expected members, pending confirmation against merged code:
   - `specify_cli.zeitgeist_client.transport.ZeitgeistClient.offer`
   - `specify_cli.zeitgeist_client.filtered_stream.<snapshot method>`
   - `specify_cli.zeitgeist_client.filtered_stream.<watch method>`
   - `specify_cli.zeitgeist_client.history.<fetch method>`
   - `specify_cli.zeitgeist_client.resolution.SaasCapabilityGateway.check_repo_admission`
   - `specify_cli.zeitgeist_client.resolution.SaasCapabilityGateway.mint_capability`
   - Read the merged WP02/WP03 source to get the exact method names — do not guess if `filtered_stream.py`/`history.py` name their methods differently than "snapshot"/"watch"/"fetch".
   - `assert len(_GATED_EDGES) >= 5` is the concrete floor (NFR-002's named floor).
   - This assertion must be a real integer, not derived from the registry's own length trivially matching itself — justify the "5" against the NFR-002 acceptance text in a comment.
3. For each registered edge:
   - AST-parse its enclosing function/method.
   - Assert the function body contains a call whose callee resolves (by attribute-tail or `ast.Name`) to `require_drain` or `drain_posture` (from `specify_cli.core.hosted_posture`).
   - The gate call must be positioned before the first relay-opener call (`NoRedirects.build(`/`open_bounded(`) or `httpx`-client-construction call in that same function.
   - Do not require it to be the *first* statement — F-2 places it inside `check_repo_admission`/`mint_capability`, not `__init__`, so the scan must look inside each named method body, not just at class-level `__init__`.
4. **Self-mutation test** (required by the tactic, must be genuinely red-first):
   - Copy the real gated source file (e.g. `transport.py`) into a `tmp_path`.
   - Use a regex or targeted AST transform to strip out the line(s) that call `require_drain`.
   - Write the mutated copy and run the scanner against it.
   - Assert the scanner reports the mutated function as ungated.
   - Before committing: run this once manually against the *unmutated* file to confirm it is currently green, then apply the strip and confirm it reds.
   - Record in your PR/notes that you observed the red state, matching the tactic's "Confirm the self-mutation check holds red-first" step.
5. **Negative control**: a synthetic passing case — a small tmp module with a function that both calls `require_drain` and then opens a relay — must be classified as gated (mirrors `TestGuardBites::test_allowlisting_the_same_sender_clears_it` in the sibling gate). Without this, an always-red scanner would pass every other test while proving nothing.
6. **Shrink-only allowlist**:
   - A `frozenset[str]` (or per-edge dict) recording any edge intentionally exempt from the gate.
   - Expect this to be empty or near-empty at authoring time — do not pre-populate it to make the gate pass.
   - If WP02/WP03 left a real edge ungated, that is a finding to report, not to allowlist away.
   - Register its size in `tests/architectural/_baselines.yaml` under a new key (e.g. `test_hosted_drain_gate.gated_edge_allowlist`) per `frozen-baseline-shrink-only-ratchet`, with a `# justification:` comment if non-zero.
7. Add `pytestmark = [pytest.mark.architectural]` at module level, matching the sibling gate.
8. Cross-link the module docstring to `contracts/hosted-posture.md` and `plan.md`'s F-1/F-2, and name NFR-002's exact floor wording.

**Files**: new file, ~250–350 lines including docstring, registry, scanner, meta-tests, self-mutation test, negative control.

**Validation**: `pytest tests/architectural/test_hosted_drain_gate.py -v` all green; manually verify (and note in the PR) that the self-mutation variant reds before the final commit lands it passing; `pytest tests/architectural/test_ratchet_baselines.py -v` green after the `_baselines.yaml` addition.

## Subtask T018: Update `tests/architectural/test_egress_consent_boundary.py`

**Purpose**: Cross-reference the new drain gate from the existing #3030 sink-boundary gate so a reader of either understands the other exists and neither is assumed to subsume the other, without weakening or renaming the existing allowlist entry.

**Steps**:
1. Read the `specify_cli/zeitgeist_client/resolution.py` entry in `_EGRESS_ALLOWLIST` (around line 589 in the current file — confirm the line number against the live file, it may have shifted) and its `note`. Append a short paragraph (do not delete existing text) explaining that `tests/architectural/test_hosted_drain_gate.py` (new, this mission) additionally requires `check_repo_admission`/`mint_capability` to consult `drain_posture`/`require_drain` before this same HTTP client is used — the two gates check different, narrower-vs-broader vocabularies (drain gate: named relay/gateway functions call the drain check; consent-boundary gate: every file under `src/` holding an HTTP/urlopen/websocket/transport-call sink is reasoned about) and are complementary, not redundant.
2. Do **not** change `kind`, `seam_symbol`, or remove/rename the row — this is additive documentation only. Do not touch any other allowlist entry.
3. Add one sentence to the module docstring's "Spec" line or a new short paragraph noting the drain gate exists as a sibling for the hosted-relay/gateway edges specifically (this file's own sink vocabulary does not see `.open(req)`-style calls the relay opener uses, by design — it only sees the sink shapes in its own vocabulary list).
4. Check `tests/architectural/_baselines.yaml` for any keys this module owns (`test_egress_consent_boundary.egress_allowlist_files`, `test_egress_consent_boundary.known_ungated_files`) — this WP must not grow either baseline. If your doc-only edit is truly additive (no allowlist membership change), both stay unchanged; confirm this by running the ratchet test after your edit.

**Files**: `tests/architectural/test_egress_consent_boundary.py`, docstring/note edits only, +10–20 lines.

**Validation**: `pytest tests/architectural/test_egress_consent_boundary.py -v` all green (unchanged pass count); `pytest tests/architectural/test_ratchet_baselines.py -v` green with no baseline diff required.

## Subtask T019: `tests/integration/test_hosted_posture_matrix.py` — NFR-001/NFR-004 end-to-end matrix

**Purpose**: A realistic, fully-instrumented integration test proving zero hosted network attempts when drain is off (NFR-001) and byte-for-byte/commit-count identity of every durable lane-FSM artifact across all four `{ledger on/off} × {drain on/off}` combinations (NFR-004), on both a flat mission and a coordination-topology mission.

**Steps**:

1. Reuse existing scaffolding before writing new fixtures:
   - `grep -rl "planned.*claimed.*in_progress\|nine.lane\|9.lane" tests/status tests/integration tests/cli --include="*.py"`.
   - Study how `tests/status/`'s existing integration tests build a temp repo, initialize `.kittify/`, and drive `emit_status_transition`.
   - Search `coordination` under `tests/` for an existing coord-topology fixture rather than hand-rolling worktree/coord-branch setup from scratch.
2. Structure the module:
   - One pytest module, parametrized `@pytest.mark.parametrize("ledger_on", [True, False])` × `@pytest.mark.parametrize("drain_on", [True, False])` × `@pytest.mark.parametrize("topology", ["flat", "coord"])` — or a single combined parametrize list of the 8 cells if the fixture cost is high.
   - Mark the module `pytest.mark.integration` and `pytest.mark.slow` (check the `pytest.ini` markers list before picking; a full mission lifecycle walk clears the "expected to take >30 seconds" bar for `slow`).
3. For each cell, build the fixture:
   - Create a temp git repo mission (flat, or with a coordination topology per the `topology` param).
   - WP05's coord-path hook registration is only exercised by the `coord` cases per F-3 — do not skip them.
   - Write the two posture-controlling files under a tmp `SPEC_KITTY_HOME`/`config.toml` (`[hosted] drain = <bool>`) and `.kittify/config.yaml` (`hosted.drain: <bool>`, `ledger.projection: <bool>`) per `contracts/hosted-posture.md`'s truth table.
4. Drive the walk for each cell:
   - Full 9-lane walk: `planned → claimed → in_progress → for_review → in_review → approved → done`.
   - Plus a `blocked` transition.
   - Plus a `canceled` transition from a second WP (per the 9-lane state machine in CLAUDE.md).
   - Plus one decision open/resolve round-trip (check `src/specify_cli/decisions/` or `events/decision_log.py` for the decision API — it must remain **unaffected** by drain/ledger per D3's arch guard, so use it as-is).
5. **Network instrumentation** (NFR-001):
   - Monkeypatch the actual opener-construction points: `specify_cli.zeitgeist_client.budget.NoRedirects.build` (or wherever `open_bounded` lives post-WP02) and `httpx.Client.send` (the method `SaasCapabilityGateway`'s injected `_http=` client ultimately calls).
   - Raise/record on any invocation — do not fake a successful response.
   - Assert **zero** calls across the whole 9-lane-plus-decision walk when `drain_on=False`, for every `ledger_on` value and both topologies.
   - When `drain_on=True`, do not assert zero. Let the instrumentation fail closed harmlessly (e.g. raise `RuntimeError` inside the monkeypatch and catch-log it) — this mission has no server, so a real send should never succeed, but a *drain-off* attempt must never even be tried.
6. **FSM-integrity assertions** (NFR-004): after the full walk, for each `ledger_on × drain_on` pair (holding topology fixed), compare across all 4 combinations:
   - (a) The lane-ledger file bytes (`status.events.jsonl`) are byte-identical modulo timestamps/event_ids if those are randomized — if so, compare the reduced/materialized snapshot instead of raw bytes for the fields that vary, and compare raw bytes for everything else.
   - (b) The tracked `status.json` bytes (kitty-specs status, not the derived projection) are identical.
   - (c) The status-ref/coord-branch commit count is identical.
   - (d) `reduce(read_events(...))` (the Lamport reducer, per `status/reducer.py`) produces an identical snapshot.
   - Use a stable actor/clock injection if the codebase supports one (check `src/kernel/clock.py` or similar) so timestamps are deterministic across cells rather than filtered out — prefer determinism over exclusion.
7. **Ledger-on assertion**:
   - When `ledger_on=True`: assert `.kittify/derived/<mission>/status.json` (and `board-summary.json`) exist after the walk and match the reduced snapshot (per D3/F-4's `refresh_execution_projection`).
   - When `ledger_on=False`: assert the derived directory is **not** created by the emits themselves, then separately run `spec-kitty materialize` (or the equivalent CLI/programmatic entry point — check `cli/commands/` for the actual command name) and assert it now produces the derived view.
   - This proves ledger-off means "no automatic refresh," not "the projection is broken."
8. **Real-default case**: add one additional, non-parametrized test using the `canonical_home` fixture (search `conftest.py` for it) with **no** drain config written at all, proving the file-based real default resolves to drain off (per D1's default-off contract) — this is the "no drain configuration ⇒ off" acceptance line from `contracts/hosted-posture.md`.
9. Fixture ownership caveat: if WP08's `drain_on`/`drain_off` autouse fixtures (F-8, landing in `tests/zeitgeist_client/conftest.py`, `tests/status/conftest.py`, `tests/specify_cli/live_work/conftest.py`) already exist by the time you implement this, do **not** rely on them here — this test needs explicit, per-cell control of posture, not an autouse default, so write the posture files directly.

**Files**: new file, ~300–450 lines given the 8-cell matrix plus the two extra tests; expect this to be the largest file in the WP — if it grows past ~500 lines, split shared fixtures into a `tests/integration/conftest.py` addition (check it doesn't already exist and collide) rather than a second test module, to keep the acceptance surface in one file per the mission's IC-03 grouping.

**Validation**: `pytest tests/integration/test_hosted_posture_matrix.py -v -m "integration"`; confirm all 8 parametrized cells plus the 2 extra tests pass; confirm the network-instrumentation assertion actually fires (temporarily comment out one gate call locally to prove the test catches a real regression, then restore — do not commit the broken state).

## Subtask T020: Validation — full suite, terminology, lint

**Purpose**: Close the WP with the mission's standard exit checks, scoped to this WP's blast radius plus the cross-cutting architectural suite this WP's own owned files require.

**Steps**:
1. Run the new tests directly: `pytest tests/architectural/test_hosted_drain_gate.py tests/architectural/test_egress_consent_boundary.py tests/integration/test_hosted_posture_matrix.py -v`. Record pass counts.
2. Run `tests/architectural/` in full (this WP touches two files under `tests/architectural/`, which is a cross-cutting-adjacent change per CLAUDE.md's blast-radius rule — architectural-suite files always warrant the full suite): `pytest tests/architectural/ -v`. Attribute any red that is not yours per the baseline-red gotcha (check the same test against `upstream/main`/merge-base before assuming it is pre-existing).
3. Run `make test-fast` as the shared baseline.
4. Run the terminology guard since this WP touches doctrine-adjacent test prose: `pytest tests/architectural/test_no_legacy_terminology.py -v`.
5. Run `ruff check .` and `ruff format --check .` (or `make format-check`) over the touched files at minimum, and ideally the whole repo per the project's zero-issues policy.
6. Run `mypy` over the three touched files (or the project's standard mypy invocation if narrower scoping isn't supported) — new code must pass `mypy --strict` per CLAUDE.md.
7. Record every command and its pass/fail count under a `## Tests run` section in your final report/PR description, per the project's Test policy (§6 in the git-workflow section of CLAUDE.md).

**Files**: none (validation-only subtask).

**Validation**: all listed commands green, or every red attributed per the baseline-red gotcha with a named reason (pre-existing P0, CI-environment-only, stale install/venv).

## Definition of Done

- [ ] `tests/architectural/test_hosted_drain_gate.py` exists, is `pytest.mark.architectural`, asserts a concrete non-zero floor (≥5 named gated edges) derived from the merged WP02/WP03 code, carries a shrink-only allowlist registered in `_baselines.yaml`, and includes a self-mutation test that was manually confirmed red-first before being committed passing, plus a positive (allowlisted/gated) negative-control case.
- [ ] `tests/architectural/test_egress_consent_boundary.py`'s `resolution.py` allowance note is updated to cross-reference the new drain gate, with no change to `kind`/`seam_symbol` and no baseline growth in `_baselines.yaml`.
- [ ] `tests/integration/test_hosted_posture_matrix.py` exists, exercises the full 9-lane walk (planned→claimed→in_progress→for_review→in_review→approved→done, plus blocked and canceled) plus one decision open/resolve round-trip, parametrized over all 4 `{ledger on/off}×{drain on/off}` combinations on both a flat and a coordination-topology mission, with every hosted network edge instrumented and asserting **0** hosted requests when drain is off, plus one additional no-config-at-all real-default test under `canonical_home`.
- [ ] The NFR-004 identity assertions (lane-ledger bytes, tracked `status.json` bytes, status-ref commit count, reduced snapshot) pass identically across all 4 combinations, on both topologies.
- [ ] Ledger-on produces a refreshed `.kittify/derived/<mission>/` matching the reduced snapshot; ledger-off does not auto-create it but `spec-kitty materialize` (or the equivalent command) still can.
- [ ] Each subtask's completion is recorded via `spec-kitty agent tasks mark-status <Txxx> --status done`.
- [ ] `make test-fast`, the full `tests/architectural/` suite, the terminology guard, and `ruff`/format/mypy are all green or every red is explicitly attributed per the baseline-red gotcha, with commands and counts recorded.

## Risks

- **Method-name drift from WP02/WP03.**
  - This prompt names `filtered_stream`'s snapshot/watch methods and `history`'s fetch method descriptively, not authoritatively — the real names may differ once WP02/WP03 land.
  - Mitigation: read the merged source before writing the gated-edge registry.
  - Do not hardcode names from this prompt without confirming them against `git log`/the actual files.
- **Vacuous self-mutation test.**
  - The single easiest way to fail NFR-002's intent while looking green is to write a self-mutation test that patches something the scanner never actually inspects (e.g. mutating a docstring instead of the gate call).
  - Mitigation: the manual red-first confirmation step in T017.4 is mandatory, not optional — do not skip it because "the test passed."
- **Flaky timestamp/ID randomness breaking NFR-004 byte-identity.**
  - Event IDs (ULID) and timestamps are generated fresh per run and will differ across the 4 cells unless clock/ID generation is injected deterministically.
  - Mitigation: T019 step 6 calls for injecting a stable clock/actor if the codebase supports it.
  - If it does not, fall back to comparing the *reduced snapshot* (which should normalize timestamps into ordering, not literal equality) rather than raw JSONL bytes for the timestamp-bearing fields.
  - Say so explicitly in code comments — do not silently exclude fields without a comment explaining why.
- **Coordination-topology fixture cost.**
  - Building a coord-topology mission from scratch inside this test is expensive and easy to get subtly wrong (worktree/coord-branch setup has many invariants elsewhere in the codebase).
  - Mitigation: T019 step 1's search-first step is not optional — reuse whatever coordination integration fixture already exists rather than reconstructing paths the resolver should provide (per CLAUDE.md's "Use Canonical Sources" rule).
- **Test runtime.**
  - An 8-cell full-lifecycle matrix plus a decision round-trip, run twice (flat + coord), is genuinely slow.
  - Mitigation: mark the module `slow`/`integration` per `pytest.ini`'s existing marker vocabulary so it is excluded from the fast tier and CI can schedule it appropriately.
- **Allowlist creep in the new gate.**
  - It is tempting to allowlist an edge the implementer cannot easily wire (e.g. a hard-to-reach private method) rather than fixing it.
  - Mitigation: the shrink-only-ratchet baseline entry makes any such allowance a visible, justified YAML diff, not a silent exemption — treat a non-zero allowlist at authoring time as a finding to raise with the reviewer, not a convenience.

## Reviewer Guidance

- **Verify the self-mutation test actually reds.**
  - Do not take "the test suite is green" as sufficient.
  - Checkout the WP branch, temporarily strip the `require_drain` call from one gated function by hand, re-run `test_hosted_drain_gate.py`, confirm it fails with a clear message naming the ungated function, then restore.
  - This is the single highest-value check for this WP because a vacuous gate is worse than no gate (it creates false confidence).
- **Verify the floor is real, not tautological.**
  - The `>= 5` (or whatever number lands) must correspond to actually-gated production functions that exist in the merged WP02/WP03 code — not to `len(_GATED_EDGES)` trivially equaling itself.
  - Cross-check the registry against the live `zeitgeist_client/` source.
- **Verify NFR-001's zero-egress claim is instrumented at the real opener, not mocked at a higher layer.**
  - A test that monkeypatches `ZeitgeistClient.offer` itself (rather than the socket-adjacent opener/`httpx.Client.send`) would prove nothing about drain-off correctness — it would just prove the mock was never called, which is trivially true if `offer` itself is skipped by the drain check before reaching the mock.
  - Confirm the instrumentation sits at `NoRedirects.build`/`open_bounded`/`httpx.Client.send`.
- **Verify NFR-004's identity claims compare the right artifacts.**
  - The *tracked* `status.json` under `kitty-specs/`, not the *derived* projection under `.kittify/derived/`.
  - The two must never be conflated per D3's arch guard.
- **Verify the `test_egress_consent_boundary.py` edit is purely additive.**
  - Diff it against the pre-WP04 version and confirm no `kind`, `seam_symbol`, or membership changed.
  - Confirm `test_ratchet_baselines.py` shows no diff.
- **Verify the coordination-topology cells are genuinely exercised, not skipped or trivially short-circuited.**
  - The coord-path projection hook (F-3) is the one behavior a flat-only test suite would miss entirely.
- **Confirm the reported Tests run section.**
  - The PR names concrete commands and pass/fail counts.
  - Any red is explicitly attributed (pre-existing P0 / CI-environment / stale install/venv) rather than silently dropped from the report.

## Implementation Command

```bash
spec-kitty agent action implement WP04 --agent claude
```
