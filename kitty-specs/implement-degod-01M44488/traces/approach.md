# Approach — implement-degod-01M44488

Running log of how the approach evolves (1-3 sentences per dated entry). Seeded at planning.

Initial approach (spec + research/code-grounding.md §2):
- Tidy-first and behaviour-preserving, following the 2026-10-04 degod precedents
  (#5650/#5664/#5679/#5695).
- Characterization pins and patch-liveness coverage land first. Code then moves verbatim into the
  existing seams, and callers are adjusted afterwards.
- #5232 is a separate slice, delivered through the write-shaped placement seam.
- Tests migrate onto the seams last, with the patch-site count measured before and after.

- 2026-10-04 — The grounding squad showed that "auto-rebase" is not on the implement path. The phase
  list was corrected to *context → claim preflight + dependency gate → planning-artifact commit →
  bulk-edit + operational context → workspace/lane selection → allocate → record claim → present*.
- 2026-10-04 — The post-spec squad corrected a wrong precedent: `mission_record_analysis` queries a
  PRIMARY kind. That triggered an empirical reachability study before planning #5232 instead of
  trusting the precedent. The study found the fallback reachable only via a duplicate WP prompt or a
  torn-down coordination branch.
- 2026-10-04 — The post-spec squad corrected a wrong precedent: `mission_record_analysis` queries a
  PRIMARY kind. That triggered an empirical reachability study before planning #5232 instead of
  trusting the precedent. The study found the fallback reachable only via a duplicate WP prompt or a
  torn-down coordination branch.
- 2026-10-04 — WP02 drives the characterization suite through `top_level_implement` (the function
  `agent action implement` calls), mounted on a one-command Typer app. The root app's callback
  rebuilds agent-skill assets on every call (~1.2 s each).
- 2026-10-04 — The SC-002 counter rose from 117 to 134 with WP02's 17 dispatch-map substitutions.
  They are counted on purpose: the reduction to 45 must come from WP09's parameterised phase
  functions plus the WP10/WP11 rewrites, not from hiding substitutions.
- 2026-10-04 — Evidence log (implementer and reviewer reports, recorded by the orchestrator):
  - **WP01**: the liveness gate is per-family, with an attribute rule. 115 implement patch hits,
    0 dead. Counter 119 → 117.
  - **WP02**: 44-case characterization suite, frozen at `8cbe74f94`. Counter 117 → 134 (17 dispatch
    substitutions).
  - **WP03**: context reads and the claim gate moved into their seams; no-CLI guard added. Counter
    134 → 118: string patches were re-pointed to the owner module `workspace.context`.
    `_WRITE_DIR_CONSUMER_MODULES` and the meta census were not widened, because the moved code only
    reads and has no `load_meta` site.
  - Reviewers re-ran their own plants on every WP.
  - Pre-existing reds: #5699 (commit recipes) and #5714 (preflight latch order dependence, filed
    by this mission).
- 2026-10-04 — A container restart killed the WP03 implementer mid-validation. Its commits survived
  in the lane worktree; a resume dispatch finished validation. Since then the lane branch is pushed
  to origin after each WP as a backup.
