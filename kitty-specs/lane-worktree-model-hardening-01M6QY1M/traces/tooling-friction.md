# Tooling friction — lane-worktree-model-hardening-01M6QY1M

Tooling the Mission touches: `spec-kitty agent mission create/finalize-tasks`, `move-task`, `consolidate`,
`doctor workspaces`, the status surface resolver, `git worktree`, `make sync-packs`/`sync-services`, the
GitHub MCP tools, the cloud-session harness.

- **[2026-11-06][setup] add_repo for spec-kitty-open-packs (push) was denied by the harness permission classifier.** S11 cannot open its upstream PR from this session; doctrine changes are drafted as a patch for the operator. Disposition: blocked, escalated in hand-off.
- **[2026-11-06][discovery] Shallow clone breaks `git diff origin/main...origin/<branch>` ("no merge base") for older in-flight PRs (#6884).** Agents fell back to per-commit `git show` and REST file lists. Disposition: workaround.
- **[2026-11-06][discovery] `gh pr view` / `gh issue view` fail (GraphQL 403 in the harness); `gh api` REST works.** Disposition: workaround.
- **[2026-11-06][discovery] The research note's "62 call sites" of `resolve_status_surface*` does not reproduce on `src/`; an AST count gives 25 direct calls in 18 files.** Grep counts docstrings/imports. Disposition: AST lister kept in the discovery scratch; the S1 gate counts by AST.
- **[2026-11-06][discovery] `_resolve_status_surface` names two different functions (`agent/status.py:139`, alias at `implement_phases.py:368`).** Misleads grep audits. Disposition: candidate tidy in S1.
- **[2026-11-06][discovery] codegraph natural-language queries returned noise (Lane enum) for status-write questions; grep/AST were faster for call-site census.** Disposition: note only.
- **[2026-11-06][discovery] No ADR file holds the #5100 explicit-only decision; it lives in an issue comment and a Mission spec FR.** Disposition: the S7 ADR supersedes it explicitly.
- **[2026-11-06][discovery] The coordination branch name equals the Mission branch name (`kitty/mission-<slug>-<mid8>`); no doc states it.** Disposition: S7 docs.
- **[2026-11-06][discovery] Five overlapping single_branch predicates (`is_planning_lane`, `is_repo_root_lane`, `lands_mission_branch`, `minted_mission_branch`, `is_single_branch_mission`); `lane_created_branch("lane-planning")` resolves to the target, a trap for gates.** Disposition: S8 tidy-first.
- **[2026-11-06][discovery] #7239/#7237/#7240 duplicate #7275's commits under different SHAs; the S4 ADR lives only on an unmerged branch.** Disposition: S5 builds a seam, binds after #7275 merges.
- **[2026-11-06][discovery] The research doctrine scan's open-packs paths/line numbers (23686fb) do not match the pinned tree (a79c3631); command skills live in core `src/charter/offering/skills/`, not in packs.** Disposition: S11 is two repos and two release paths.
- **[2026-11-06][setup] The container restarted mid-discovery; discovery files in the scratchpad survived, the primary working directory flips between /home/user and the checkout.** Disposition: always cd into the checkout.
- **[2026-11-06][specify] Discovery briefs live under a scratchpad path keyed on the old cwd (`-home-user-spec-kitty`), not the session's current scratchpad (`-home-user`).** A sub-agent must be handed the absolute path. Disposition: workaround (paths passed explicitly).
- **[2026-11-06][specify] The spec scaffold has no slots for Domain Language, Assumptions, Dependencies, Out of Scope or Rules; the specify prompt asks for them.** Added as extra sections after Success Criteria, keeping scaffold order. Disposition: note; candidate template gap for open-packs.
