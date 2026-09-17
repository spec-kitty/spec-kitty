# Final provenance manifest

Factual evidence assembly only; no review verdict, test run, repository mutation or CLI operation. Sources: Git object metadata, retained WP handoffs, canonical status.events.jsonl and retrospective.yaml. Snapshot inspected after canonical local merge. Original mission code baseline be490214baa3cb1ee54b153e254b48f572ca40a1; integration incorporates upstream b17a81506.

## Exact implementation commits

### WP01

- red: `7609fa3d8e4d98943ae9bc0b3663d4f7f43da546` — test(WP01): reproduce corrupt config startup and unreadable diagnostics
- red live integration: `d869b547bc70e11adf10407d08dd317466d5945f` — test(WP01): pin live consistency and global doctor failure paths
- tidy explicit UTF8: `6f50427ecfcc9b669637398caa240e9687ca6354` — refactor(WP01): make git metadata UTF-8 encoding explicit
- format only: `333bd3984ad23ec25fb4bd77f054dea932f91db4` — style(WP01): format owned boundary modules with the pinned formatter
- formatter exclusion shrink: `273f752cf1b30ed94d019da97de9f89bb4f9a8fc` — chore(WP01): retire formatter debt exemptions for cleaned boundary modules
- functional: `d8d9bd47c2e832d15e97a4985c5e87d63e950187` — fix(WP01): contain unreadable config and version metadata at CLI boundaries

### WP02

- red: `60c420d0d9b9b51495e4cfac4647db8369059f5e` — test(WP02): capture JSON seam and doctor guard adoption failures
- additional coordination red: `df701062792679ae20b2e9e6c5181186fc35bc93` — test(WP02): pin canonical coordination error envelope
- functional; no distinct tidy commit: `105ef7167c85378d091918beaac0a611b54b3eda` — fix(WP02): unify JSON boundary errors and doctor root guards

### WP03

- red cycle1: `339bcb15a0df05e2ec9d6c86036be148328bef70` — test(WP03): reproduce context default and JSON boundary failures
- tidy cycle1: `16cfcf8e2dd175b36a43b785218ed0372d5b7856` — refactor(WP03): remove unused context imports before boundary changes
- functional cycle1: `24ef6acf7f5cb7a83d95006d9b7949d3d770ccda` — fix(WP03): preserve context defaults and canonical JSON failures
- red cycle2: `c48aae8cdcad844b004428df3f4a44aeacc3fb1c` — test(WP03): reproduce undecodable and unreadable mission tokens
- functional cycle2 token read: `da03c5daddc0935f730c59a09dfdcf48c8b645a8` — fix(WP03): translate unreadable mission token failures at command boundary
- red implementation cycle3: `f9e9b9bdba793305be1a44dddade076a66009a32` — test(WP03): reproduce workspace metadata read failures
- functional implementation cycle3 workspace read: `466c75b3dd4c9eaff54886bc8603e5cf373b771e` — fix(WP03): render workspace read failures at context boundaries

### WP04

- red: `487814ca4176aaf883708968e3a4b977013e5880` — test(WP04): reproduce mission-type configuration and JSON boundary failures
- tidy: `af3386f970f00b888a1ba4b1a28d8aa5106b5378` — refactor(WP04): separate mission-type row construction from rendering
- functional: `4ea7b2f9700f248f2f6c6e515e000a0d9b39f73c` — fix(WP04): enforce mission-type configuration and JSON error boundaries

### WP05

- red cycle1: `51a46c5a9b6d81004b353d953496fb147e8235c9` — test(WP05): reproduce empty status and remaining JSON boundary failures
- functional cycle1; no distinct tidy commit: `a2aea67b05b594ed90fc52aeddda591aeb1105c2` — fix(WP05): preserve empty status success and unify adopted JSON errors
- red cycle2: `99e37ca935f5bcd9caa21a5f9b71aed51e5f2fe1` — test(WP05): reproduce rejected selector JSON boundaries
- functional cycle2 selector correction: `60d2d0b1a74f198aa1f9234f7e67d4a5c787a4f7` — fix(WP05): normalize selector failures before command rendering
- fixture-only implementation cycle3; existing test red recorded, no synthetic red commit: `819e78c8b98d6e652422bb9000abcbd1c275f118` — test(status): align missing-mission fixture with canonical error contract

### WP06

- red original-baseline guard proof: `e75d427e2f2f12c3ea4101789a96f909e3390fb6` — test(cli): record architectural boundary regressions on mission baseline
- completed test harness; no product implementation or distinct tidy: `36e945bd8c1f572a5680acdc92e4118618d76ee6` — test(cli): guard registered JSON boundaries and callback output

Tidy distinctions are explicit: WP02 has no separate tidy commit; WP05 cycle1 likewise recorded a process deviation rather than relabeling functional changes. Fix-mode cycles intentionally avoid unrelated tidy work. WP06 is test-only; red proof ran its real boundary tests against original source before harness completion. WP05 cycle3 used the existing failing golden-contract test (1failed), then corrected only its expected shape/exit; no invented test or empty commit.

## Canonical review verdicts

WP03 and WP05 each have four review cycles but three implementation cycles: reject→approve→reopen/reject→approve. Cycle numbers here come from canonical review references, not counts of actor-repair transitions.

| WP | Event | Transition/verdict | Actor recorded |
|---|---|---|---|
| WP01 | `01M2NYBD3BE5JN1V405KSCMKWX` | in_review→approved; approved | codex:gpt-6:reviewer-renata:reviewer |
| WP02 | `01M2P0BCKE0YCE4WCM9CFBFH17` | in_review→approved; approved | user:None:None:reviewer |
| WP03 | `01M2P1WD76ZXT0RH0WGMD2JYJ3` | in_review→planned; changes_requested | codex:gpt-6:reviewer-renata:reviewer |
| WP04 | `01M2P1Z9YYC817RMDAG3GXC6A8` | in_review→approved; approved | codex:gpt-6:reviewer-renata:reviewer |
| WP05 | `01M2P2943P6KCX4VXGANNEZZKK` | in_review→planned; changes_requested | codex:gpt-6:reviewer-renata:reviewer |
| WP03 | `01M2P2MKA9ZMJ2NNZ375JEKTRX` | in_review→approved; approved | codex:gpt-6:reviewer-renata:reviewer |
| WP05 | `01M2P3A742HM2Q0H0M6NG4YXY0` | in_review→approved; approved | codex:gpt-6:reviewer-renata:reviewer |
| WP03 | `01M2P4NJBJAWTRNCHSH2MZH5D5` | in_review→planned; changes_requested | codex:gpt-6:reviewer-renata:reviewer |
| WP05 | `01M2P6VS0PR4MK9SHGKFKW3H7P` | in_review→planned; changes_requested | codex:gpt-6:reviewer-renata:reviewer |
| WP03 | `01M2P6YP40MZMMM53E5BCGRSTG` | in_review→approved; approved | codex:gpt-6:reviewer-renata:reviewer |
| WP05 | `01M2P7DA2BXW5Z4ZW5G3NB0CXD` | in_review→approved; approved | codex:gpt-6:reviewer-renata:reviewer |
| WP06 | `01M2P7N4TJV3S6Z0XZGWZBC3FP` | in_review→approved; approved | codex:gpt-6:reviewer-renata:reviewer |

**WP02 actor misattribution #4670:** event01M2P0BCKE0YCE4WCM9CFBFH17 stores actor tool=user and reviewer Robert Douglass because generated verdict command omitted explicit --agent. Actual independent reviewer-renata evidence is tasks/WP02-canonical-json-contract/review-evidence-1.md (9579f8749) and125independent passing tests. Do not claim Robert personally reviewed. Subsequent commands explicitly supplied actor. WP04 event has structured Renata actor but its nested reviewer display is also Robert Douglass; retain distinction rather than rewriting history.

## Force flags: semantics and reasons

All approval events above have force=false. The canonical event log marks backward review rewinds force=true even when initiated through the supported rejection/reopen flow. Same-lane assignment repairs are separate metadata recovery operations for #4673; they grant no approval and skip no subsequent review. Normal implementer for_review retries used no force.

- WP03 `01M2P1WD76ZXT0RH0WGMD2JYJ3` **review rejection rewind** (in_review→planned): backward rewind: in_review -> planned: review-cycle://cli-boundary-robustness-01M2NQCB/WP03-context-boundaries/review-cycle-1.md: R1: non-UTF8 token leaks UnicodeDecodeError/empty JSON stdout. Repro and criteria in review-feedback-1.md; parent/WP03-independent-review.md.
- WP05 `01M2P2943P6KCX4VXGANNEZZKK` **review rejection rewind** (in_review→planned): backward rewind: in_review -> planned: review-cycle://cli-boundary-robustness-01M2NQCB/WP05-remaining-json-adoption/review-cycle-1.md: Reject: selector errors escape archive/materialize/verify; status delegates retain legacy JSON and wrong exits. Evidence: WP05-independent-review.md.
- WP03 `01M2P2BWQG9KJP31SHH8K4TAF9` **same-lane actor repair** (in_progress→in_progress): Repair stale reviewer assignment after successful cycle2 implement claim; source da03c5dad, normal review still required.
- WP05 `01M2P2DWN9KKPX66RDWR68JQ97` **same-lane actor repair** (in_progress→in_progress): Repair stale reviewer ownership after successful fix-mode claim; #4673. Normal implementation and independent review gates remain required.
- WP03 `01M2P4JM7QV92Z4NMGPEMF44XY` **reopen previously approved review** (approved→for_review): backward rewind: approved -> for_review: Reopen review: independently reproduced raw workspace read errors in info/list. Evidence: WP03-workspace-read-finding.md.
- WP03 `01M2P4NJBJAWTRNCHSH2MZH5D5` **review rejection rewind** (in_review→planned): backward rewind: in_review -> planned: review-cycle://cli-boundary-robustness-01M2NQCB/WP03-context-boundaries/review-cycle-3.md: Reject: workspace info/list/orphaned reads leak IsADirectoryError and empty JSON stdout. Evidence: WP03-independent-review-cycle3.md.
- WP05 `01M2P6RFYMBXE6KX5EY23195KQ` **reopen previously approved review** (approved→for_review): backward rewind: approved -> for_review: Reopen review: integration found stale status-only golden envelope/exit fixture; C2/C4 product behavior verified.
- WP03 `01M2P6SBZ5XDWX9VDQCMJ37ZWJ` **same-lane actor repair** (in_progress→in_progress): Repair stale reviewer assignment after successful cycle3 implement claim (#4673); correction466c75b3d requires normal independent review.
- WP05 `01M2P6VS0PR4MK9SHGKFKW3H7P` **review rejection rewind** (in_review→planned): backward rewind: in_review -> planned: review-cycle://cli-boundary-robustness-01M2NQCB/WP05-remaining-json-adoption/review-cycle-3.md: Reject R3: status-only golden fixture retains old exit/shape; product C2/C4 correct. Evidence: WP05-independent-review-cycle3.md.
- WP05 `01M2P73CAV834WH90ZR56PTYQZ` **same-lane actor repair** (in_progress→in_progress): Repair stale reviewer assignment after successful cycle3 implement claim (#4673); fixture correction819e78c8b still needs normal independent review.

Counts from events:4 canonical rejection rewinds,2 approved-review reopenings,4 same-lane actor repairs. No forced approval. First-claim compact/raw identity failure #4665 and agentless resume are separately documented claim recovery; do not misclassify as review approval or force bypass.

## Retrospective record and classification

Path: `kitty-specs/cli-boundary-robustness-01M2NQCB/retrospective.yaml`. Runtime-generated (`provenance.kind: runtime_post_completion`, generator Spec Kitty Generator), created2026-09-16T23:11:09.908381+00:00. `findings_status: has_findings`; `proposals: []`. Classify as **generated retrospective with findings requiring contextual interpretation**, not clean/no-findings, not manually completed independent review, and not applied policy changes.

Its aggregate prose says WP03/WP05 multi-cycle rework was not captured as documented rejection and summarizes force overrides generically. Canonical review_result entries above DO document two rejections each; same-lane actor repairs and supported rejection rewinds explain force semantics. Retrospective appears generated before later aggregate force counts; do not treat its raw counts as final authority or silently rewrite it. Preserve record and use this event-backed clarification in final report. No proposals were applied by this evidence task.

## Other retained provenance qualifications

- WP06 exploratory regen/regenerate-graph default calls were an operational deviation: resolved editable lane source despite scratch cwd. They were byte-identical to pre-probe dependency source, directly verified by git diff --exit-code; final guards use no write arm. Full target/cwd/home/runtime details remain WP06-handoff.md.
- Runtime submission pre-review gate sometimes reported no_coverage due empty injected ScopeSource targets; manual exact scoped test evidence is retained separately, never relabeled as an automatic gate pass.
- Original baseline failures, interrupted slow help traversal and external E2E timeouts remain explicit in validation manifest; commit/review provenance alone is not final integrated validation.
