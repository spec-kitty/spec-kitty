# spec phase: operator rulings after the R1-R3 HALT (2026-10-05, round 2)

The operator accepted every arbiter recommendation for the six forks and the six author open questions. These rulings replace the acceptance bar for the findings they name.

- ARCH-001: option A. For a Mission whose meta.json names a coordination branch, kind 3 expects that branch and never `mission_branch`. Fixture pair for coordination topology (branch present, branch absent).
- ARCH-002: option A. `DriftSeverity` is `error` and `warning` only, pinned, CHANGELOG line that `info` is not carried.
- GOV-007 / ARCH-008: a manifest predating `mission_slug` (legacy shape) is "not evaluated for kind 3", detected by a raw JSON pre-read, counted on the named list; every other corrupt manifest is a 500 `drift_scan_unreadable`. Cite a ledger entry and say why drift differs from the v1 detail read.
- COMPLETE-004: option a. The credential check runs on the stored `evidence_ref` before redaction steps; one plant per shape with a clean control.
- COMPLETE-013: option a. An OSError on a candidate Op file is 500 `ops_unreadable`; legacy or shape failures and a listed-then-vanished file are skipped.
- OQ-1: (a) every non-completed Mission. OQ-2: (a) no branch name in a finding. OQ-3: (a) local branches only, wording "no local branch". OQ-4: (b) a `status.json` that is not JSON or not an object is an `error` kind 1 finding with `sourceCode` `CORRUPT_JSON`, `remedy` `materialize_status`, `laneComparison` `[]`; an OSError reading it and a reducer that raises stay 500. OQ-5: withhold, the Op is served with `evidence: null`, described as "no evidence, or withheld because it holds a credential". OQ-6: (b) a provisional `skippedCount` on `OpsInvocationPage`, over the same candidate set as `totalCount`, independent of the `profile` filter.
- GOV-001 hidden forks: no remedy (null) on a Mission merged to main (archive-frozen) for kind 1 errors; say which read supplies the slug for `--mission`.
- COMPLETE-001: branch source is one `git for-each-ref refs/heads` listing per scan, fail closed (non-zero exit is a 500 when any Mission has an expected lane); the oracle reads refs another way and stays independent.

# Round 3 (2026-10-05): fresh-sweep forks, all option A

- FRESH-001 A: kinds 1 to 3 read status through the same coordination-aware resolver as v1 (`resolve_read_dir`). Each resolver exception is stated as 500 `drift_scan_unreadable` or as a named fallback.
- FRESH-005 A: keep the semantics of `lastActivityAt` and `missionCount`. Drop "scans nothing" and "cheap". Add an NFR time bound over this checkout and a description sentence that cost grows with the Mission count.
- FRESH-007 A: read and validate `lanes.json` only for Missions that are not completed; the completion test comes first. State the order in FR-012 and AD-10, with a fixture pair (completed with malformed manifest: no read, no 500; non-completed with malformed manifest: 500).
- FRESH-014 A: `missionId` and `artifactPath` of `DriftFinding` become non-null; the null-ordering clause is dropped.
- Accepted fixer self-choices from round 1: COMPLETE-012 (kind-3 oracle shares the product's `is_mission_completed` and `materialize_snapshot`, no corpus floor for kind 3, named plants) and the unreadable-spine 500 rule.

# Round 4 (2026-10-05): FRESH2-001, option B (amends FRESH-001)

- For `CoordinationBranchDeleted` ONLY, the scan reads the Mission's own directory, as v1 does, and attaches a named reason, with its visibility place stated within the contract conventions (no invented source). Every other resolver exception stays 500 `drift_scan_unreadable`.
- The spec states the corpus outcome: `/drift` succeeds on this repository, and the fallback Missions (37 at measurement time, clone-dependent) are listed by an independent derivation in the reality check.
- `lastActivityAt` stays resolver-based, same definition as `GET /missions`.
- NFR-009, NFR-001 and NFR-002 are re-measured with the resolver included, the resolver is memoised per Mission, and the exact measured command is stated.
- FR-007's no-subprocess test is restricted to the reader's own code, or the resolver's git calls are explicitly exempted (resolves FRESH2-002 and FRESH2-003).

# Round 5 (2026-10-05): FRESH3-001, option A

- Keep the stock coordination resolver and state the facts: it may run `git ls-remote --heads` (5 s timeout per remote); the fallback count and the 200 of `GET /drift` are network-dependent; offline gives a 500 `drift_scan_unreadable`; `GET /project` has the same network behaviour; NFR-001 and NFR-009 hold with the remotes reachable; AC-REALITY is conditioned on reachable remotes (or the network-less outcome is marked as expected); "read-only git queries" is reworded in FR-007, FR-015, NFR-002, NFR-009 and R-9; "no kitty/* refs" becomes "no local kitty/* branches"; an offline row in FR-024 and AC-DRIFT with a real-git fixture whose remote is unreachable.
- Design note for the read service (#5528), out of scope for this slice: resolve coordination locally (refs and remote-tracking refs only). No src/ change.
- Purely internal behaviour of the resolver that changes no observable contract outcome goes into a stated assumption or R-9, not a new rule.
