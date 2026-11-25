---
affected_files: []
cycle_number: 2
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-25T22:16:55Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review cycle 2 (claude::reviewer-renata): REJECT

Commit reviewed: b292615c.

## The six cycle-1 findings: all resolved

- **F1 resolved.** The probe no longer guesses the branch name; it reads each branch's own meta.json. The slug-without-mid8 and lane-copy tests pass.
- **F2 resolved.** `planning_write_ref` raises on its own, and `PlanningWriteRef` has the 3 fields of the data model.
- **F3 resolved.** The landing test is no longer vacuous. It sets `merged_at` and patches `specify_cli.status.is_mission_merged` to raise StoreError; `landing.py` imports that name inside the function, so the patch reaches it.
- **F4 resolved.** The mis-argued helper is gone, and both the run_git and blob_at failure paths are tested.
- **F5 resolved.** `default_mission_rule_applies` is shared by both readers. `default_mission_primary_ref` is byte-identical for every input: `str()` of a non-empty `str` is the same value.
- **F6 resolved** for the local case (see finding 2 below).

Checks: 28 tests pass, and ruff, format, C901 and mypy are clean.

Not findings:
- The probe costs 2 git spawns per local `kitty/mission-*` branch, and only on the missing-meta path.
- If two branches claim the same Mission, the first in ref order wins. That is deterministic, and a copied branch names its source, so it does not qualify.
- If the claimed branch equals `fallback`, the correct branch is returned.

## Findings (reproduced with a standalone script on real git)

1. **[MEDIUM] src/mission_runtime/resolution.py:1253 (with :1199 and :1173): the probe ignores topology_source, so an explicit-topology Mission now gets a refusal with the wrong remedy.**
   - Reproduction: an explicit `single_branch` Mission (no topology_source; minted `kitty/mission-sb-01M8BBBB` whose meta records itself as `mission_branch`), with the root checkout moved back to `main`.
   - Result: `planning_write_ref` raises `PLANNING_CHECKOUT_MISSING`. The message calls the branch "the coordination branch" and prescribes `spec-kitty doctor coordination --mission sb-01M8BBBB --fix`, but that Mission has no coordination topology.
   - This changes the behaviour of an explicit topology, which FR-006 says stays unchanged, and the remedy is misleading.
   - Recommendation: accept a claiming branch only when its own meta has `topology_source == "default"` and has not landed. For the other shapes, keep today's behaviour or raise a refusal whose text fits them. Add a test for an explicit `single_branch` Mission.

2. **[MEDIUM] src/mission_runtime/resolution.py:1196/1213 (and the ADR "Fail closed" bullet, line 252): a Mission branch that exists only on the remote still falls back to the target silently.**
   - Reproduction: clone a repository whose default, not-landed Mission branch `kitty/mission-rm-01M8CCCC` exists only as `origin/kitty/mission-rm-01M8CCCC`.
   - Result: `planning_write_ref` returns `PlanningWriteRef(branch='main', on_mission_branch=False, landed=False)`.
   - That breaks NFR-002 (0 silent fallbacks) and recreates the #7759 shape, where planning work is committed on the target.
   - The coordination doctor already treats a remote-only coordination branch as a real state (precedent 2c1caf39, `remote_only_branch`).
   - The ADR's "Only a Mission with no `meta.json` anywhere keeps the target" is untrue for this case.
   - Recommendation: also probe `refs/remotes/*/kitty/mission-*`. A remote-only claiming branch should refuse, naming the materialize remedy. Add a fresh-clone test, and align the ADR bullet.

3. **[LOW] src/mission_runtime/resolution.py:1213: `--format=%(refname:short)` is ambiguous.**
   - When a tag or other ref has the same short name, git prints `heads/kitty/mission-...`. That string never equals the meta's `mission_branch`, so the branch is silently skipped and the result falls through to the target.
   - Recommendation: use `%(refname:strip=2)`, or `%(refname)` with the `refs/heads/` prefix stripped, and pass the full refname to `blob_at`.
