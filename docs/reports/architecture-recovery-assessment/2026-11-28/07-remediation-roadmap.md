---
doc_status: draft
updated: '2026-11-28'
---

# 7. Incremental remediation roadmap

Consolidator K3, profile `planner-priti`. A proposed sequence: no work item is created, nothing is scheduled, the architect decides. Target: `04-candidate-architecture.md`. Decision ids `D1` to `D16`: `06-capability-dispositions.md`. Obstruction ids `O01` to `O58`: `05-obstruction-map.md`. Tags: [read], [executed] mine; [relayed] from an input.

## Conclusion

1. **Four steps and ten probes can start now, with no ruling.** They delete copies, give every command one Mission value, put the built-in mission types on their own extension mechanism, and route charter imports through the seam. Each is undone by a revert and writes no user data.
2. **One step is the unlock: T8, the record on a ref.** It waits for D1 and D2. Until it is done, no step can delete lanes, coordination, the placement seam or consolidation (M1 §10.1 [relayed]).
3. **The large deletion is one step, T11, the only one not reversible after release.** It removes the old Mission shape as a set. Before it, both shapes run on the release-candidate line only; no general release ships both.
4. **Two tracks run beside the main line**: the charter switch (T3, T12) and tools as data (T13). They share no code with T5 to T11. The baseline cut (T14) comes last, so its converter is written once.
5. **Eleven of fifteen steps touch persistent data or a public contract.** Each names its consumers and the assurance it needs.

Confidence: high for T1 to T4; medium for the order T5 to T11; medium-low for sizes, since about 79,000 lines of core have no disposition (04 §8).

## 1. The sequence at a glance

| Step | What | Waits for | Data or contract | Removes obstructions |
|---|---|---|---|---|
| P1 to P10 | probes | nothing | no | settle D3, D4, D8, D10, D16 |
| **T1** | retire copies and unread stores | nothing | no | O20, O24, O33 (each in part) |
| **T2** | one Mission value; one predicate per rule | nothing | no | O37, O45, O46; part of O02, O38, O54, O57 |
| **T3** | the charter seam carries the traffic | nothing | no | O30 |
| **T4** | built-in types on the declared path | P7 | no (commands gain entries) | O19 to O23, O25, O26 |
| **T5** | one operation behind every door | T2 | **contract** (behaviour of API 1.x) | O09, O10, O11, O42 |
| **T6** | six states, one envelope, one log per Mission | D5, P8, T5 | **data and contract** | O12, O17 and O06 in part; O48, O57 |
| **T7** | guards and fold behind `append` | D4, P2, T6 | contract (events package) | O10, O12 to O14, O16, O43 |
| **T8** | the record on a ref, with `sync` | D1, D2, D16, P1, P9, T7 | **data and contract** | O01, O13, O15 for new Missions; O48 |
| **T9** | work-package branches, `accept`, `land`, API 2.0 | D3, D11 to D13, P4, P6, T8 | **data and contract** | O05 to O08, O11, O44 for new Missions; bounds O52, O55 |
| **T10** | stateless `decide`; one type format | T4, T8 | **data** (custom types) | O18, O24, O27, O56 |
| **T11** | remove the old Mission shape as a set | T9, T10, D8, D14, D15, P10 | **data and contract; not reversible after release** | O01 to O06, O08, O15, O17, O43, O47, O49 to O51, O54, O58 |
| **T12** | charter switch to the compiled bundle | T3, D6, D7 | **data** (activation, bundle) | O29, O31, O32, O33 |
| **T13** | tools as data rows | P3, D10 | **data** (generated files) | O34, O35 |
| **T14** | baseline cut | T11, T12, T13, D9, D15 | **data; one-way** | O15, O36, O38 to O40, O43, O50, O58 |
| **T15** | 4.1.0: remove aliases and any import | T11, T14 | contract | O44, O51, O53 |


## 2. Available now: probes

Each runs in a disposable clone or on paper and changes no product code.

| Probe | What it does | Settles; informs |
|---|---|---|
| P1 | several Missions append and push to one record ref from several clones; count refused pushes | one ref per repository or per Mission; D16, T8 |
| P2 | rule-by-rule table of the Java guards against core's guards; mark the missing independence guard | the size of the move behind `append`; D4, T7 |
| P3 | desk check of the tool row schema against the 17 supported tools | which tools need a renderer of their own; D10, T13 |
| P4 | one pilot Mission by hand on work-package branches; count second reviews after integration conflicts | integration on approval, or thin lanes; D3, T9 |
| P5 | reading pass over the 113 `cli` files without a command entry and the about 40 unassessed packages | a disposition for X.1 and X.3; all sizes, T15 |
| P6 | replay the tree-equality check over landed Missions; compare with the recorded gate verdicts | what the weaker guarantee would have let through; T9 |
| P7 | write the research and documentation guards as declared checks from a closed vocabulary | whether the vocabulary covers the Python chains; T4 |
| P8 | fold the existing logs by append order; compare with the present fold | which Missions read differently; T6, T8 |
| P9 | prototype replay of local-only rows through the state machine at `sync` (not built, 04 §5 F2) | whether a refused replay is reportable and safe; D2, T8 |
| P10 | ask, do not measure: who holds Missions in flight across an upgrade; who reads the on-disk log; who owns the hosted `status.json` consumer and the `event-router` registrants | consumers of two breaking changes; D1, D8, T11 |

P4 and P6 carry the most weight: frequent second reviews in the pilot bring back thin lanes and keep about 20,000 lines of consolidation (04 §13).

## 3. Available now: steps T1 to T4

### T1. Retire copies and unread stores

- **Deletes:** the copied `src/specify_cli/missions/<type>/mission.yaml` files (byte-identical to the pack tree for all four types [executed]), with readers repointed; the empty shim registry with its doctor and gates (ST S35 [relayed]); one of the two `resolver.py` modules (402 and 846 lines [executed]); the `software-dev` literal beside `wp_driven` (`runtime_bridge_composition.py:509` [read]); `canonical-events.jsonl` and the hosted vocabulary, which have no reader in core (M4.6).
- **Not here, on purpose:** the produce seam (registrants outside core, O47); `mission-events.jsonl` (the research guards read it until T4); committed `status.json` (an outside consumer, ST S28); the frontmatter lane mirror (named in 12 non-migration files [executed]; T6); workflows (documented; T10).
- **Prerequisites:** none. One commit per item.
- **Verify:** per item, a grep shows no importer left; `make test-fast` and the test files of the touched modules.
- **Reverse:** revert the commit. Nothing was written to a project.

### T2. One Mission value, one predicate per rule

- **Does:** one value object answers identity, target, Mission branch and status location; one handle resolver; one predicate each for "approved or done", "bookkeeping path" and "single branch"; topology readers leave `migration/`; one typed protection refusal.
- **Deletes:** about 22 target-branch resolvers and five private `_resolve_mission_slug` (X1 2.1, 2.4 [relayed]); 34 restatements of "approved or done"; the run-time imports of `backfill_topology` (26 files [executed]).
- **Prerequisites:** none. Tests that patch private names (O42) are restated first.
- **Verify:** a count per deleted name reaches zero; command JSON output is byte-identical on fixed Mission fixtures.
- **Reverse:** revert; a pure refactor. **Data or contract:** none. The nine JSON keys for branch facts stay until T9.

### T3. The charter seam carries the traffic

- **Does:** every import of `charter.*` from outside `src/charter` goes through `charter.offering.api` or `charter.activation.api`; a gate forbids the rest. Today 149 files import `charter.*`, `charter.drg` on 80 lines [executed].
- **Deletes:** nothing yet. It creates the place where T12 happens.
- **Verify:** the gate, starting as a shrink-only count. **Reverse:** revert. **Data or contract:** none.
- **Caution:** the seam exposes what callers use today, no more.

### T4. Built-in types on the declared path

- **Does, in order:** (a) restate the research guards on artefacts, fixing the defect (O25); (b) evaluate declared checks from a closed, versioned vocabulary **beside** the Python tables; (c) delete the tables; (d) generate one command per step that declares one.
- **Deletes:** `_GUARD_TABLES` (`runtime_bridge_cores.py:859-864` [read]), `BUILTIN_TYPE_CAPABILITIES`, `_ACTION_PROFILE_DEFAULTS`, the `research` branches in `grammar.py:83, 196` [read], `if mission == "documentation"` (`mission_creation_meta.py:262` [read]), the fixed command tuple (`command_installer.py:101-114` [read]), then `mission-events.jsonl`.
- **Prerequisites:** P7. Check definitions are authored in `spec-kitty-open-packs` and arrive by a pin bump.
- **Transitional:** both evaluations for **one release candidate**; a disagreement fails CI. A shrink-only count of `software-dev` literals (156 in 64 files, CH CB12 [relayed]) ends at zero in T10.
- **Verify:** zero disagreements over the parity fixtures; one Mission of each built-in type runs to `done`; a research Mission passes `gathering`.
- **Reverse:** until (c), remove the declared evaluation. After (c), revert.
- **Data or contract:** none broken. Research and custom steps gain commands.

## 4. The main line: T5 to T11

### T5. One operation behind every door

- **Does:** the guards of `tasks_move_task_gates.py` (1,703 lines [executed]) move into one transition operation in core, called by `move-task`, `agent status emit` and the API `transition` verb. `consolidate-mission` calls the one landing executor. Both claim paths call one `start`.
- **Deletes:** the second landing executor and its nine `_refuse_*` functions (`orchestrator_api/consolidation.py:586` [read]); the second claim path in `orchestrator_api/wp_lifecycle.py` (1,074 lines [executed]); the guard copy in the command module.
- **Prerequisites:** T2.
- **Public contract: yes.** API transitions that pass today may refuse. Consumers: `spec-kitty-orchestrator` (04 §12 [relayed]), `spec-kitty-mcp`.
- **Decision:** no id covers this alone; D11 is nearest. **Default assumed:** the guards apply to every door.
- **Transitional:** the API warns in place of the new refusals for **one release candidate**.
- **Verify:** one table-driven test runs each guard through each door and expects one verdict; the client's suite against the release candidate.
- **Reverse:** revert; no data format changes.
- **Why early:** it removes the most dangerous pattern (03, conclusion 3); T7 moves the guards from this one place.

### T6. Six states, one envelope, one log per Mission

- **Does:** states `planned`, `in_progress`, `for_review`, `in_review`, `approved`, `canceled`; `blocked` as a flag; an override as its own event; decisions and Mission position in the same log. Still a file.
- **Deletes:** the frontmatter lane mirror (`status/emit.py:640, 823, 879, 1207` [read]); `decisions.events.jsonl`; the two sentinel states; the force flag as a meaning of a state.
- **Prerequisites:** D5 (default: yes, before the record contract reaches 1.0); P8; T5.
- **Persistent data and contract: yes.** `claimed` and `done` vanish. Consumers: every project's log; `fleet-kitty`; `spec-kitty-planning` (18 files); the orchestrator scheduler; 12 pack prompts; the events contracts below 1.0 (04 §12 [relayed]).
- **Transitional:** a name map reads old rows; it ends at T11 with the old-format reader.
- **Stronger assurance:** P8 over the 859 landed Missions; consumers told one release candidate ahead. The stamp fields that landing still reads (O06) stay until T11.
- **Verify:** the fold of every existing log gives the mapped state it gave before.
- **Reverse:** before a general release, revert, with the map read in reverse. After release: not cheaply.

### T7. Guards and fold behind `append`

- **Does:** the transition operation of T5 moves into `spec_kitty_events` as `append(event, facts, expected_tip)`; core supplies the facts. A local-file adapter sits behind the event port.
- **Deletes:** core's state machine and reducer copies (`status/wp_state.py:221`, `status/models.py` [relayed]); parity against a pinned core commit as the method (O14).
- **Prerequisites:** D4 (default: Python library in process); P2; T6; a release of the events package.
- **Contract:** the events package's public API. The default challenges the recorded "no Python fallback writer" (04 §5 F3).
- **Transitional:** the local-file adapter; it ends with T11.
- **Verify:** the door table of T5 passes against the package; core holds no legal-edge table (a gate).
- **Reverse:** the append contract is the same for both writers, so the choice stays reversible; the move itself by revert and a pin back.

### T8. The record on a ref, with `sync`

- **Does:** new Missions write `refs/heads/spec-kitty/record` by compare-and-swap; `sync` fetches, replays local-only rows through the state machine and pushes the record with the commits its events name; every command counts unshared events; `accept` and `land` refuse while the record differs from the remote.
- **Deletes:** nothing yet. Old-format Missions keep the file.
- **Prerequisites:** D1 (default yes), D2 (default `auto`), D16 (default one ref per repository, after P1); P9; T7.
- **Persistent data and contract: yes.** A branch `spec-kitty/record` appears on the forge. Consumers as in T6, plus the read-service resolver.
- **Transitional:** old and new Mission shape side by side, chosen by the Mission's format field. **End: T11; no general release ships both.**
- **Stronger assurance:** the two-clone scenario of ST S1 as an acceptance test (a stale approval after a rejection is refused at replay); a forge rule matching every branch; a sandbox without push credentials.
- **Verify:** the working tree stays clean after every state-changing command; a refused push is replayed and reported.
- **Reverse:** new Missions fall back to the file adapter by the format field; a record on the ref is exported by one read.

### T9. Work-package branches, `accept`, `land`, API 2.0

- **Does, for new-format Missions:** `start` cuts a branch from the Mission tip; a verdict names a commit; approval integrates by merge; `accept` names the tip and lists unreviewed commits; `land` checks tree equality and moves the target once. API 2.0 renders the same operations.
- **Deletes:** nothing yet.
- **Prerequisites:** D3 (default: on approval), D11 (yes), D12 (interactive), D13 (merge commit); P4 and P6; T8. Git 2.38.
- **Persistent data and contract: yes.** New Missions have no `lanes.json`, `--topology` or lane ids. The guarantee changes from per-line proof to "a human accepted the tip, with unreviewed commits named" (04 §5 F1). Consumers: operators, step prompts, two recovery guides, both API clients.
- **Transitional:** present command names and API 1.x verbs as aliases. **End: 4.1.0 (T15).**
- **Stronger assurance:** P6; the F1 experiment (two clones integrate and join) kept as a test.
- **Verify:** `land --dry-run` runs the same checks as `land`; undo swaps back to the tip stored in the landing event.
- **Reverse:** the old shape stays available while both exist. If P4 fails, the step is redesigned with thin lanes before T11.

### T10. Stateless `decide`; one type format

- **Does:** `decide` is a function of `type.lock.yaml`, the artefacts and the record; one definition format; replacing a built-in needs an explicit `replaces:`; `dispatch` takes or asks for a profile and writes Ops to `ops.jsonl`.
- **Deletes:** the run cursor and run index, the internalised engine and its bridge (most of `src/runtime`, 17,627 lines [relayed]); four older definition generations; workflows; `RESERVED_BUILTIN_KEYS`; the keyword router.
- **Prerequisites:** T4, T8.
- **Persistent data: yes.** Custom `.kittify/missions/<key>/mission.yaml` and workflow files stop loading. Consumers: projects with custom types, organisation packs, the pack composer. Migration: a converter in the charter system, one run per type.
- **Verify:** an upgrade in the middle of a Mission does not change its step list (ST S7); a custom type and a built-in type load through one path.
- **Reverse:** before release, revert. RACI and significance scoring (M2.6) stay until their intent is decided.

### T11. Remove the old Mission shape as a set

- **Deletes together:** the topology grid, the coordination branch and worktree, the placement seam (`src/mission_runtime`), execution lanes, consolidation with its gate axes, attestations and rollback authority, both status write shells and the read door, the ordering rules and merge driver, the protection policy, committed `status.json`, the produce seam, the file adapter, the name map, the doctors of deleted stores, and the gates that pin them (O41). In the events repository: `Topology.yaml`, `WriteSurface.yaml` and the read-directory rule.
- **Prerequisites:** T9 and T10 proven on the release-candidate line; D8 (default: no import); D14 (`--commit-to-target` given up); D15 (the consolidation, topology and coordination ADRs superseded as sets); P10.
- **Persistent data and contract: yes, and this is the step that cannot be undone after release.** Missions in flight in the old shape cannot continue on the new CLI. Landed Missions stay as files in history.
- **Trade-off (D8):** with no import, each open Mission lands on the last release that has `consolidate`: one extra landing, a pinned old CLI, a split identity. A bounded import keeps thousands of lines until 4.1.0 (04 §5 F7).
- **Stronger assurance:** the answers of P10; a last release with `consolidate` that stays installable; a refusal with a named remedy when the new CLI meets an old-format Mission; the registrants' owner agrees before the seam goes.
- **Verify:** no source file names a topology; each of the 18 strict `xfail` residuals is checked against the new listing before it is deleted; one Mission of each built-in type runs from `create` to `land`.
- **Reverse:** before 4.0.0, revert the set. After, only by reinstalling the old release.

## 5. The side tracks: T12 to T15

### T12. Charter switch

- **Does:** the charter system reduces the activation model and compiles a committed bundle; equivalence with the Python charter is shown in CI on the conformance corpus; one switch release makes core read the bundle.
- **Deletes:** the Python charter in core (about 85,000 lines; a move for half of it), context state, the per-worktree daemon and run-time graph, the template chain, legacy activation keys.
- **Prerequisites:** T3; D6 (default: 4.0.0 waits); D7 (default: also `only:` and opt-in kinds); a charter-system release with `compile`.
- **Persistent data: yes.** `charter.yaml` selections and legacy keys are ignored. Consumers: every project with a charter; organisation packs. Migration: one converter that writes `only:` where a project had narrowed.
- **Transitional:** the Python charter behind the seam. **End: before 4.0.0, or 4.1.0 by D6.** Nothing is added to the Python side meanwhile.
- **Verify:** the same text in every checkout of one commit; a pin bump on a narrowed pack changes nothing; a hand edit of the bundle is detected.
- **Reverse:** nothing changes until the switch release. After it, a revert restores the Python charter; the converter keeps its input files.

### T13. Tools as data rows

- **Does:** one row per tool, one ownership manifest; a tool that fails P3 keeps a renderer or is dropped by ruling.
- **Deletes:** the per-tool tables, three of four manifests, `AGENT_DIRS` in a migration module; user-global installs and session hooks, feature by feature.
- **Prerequisites:** P3; D10. **Persistent data:** generated files in tool directories; the reconciler removes only what it owns. A user's other projects on an older CLI lose global commands: announced, not solved.
- **Verify:** generated files for each tool compared with today's before any table is deleted. **Reverse:** revert and re-run the reconciler.

### T14. Baseline cut

- **Does:** shape 4 with `schema_version` as the one authority; floor 3.2.x through a pinned stepping stone; one converter; reconcilers for tool files and ignore lines, which also remove old merge-driver lines.
- **Deletes:** the migration registry, ledger partitions, order manifest and supersession; the `migrate` family; run-time legacy readers in 26 files; the doctor family down to one.
- **Prerequisites:** T11, T12, T13, so the converter is written once for the final shape; D9; D15 (the migration-ledger ADR and a ruling that a baseline cut is a retirement under DIRECTIVE_044).
- **Persistent data: yes, one-way.** Consumers: users below 3.2 (two commands), four open-packs prompts.
- **Stronger assurance:** the converter runs on copies of real projects at each supported shape, with a preview, and refuses what it does not recognise.
- **Verify:** a project at the floor converts and passes the one doctor. **Reverse:** the converter keeps a backup; the old release reads it.

### T15. 4.1.0

Removes the aliases, a bounded import if D8 chose one, and what P5 names in `cli` and the unassessed packages. It ends the last transitional arrangements.

## 6. Transitional mechanisms and their ends

| Mechanism | Introduced | End condition |
|---|---|---|
| Declared and Python guards evaluated together | T4 | one release candidate without a disagreement |
| Shrink-only count of pack literals in core | T4 | zero, at T10 |
| API warnings in place of the new refusals | T5 | one release candidate |
| Name map for old state names | T6 | T11 |
| Local-file adapter behind the event port | T7 | T11 |
| Old and new Mission shape by format field | T8 | T11; no general release ships both |
| Command names and API 1.x verbs as aliases | T9 | 4.1.0 |
| Python charter behind the seam | T3 | before 4.0.0; 4.1.0 if D6 says so |
| Last release with `consolidate`, for Missions in flight | T11 | no code in core; the architect dates the end of its support |
| Bounded import, only if D8 chooses it | T11 | 4.1.0 |
| Pinned 3.2.x stepping stone | T14 | no code in core; the pin stays installable |

A mechanism still present after its end condition is a finding, not a default.

## 7. Decisions the steps wait for

| Decision (first step) | Default assumed | If the ruling differs |
|---|---|---|
| D5 six states (T6) | yes | nine states stay; T6 keeps only the envelope |
| D4 writer (T7) | Python library | the Java service is bound; a launcher is added |
| D1 record off the tree (T8) | yes | a partition survives; T11 shrinks to the coordination copy |
| D2 the tool may push (T8) | yes, `auto` | `manual` only |
| D16 ref granularity (T8) | per repository | per Mission; more forge branches |
| D3 integration on approval (T9) | yes | integration at acceptance; a dependency merge returns |
| D11, D12, D13 (T9) | API 2.0; interactive; merge commit | per decision |
| D8 Missions in flight (T11) | no import | bounded import until 4.1.0 |
| D14, D15 (T11, T14) | flag given up; supersede as sets | the policy component stays; ADRs amended one by one |
| D6, D7 (T12) | wait; `only:` and opt-in kinds | 4.0.0 ships the Python charter |
| D10 (T13) | rows; features by desk check | per-tool renderers stay |
| D9 (T14) | floor 3.2.x | the floor moves; the converter grows |


## Limits

Two risks apply to every step. A gate that pins the old shape refuses the deletion (O41): each step retires that gate by name and adds the replacing one. Prompts in `spec-kitty-open-packs` drift from the new commands (O28): each step lists its prompt changes and takes one pin bump. The order follows 04 §11; both candidates agree on it. No effort is estimated. The Java and charter repositories were not opened; T7 and T12 rest on relayed statements about them.
