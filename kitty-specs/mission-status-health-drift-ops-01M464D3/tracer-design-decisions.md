# Tracer: Design Decisions

Mission: `mission-status-health-drift-ops-01M464D3` (#5776). Operator rulings on #5776. Part of epic #5528.

## Operator rulings, 2026-10-05

The operator answered the ten open questions of issue #5776 with one line, recorded verbatim: "Accept all 10 (Recommended)".
Each question is therefore decided as its written recommendation. The rulings are binding, are not re-opened by the spec,
and no alternative to them is offered. The spec records them as OR-1 to OR-10; the rationale below is the issue's own.

- **OR-1 (Q1) Land the `Project` fields before 1.0.0.**
  Question: the `Project` fields are breaking once the contract is tagged; when does this slice land?
  Ruling: before the `1.0.0` tag. The fields are additive under `1.0.0-SNAPSHOT` and move out of "Deferred" in
  `contracts/mission-status/CHANGELOG.md`.
  Rationale: the breaking-change check treats an added response property as breaking, and no `contract-mission-status-v*`
  tag exists, so the Projects screen is served additively only now. Resolution recorded in the spec: five properties are
  added (the issue says "four" and tabulates five); only the project-branch line leaves "Deferred".
- **OR-2 (Q2) `lane_branch_missing` and `derived_view_stale` have no shipped check.**
  Ruling: keep both as provisional kinds with an `x-derived` rule and an example from the reality check. A kind without both
  is not shipped. If the reality check finds no honest rule for `derived_view_stale`, drop it and say so in the CHANGELOG.
  Rationale: the contract must not publish a kind that no check can produce on real data. Applied in the spec: `lane_branch_missing`
  ships with a rule that expects a branch only where the product would have created one, for a Mission not completed (the literal
  rule gives one finding per manifest whose branch is absent, most of them completed Missions: noise); `derived_view_stale` is dropped by the decision procedure of FR-013 (no
  `.kittify/derived/` in the corpus, it is gitignored; the product's own check is a permanent no-op).
- **OR-3 (Q3) Keep `laneComparison`.**
  Ruling: keep it, derived from the reducer, provisional.
  Rationale: the Drift screen's main panel is that table, and the doctor offers only strings.
- **OR-4 (Q4) Include the provenance-only and terminal drift warnings.**
  Ruling: include `SNAPSHOT_DRIFT_PROVENANCE` and `SNAPSHOT_DRIFT_TERMINAL` as `severity: warning` with `sourceCode` set; the screen may dim them.
  Rationale: hiding them would make the screen disagree with `spec-kitty doctor`.
- **OR-5 (Q5) A swept Op reads as closed.**
  Ruling: `closed` means a completed event in the Op file or on the closure spine (`closed_invocation_ids`). The CLI reader is fixed separately if it
  should match; the contract does not copy the gap.
  Rationale: `invocations list` reads only the Op's own file, so an Op closed by `doctor ops` shows open there. Measured: 6 Ops open in the CLI, closed in the contract.
- **OR-6 (Q6) `totalCount` accuracy.**
  Ruling: count from the index when present and from the directory scan otherwise; the description says the count can lag the newest records.
  Rationale: the index is a performance aid that silently degrades.
- **OR-7 (Q7) Drift findings are not paged.**
  Ruling: cap at 1000 with `truncated`, as the artifact listing does; revisit with that listing's paging decision.
  Rationale: a project with over 1000 findings needs a repair, not a better scroll.
- **OR-8 (Q8) `health` does not count drift errors.**
  Ruling: no; `/project` is read-only and independent of a scan (FRESH-005 dropped the word "cheap").
  Rationale: the Projects card shows schema health only; the Drift screen owns findings.
- **OR-9 (Q9) No badge code namespace.**
  Ruling: the screen shows `kind` and `sourceCode`; the contract invents no code namespace.
  Rationale: the prototype's two badge codes have no source in `src/`.
- **OR-10 (Q10) The host's reach into a project that is not open.**
  Ruling: a Kitty Desktop decision. The contract only promises that `GET /project` is read-only, side-effect-free and safe to call once per recent project, and states its cost (amended by FRESH-005, round 3, below: the word "cheap" is dropped).
  Rationale: whether the host starts one service per project or reads on demand is not a contract matter.

## Precedent rulings applied (from `mission-status-contract-1-1-01M42XJC`, #5625)

- **PR-1 No new contract version (2026-10-05).** `info.version` stays `1.0.0-SNAPSHOT`; the CHANGELOG additions merge into that section; the
  version proof becomes "additive against the contract tree on `main`". Applied here with one stated exception: `Project` gains properties, which the tooling
  reports as breaking (lowered-major scratch baseline: `breaking=` equals the non-provisional additions; same-major baseline: `BREAKING_WITHOUT_MAJOR`). The previous
  slice's `breaking=0` assertion does not carry over (FR-022).
- **PR-2 Enums are snake_case (2026-10-04).** The J-1 replay refused kebab-case `ArtifactKind` under the vacuum `enum-case` rule. Every new enum is snake_case and pinned.
- **PR-3 The JVM replay J-1 runs once the contract shape is final.** The spec states it as FR-028, over the new shapes, with the two scratch baselines.
- **PR-4 A named refused list, never a skip list (WP06 ruling a).** The corpus checks count examined plus named skipped equals discovered, with the list derived
  independently and a stale-entry check (FR-025): 7 Ops with a legacy completion line and 1 legacy-shaped `lanes.json` today.
- **PR-5 Linear e-mail redaction (2026-10-04).** `redact_emails` and `email_matches`, never `EMAIL_PATTERN`, with a timed regression (NFR-008).
- **Also applied:** oracle independence by AST test (D-P14); floors fixed at plan time and never re-pinned (spec D-P15); the closed-schema, one-citation, `x-provisional` plus
  CHANGELOG `Provisional` conventions of the v1 tree.

## Operator rulings (2026-10-05, round 2)

After the squad R1-R3 HALT the operator accepted every arbiter recommendation (`reviews/spec.ruling.md`). The rulings replace the acceptance bar of the findings they name and are not re-opened. One principle covers the cluster: **a broken derived file is a finding; a broken authority makes the read a 500; an older but valid shape is "not evaluated" under a stated rule and is counted on the named list (PR-4).** It is the line the precedent draws (fail closed, never a silent empty answer), applied to a scan of the whole project instead of one Mission's detail read.

- **ARCH-001: which Mission-level branch kind 3 expects for a coordination-topology Mission.**
  Question: should the rule expect `lanes.json`'s `mission_branch`, which the product never creates there?
  Ruling: option A. A Mission whose `meta.json` names a coordination branch expects that branch and never `mission_branch`; fixture pair (branch present, branch absent); the oracle reads `meta.json` itself.
  Rationale: the allocator's coordination arm creates the coordination branch only; AD-3 expects a branch only where the product creates one; the name is in `meta.json`, which the scan already opens. Option B would leave a lost coordination branch, the one holding the status, unreported.
- **ARCH-002: the `info` value of `DriftSeverity`.**
  Question: keep a value no shipped kind produces?
  Ruling: option A. `DriftSeverity` is `error` and `warning`, pinned; CHANGELOG says `info` of the audit vocabulary is not carried.
  Rationale: the precedent has no dead enum value; AD-6 removed two on the same ground; the no-dead-value row cannot pass with `info`. A future kind adds it with its fixture.
- **GOV-007 / ARCH-008: a legacy or malformed `lanes.json` in the drift scan.**
  Question: what does the scan do with the legacy-shaped manifest, and with a JSON-valid malformed one?
  Ruling: a manifest predating `mission_slug` is "not evaluated for kind 3", detected by a raw JSON pre-read before `read_lanes_json`, counted on the named list (the reason: a known defect of the legacy lanes manifest reader, which refuses that shape); every other corrupt manifest is 500 `drift_scan_unreadable`.
  Rationale: the v1 500 refused one Mission's detail; the same 500 here would fail the project-wide read permanently on this repository (the one legacy file, `064-complete-mission-identity-cutover`, is archive-frozen and cannot be repaired). The rule is stated in the `DriftKind` description, kinds 1 and 2 still apply, and a broken (non-legacy) authority fails closed.
- **COMPLETE-004: where the credential check sits relative to redaction.**
  Question: on the stored `evidence_ref` before steps 1-5, or on the redacted result?
  Ruling: option a, before; one plant per shape (query, userinfo, absolute path, free text, bare relative path), each with a clean control.
  Rationale: the precedent runs the credential check before redaction so redaction can never mask a credential (WP05 F1). Residual accepted: a userinfo password matching no `SECRET_PATTERNS` kind is still removed, `redacted: true`.
- **COMPLETE-013: Op files that cannot be opened.**
  Question: skipped, or does the read fail?
  Ruling: option a. An `OSError` on a candidate file is 500 `ops_unreadable`; legacy or shape failures and a file listed then gone (`FileNotFoundError`) are skipped; a partial first line of a concurrent writer is a shape failure. The spec applies the same rule to an unreadable spine.
  Rationale: FR-024 says "could not read" is never an empty success; a record fact differs from an environment fault.
- **OQ-1 (closed): which Missions kind 3 covers.** Ruling: (a) every non-completed Mission. Rationale: completion does not depend on the clock, so a finding never appears or disappears with time alone; an abandoned Mission that lost its lane branch lost work; the screen can filter.
- **OQ-2 (closed): a branch name in a finding.** Ruling: (a) none; one finding per Mission. Rationale: keeps AD-2's unique key and the minimal leak surface (a branch name can carry a handle); the client resolves names from the workspace read.
- **OQ-3 (closed): remote-only branches.** Ruling: (a) local branches only, wording "no local branch". Rationale: literally true, independent of stale or pruned remote-tracking refs.
- **OQ-4 (closed): a `status.json` that is not valid JSON.** Ruling: (b) not JSON, or not an object: an `error` kind-1 finding, `sourceCode` `CORRUPT_JSON`, `remedy` `materialize_status`, `laneComparison` `[]`; the fixed-summary table gains the pair. An `OSError` reading it, and a reducer that raises, stay 500 (the spec departs from the audit's `SNAPSHOT_DRIFT` mapping of a raising reducer, and says so). Rationale: the snapshot is the derived side with the log intact; `classify_status_json` already emits `CORRUPT_JSON` as an error; a 500 would hide the defect from the screen meant to show it.
- **OQ-5 (closed): a credential in `evidence_ref`.** Ruling: withhold; the Op is served with `evidence: null`, described as "no evidence, or withheld because it holds a credential"; the description names the credential kinds and says other shapes are not detected; plant and control. Rationale: precedent AD-17 (credentials refused or withheld, never masked, no `[secret]` token); a field inside a list is withheld as a v1 title is; a 500 would break the screen on one committed record; skipping would lose a real Op silently.
- **OQ-6 (closed): where the skipped-record count lives.** Ruling: (b) provisional `skippedCount` on `OpsInvocationPage`, over the same candidate set as `totalCount`, independent of `profile`; cited `x-derived`; named in the CHANGELOG. Rationale: a static description cannot carry a runtime count; it is the client-facing counterpart of "examined plus skipped equals discovered"; it gives AD-7's marker an exit condition.
- **GOV-001 (hidden forks).** `remedy` is `null` for a kind-1 `error` finding on a Mission merged to `main` (`meta.json` `merged_at`; archive-frozen `status.json`); the slug for `--mission` comes from `MissionHead.slug` of the finding's `missionId`; the command is `spec-kitty agent status materialize`, not `spec-kitty materialize`.
- **COMPLETE-001 (hidden choice).** The branch source is at most one `git for-each-ref refs/heads` listing, run once when the first Mission with an expected lane needs it (zero listings when no Mission has an expected lane; NFR-002 counts it), failing closed (a non-zero exit is 500 when any Mission has an expected lane); the oracle checks each expected name with its own `git rev-parse --verify`, an independent read.
- **Single-remedy facts applied:** `Project` gains five properties, not four (FR-022's count of four breaking additions holds because `health` is provisional).

## Operator rulings (2026-10-05, round 3)

The operator ruled option A on the four forks of the fresh sweep and accepted the two round-1 fixer choices. Binding; the spec does not re-open them.

- **FRESH-001: the directory kinds 1 to 3 read status from.**
  Question: the coordination-aware resolver of the v1 reads, or the Mission's own primary directory?
  Ruling: option A. The resolver `MissionStatus.load`; each resolver exception is 500 `drift_scan_unreadable`, none a fallback (amended by round 4, below: `CoordinationBranchDeleted` is the one named fallback): `CoordinationBranchDeleted` (the resolver calls it data loss and forbids a primary fallback), `CoordAuthorityUnavailable`, `MissionMetadataUnavailable`, `InvalidMissionSlug`, `WorktreeRegistryUnavailable`, and a read directory outside the repository root. `meta.json` and `lanes.json` stay in the Mission's own directory.
  Rationale: for a coordination-topology Mission the primary copy of status is stale or absent, so a primary-only scan compares stale files; v1's fallback names its reason, but a project-wide scan that falls back would report stale comparisons as findings. Fixture pair: coordination copy consistent with a stale primary copy, and the reverse.
- **FRESH-005: what `GET /project` promises about cost.**
  Question: keep `lastActivityAt` and `missionCount` as defined (every Mission read), or serve them from a cheaper source?
  Ruling: option A. The semantics stay; "scans nothing" and "cheap" are dropped; NFR-009 bounds one `Project` build over this checkout (re-measured with the resolver included in round 4, below: 120 seconds, 44.4 measured; the first figure, 1.5 seconds, omitted the resolver); the `Project` description says the cost grows with the Mission count. OR-10 is amended as above.
  Rationale: the figure depends on every Mission's event log, so the honest promise is read-only, side-effect-free and safe once per recent project, with the cost stated.
- **FRESH-007: whether a completed Mission's `lanes.json` is validated.**
  Question: validate for every Mission, or only for those that are not completed?
  Ruling: option A. The completion test comes first; `lanes.json` is read and classified only for a Mission that is not completed. Fixture pair: a completed Mission with a malformed manifest (no read, no 500, no finding) beside a non-completed one (500).
  Rationale: the GOV-007 rationale applies equally to a frozen manifest of a completed Mission: a permanent 500 on a file that cannot be repaired would fail the project-wide read forever, and kind 3 never needs that file.
- **FRESH-014: nullable `missionId` and `artifactPath` on `DriftFinding`.**
  Question: keep a null branch with no producer, or make both non-null?
  Ruling: option A. Both are non-null; the null-ordering clause is dropped; FR-009, the examples and the CHANGELOG say so.
  Rationale: the no-dead-value principle that removed `info` (AD-6); a project-wide kind, if ever added, is a later breaking change.
- **Accepted round-1 fixer choices.** COMPLETE-012: the kind-3 oracle shares the product's `is_mission_completed` and `materialize_snapshot`, kind 3 has no corpus floor, planted fixtures cover the shared readers. The unreadable-spine rule: an `OSError` reading the spine is 500 `ops_unreadable` (round 3 adds invalid UTF-8 in the spine; invalid UTF-8 in an Op file is a shape failure).
- **Single-remedy facts applied in this round.** One absent-file rule: an index entry without a file and a file gone after listing are both skipped and counted in `skippedCount` (they are in the candidate set; the round-2 ruling already skips the vanished file). `profile`, `totalCount` and the cursor use the `profile_id` of the Op's own `started` event. `profileId` joins `STRICT_FIELDS` by exact name. The kinds 1 and 2 oracle is restricted to the reader's population. NFR-001 is at most two reductions per Mission.

## Operator rulings (2026-10-05, round 4)

The operator ruled option B on FRESH2-001 after the fresh round-2 sweep reproduced the round-3 ruling on the real corpus. Binding; the spec does not re-open it. It amends FRESH-001.

- **FRESH2-001: what the scan does when the resolver raises `CoordinationBranchDeleted`.**
  Question: keep FRESH-001 (every resolver exception is 500) and list the failing Missions, or return to v1's behaviour for that one outcome?
  Ruling: option B. For `CoordinationBranchDeleted` only, the scan reads the Mission's own directory, as v1 does, and attaches a named reason; every other resolver exception stays 500 `drift_scan_unreadable`. The spec states the corpus outcome (`GET /drift` succeeds on this repository) and the reality check lists the fallback Missions by an independent derivation with a stale-entry check. `lastActivityAt` stays resolver-based, the same definition as `GET /missions`. NFR-009, NFR-001 and NFR-002 are re-measured with the resolver included; the resolver is memoised per Mission; FR-007's no-subprocess test is restricted to the reader's own code with the resolver's git calls exempted explicitly.
  Rationale: measured on this checkout (a normal clone with no local `kitty/*` branches and 16 remote-tracking `refs/remotes/origin/kitty/*` refs), 37 of 569 Missions raise `CoordinationBranchDeleted`, so the strict rule made the project-wide read a permanent 500 here and on every fresh CI clone, and the proof (AC-REALITY, SC-002) could not pass.

Decisions made under the ruling (the operator left them to the author within the contract conventions; recorded so a reviewer can contest them):

- **Where the named reason is visible.** In the reference reader's result, as a `fallback` field with the one-value vocabulary `coordination_branch_deleted`, and in a reality-check report line, as v1 reports its coordination fallbacks (`CaseResult.fallback`, the report line "coordination fallbacks"). The contract gains no property: v1's schemas carry no fallback reason, a property would be a new source with its own citation and provisional cost, and the `DriftReport` description states the rule in words. The service (#5528) may surface it.
- **The v1 helper is not the model (FRESH2-004).** `resolve_read_dir` also falls back for `CoordAuthorityUnavailable`, `MissionMetadataUnavailable` and a read directory outside the checkout, which are 500s here. The reader adds a strict sibling catching `CoordinationBranchDeleted` only; the helper stays untouched (a ratchet file) and is the control of a plant.
- **Completion reads the own directory (round-3 verification of FRESH-001, FRESH2-006).** `is_mission_completed` and `materialize_snapshot` read `meta.json` in the directory they are given; for an unmerged coordination Mission the own directory's copy carries `merged_at`. The reader applies the two arms of `is_mission_completed` itself: own `meta.json` `merged_at`, or `derive_mission_lifecycle` of the read directory completed. A coordination fixture pair pins it (`merged_at` in one copy only).
- **Invalid UTF-8 (FRESH2-005).** `status.json` is a `CORRUPT_JSON` finding (the classifier does not catch `UnicodeDecodeError`; the oracle wraps it), `lanes.json` of a non-completed Mission is the "not JSON" 500, `meta.json` is `MissionMetaReadError` (500), an event log is a raising reducer (500). Consequence of the principle already ruled (a broken derived file is a finding, a broken authority a 500).
- **Reducer generation gate (FRESH2-007).** `materialize_snapshot` replays at the generation recorded in the existing `status.json`; R-8, FR-010 and the `DriftFinding` description say so; a fixture pair pins it.
- **Qualified provisional names (FRESH2-008).** `kind`, `code` and `truncated` are already named in the CHANGELOG `Provisional` section, so a committed test asserts `DriftFinding.kind`, `DriftReport.truncated`, `DriftRefusal.code` and `OpsRefusal.code` literally, with plants.
- **Refusal schemas (FRESH2-010).** `DriftRefusalCode` is `mission_not_found` (404) and `drift_scan_unreadable` (500); `OpsRefusalCode` is `ops_unreadable` (500); the 404 no longer reads "shared Problem shape"; the catalogue gains rows for both `code` properties and the three `OpsEvidence` members.
- **No private ledger ids (FRESH2-009).** The spec and this tracer describe each known defect by its class and carry no pointer to a private list; the prototype badge codes above are non-sources, not ledger ids.
- **Bounds on the measured basis.** NFR-009 120 seconds (44.4 measured), one scan 120 seconds (40.3 to 52.0 measured in three runs), reality job gain 120 seconds (round 4 fix: the 180 second figure was never measured and is dropped): about 2.3 times the slowest measured scan, for a slower runner; the gain is one memoised resolver pass plus the reductions (the Project build adds about 7 seconds: 44.4 against 37.9). Subprocesses: one listing plus the resolver's, counted (785 measured, 784 of them the resolver's).

### Measurement (2026-10-05, this checkout, resolver included)

569 directories under `kitty-specs/`, 37 raise `CoordinationBranchDeleted`; the clone has no local `kitty/*` branches (it holds 16 remote-tracking `refs/remotes/origin/kitty/*` refs), and 37 of the resolver's runs include a `git ls-remote --heads` probe of origin, so the figures hold with the remote reachable. Run from the repository root with the repository's own interpreter. One scan, composed of the real readers (resolver once per Mission through the memo, the snapshot comparison where both files exist, the completion test, the `meta.json` and `lanes.json` reads and the one branch listing); three runs of the command below gave `seconds=52.0`, `seconds=48.0` and `seconds=40.3`, each with `missions=569 fallbacks=37 subprocesses=785`:

```
.venv/bin/python - <<'PY'
import json, subprocess, time
from pathlib import Path
from specify_cli.core.paths import load_meta_fail_closed
from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.status.aggregate import MissionStatus
from specify_cli.status.lifecycle import is_mission_completed
from specify_cli.status.reducer import materialize_snapshot, materialize_to_json
root = Path.cwd()
spawned = []
_popen = subprocess.Popen.__init__
subprocess.Popen.__init__ = lambda self, *a, **k: (spawned.append(1), _popen(self, *a, **k))[1]
memo, fallbacks = {}, []
t0 = time.perf_counter()
for own in sorted((root / "kitty-specs").iterdir()):
    if not own.is_dir():
        continue
    try:
        memo[own.name] = Path(MissionStatus.load(root, own.name).read_dir)
    except CoordinationBranchDeleted:
        memo[own.name] = own
        fallbacks.append(own.name)
    read = memo[own.name]
    load_meta_fail_closed(own)
    status, log = read / "status.json", read / "status.events.jsonl"
    if status.is_file() and log.is_file():
        json.loads(status.read_text()) != json.loads(materialize_to_json(materialize_snapshot(read)))
    if not is_mission_completed(read) and (own / "lanes.json").is_file():
        json.loads((own / "lanes.json").read_text())
subprocess.run(["git", "for-each-ref", "refs/heads"], capture_output=True, text=True, check=True)
print(f"missions={len(memo)} fallbacks={len(fallbacks)} seconds={time.perf_counter() - t0:.1f} subprocesses={len(spawned)}")
PY
```

The resolver alone (`MissionStatus.load` over the 569 directories): 37.9 and 36.7 seconds, 784 subprocesses (281 `git symbolic-ref`, 281 `git rev-parse`, 222 `git -C`). One `Project` build proxy, the v1 `load_source` of `tests/contract/_mission_status_payloads.py` over the 569 directories (resolver, meta, identity, snapshot): 44.4 seconds, 784 subprocesses, 37 fallbacks. After the resolver, 569 `materialize_snapshot` calls take 0.5 to 5.4 seconds and 569 `is_mission_completed` calls 0.3 second. The earlier figure of 1.5 seconds (`materialize_snapshot` and `is_mission_completed` only) omitted the resolver.

Independent derivation of the fallback list: `meta.json` names a `coordination_branch`, holds no `merged_at`, and the name is in neither `git for-each-ref refs/heads` nor `git worktree list --porcelain`; it yields the same 37 Missions as the resolver (35 of topology `coord`, 2 of `lanes_with_coord`). The 14 further Missions that declare a missing coordination branch are merged, and the resolver re-anchors a merged Mission on its own directory, so they do not raise.

## Operator rulings (2026-10-05, round 5)

The fresh round-3 sweep found, with the real resolver over this checkout, that the stock resolver probes the network.

- **FRESH3-001: the coordination resolver runs `git ls-remote --heads`.**
  Question: keep the stock resolver and state its facts (A), or escalate a seam that lets the read-side scan decide "branch deleted" without remote probing (B, a `src/` change)?
  Ruling: option A. The resolver may run `git ls-remote --heads` (5 s timeout per remote); the fallback count and the 200 of `GET /drift` are network-dependent; offline, `GET /drift` is a 500 `drift_scan_unreadable`; `GET /project` has the same network behaviour; NFR-001 and NFR-009 hold with the remotes reachable; AC-REALITY is conditioned on reachable remotes or marks the network-less outcome expected; "read-only git queries" is reworded in FR-007, FR-015, NFR-002, NFR-009 and R-9; "no `kitty/*` refs" is "no local `kitty/*` branches"; FR-024 and AC-DRIFT gain an offline row with a real-git fixture whose remote is unreachable. Purely internal resolver behaviour that changes no observable outcome is a stated assumption (R-9), not a rule.
  Rationale: option B changes `src/` and the slice is a contract slice (C-006); the stock behaviour is stated, not hidden. Verified in `src/specify_cli/coordination/surface_resolver.py` (`_coord_branch_exists`: local head, then `refs/remotes/`, then `remote_branch_lookup`) and `src/specify_cli/git/remote_probes.py` (`_LS_REMOTE_TIMEOUT_SECONDS = 5.0`; a hit or an error means present; a clean miss or no remote means deleted), and `src/specify_cli/status/aggregate.py` (`StatusReadPathNotFound` re-spelled `CoordAuthorityUnavailable`, `CoordinationBranchDeleted` propagated first).
- **Design note for the read service (#5528), out of scope, no `src/` change.** Resolve coordination locally, with local refs and remote-tracking refs only, so a read never depends on the network.

Decisions made in fixer round 4 (single remedies, recorded so a reviewer can contest them):

- **FRESH2-002 / FRESH3-003: how the Project build reaches the memo.** The new reader exposes the memo; the new Project builder calls it and applies all four of v1's fallbacks (the three exceptions and a read directory outside the checkout) to the raw outcome. v1's `resolve_read_dir`, `load_source` and the v1 reality test are not edited (ratchet files); their own pass stays separate and is the control. "Once per Mission per run" is stated for the new reader code; FR-007's stub test, NFR-001, NFR-002 and AC-REALITY say the same.
- **FRESH2-003: measured figures only.** The 180 second figure is dropped; the job gain is bounded at 120 seconds by the measured scan time (52.0 s slowest) plus headroom, with the command above. NFR-002's "exactly one" is conditional on an expected lane (FRESH3-005).
- **FRESH3-002: the fallback derivation's scope.** It is an agreement check on this corpus, not a mirror of the resolver's reopen-aware merged test, stored-topology gate and remote existence arms; each arm has a fixture (FR-026).
- **FRESH3-004: memo key.** (resolved repository root, Mission directory name), one memo per run, with a two-repository test.
- **FRESH3-006: `missionId` lookup.** It uses the v1 identity read; a directory whose identity cannot be read matches no ULID and does not fail another Mission's report (AD-10, `missionId` isolates the Mission).
- **FRESH3-007: citation.** `write_derived_views` is cited at `src/specify_cli/status/views.py`.

## Author decisions AD-1 to AD-10, as amended by rounds 2 to 4

Ids are stable. AD-1: `DriftSeverity` is `error`, `warning`; `CORRUPT_JSON` is `error`. AD-2: kind 3 is one finding per Mission, no branch name. AD-3: population is every non-completed Mission (completion tested first, lifecycle states include `reopened`); the expected Mission-level branch is the coordination branch or `mission_branch` by topology; local branches only. AD-4: `materialize_status` maps to `spec-kitty agent status materialize`; null for the warning variants, for kind-1 errors on a merged Mission, for kind 2 with a missing log (deliberate divergence from the doctor), for kind 3. AD-5: `skippedCount` over the `totalCount` candidate set. AD-6: `DriftSeverity` joins the no-dead-value rule. AD-7: exit condition of the Ops operation marker is the settlement of the legacy handling and `skippedCount`. AD-10: the 500 list gains `status.json` `OSError`, a corrupt `meta.json` and a non-legacy corrupt `lanes.json`, plus a failed branch listing; a legacy-shaped `lanes.json` and a `CORRUPT_JSON` snapshot are defined outcomes (round 4 adds the fallback Mission and the invalid UTF-8 outcomes). Round 3: AD-10 reads status in the resolver's directory (FRESH-001) and validates `lanes.json` only for a Mission that is not completed (FRESH-007); AD-2's key stays unique with `missionId` and `artifactPath` non-null (FRESH-014). AD-8 and AD-9 are unchanged.

## Spec phase notes (2026-10-05)

- **Corrections found against the checkout** (full list in the spec's Clarifications): the unborn branch is a name, not null; `get_project_version` raises on two metadata shapes and returns the sentinel `unknown` on a third; the branch pattern belongs to `Workspace.laneBranch`; the issue's `authority` value `meta`, `derivedSide` value `derived_views` and the audit's `info` severity have no producer; `mission_not_found` is a new code of the module's `DriftRefusalCode`; the prototype's remedy command is wrong; the corpus has no `url`-kind evidence.
- **Open questions:** all six are closed by the round-2 rulings above.
- **Measured on this checkout (2026-10-05, moves with the tree):** 569 directories under `kitty-specs/`; 31 with an event log and no `status.json`, none the other way, 2 with neither; 43 `SNAPSHOT_DRIFT_TERMINAL`, 1 `SNAPSHOT_DRIFT_PROVENANCE`, 0 `SNAPSHOT_DRIFT`; 489 `lanes.json` (1 legacy-shaped); 480 Op files, 6 spine closures (none for the 7 legacy completions), no index, no `mission_id` or `wp_id` on any Op; evidence of 467 own-file completions: 351 none, 32 absolute, 56 free text (one embeds a URL), 28 relative, 0 `url`.
- **Re-measurement owed (reality check).** The kind-3 counts (488 manifests, 370 completed, 118 not, 93 with an expected lane and a missing branch; 89 abandoned, 22 active, 4 stale, 3 recoverable) were taken before the ARCH-001 and COMPLETE-001 fixes and include the coordination false positive. The plan's first task re-measures them under the final rule, records the result here, and pins no kind-3 corpus floor.

## Wrap-up records (filled when the proofs run)

- FR-022 baseline: the full SHA of the merge-base of the branch with `origin/main` at the run, asserted an ancestor of `origin/main`; the two `breaking_check.py` runs with their `counts:` lines and planted controls; the byte-identity command against that SHA.
- FR-028 J-1: the commit of the final `contracts/` change and one line per job with its conclusion.

## Spec phase closed (2026-10-06)

The spec phase used all five fix rounds. The final verify left one severity-2 wording item (FRESH4-003, "three fallbacks" against four), fixed in 3443bbbfe and checked by the orchestrator (no "three fallbacks" remains; FR-015 and the memo section say "all four"). No contract fork remained. The orchestrator accepted the spec as passed on that check, without another verify round. Two severity-1 nits go to the plan phase: two AC-REALITY bullets lack their own reachability condition, and the old wording of the single branch listing (a fixed count tied to the scan) survives in a heading and in this file.

## Plan phase (2026-10-06)

The plan, research, data model, quickstart and the two contract notes are in this directory; the rulings above are not re-opened. Decisions the plan made inside the spec's conventions (recorded so a reviewer can contest them):

- **Spec edits of this phase (the only ones allowed).** The two AC-REALITY bullets that lacked their own reachability condition now state it, in the wording of FR-025 (with the remotes reachable and the corpus condition; offline they take a named skip, never a silent pass, and an offline run is not evidence for SC-002 or SC-007). The old wording of the single branch listing is gone from the spec (the clarification, FR-012 step 4, the AC-DRIFT row) and from the COMPLETE-001 line above; the sentence of the "Spec phase closed" section that quoted it now describes it instead.
- **PD-1 Three new test modules and five helper modules** (project, drift, ops; memo, project, drift, ops, oracles), none `fast`, each with a module-level `pytestmark`; contract-level proofs extend the existing 1.1 proof module.
- **PD-2 Registrations outside the spec's file set** (operator-acknowledged, plan-round ruling 7): one `--deselect` in `packs.yml` and one registry row per new module, and `contract_tools` globs in `ci-router.yml`; they select the heavy battery on this PR. The spec's two other named files (`ci-module-registry.yml`, `contracts.yml`) need no edit.
- **PD-3 The `Project` change, the memo, the Project builder and the ratchet edits of two v1 tests land in one work package** (IC-03) so no tip is red.
- **PD-4 The two new root tags `Drift` and `Ops`** are removed with the two path keys from the scratch baseline of the additive proof.
- **D-P2 The resolver memo** is a neutral helper keyed by (resolved repository root, Mission directory name) and counts subprocesses through a `pytest.MonkeyPatch` context, never a manual global patch.
- **D-P6 Kind 3 stays provisional and unfloored**; its corpus population is re-measured by IC-01 under the final rule, and an honest-rule criterion that cannot be met goes to the operator.
- **D-P10 The additive proof**: committed pure tests over the extended scratch pair; recorded wrap-up commands for `oasdiff`. **Measured on a spike** (research R-5): lowered-major baseline exits 0 with `breaking=4 provisional_changes=1`; same-major baseline fails `BREAKING_WITHOUT_MAJOR` naming `currentBranch`, `lastActivityAt`, `schemaVersion`, `specKittyVersion`. `breaking=4` is pinned; `provisional_changes` is pinned on the final tree.
- **D-P13 Floors** (fixed, never re-pinned): Missions 540, Ops served 440, spine-closed 5, evidence none 330 / absolute 28 / free text 50 / relative 25, kind-1 findings 39, kind-2 findings 27, completion_non_coord 490 (completion-equality guard of AC-DRIFT 19: Missions declaring no coordination branch compared, of 518; added by plan-round ruling 4); no kind-3 floor, no fallback floor.
- **Departures from the spec text** (plan, "Departs from the spec", not edited into the spec): the registrations; the two tags in the bundle comparison; "recorded in the plan" for CI-runner timings; the J-1 commit citation that compaction rewrites (re-cited at W-7 with a byte-equality check); the offline skip scope of AC-REALITY bullets 2 and 3 (resolved by plan-round ruling 1: the spec is now edited to match, see "Plan-round operator rulings"); the JVM or lint plants of FR-027.
- **Corpus facts at plan time** (research R-2, R-3): 569 Missions, 473 Ops served and 7 skipped, 37 fallback Missions by independent derivation, 0 non-merged Missions declaring a coordination branch present only on a remote (the corpus condition of FR-025 holds today).

## Plan-round operator rulings (2026-10-06, binding; not re-opened)

The plan-phase squad confirmed 15 findings; seven of them were forks. The operator ruled:

1. **Offline scope of AC-REALITY (the departure of the plan from the spec's wholesale skip).** Keep the plan's behaviour. Offline skips only the resolver-dependent assertions, each by a named skip; the Ops walk, `skippedCount` equality and read-only fingerprint run in every environment because they need no network. The spec (AC-REALITY bullets 2 and 3, the FR-025 sentence) is edited to match, and the plan words this as an explicit departure. Rationale: a skip hides a defect for no reason where no network is involved.
2. **`ProjectMetadata.load` raises on non-mapping shapes.** Pre-check the YAML shape in the reader (top-level mapping, `spec_kitty` mapping), call `load` only when the shape is safe, treat a residual `AttributeError` or `TypeError` as null. The spec wording "read as load reads it" stays.
3. **Baseline before dispatch.** The D-0 sync, the baseline and the synced environment are an orchestrator step before any dispatch; IC-01 keeps the re-measurements and the campsite; the IC-01 beside IC-02 parallel window stays.
4. **Corpus-reading assertions placement.** AC-DRIFT row 19 and the corpus-sized cases of AC-CROSS 4 move into `test_mission_status_reality.py` (corpus job) with a discovered-count guard; the three new modules are fixture-built only.
5. **Wrap-up order.** Restore the procedure order for dev-assist cleanup and the verdict; the terminal #5776 verdict comes after the squad; Departs 11 keeps only consolidate-before-squad.
6. **Timing method.** Each timed shape is the minimum of at least 5 in-test repeats, the control timed the same way, the planted quadratic mutation still failing; the measured minimum and margin go in the hand-off. Every repeat is cold (fresh state, no memo or cache reuse; a counter asserts no cache hit) and a planted cache-the-result mutation must fail (plan D-P16).
7. **PD-2 is operator-acknowledged.** The widened registration file set is approved; `SLICE_ALLOWED` lists every such file.
8. **Proxy escalation threshold (PLAN-FRESH3-001).** The threshold in D-P5 and IC-01 moves to about 70 s local (120 s divided by the 1.7 local-to-CI factor); the W-7 pass rule stays the final arbiter.
9. **cache-the-result coverage (PLAN-FRESH3-003).** The mutation is added to the AC-CROSS 4 row and to IC-09 Red-first, so the real 5 s listing case is covered.
10. **In-test bound versus job gain (PLAN-FRESH3-002).** D-P5 says the combined case and the job gain are different quantities (the completion equality and the listing repeats sit in the job gain only); the W-7 pass rule is the arbiter.

11. **Escalation line against the sum (PLAN-FRESH4-001, orchestrator note 11 of `reviews/plan.ruling.md`; within ruling 8).** The 70 s figure bounds the whole local job-gain proxy; D-P5 and IC-01 state it against the sum of the combined case and the 10 to 15 s the job gain adds (completion equality, listing repeats), so the combined case alone escalates at about 55 s local. IC-01 step 4 measures every component of that sum; the W-7 pass rule stays the final arbiter.

## Tasks-phase rulings

The tasks squad confirmed 11 findings; three were forks. The operator ruled (full text in `reviews/tasks.ruling.md`):

12. **TASKS-COVER-001.** The legacy-shape-literal pin test is a WP07 subtask; the camel-case enum plant is named in WP04, WP05 or WP06; WP06 no longer claims the parts of AC-VERSION e it does not carry.
13. **TASKS-SEQ-001.** The orchestrator fast-forwards the Mission branch and merges the planning branch into each lane workspace before dispatch and greps the records there; WP10 works in the planning branch; no `--refresh-planning-commit`.
14. **TASKS-VERIFY-002.** The full architectural battery is a binding local gate on WP03, WP07 and WP08 (legs named concretely), replacing the plan's CI-owned default for those work packages.

## Refinement at WP04: the citation of `DriftFinding.artifactPath` (2026-10-06)

The spec's field catalogue cites `DriftFinding.artifactPath` with `x-source`. The contract carries `x-derived` (input `MissionFinding`) instead, because the referenced `ArtifactPath` schema carries its own `x-derived`, and `citation_check` refuses both citations on one property (BOTH_CITATIONS). `ArtifactEntry.path` and `ArtifactReference.path` already follow this pattern. The catalogue row is stale; the contract is authoritative.

## Refinement at WP05: `OpsInvocation` has thirteen members (2026-10-06)

Spec FR-017, its field catalogue and data-model.md list thirteen `OpsInvocation` members, `evidence` being the thirteenth. All thirteen are required, and seven are nullable. "Twelve members" in `contracts/operations-and-schemas.md` and in the WP05 prompt text is a miscount. The contract follows the spec.

## Record: J-1 (47c18d11c)

contracts-commit: 47c18d11ca258c065e925e52b859a093ccd8603c

JVM replay of every `contracts.yml` job on lane-a at the commit of the final `contracts/` change (2026-10-06): verdict PASS, no red.
- verify-pins: success (verify_pins --fetch exit 0, gradle_pin_check exit 0)
- python-checks: success (ten checks exit 0; examples 124/124, enum pins 20 enums/72 values, leak_scan files=1111)
- validate-bundle: success (bundle modules=1 bundles=1 path_items=10; tamper_check PLANT_DETECTED; client_smoke files_emitted=127 warnings=0)
- resolver-parity: success (path_items=10 schemas=78 refs_resolved=413 operations=10 examples_cross_checked=124)
- lint: success (vacuum rules=9 violations=0; every planted fixture and the other_content_type plant fails with its own rule; clean passes)
- breaking-change: success (tag-less NO_BASELINE_INITIAL_VERSION exit 0; the workflow's planted step with 18 plants and 3 controls exit 0)
- release-dry-run: success (tag-less SNAPSHOT_DRY_RUN verified=1; sha256sum -c OK; 5 planted tags and the clean control pass)
- negative-tests: success (no skip tags: cases=133 ran=133 skipped=0 passed=133 failed=0)
- contracts-gate: success (every needed job succeeded)

The camel-case enum plant on a scratch copy is refused by the lint (enum-case, exit 1). The two `breaking_check.py` runs against scratch baselines from abafc135e give: lowered-major (0.9.0) exit 0, `breaking=4 provisional_changes=1`; same-major (1.0.0) exit 1, BREAKING_WITHOUT_MAJOR naming `currentBranch`, `lastActivityAt`, `schemaVersion` and `specKittyVersion`. Replay infidelities (none produced a red): PATH was set by hand in place of GITHUB_PATH; TMPDIR was outside `/tmp`, because `/tmp` holds a stray `.git`; the venv was kept out of tree; the local bundle output replaced download-artifact.

## Operator ruling at WP07: an unreachable remote does not end the drift scan (2026-10-06)

The WP07 implementer found the problem and the review reproduced it on a real repository with an unreachable remote. The stock coordination resolver judges a declared coordination branch present when a remote cannot be asked: `MissionStatus.load` keeps the Mission's own directory, so the drift scan answers 200 with no fallback entry. `CoordAuthorityUnavailable` fires only when a coordination worktree root exists without the Mission directory. The spec's "facts of the stock resolver" under FRESH3-001, consequences (2) and (3), AC-DRIFT 14, FR-024 and the prose of `DriftReport` and `paths/drift.yaml` said an unreachable remote ends the scan in 500. That premise was false.

**Ruling: fix the text to the real behaviour** (option a). Offline, the scan answers 200 from each Mission's own directory. A reachable remote that lacks the branch gives the `coordination_branch_deleted` fallback. Every other resolver error stays a 500. The schemas and the API shape do not change. The contract descriptions return to WP04 by rejection, and the J-1 replay repeats. The spec, plan, planning contracts and the WP09 prompt are amended to match: offline, the corpus scan is a 200 with no fallbacks, and the named offline skip covers only the resolver-dependent assertions. Rejected: (b) the reader probes the remote itself, which needs a network probe, breaks the one-process rule and risks false 500s on the corpus; and (c) a `src/` seam, which is out of scope.
Also accepted at the WP07 review: the 500 for a current-shaped manifest with non-text types, and for a finding whose Mission has no ULID `mission_id` (AD-10 clauses; `missionId` is never null); the `laneComparison` (null, null) row; and the claim that the reader never opens `lanes.json`, which is scoped to the reader's own opens (the resolver's `backfill_topology` reads it).

## Record: J-1 (0d070a3a1)

contracts-commit: 0d070a3a10f89ed9df8366f79cb55102cf80b9bb

The repeated JVM replay of every `contracts.yml` job, after the WP04 rework (descriptions only, operator ruling at WP07), passed with no red (2026-10-06).
- verify-pins: success (verify_pins --fetch exit 0, gradle_pin_check exit 0)
- python-checks: success (ten checks exit 0)
- validate-bundle: success (bundle modules=1 bundles=1 path_items=10; tamper_check PLANT_DETECTED; client_smoke files_emitted=127 warnings=0)
- resolver-parity: success (path_items=10 schemas=78 refs_resolved=413 operations=10 examples_cross_checked=124)
- lint: success (vacuum rules=9 violations=0; every planted fixture and the other_content_type plant fails with its own rule; clean passes)
- breaking-change: success (tag-less NO_BASELINE_INITIAL_VERSION exit 0; the workflow's planted step exit 0)
- release-dry-run: success (tag-less SNAPSHOT_DRY_RUN verified=1; sha256sum -c OK; 5 planted tags and the clean control pass)
- negative-tests: success (no skip tags: cases=133 ran=133 skipped=0 passed=133 failed=0)
- contracts-gate: success (every needed job succeeded)

The camel-case enum plant is refused by the lint (enum-case, exit 1). Breaking checks against abafc135e: lowered-major exit 0 with `breaking=4 provisional_changes=1`; same-major exit 1 with BREAKING_WITHOUT_MAJOR naming exactly the four Project properties.

## Operator rulings at WP08: closure instants and credential-shaped handles (2026-10-07)

1. **A bad closure instant skips and counts the Op.** If the record that would close an Op (its own `completed` line or a closure-spine record) carries a `completed_at` that is not an RFC 3339 instant, the Op is skipped and counted in `skippedCount`, whether that record is the Op's own or comes from the spine. The read never serves a swept Op as open because its closure record was malformed. Rejected: ignoring the bad spine record (a swept Op shows as open), and falling through to the other source.
2. **A credential-shaped value in a handle is never served.** A value in `profileId`, `action` or `actor` that matches the contract tools' credential patterns (`SECRET_PATTERNS`) skips the record as a field defect, with a plant and a clean twin per field. The operator's option text said `actor` would become null. `OpsInvocation.actor` is required and not nullable in the final contract, so `actor` is skipped like the other two, which keeps the contract unchanged and needs no J-1 repeat. Rejected: serving the value verbatim (v1 does this for `actor`), and a 500.

   - Superseded 2026-10-07 by the post-squad operator ruling: `actor` is nullable; a credential-shaped `actor` is served null; a third J-1 replay ran (5dc9cc427).

## Close-out assessment (IC-10, pre-rebase)

Written 2026-10-07 by WP10. Pre-rebase; the final evidence is W-7. Decisions refined or reversed during implementation, each with its record.

- **Kept as ruled.** OR-1 to OR-10 and plan-round rulings 1 to 11 stand. Ruling 4 (corpus assertions in the reality module) and ruling 6 (cold minimum of repeats, cache-the-result mutation) were applied in WP09 without change; the timed block runs the production index walk and refuses a patched run (f021fe87b). OR-2 (derived_view_stale dropped by the FR-013 procedure) was applied in WP04 and is not reopened.
- **Reversed: the effect of an unreachable remote on the drift read** (WP07 ruling, option a). The spec said 500; the stock resolver answers 200 from the Mission's own directory with no fallback. The text, not the code, changed, and WP04 was rejected to carry the contract prose (0d070a3a1). Why: the alternative probes the remote from the reader, which breaks the one-process rule. Lesson: a fact about a stock component is a measured fact or an assumption, never a spec rule (R-9).
- **Refined: `DriftFinding.artifactPath` cites `x-derived`, not `x-source`** (WP04), because the referenced schema carries its own `x-derived` and a second citation is BOTH_CITATIONS. The spec's field catalogue row is stale and the contract is authoritative.
- **Refined: `OpsInvocation` has thirteen members** (WP05); the "twelve" of the contract note and the WP05 prompt is a miscount. Seven are nullable, all required.
- **Refined: citation of `OpsEvidence.kind`, `.value` and `.redacted`** is `OpCompletedEvent.evidence_ref`, not the bare event (WP06 contract edit, 47c18d11c).
- **Refined at WP08 (operator rulings):** a bad closure instant skips and counts the Op, whether the record is the Op's own or from the spine; a credential-shaped `profileId`, `action` or `actor` skips the record and `actor` is never nulled, because it is required and not nullable in the final contract. Effect: no contract change and no third J-1 replay.

  - Superseded 2026-10-07 by the post-squad operator ruling: `actor` is nullable; a credential-shaped `actor` is served null; a third J-1 replay ran (5dc9cc427).
- **Refined at the WP09 review:** the Project read never raises on an undecodable `status.json`; the Mission still counts and adds no activity (WP03 rework 8b970f977, review cycle 3). The WP09 workaround was removed in the same commit.
- **Applied but with a changed condition: D-P10 (revert-Project control).** The control must also remove the new `/drift` and `/ops/invocations` operations, otherwise same-major exits with BUNDLE_CHANGED_VERSION_SAME instead of 0 (WP06 record).
- **Decision D-P6 (kind 3 stays, no floor)** was confirmed by the operator at IC-01 and held through WP07 and WP09; the dominant class reflects the clone's ref set. A future Mission that wants a kind-3 floor needs a fixed ref set in the fixture, not the clone.
- **Not decided here, carried to the wrap-up:** the strategy of `consolidate` (W-1), the aggregate squad verdict (W-4), the measured diff per group (W-5) and the final evidence (W-7) remain to be recorded under "Wrap-up records".

## Operator rulings on the pre-merge squad forks (2026-10-07)

1. **A credential-shaped `actor` becomes null (correcting the WP08 rationale).** The WP08 ruling record said `OpsInvocation.actor` is "required and not nullable". The squad (PR-CONTRACT-003) found that premise false: `actor` is required, but `ActorHandle` is `[string, null]`. The operator's original option stands. A credential-shaped `actor` is served as `null`; the Op stays in `items` and in `totalCount`, and `skippedCount` is unchanged. A credential-shaped `profileId` or `action` still skips the record. The `OpsInvocation.actor` description says so. FR-017/FR-019 and the AC-OPS row are corrected. The contract-text change is folded into one repeated J-1 replay.
2. **A broken event log fails the Project read (PR-CONTRACT-001).** Only an unreadable `status.json` gives null activity for its Mission. An event log that cannot be decoded or parsed fails the Project read under the default Problem (500), as FR-024 states for a broken authority; the drift read already does this. The WP03-rework catch is narrowed to the `status.json` read, and a red-first event-log plant pins it.
3. **The corpus job runs on `kitty-ops/`-only changes (PR-BOUNDARY-001).** `kitty-ops/**` is added to the CI router's `corpus` group and to `_CORPUS_DATA_ROOTS`, so a PR that changes only Op files runs the reality check. This is CI configuration, with no `src/` change (NFR-007 holds).

## Record: J-1 (5dc9cc427)

contracts-commit: 5dc9cc427c9ec9e6b03fecf13a7af46b0daaa986

Third JVM replay, after the pre-merge squad fixes changed contract text (d36b2fd08, the `OpsInvocation.actor` description; 5dc9cc427, the AD-4 remedy rules, the unreachable-remote sentence and the Op-file 500). It ran on a shared clone of the consolidated tip 094bbd2c2 (2026-10-07). Verdict: PASS, no red.
- verify-pins: success
- python-checks: success (ten checks exit 0)
- validate-bundle: success (path_items=10; tamper_check PLANT_DETECTED; client_smoke files_emitted=127 warnings=0)
- resolver-parity: success (path_items=10 schemas=78 refs_resolved=413 operations=10 examples_cross_checked=124)
- lint: success (vacuum rules=9 violations=0; every plant fails with its own rule)
- breaking-change: success
- release-dry-run: success (SNAPSHOT_DRY_RUN verified=1; sha256sum -c OK)
- negative-tests: success (cases=133 ran=133 skipped=0 passed=133 failed=0)
- contracts-gate: success

The camel-case enum plant is refused (enum-case, exit 1). Breaking checks against abafc135e: lowered-major exit 0 with `breaking=4 provisional_changes=1`; same-major exit 1 with BREAKING_WITHOUT_MAJOR naming exactly the four Project properties. W-2 and W-7 compare against this commit.

## Record: J-1 (5d9ffad5a)

contracts-commit: 5d9ffad5a7894e252b1c1715f925d32c81fb768e

Fourth JVM replay, run after the R3 fold-in that states the `Project.lastActivityAt` degrade and failure rules in the contract, on a shared clone of c21576cfa (2026-10-07). Verdict PASS, no red. Every `contracts.yml` job succeeded: verify-pins, python-checks, validate-bundle (path_items=10, tamper PLANT_DETECTED, client_smoke 127 files and 0 warnings), resolver-parity (schemas=78 refs_resolved=413 operations=10 examples_cross_checked=124), lint (rules=9 violations=0, every plant fails with its own rule), breaking-change, release-dry-run (sha256sum -c OK), negative-tests (133 of 133 ran and passed) and contracts-gate. The camel-case plant is refused. Breaking checks against abafc135e: lowered-major exit 0, `breaking=4 provisional_changes=1`; same-major exit 1, BREAKING_WITHOUT_MAJOR naming exactly the four Project properties. W-2 and W-7 compare against this commit.
