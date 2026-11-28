---
doc_status: draft
updated: '2026-11-28'
---

# Challenge of the candidate architectures

Assessor CH, profile `paula-patterns`. The profile's scout swarm and its "decide" verb yield to the envelope: I answer from one lens and recommend. `A/` is this folder. Code references are to core at head unless a repository is named; every one was checked by me and carries [read], [executed] or [inferred]. Grades: **major** (would change a disposition or the roadmap), **minor**, **note**. Row-level detail is in `reference-checks.csv` and `forks.csv`.

## 1. Conclusion

The two candidates were written from opposite stances and reached the same four structural choices: the record on a git ref no checkout holds, one branch per work package, integration on approval, landing by tree equality. That agreement is the strongest result of the exercise. The code facts both relay hold up: 19 of 20 sampled references are true, and of the 20 load-bearing claims checked 13 are true, 5 partly true and 2 false.

Seven findings are major. Four apply to both candidates in full.

| # | Finding | Applies to | Grade |
|---|---|---|---|
| F1 | Integration on approval moves the join problem from the status file to the Mission branch. Two clones that each approve a work package produce two Mission-branch tips. Neither candidate gives the join rule for the code branch, and the recorded events name commits that the join invalidates | both | major |
| F2 | Nobody pushes the record. A branch that is not checked out is not pushed by a plain `git push`. Events then stay clone-local in silence, which is the "hidden local-only authority" C32 forbids | both; CA also denies needing clone-local git configuration | major |
| F3 | The lifecycle guards both hand to the events system exist only in its Java write service (dependency, claim and pipeline guards; no reviewer-independence guard found). CA takes that service off the path and names the Python package, which has edge rules only. CA must therefore write the guards a further time; CB must add one | CA major; CB minor | major |
| F4 | The `cli` package, 107,407 lines and the largest in core, has no disposition in either candidate. CA's end state of 25,000 to 40,000 lines does not follow from the deletions CA names | both; CA's headline | major |
| F5 | Narrowing by allow list (steelman S6) and the lane test-origin probe (S4) are lost. S6 is understated; S4 is not mentioned by either | both | major |
| F6 | CA's largest transitional arrangement, a trimmed Python charter compiler in core, has no end ("the architect sets the date") | CA | major |
| F7 | The flatten import for Missions in flight is priced at "a few hundred lines". It performs, once and without the present gate, the mixed-lane and canceled-content cases that the consolidation subsystem exists for | both | major |

None of these overturns the four shared choices. F1 and F2 must be answered before "integration on approval" and "the record on a ref" are put to the architect as decisions, because each changes what those decisions cost.

## 2. Against the needs

Capabilities rated core or important in `A/needs/capabilities.csv`. Rows not listed are provided by both with no loss I could find (C01, C03, C04, C05, C13, C19, C21, C23, C29, C30).

| Id | CA | CB | Loss or risk | Grade |
|---|---|---|---|---|
| C02 core | adapter rows in a pack; hooks, plugin bundles, native profile projection go | tool profiles as data; one manifest | Both assume a tool is "directory, format, placeholder". Three tool-named renderers and eight provider modules exist today (`src/specify_cli/tool_surface/profiles/`, `providers/` [read]). The row schema is unproven | minor |
| C06 core | one ref per repository | one ref per Mission | "Mergeable through git" holds only if F2 is solved | major (F2) |
| C07, C08 | branch and worktree per work package, cut from the Mission tip | same | Conflict avoidance becomes a warning. Admitted by both | note |
| C09 core | approval names a commit | same | A rejection after integration costs a revert. Admitted | note |
| C10 core | asserted actor; open decision 7 | interactive unless a standing delegation | CA leaves the one remaining integrity point as strong as an asserted name | minor |
| C11 core | tree equality | same | "Only reviewed work lands" becomes "a human accepted the tip". Commits made directly on the Mission branch (planning, conflict resolutions, target merges, reverts) pass through no work-package review. CB calls the target merge "a reviewed unit" without saying who reviews it | major, argued |
| C12 | protection policy deleted | protection policy kept | CA drops `--commit-to-target` in silence. CB keeps a component whose only caller, in its own design, is `land` | minor |
| C14, C15 | closed check vocabulary | same, with side-by-side evaluation for one release candidate | CA has no equivalence step before the Python guards go (steelman S14) | minor |
| C16 core | committed bundle | compiled files; committed or not is not said | If CB's files are not committed, every clone needs the charter system installed to work | minor |
| C17 | pack list plus exclusions | same | S6: an exclusion list does not hold a narrowed set still when a pack grows | major (F5) |
| C18 | compiler refuses an exclusion | same | CA hashes the inputs only; a hand-edited committed bundle passes the staleness check | minor |
| C22 | `--json` on every command | API 2.0, about 8 verbs | CA makes every command's JSON a public contract: a wider surface than today's 27 verbs | minor |
| C24 core | fold of the record | same, plus a `history.md` export | CB does not say when the export is written. If it is committed to the Mission branch it is a second store, and it moves the tip after acceptance | minor |
| C26 | reduced; "no documented journey" | kept | The capability is rated important and stated, with journeys J2 and J5 (`A/needs/capabilities.csv` C26 [read]). CA's reduction rests on a false premise | minor |
| C27 | import, floor | flatten converter, floor | F7 | major |
| C32 | fetch and push of the record ref, replay | same | F1, F2 | major |

CB states that nothing documented is dropped outright; that is correct. CA drops C28 and C31 (both optional; for C31 I confirm no guide describes close, reopen or follow-up as a journey: the only hits are an unrelated `--follow-up` flag, `docs/guides/how-to/missions/accept-and-merge.md:216` [read]).

## 3. Against the steelman

The seven items where the reason holds and the proposal loses it:

| Item | CA | CB | Verdict |
|---|---|---|---|
| S1 two clones write one Mission's status | replay of local events on the fetched tip through the state machine | the same rule | Answered for the record, and better than a wall clock. Not answered for the code branch (F1) |
| S2 landing without a forge | `land` moves the target locally; a pull request may also land it | `land`; publication stays a pull request | Answered by both |
| S3 mixed lanes against one unit per branch | one branch per work package | the same | Answered, independently |
| S4 lane test-origin probe | deletes the `lanes` package whole, which includes `lane_invocation.py` (476 lines [executed]) | not named; "worktree allocation" kept | Lost in silence. One worktree per work package raises the exposure |
| S5 native files for twelve tools | adapters kept as data | 17 rows | Answered: neither chose two formats only |
| S6 narrowing by allow list; skills absent default | a rule change is a reviewable diff of the committed bundle (answers the human-act half) | "long exclusion lists" | (a) partly answered by CA, not by CB. (b) "every pack skill is projected" is answered by neither |
| S7 frozen step definition | a digest in `mission.yaml`; a human re-pins; the live definition is evaluated meanwhile | `type.lock.yaml` commits the resolved definition | CB answers it. CA reports the change but does not freeze |

Conditional items where a candidate does not meet the condition:

| Item | Condition | Result |
|---|---|---|
| S8 never delete an unabsorbed branch | drop squash, or keep one absorption check | CA keeps squash and relies on `git branch -d`. After a squash landing `git branch -d` refuses both the work-package branch and the Mission branch, although the trees are equal [executed, scratch repository: branch, `merge --no-ff`, `merge --squash`, `branch -d`]. Users are pushed to `-D`. CB's rule (compare with the Mission branch) holds for work branches; for the Mission branch it needs the landing fact. Minor |
| S15 sentinel states | one source of work-package existence | CA: a `work-packages/WPnn.md` file with no event reads as `planned`, the #1589 shape. CB keeps `wps.yaml` and task files: still two sources. Minor, both |
| S17 produce seam | a read surface exists before the seam goes | CB retires the seam in step 1 and binds the reader in step 4. Preserved registrants exist outside core (11 files in `event-router` reference `status.adapters` [executed]). Minor |
| S13 reserved built-in keys | replacing a built-in type is an explicit, visible act | CB allows the override, CA is silent; neither states the act. Minor |
| S9, S10, S12, S16, S22, S36 | | Met by both. The `human-decision` step kind answers S36 well, in both independently |

Consumers the steelman lists that neither candidate names: `spec-kitty-planning` (18 files name the on-disk log); the orchestrator's transitions that start refusing once guards sit behind every door; a user's other projects on an older CLI when user-global installs are removed. Minor, R16.

## 4. Against reality

Ten claims per candidate, checked in the code. Full rows in `reference-checks.csv`.

### CA

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | Five packages total about 96,000 of 524,936 lines | true | 36,414 + 16,574 + 15,036 + 21,397 + 6,868 = 96,289 [executed: `find … -name '*.py' -not -path '*__pycache__*' \| xargs cat \| wc -l`] |
| 2 | Core ends at 25,000 to 40,000 lines | false as derived | The deletions CA names sum to about 256,000. About 269,000 remain, of which `src/specify_cli/cli` is 107,407 [executed] with no disposition |
| 3 | The events repository has accepted commit-by-ref with compare-and-swap | true, with a limit | `spec-kitty-events:docs/adr/0007-…-by-ref.md:3` [read]. It writes the coordination branch and refuses a checked-out ref (`:190`). Core's counterpart `docs/adr/4.x/2026-11-06-4-…md:4` is Proposed |
| 4 | The command set is a fixed tuple matching software-dev | true | `src/specify_cli/skills/command_installer.py:101-114` [read]. Research steps (`scoping`, `gathering`) get no command |
| 5 | The produce seam has no subscriber | partly | No call to a `register_*_handler` in `src` [executed]. Registrants are preserved in `event-router` (11 files) |
| 6 | A second and third copy of the state machine exist | true | `src/specify_cli/status/wp_state.py:221-605`; `spec-kitty-events:src/spec_kitty_events/status.py:692`; `spec-kitty-events:service/command-cli/…/domain/authority/UnitJudge.java` [read] |
| 7 | The in-process Python events package can be the one state machine with every guard (target; premise) | partly | Its `validate_transition` checks edges, force and `review_ref` only (`spec-kitty-events:src/spec_kitty_events/status.py:692-750` [read]). Reviewer independence is `src/specify_cli/status/models.py:411`; dependency readiness is `src/specify_cli/core/dependency_graph.py:35`, called from 6 files [executed]. The Java write service does carry `DependencyGate`, `ClaimGate`, `PipelineGuards` and `LaneMachine` (`spec-kitty-events:service/command-cli/…/domain/authority/` [read]), and CA sets it aside |
| 8 | Cleanup with `git branch -d` refuses only unmerged work | false under squash | See S8 [executed] |
| 9 | No clone-local git configuration is needed; the record travels by ordinary fetch and push | partly | Fetch: yes, it is a branch. Push: a plain `git push` sent the current branch and left `refs/heads/spec-kitty/record` behind [executed, scratch clone and bare remote] |
| 10 | The orchestrator calls a verb core does not register | true | `spec-kitty-orchestrator:src/spec_kitty_orchestrator/host/client.py:399` (`merge-mission`); `src/specify_cli/orchestrator_api/commands.py:619` (`consolidate-mission`) [read] |

### CB

| # | Claim | Verdict | Evidence |
|---|---|---|---|
| 1 | The owned checkout exists and can become the general rule | true | `src/mission_runtime/owned_checkout.py` [read] |
| 2 | `owned_files` is planning data in the manifest | true | `src/specify_cli/core/wps_manifest.py:53` [read] |
| 3 | `_GUARD_TABLES` keys guards by type name | true | `src/runtime/next/runtime_bridge_cores.py:859-864` [read] |
| 4 | The coordination ADR refuses a checked-out ref and moves the root checkout | true | `docs/adr/4.x/2026-11-06-4-…md:152,183` [read]; status Proposed |
| 5 | An event port exists; core binds no remote writer | true | `src/runtime/next/event_bridge.py:1-25` [read] |
| 6 | The produce seam has no registrant | partly | As CA 5 |
| 7 | The tool surface is "already declarative" | partly | Eight provider modules, among them `plugin_bundle.py`, `session_presence.py`, `native_config.py`; three tool-named renderers. A tool id literal occurs in 44 non-migration files [executed] |
| 8 | `MIN_SUPPORTED_SCHEMA` is one constant to raise | true | `src/specify_cli/migration/schema_version.py:22-23`; both bounds are 3 [read] |
| 9 | 144 registered migrations; 14 `migrate` subcommands | true | [executed: `ls m_*.py \| wc -l`; `spec-kitty migrate --help`] |
| 10 | 62 registered state surfaces | true | 62 `StateSurface(` in `src/specify_cli/state/contract.py` [executed] |

Also: CB gives the Python charter as "about 78,000" lines in its conclusion and "about 87,000" in its section 4.5. `src/charter` is 77,725; with `charter_runtime` and `charter_packs` it is 85,238 [executed]. Note.

Scale for the "no pack identifier in core" gate both propose: the literal `software-dev` occurs 156 times in 64 non-migration files [executed]. The gate is a programme of work, not a test to switch on.

## 5. Against themselves

| # | Where | What returns, or what is only a move | Grade |
|---|---|---|---|
| T1 | both, integration on approval | A merge into the Mission branch needs a clean checkout of it. A solo user in CB's "checkout the caller is already in" is on the work branch, so the Mission branch has no checkout. The merge then runs in a temporary worktree or by plumbing, followed by a ref update. That is the pattern whose side effect (`src/specify_cli/git/ref_advance.py:3-9` [read]: a checkout left behind its own HEAD) the resync code exists for | minor |
| T2 | both, F1 | Today approved lanes stay apart until one clone consolidates, so approvals in two clones commute. After the change they do not. A join rule for the Mission branch is a new mechanism neither names | major |
| T3 | both, guards in the events system | Copies of the edge rules are deleted: real. Under CA, independence and readiness are written again in Python while the Java port is shelved. Under CB they are where the Java service already has them, less independence. In both, the facts the guards judge (manifest, reviewed commit) are supplied by core, so two places must still agree, across a PyPI range (CA) or a pinned native binary (CB). The Java service today reads Mission facts from the root checkout (`FilesystemMissionCatalog.java:17` [read]), against both candidates' "knows nothing about worktrees" | major for CA (F3) |
| T4 | both, the literal gate | `review` and `accept` are step ids of the software-dev type and also core operations in both designs (CA 4.6: "review, accept and land are the three governed transitions"; CB: `act`). The work-package loop is therefore known to core by name. Neither says where the line between a core verb and a pack step id runs. This is the architect's own example in a smaller form | minor |
| T6 | CA, "nothing is clone-local" | Unpushed record events are clone-local authority until someone pushes (F2) | major (F2) |
| T7 | CA, the charter | "Leaves core" is a move of 78,000 lines of concept into a Java compiler, with a Python compiler kept in core without an end (F6). The model reduction is real; the line count is not a deletion | major (F6) |
| T8 | CB, definition stores | A mission-type definition lives in the pack, in `compiled/` and in each Mission's `type.lock.yaml`. Three copies with one authority is defensible; the lock does not say whether prompts are frozen too | minor |
| T9 | CB, the ledger writer | A resident native process on every write, reached through a port with one implementation after step 4. CB lists this itself as complexity its stance keeps | note, argued |
| T10 | both, F7 | The flatten import is the consolidation problem run once without its gate. "A fresh accept" is the only protection against canceled content on a shared lane | major |

## 6. Against the principles (R8)

| Principle | CA | CB |
|---|---|---|
| Human in Charge | Weakened at `accept` (asserted actor); **argued**, as open decision 7. Rule changes on a pin bump: argued through the committed diff. Attestations become override events: argued | Strengthened at `accept` (interactive, standing delegation). Rule changes on a pin bump with a narrowed set: **silent** |
| Responsible delegation | An agent's approval now moves the Mission branch at once; before, nothing integrated until a human ran consolidation. **Silent** | Same change; argued only as the cost of a late cancel |
| Explicit responsibility ownership | Per-line authorship proof dropped; listed as "worse at". Direct commits on the Mission branch carry no review: **silent** | Dropped and **argued** by name in section 10. Direct commits: **silent** |
| Independent evolvability | Three contracts; bundle schema frozen first. A guard change now needs an events release and a lock refresh in core: **silent** | The same, plus a native binary pin on the write path: listed, not argued as an evolvability cost |
| Governed coordination | Conflict avoidance becomes a warning: argued. Guards behind every door: stronger | Same |

Neither candidate weakens a principle without leaving a trace somewhere in its text, except the two silent rows on direct Mission-branch commits and on delegation.

## 7. Target, transitional, legacy; trade-offs; deletion (R16 to R18)

| Check | CA | CB |
|---|---|---|
| Target, transitional and legacy kept apart | yes (section 11) | yes (section 11, three lists) |
| Every transitional mechanism has an end | no: the Python compiler has none (F6); the others end in 4.1 | yes: each of six names a step or 4.1 |
| Breaking changes as trade-offs | 10 rows with consumers and options | 9 rows, each with a recommended option |
| Missing from both tables | who pushes the record; the Mission-branch join; `spec-kitty-planning`; orchestrator transitions under central guards; user-global files of other projects; the test-origin probe | the same |
| Deletes, or redistributes | Deletes most. Moves: guards, charter, tool tables. Headline end state unsupported (F4) | Replaces three subsystems; names what it keeps and why. Its counts are smaller and consistent with its sources |
| States what would change its mind | yes | yes |

CB is the better-formed proposal against R16 and R17. CA is the more complete deletion against R18 but overstates its end state.

## 8. Where they agree and differ

Full table with costs in `forks.csv`. "Independent" marks agreement reached from opposite stances.

| Fork | CA | CB | Decided by |
|---|---|---|---|
| Record location | a ref no checkout holds | the same | **Independent.** A ruling that the live record need not be in the target tree |
| Record granularity | one ref per repository | one ref per Mission, one for Ops | An experiment on push contention; a ruling on branch clutter on the forge |
| Unit of isolation | branch per work package | the same | **Independent.** A pilot measuring re-review after integration conflicts |
| When work integrates | on approval | on approval | **Independent.** A product ruling; F1 answered first |
| Landing | tree equality; fast-forward or squash | tree equality; merge or squash | **Independent.** The default strategy is a ruling; squash needs an absorption check |
| States | six, a flag, an override event | the same | **Independent** |
| Activation | pack list plus exclusions | the same | **Independent**; both lose S6. A ruling on whether exclusion is the only narrowing |
| Tools | data rows | data rows | **Independent.** A desk check of the row schema against the 17 tools |
| Ledger writer | Python library in process | Java service | A ruling on a resident native process for 4.0. Same ref format, so reversible |
| Charter delivery | committed bundle, precompiled built-ins | compiled files; charter verbs forward to the charter system | Whether a clone must work without the charter system installed |
| Step definition in flight | digest, human re-pins | committed lock | S7: whether a Mission may change steps under a running CLI |
| Programmatic contract | `--json` on every command | API 2.0, about 8 verbs | How much surface is promised to the two known clients |
| Acceptance identity | asserted | interactive unless delegated | Ruling (CA decision 7, CB decision 10) |
| Optional capabilities C20, C26, C28, C31 | dropped or reduced | kept | Ruling per capability |
| Protection policy | deleted | kept | Whether `--commit-to-target` survives |
| Charter transition | Python compiler in core, no end | one switch | A date; or CB's form |

One alternative both reject in a line deserves a second look before the first fork is put to the architect: the record as a tracked file on the Mission branch, written by commit without a checkout. It keeps default push and forge visibility (F2 disappears). Its cost is real: the Mission tip moves on every event, so "accepted commit equals Mission tip" needs a definition of bookkeeping paths, which is a residue of the present gate. The candidates are right that this is worse; they do not show the price of their own choice at the same point.

## 9. Spot check of source references

**Draw.** All data rows of `A/mechanisms/M1-evidence.csv` to `M8-evidence.csv` and `A/duplication/catalogue.csv` were concatenated in that order: 437 rows. Twenty were drawn with Python `random.Random(20261128).sample(rows, 20)`.

**Result.** 19 true, 1 partly, 0 false.

Rows drawn per source: M1 2, M2 4, M3 1, M4 4, M5 2, M6 1, M7 2, M8 3, catalogue 1.

The one "partly": catalogue row 1.9, "31 comparisons of step id against a literal", 16 of them in `runtime_bridge_cores.py`. The row gives no pattern. `step_id (==|!=|in) <literal>` finds 15 in `src`, 11 of them in that file; a wider pattern over `step`, `step_id` and `action` finds 24 there [executed]. The pattern is real; the count is not reproducible as written.

Five executed counts in the sample reproduced exactly. The mechanism assessments can be relied on at the level of their references.

## 10. Limits

- The join failure in F1 is reasoned from git semantics and the candidates' text; I did not build a two-clone reproduction. It is cheap to settle by experiment.
- I read the guard set of the events Python package in full and the Java write service's authority package by file names and two class headers; I did not compare the Java guards with core's rule by rule.
- I did not test any agent tool against a data-row adapter.

What would change my grading: a stated join rule for the Mission branch with a reproduction (F1); a ruling that the tool may push the record itself (F2); a dispositions table for `cli` (F4).
