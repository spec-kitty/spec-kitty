# Independent aggregate review — #6753 (stale coord lane base)

Reviewer: `reviewer-renata` profile, run as a **separate model**
(`tokenfactory/kimi-k3`, provider `pi`) over the two lane branches, read-only, in a
scratch aggregate copy (`lane-b` archive + `lane-a`'s changed files; the two lanes
touch disjoint paths). The reviewer's own closing line named a different model id
(`claude-opus-4-1`); the platform records the run as `tokenfactory/kimi-k3`, which
is the identity this record and the approval use.

Scope reviewed: `git diff kitty/mission-stale-coord-lane-base-01M67HRA..<lane>` for
`kitty/mission-...-lane-a` (WP01) and `...-lane-b` (WP02), against spec/plan/tasks.

## Verdict

**LAND.** "The probe is correct, single-shot, fail-silent, and correctly scoped to
the fresh-coord-cut seam; the default parent is demonstrably unchanged; the stderr
channel is justified against `--json` (verified in `_json_safe_output`); WP02
threads `--base` through parity-complete honor/refuse/ignore routes; and the new
tests survive both mutants I ran."

Verified independently, not taken on trust:

- Probe cardinality/placement: one call, inside the FRESH_COORD arm, after both
  early returns and after `resolve_lane_base_or_refuse`; legacy/reuse/crash-recovery/
  planning routes pay zero extra subprocesses.
- Probe correctness: exit 0 → current, 1 → stale, ≥2/`OSError` → silent; direction
  (`merge-base --is-ancestor <target_tip> <parent_ref>`) correct; reads
  `decision.parent_ref`, so explicit and `origin/`-preferred bases are described
  accurately; runs before `_ensure_branch_exists`, so a not-yet-minted coordination
  branch cannot produce a false warning.
- C-001/FR-003: `_resolve_lane_parent` untouched; the lane is still cut at
  `decision.parent_ref` regardless of the warning.
- Channel: `_json_safe_output` redirects only the rich console, so a stdout print
  would have prepended a line to the `--json` payload — the stderr move is load
  bearing, and `captured.out == ""` pins it.
- WP02: `--base` reaches the allocator only on the create path; the reuse branch
  refuses before the self-heal; checkout-root parity with FR-007 holds; `--base` is
  never silently dropped.
- Mutation checks run by the reviewer on the scratch copy: disabling the probe, and
  moving the print back to stdout, each fail the stale scenario — the silence
  controls and the positive control are non-vacuous.

## Findings and disposition

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | NON-BLOCKING | The warning's remedy command fires before the lane exists, so acting on it later hits the reuse refusal, whose follow-up never explains how to re-cut. | **Fixed** (`1c7fb85`): the refusal now names the discard-and-re-cut step (`git worktree remove` + `git branch -D`, then re-run with `--base`), pinned in the CLI test. |
| 2 | NON-BLOCKING | Spec C-004, `plan.md` and the WP01 prompt still said "stdout convention" while the code (correctly) uses stderr. | **Fixed** (this commit): C-004 amended with the `--json` rationale, `plan.md` and the WP01 prompt corrected. The risk it names — post-merge review reading the stderr move as silent drift — is what the amendment removes. |
| 3 | NIT | No timeout on the probe subprocess. | **Fixed** (`a35f996`): 10s bound; `TimeoutExpired` is "unknown" — silent, never a warning, never a block. |
| 4 | NIT | `capture_branch_tip` resolves a local branch only, so an `origin/<target>`-only target degrades to silence. | **Fixed** (`a35f996`): recorded in `_stale_base_warning`'s docstring as a deliberate edge case. |
| 5 | NIT | The "explicit base that is also stale" spec edge case had no test. | **Fixed** (`a35f996`): new fixture variant asserts the report names the ref it actually used. |
| 6 | NIT (cosmetic) | The checkout-root "ignored" line also covers `owned_checkout`, which is not necessarily repository-root planning work. | **Not fixed on purpose.** Changing the wording breaks byte-parity with the top-level command's FR-007 line, which is the property the check exists to preserve. Named in the PR's `## Deferred`. |
