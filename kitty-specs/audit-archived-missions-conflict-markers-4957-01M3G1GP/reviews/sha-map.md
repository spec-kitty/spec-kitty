# Pre-fold SHA map

This mission's pre-publication commit history was folded before first publication to
the public repository, to keep 8 lines that leaked the operator's local absolute home
path (an OS username, pasted into mission trace and review files from agent CLI output)
out of the public git history. The fold combines the branch's ~80 development commits
into a small number of commits built directly from the final, already-redacted content
of every touched path, so no intermediate blob carrying the leaked path ever reaches
the public repo.

The review verdicts, status/tracer records, and other committed artifacts under this
mission directory are the audit trail and were **not edited** to account for the fold —
they still cite the pre-fold commit SHAs exactly as the reviewing agent or tool wrote
them at the time. Those SHAs no longer resolve to any commit in this repository. This
file is the map from each such SHA to the new commit that now carries the same content,
kept so the audit trail stays readable.

Excluded from this map: SHAs cited in `spec.md`'s forensic account of the archived
merge conflict itself (`5eda48f7…`, `df2dac046…`) — those are pre-existing commits from
the original 025 mission, unrelated to this fold, and either remain resolvable (on other
branches/tags) or are already on `main`.

| Pre-fold SHA | Original subject | Now carried by |
|---|---|---|
| `0dfbfc90c0299b34030176cc23db90a22d8e316a` | fix(architectural): check the exemption baseline against a landed ref, not live, when the base predates it | `test(architectural): guard tracked files against committed conflict markers (#4957)` |
| `117c55ebb06ccb30ceb69d3bf2e261a8f97341e8` | chore(audit-archived-missions-conflict-markers-4957-01M3G1GP): capture mission retrospective | `chore(kitty-specs): record mission status, WP and pre-merge review trail (#4957)` |
| `130ccd0d33ed87c1c21b05f1d89c1708912f9eab` | plan(4957): address R3 confirmed findings (SK-279 tracer entry, freeze-test mechanism accuracy, tmp_path fixture mechanism, corpus-suite mischaracterization, NFR-001 verification step) | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` |
| `27ba31215e9578dcb8c11caaacb26e255d17232c` | fix(plan): resolve PLAN-FRESH2-001/002 - align enumeration-mechanism claims and remove fabricated env-var conditionality | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` |
| `2c7132a034f4d3c2856ecf7b8e83828c0fc4be0b` | plan(4957): author implementation plan and seed mission tracer files for archived-conflict-marker audit | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` (touched `status.events.jsonl` too; that hunk is now in the `chore(kitty-specs): record mission status...` commit) |
| `33a9422289b8590d6f1494c2aaa3ade594dc1880` | fix(plan): resolve PLAN-FRESH-001 contradiction on conflict-marker enumeration mechanism | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` |
| `433d38f026e56688833b93a1a2bee20617a763ac` | fix(architectural): log skipped undecodable files in conflict-marker guard (#4957) | `test(architectural): guard tracked files against committed conflict markers (#4957)` |
| `45717050f3f31f5e7207905400f678fe38a804f9` | fix(architectural): shrink-only ratchet uses subset comparator, add shrink positive control (#4957) | `test(architectural): guard tracked files against committed conflict markers (#4957)` |
| `4937cddc2ffcc31208be38ad2b294784fcd7018e` | chore(review): commit pre-merge squad R1-R3 trail (5 raised, 4 confirmed, 1 refuted) | `chore(kitty-specs): record mission status, WP and pre-merge review trail (#4957)` |
| `4c27d59f2a1829fe8b47426be32b0942caeb399b` | Add tasks for feature audit-archived-missions-conflict-markers-4957-01M3G1GP | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` (touched `lanes.json`/`wps.yaml` too; those hunks are now in the `chore(kitty-specs): record mission status...` commit) |
| `53abe8616d63deedf334f9ec38f082949a100bf4` | docs(tracer): record WP02 venv-build friction and issue-matrix deadlock confirmation (#4957) | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` |
| `687dcebf63bff57beb12c300dce86f63baebeb2a` | fix(kitty-specs): resolve committed conflict markers in archived 025 WP01 activity log (#4957) | `fix(kitty-specs): resolve committed conflict markers in archived 025 WP01 activity log (#4957)` |
| `7d975494a5ae3876ac6faa32dd36530af6fcd219` | chore(review): redact worktree paths in round-2 verify record | `chore(kitty-specs): record mission status, WP and pre-merge review trail (#4957)` |
| `94235f937dd918525501d81ed4b80d57de80838c` | chore: remove planning artifact edits from lane-a branch (kitty-specs/ must live on planning branch, not a lane branch) | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` |
| `97101b85997d4a6502517f07808ad7d4ffaf84a9` | Add tasks for feature audit-archived-missions-conflict-markers-4957-01M3G1GP | `chore(kitty-specs): record mission status, WP and pre-merge review trail (#4957)` |
| `a4907deb1427a2f1600412e43bc53ee4b10f717a` | refactor(architectural): hoist the git-subprocess env override dict to one constant | `test(architectural): guard tracked files against committed conflict markers (#4957)` |
| `a8ee46c0dfa1631f3ce5df12946681dc37c37576` | test(architectural): add closing-marker self-mutation coverage | `test(architectural): guard tracked files against committed conflict markers (#4957)` |
| `b20c4ae4bdbdfed7fbc5ac441c16541c3e641a00` | Add tasks for feature audit-archived-missions-conflict-markers-4957-01M3G1GP | `chore(kitty-specs): record mission status, WP and pre-merge review trail (#4957)` |
| `c0ce9cf7648fd720e264411cde0535367b9ff105` | chore(review): commit pre-merge squad round-1 verify and fresh sweep | `chore(kitty-specs): record mission status, WP and pre-merge review trail (#4957)` |
| `d42f3c938135664d331730ed2c2db454ade78a3d` | chore(spec-kitty): persist WP01 approval status and review-cycle record | `chore(kitty-specs): record mission status, WP and pre-merge review trail (#4957)` |
| `f7aa28670f3be641a6d213f9d38c191f6680c94c` | Add scaffold for feature audit-archived-missions-conflict-markers-4957-01M3G1GP | `spec(kitty-specs): design mission for archived conflict-marker audit (#4957)` (touched `meta.json`/`status.events.jsonl` too; those hunks are now in the `chore(kitty-specs): record mission status...` commit) |
| `ff4958e1ef593360fd633f9e471da7d27f6f7913` | feat(kitty/mission-audit-archived-missions-conflict-markers-4957-01M3G1GP): squash merge of mission | `test(architectural): guard tracked files against committed conflict markers (#4957)` (touched `meta.json` too; that hunk is now in the `chore(kitty-specs): record mission status...` commit) |

Three of the SHAs above (`433d38f02…`, `53abe8616…`, `94235f937…`) were never on any branch
tip — they were individual work-package-lane commits folded into the mission's original
squash-merge commit and are cited in review files as point-in-time evidence.
