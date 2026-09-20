# Tracer: Design Decisions — charter-catalog-coherence (#4785)

Durable rationale for choices that shaped the mission.

## Planning

- **DD-01 — Activate recompiles the catalog by default** (Decision
  `01M2XQRXWVK1DHVMYEBJNYDQMC`, resolved under delegated autonomy). The config-only default
  is the direct cause of the #2524 dangler; the default recompile is fast (it is what the
  background references-refresh heal already runs). Config-only stays available behind an
  explicit opt-out flag.
- **DD-02 — Single catalog authority; no minimal-writer** (C-001/C-004). All
  `catalog.references` writes route through the one `compile_charter`/`write_compiled_charter`
  authority. A "minimal one-entry append" path is rejected: it would be a competing authority
  the charter forbids. The whole-derived-section recompile is canonical; NFR-002 guarantees
  authored sections and `charter.md` stay byte-identical, and FR-008 makes repeated recompiles
  a no-op diff so "whole recompile" does not mean "churn".
- **DD-03 — Worktree safety lives at the charter-write boundary, not in the shared resolver**
  (C-002/C-003). Do NOT change shared `find_repo_root`/`get_main_repo_root` (used far beyond
  charter). Reuse the kernel `git_topology` probe; collapse the 3-way parallel root resolution;
  fail closed (or honour the invoking worktree) only at the charter command boundary.
- **DD-04 — F4b pinned by outcome, not mechanism.** The exact DRG-closure ↔ typed-repository
  key/loader mismatch is deferred to a red-first repro at implement time; the spec contracts the
  observable outcome (no silent "Definition unavailable" for directives that have a definition;
  genuine misses become diagnostics).
- **DD-05 — Worktree policy is fail-closed, not honour-the-worktree** (post-spec review S5).
  The issue's Finding 3 states a dedicated clone (not a git worktree) is required for safe
  charter authoring, so every charter write command refuses (non-zero exit + "use a
  repository-root checkout or dedicated clone" message) when invoked from a linked worktree.
  Uniform across activate/deactivate/generate/synthesize/resynthesize. Simpler and safer than
  per-command honour-the-worktree, and it kills the split-brain.
- **DD-06 — "No churn" is a `catalog.references`-section contract, not whole-file** (post-spec
  review B1/B2). `write_compiled_charter` stamps `metadata.generated_at` every compile, so a
  whole-file zero-diff is impossible; the stability contract is scoped to the `catalog.references`
  section with canonical deterministic entry ordering (NFR-005) and `generated_at` preserved when
  the catalog is byte-unchanged.
- **DD-07 — Recompile-on-activate uses `from_interview=False`** (post-spec review N1). No
  `CharterInterview`/`answers.yaml` needed; the recompile recomputes only the derived catalog.

## Implement

- **F4b mechanism confirmed empirically** (not the a-priori guess): the placeholder came from
  `_render_kind_references` looking up DRG-transitive-closure ids against the ACTIVATION-FILTERED
  `doctrine_service.<kind>` property; the fix routes through the raw/unfiltered repository
  (`raw_repository(kind)`) via a `_raw_kind_repository` duck-typing helper (handles both the
  activation-aware wrapper and a plain offering `DoctrineService`). Membership stays DRG-closure-driven.
- **DD-08 — recompile-on-activate only refreshes an ALREADY-established charter.yaml** (integration
  regression R2 fix). Recompiling on the first activate of a config.yaml-only project bootstrapped a
  charter.yaml + minted the `charter:` pointer, flipping the activation write-target and splitting
  activation state across config.yaml + charter.yaml (a C-001 violation). `recompile_catalog` now
  returns early when charter.yaml is absent (no coherence exists to maintain there). Strengthens C-001.
- **DD-09 — synthesize fresh-detection requires interview answers alongside the manifest signal**
  (integration regression R3 fix). A `built_in_only:false` synthesis manifest WITHOUT interview
  `answers.yaml` is an orphan/incomplete marker a real synthesis would have consumed, so it must not
  count as "established" (else synthesize's legitimate re-seed remediation is blocked). `_catalog_is_established`
  now ANDs `_interview_answers_present` with the manifest signal — keeps the F2 gain (real
  manifest + answers stays established) while restoring remediation for genuinely-incomplete stores.
- **DD-10 — run_full_synthesize re-wired, not de-contracted.** WP03's refactor orphaned the
  cross-module import; re-exported it from the charter package `__init__.py` rather than reconciling
  the `activate.__all__` contract test — `--resynthesize` still routes through it (intra-module).

## Review / Close

- Composite `(id, kind)` catalog sort key (pre-PR nice-to-have) deliberately NOT folded: the
  same-id-across-kinds case is impossible in practice and WP01's compiler was already approved —
  noted as a PR-body fast-follow to avoid gold-plating.
- `_recompile_catalog_best_effort`'s `UnknownArtifactIdError` catch residual (own-target unresolvable
  by `resolve_artifact_urn` while resolvable by `list_available` → warning + exit 0) accepted as
  non-silent + guard-backed; noted in the PR body as a fast-follow, not folded (the divergence is a
  separate latent condition, not this mission's code).
