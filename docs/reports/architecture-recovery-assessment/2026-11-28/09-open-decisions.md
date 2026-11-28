---
doc_status: draft
updated: '2026-11-28'
---

# 9. Outstanding decisions for the architect

Consolidator K4, profile `architect-alphonso`; its verb "decide" yields to the envelope. Decision ids D1 to D16 are those of `06-capability-dispositions.md` section 2, unchanged. D17 to D22 are added here because the inputs raise them and no id covered them. `04`, `06`, `08` are the deliverables of this folder; CH is `challenge/candidate-challenge.md`; "steelman S6" is an item of `challenge/steelman.md`. Tags: [read] and [executed] are mine at head; [relayed] is checked by an input. Mechanism ids (M1.1) and capability ids (C07) are those of `06`.

## 1. Conclusion

1. **Twenty-two decisions are open. Three gate most of the deletion.** D1 (the record may leave the target tree), D2 (the tool may push it) and D3 (approved work is integrated on approval) together decide whether topologies, the coordination branch, execution lanes and consolidation are replaced as a set, or only tidied. That set is about 96,000 lines in five packages (CH [relayed]).
2. **Three more decide how, not what.** D17 authorises the experiments that raise the confidence of D3, D4, D10 and D16. D15 decides whether recorded decisions are superseded as sets. D22 decides whether the break belongs to 4.0.0.
3. **Every decision has a default.** If no ruling is given, the recommended architecture proceeds on the defaults in section 2. No default removes a capability rated core or important.
4. **Four defaults contradict something recorded** and are challenges under R1: D4 (the recorded "no Python fallback writer"), D13 (squash as default), D15 (amendment as practice), D9 (upgrade from every version).
5. **One fact would change several defaults and nobody has it**: how many users hold Missions in flight, or read the on-disk log, outside the repositories examined (D1, D8).

## 2. The decisions in order of what they unblock

| Rank | Id | Question | Default if no ruling | Unblocks |
|---|---|---|---|---|
| 1 | D1 | May the live Mission record leave the target tree, onto a ref | yes | M1.1 to M1.3, M1.6, M3.3, M3.4, M4.1; every later step |
| 2 | D2 | May the tool push the record and the commits its events name | yes, `sync: auto` | M4.1, M4.2, C32 |
| 3 | D3 | Is approved work integrated on approval, or at acceptance | on approval | M1.4, M1.5, M7.1, C07, C08, C11 |
| 4 | D17 | Are the reversible experiments and the reading pass authorised | yes, in disposable clones and at the desk | confidence of D3, D4, D10, D16; the size of the roadmap |
| 5 | D15 | Are the consolidation, topology, coordination and migration-ledger records superseded as sets | supersede | all of M1, M7, M8 |
| 6 | D22 | Does the breaking set land before 4.0.0 general availability | yes | the timing of D5, D8, D9, D11; every transitional end |
| 7 | D8 | Missions in flight: land on the old CLI, or a bounded import | no import | M8.6; when M1.1 and M7.1 can be deleted |
| 8 | D9 | Upgrade floor and removal of `migrate` | floor 3.2.x | M8.1 to M8.3 |
| 9 | D4 | Record writer for 4.0: Python library in process, or the Java service | library | M3.2, M4.4, M7.7 |
| 10 | D5 | Six states before the record contract reaches 1.0 | yes | M3.1 |
| 11 | D18 | Is "a human accepted the named tip, unreviewed commits listed" an acceptable landing guarantee | yes | M7.1, M7.2, M7.5 |
| 12 | D6 | Does 4.0.0 wait for the charter system's compile | wait | M5.1, M5.5 |
| 13 | D11 | API 2.0 of about 8 verbs, breaking both known clients once | yes | M6.2 |
| 14 | D12 | Acceptance: interactive unless a standing delegation, or an asserted actor | interactive | C10 |
| 15 | D7 | Is exclusion the only narrowing | no: also `only:` per pack, opt-in kinds | M5.2, M5.6 |
| 16 | D19 | Must a clone work without the charter system installed | yes: the bundle is committed | the delivery form of M5.1 |
| 17 | D13 | Default landing strategy | merge commit | M7.6, M1.8 |
| 18 | D10 | Is the list of 17 tools a commitment; which tool features stay | rows; features by desk check | M6.3, M6.4, C02 |
| 19 | D16 | One record ref per repository, or per Mission | per repository | the layout of M4.1 |
| 20 | D20 | Are the constraints of `08` adopted, including those that need a register | yes, with each roadmap step | nothing is blocked; nothing is protected without it |
| 21 | D14 | Optional capabilities C20, C26, C28, C31 and `--commit-to-target` | C26, C28 kept; C20, C31 reduced; flag given up | M1.11, M5.7 |
| 22 | D21 | Is event consumption by other systems (C25) a 4.0 need; who owns the preserved registrants | no; remove the seam once the ref is readable | M4.3 |

## 3. Each decision

Each block gives the options, what the evidence says, and the consequences for users and data (R16). "Blocks" and the default are in the table above.

### D1. The record leaves the target tree

- **Options.** (a) One append-only file per Mission on `refs/heads/spec-kitty/record`, never checked out. (b) A tracked file on the Mission branch, written by commit. (c) As now: tracked files on branches that carry code.
- **Evidence.** Four assessors named (c) independently as the cause of their mechanism's excess (`02` RC1). Both candidates chose (a) from opposite stances. The events repository has accepted commit by ref (`spec-kitty-events:docs/adr/0007-write-service-commits-coordination-status-by-ref.md` [read: present]); core's counterpart is Proposed [relayed CH]. (b) keeps default push and forge visibility, but the Mission tip moves on every event, so acceptance needs a definition of bookkeeping paths: a residue of the present gate (CH section 8).
- **Users and data.** `status.events.jsonl` and `status.json` are no longer written; a branch `spec-kitty/record` appears on the forge; an observer without the CLI reads JSONL there. Consumers: `fleet-kitty`, `spec-kitty-planning` (18 files name the log [relayed]; 21 by my `grep -rIl` [executed]), the hosted dossier, the read service's resolver, the orchestrator's scheduler, 12 pack prompts [relayed `04` section 12]. Landed Missions stay as text in history. Cost: one name map and one update per consumer.
- **Would change it.** A documented journey that needs the live record in the target tree. None was found.

### D2. The tool pushes

- **Premise to confirm.** Mission state is shared through git (C32), not through one store.
- **Options.** (a) `sync: auto`, the tool pushes after each state-changing operation. (b) `manual` only. (c) D1 (b), which makes the question disappear.
- **Evidence.** A plain `git push` leaves a branch that is not checked out behind [relayed CH, executed]. Today the tool pushes only under `consolidate --push` (`src/specify_cli/consolidation/phase_finalize.py:50` [read]). The charter forbids agents to push `origin/main` only (`.kittify/charter/charter.md:544` [read]); no recorded rule covers a push of another branch. Replay through the state machine is not built [relayed `04`].
- **Users and data.** A network round trip per state-changing command; credential prompts in agent sandboxes; a forge rule on every branch may refuse the push. Under (b) the protection is a printed count of unshared events and a refusal at `accept` and `land`.

### D3. When approved work is integrated

- **Options.** (a) On approval, into the Mission branch. (b) At acceptance. (c) Thin lanes, as the fallback.
- **Evidence.** (a) was reached independently by both candidates. CH F1: approvals in two clones no longer commute. Answered by experiment: a join by merge keeps every approved commit an ancestor [relayed `04`, executed]. Under (b) approvals commute again, but a dependent work package needs a merge of its predecessors and every conflict reaches the human at once. Unknown: how often an integration conflict forces a second review.
- **Users and data.** An agent's approval moves a shared branch at once; the target moves only on `accept` and `land`. A cancel after approval is a revert. Attestations, `--dependency-ref` and 22 flags go; two recovery guides are rewritten [relayed `04` section 12]. No data migration.
- **Would change it.** A pilot in which most Missions need a second review: then (c), and about 20,000 lines of consolidation stay.

### D17. Experiments and the reading pass

- **Options.** Authorise all, a subset, or none. The mandate authorises no implementation; these run in disposable clones or at the desk.
- **What they are.** A pilot Mission on work-package branches that counts re-reviews (D3). Push contention on one record ref (D16). A rule-by-rule comparison of the Java guards with core's (D4). A desk check of the tool row schema against the 17 tools (D10). Declarative step checks beside the Python guards. A module-by-module reading of `cli` and of about 79,000 lines no assessor covered (`06` X.1, X.3). A trial of constraints AC-01 and AC-07 on one package (`08`).
- **Evidence.** The end-state size of core (about 147,000 lines) carries 79,000 lines unassessed (`04` section 8).
- **Users and data.** None.

### D15. Supersede as sets

- **Options.** (a) One new record per subject that supersedes the old ones. (b) Amend in place, as now. (c) Leave the records and mark them historical.
- **Evidence.** Five landing records carry 41 amendment headings [relayed M7]; the migration-ledger record carries 8 (`docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` [executed: `grep -c`]). R1 permits the challenge.
- **Users and data.** None directly. Contributors and their agents read fewer special rules; `CLAUDE.md` shrinks with them.

### D22. The release that carries the break

- **Options.** (a) Every breaking change lands before 4.0.0 general availability; release candidates carry the old and the new Mission shape, no general release does. (b) 4.0.0 ships the present shape and the break waits for 5.0. (c) Split across 4.0 and 4.x.
- **Evidence.** R7 names "the best possible 4.0". The contracts that change are below 1.0 [relayed `04`]. (c) breaks the same consumers twice.
- **Users and data.** (a): release-candidate users meet one break. (b): every compatibility mechanism lives one more major version, and the record contract is broken after it reached 1.0.

### D8. Missions in flight

- **Options.** (a) No import: a Mission in flight lands on the last release that has `consolidate`; unfinished work continues as a new Mission. (b) A bounded import until 4.1.0. (c) A full import.
- **Evidence.** CH F7: an import performs the mixed-lane and canceled-content cases once, without the gate built for them. The number of users with Missions in flight is unknown.
- **Users and data.** (a): per open Mission one extra landing, a pinned old CLI and a split Mission identity; nothing is lost. (b): readers for `lanes.json`, the log and four topologies stay, thousands of lines; the only protection is a fresh `accept`. (c): none. The 859 landed Missions in core stay as files [relayed].

### D9. Upgrade floor

- **Options.** Floor 3.2.x with a pinned stepping stone; floor 3.0; no floor, as now.
- **Evidence.** 144 registered migrations [executed: `ls m_*.py`], 59 below 3.0 [relayed M8]. The start-up gate is a no-op: both bounds are 3 (`src/specify_cli/migration/schema_version.py:22-23` [read]). No documented need below 3.0 [relayed M8].
- **Users and data.** A project below 3.2 upgrades in two commands. Four open-packs prompts name `migrate` [relayed M8]. The migration-ledger files become inert.

### D4. The record writer

- **Options.** (a) `spec_kitty_events` as a Python library in process (CA). (b) The Java write service (CB).
- **Evidence.** The Python package checks edges, force and `review_ref` only [relayed CH]; reviewer independence is in core (`src/specify_cli/status/models.py:411` [read]). The Java service has three of four guards and no independence guard [relayed CH]. Its pin is not vendored: `pins/README.md:28` names the read service only [read]. Default (a) contradicts the recorded "no Python fallback writer" (`CLAUDE.md`, Shared Package Boundary [read]). The ref format is the same, so the choice is reversible.
- **Users and data.** (a): a pure-Python install; a guard change needs an events release. (b): a native process on every write, a launcher and a four-platform release matrix.
- **Disagreement kept.** CA and CB differ; the guard comparison of D17 and a ruling on a non-Python writer for 4.0 settle it.

### D5. Six states

- **Options.** Six states, `blocked` as a flag, override as its own event; or nine lanes as now.
- **Evidence.** Independent agreement of both candidates. A lane reached by force does not mean what it says, so landing re-reads history [relayed M3]. Steelman S15 and S16 are answered by "not finalized" and by an exclusive start.
- **Users and data.** `claimed` and `done` vanish as names: the orchestrator's scheduler, step prompts, `lane.schema.json`. One name map. Cheap before the contract is 1.0, a breaking change after.

### D18. The landing guarantee (added)

- **Options.** (a) Accept "a human accepted the named tip, with unreviewed commits listed". (b) Add a review requirement for commits made directly on the Mission branch. (c) Keep per-line proof, and with it lanes and about 30,000 lines.
- **Evidence.** CH grades the loss major, argued (C11). The present proof is itself incomplete: 18 pinned residuals [relayed M7]. The merge-attribute guard is given up: a local merge driver can alter an integration merge, which is then listed, not refused (`04` section 10).
- **Users and data.** An operator who relies on the gate to catch canceled content must read the acceptance listing. No data.

### D6. The charter switch

- **Options.** 4.0.0 waits for a charter-system release with `compile`; or ships with the Python charter, which ends at 4.1.0.
- **Evidence.** Two complete implementations disagree on what an absent activation key means; core has no client, pin or launch path [relayed M5]. The model must be reduced on the Java side before the switch, or the move deletes nothing (CH T7).
- **Users and data.** Wait: the date of 4.0.0 depends on another repository. Not waiting: rules delivery still depends on checkout state in 4.0, and activation breaks again at 4.1. `charter.yaml` selections and legacy keys are converted once.

### D11. API 2.0

- **Options.** About 8 verbs rendered from the same operations (CB); `--json` on every command as the contract (CA); keep the 27 verbs.
- **Evidence.** The API lands a Mission "with no claim and no gate behind it (and no rollback)" (`src/specify_cli/orchestrator_api/consolidation.py:586` [read]). The orchestrator calls `merge-mission` (`spec-kitty-orchestrator:src/spec_kitty_orchestrator/host/client.py:399` [read]); core registers `consolidate-mission` (`src/specify_cli/orchestrator_api/commands.py:619` [read]).
- **Users and data.** `spec-kitty-orchestrator` and `spec-kitty-mcp` update once. Transitions that pass today may refuse, the pre-review gate included. Aliases until 4.1.0.

### D12. Who accepts

- **Options.** Interactive unless a named human recorded a standing delegation; an asserted actor; identity verified by a host (not designed here).
- **Evidence.** Human in Charge is carried by mechanism at three points only, and the actor is a caller-asserted string [relayed M6, M7]. A terminal check is a recorded act, not proof of a human.
- **Users and data.** An unattended pipeline records a delegation once. An agent can no longer accept in a non-interactive session.

### D7. Narrowing

- **Options.** Exclusions only; or also `only:` per pack and opt-in kinds.
- **Evidence.** Steelman S6 holds: an exclusion list does not hold a narrowed set still when a pack grows. Both candidates lost it; CH F5.
- **Users and data.** The converter writes `only:` where a project had narrowed. With exclusions only, a pin bump brings rules into force with no human act.

### D19. A committed bundle (added)

- **Options.** The compiled bundle is committed and built-ins are precompiled in the wheel; or it is not committed and every clone and CI job needs the charter system.
- **Evidence.** `04` assumes "yes" without a ruling. The manifest must hash outputs too, or a hand edit passes (CH C18).
- **Users and data.** Committed: a bundle diff in every rules change, reviewable. Not committed: a Java tool on every contributor's machine.

### D13. Landing strategy

- **Options.** Merge commit by default, squash optional with an `Accepted-Commit` trailer; or squash by default. `rebase` is removed in both.
- **Evidence.** After a squash landing `git branch -d` refuses although the trees are equal [relayed CH, executed]. Squash's reason was bookkeeping commits, which leave the branch under D1.
- **Users and data.** The target shows a Mission's commits behind one merge commit. A team that requires linear history chooses squash.

### D10. Agent tools

- **Options.** Rows for all 17 with features decided by a desk check; two open formats only; keep the renderers.
- **Evidence.** Three tool-named renderers and eight provider modules exist; the row schema is unproven [relayed CH]. Steelman S5 holds.
- **Users and data.** A tool that fails the desk check keeps a renderer or is dropped by ruling. Without user-global installs, a user's other projects on an older CLI lose global commands: announced, not solved.

### D16. Record granularity

- **Options.** One ref per repository with one file per Mission; or one ref per Mission.
- **Evidence.** Replay per file works mechanically [relayed `04`, executed]. Contention is unmeasured (D17).
- **Users and data.** One extra forge branch against one per Mission. Cheap to change before the contract is 1.0.

### D20. The constraints and the knowledge capability (added)

- **Options.** (a) All 27 constraints of `08`, registers in core, a cross-repository index for two. (b) Only the 18 a check decides alone. (c) None until the remediation is done.
- **Evidence.** The present gates pass with all ten patterns present; no check can decide whether a new mechanism duplicates an old one (`08` sections 1 and 4).
- **Users and data.** None for users. Contributors keep a few register files; a release can fail on a transitional entry that reached its end.

### D14. Optional capabilities

- **Options.** Per item: keep, reduce, drop.
- **Evidence.** C26 is rated important with journeys J2 and J5; CA's reduction rested on a false premise [relayed CH]. C31 has no journey [relayed CH]. C28 was not assessed, and the README's promise for it is unmet (`needs/needs-and-journeys.md` section 4 [read]).
- **Users and data.** A user of `--commit-to-target` lands through `land`. A reopen becomes a new Mission that cites the old one.

### D21. Event consumption by other systems (added)

- **Options.** Remove the produce seam once the ref is readable; or keep it.
- **Evidence.** No registrant in core's `src` [executed: no call of a `register_*_handler`]; registrants are preserved in `event-router`, 11 files [relayed CH]. Steelman S17: a read surface must exist first.
- **Users and data.** The owner of the hosted surfaces turns registrants into readers of the ref.

## 4. Dependencies between the decisions

- D2 and D16 have a subject only if D1 is (a).
- D3 presumes D1: with status in the tree, integration on approval would move the status file on every approval.
- D5 comes before the record is first written to the ref, or the name map is applied twice.
- D8 and D9 follow D22: the floor and the import are counted from the release that breaks.
- D18 follows D3: under thin lanes an attribution rule returns, and D18 (c) is the consequence.
- D19 follows D6.

## 5. Limits

- The defaults are those of `06`; I changed none. D17 to D22 are my additions and carry my defaults.
- The ranking is a judgement of how many dispositions wait, read from `06` sections 2 to 4. I did not read `05` or `07`, written in parallel; a roadmap step may order two neighbours differently.
- Decision-material and unknown: users with Missions in flight; readers of the on-disk log outside these clones; whether a non-Python writer is required for 4.0. Settled by experiment: everything under D17.
