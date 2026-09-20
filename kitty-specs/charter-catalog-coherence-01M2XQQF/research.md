# Research: Charter Activation Catalog Coherence (#4785)

Phase 0 synthesis of a 4-lens grounding squad (debugger root-cause + repro, architect
right-design, paula-patterns surface map, researcher supersession/related-tickets), all
run against current `main` @ `ba4e590142`. Every finding is CONFIRMED real; none is
superseded (the one in-flight worktree attempt, PR #4251, is closed unmerged).

## The unifying fact

`.kittify/charter/charter.yaml`'s `catalog.references` is a **derived** section with
exactly ONE compiler authority:

- **Decision**: All catalog writes route through `compile_charter()` +
  `write_compiled_charter()` in `src/charter/activation/compiler.py:383,502`.
- **Rationale**: `write_compiled_charter` is round-trip-preserving — it rewrites only the
  derived `catalog`/`metadata` sections and leaves authored `governance`/`directives`/
  activation/`overrides` byte-for-byte (`references_refresh.py:44-51`). `charter pack apply
  --compile` (`pack.py:140-224`) is the reference implementation of the correct call pattern:
  invoke the compile functions directly with an **explicit `repo_root`** and
  `from_interview=False`.
- **Alternatives rejected**: a "minimal one-entry" catalog writer (a second authority the
  charter forbids); mutating the shared `find_repo_root` (used far beyond charter).

## Finding 1 — `activate` leaves the catalog stale (F1)

- **Root cause**: `activate_cmd` (`activate.py:629-640`) calls `manager.activate()` +
  `commit_project_registration()` — a config-only write — and only recompiles when
  `--resynthesize` is passed (`activate.py:666-667`). `RESYNTHESIZE_HELP` (`activate.py:67-73`)
  deliberately keeps the default a "fast config-only write". So `catalog.references` diverges
  immediately → the coherence guard reds with `reference_id_divergences=[...]` (the #2524
  dangler class). Reproduced: activating `051-supply-chain-install-safety` reds
  `tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent`.
- **Decision**: Make `activate`/`deactivate` recompile the catalog by DEFAULT via
  `compile_charter(from_interview=False)` (the `pack apply --compile` pattern); demote
  config-only to an explicit `--no-compile` opt-out (Decision `01M2XQRXWVK1DHVMYEBJNYDQMC`).
- **Rationale**: coherent-by-construction closes the dangler class; the recompile is the same
  fast path the background references-refresh heal already runs.

## Finding 2 — remediation points at a command that cannot recompile (F2)

- **Root cause (primary)**: `charter synthesize` is **architecturally incapable** of
  recompiling `catalog.references` in any branch — only `generate`/`compile_charter` does
  (`references_refresh.py:5-13`, `_synthesis.py:36-44`). The coherence-guard suggestion string
  and `--resynthesize` help nonetheless send the operator to `synthesize`.
- **Root cause (secondary)**: the fresh-project short-circuit
  (`synthesize.py:222-228`) fires when `adapter=="generated"` AND
  `not _has_generated_artifacts(repo_root)` AND `charter_yaml.is_file()`. An established store
  with no `.kittify/charter/generated/` dir satisfies all three → misclassified "fresh" →
  seeds minimal doctrine and returns. Reproduced: `synthesize` printed
  "Charter synthesis (fresh project)…" and left the divergence.
- **Decision**: (a) correct the remediation string + `RESYNTHESIZE_HELP` to name `generate`
  (folded into WP01); (b) gate the fresh-project predicate on actual catalog emptiness rather
  than `generated/` absence (WP03).
- **Rationale**: the guidance must name a command that actually recompiles; an established
  store must not be treated as fresh.

## Finding 3 — charter writes resolve to the PRIMARY checkout (F3)

- **Root cause**: `generate`/`synthesize`/`resynthesize` resolve root via
  `_charter_pkg.find_repo_root()` (`generate.py:296`, `synthesize.py:199`, `resynthesize.py:98`),
  which delegates to `get_main_repo_root()` (`core/paths.py:498-540`) — by contract it follows
  a linked worktree's `.git` pointer back to the PRIMARY checkout. Reproduced: `generate` from a
  worktree modified the primary's `charter.yaml`, not the worktree's. Extra hazard: `activate`
  defaults `repo_root=Path(".")` (worktree) but `run_full_synthesize` re-resolves via
  `find_repo_root` (primary) → split-brain. Root resolution is a **3-way parallel authority**
  (`find_repo_root`, `get_main_repo_root`, a local `_is_inside_git_worktree` in
  `generate.py:48`), none of them the kernel canonical `src/kernel/git_topology.py`.
- **Decision**: Add a shared charter-write-root helper that reuses kernel `git_topology`
  (git-dir vs git-common-dir) and **fails closed** when invoked from a linked worktree, applied
  to all charter write commands; retire the `chdir` hack + split-brain. Do NOT modify the shared
  `find_repo_root`/`get_main_repo_root`.
- **Rationale**: the issue's own finding is that a dedicated clone (not a worktree) is required
  for safe charter authoring; fail-closed is the uniform, safe policy. `git_topology` is the
  single canonical probe already used by ~20 other consumers (C-003).
- **Alternatives rejected**: honour-the-worktree resolution (more complex; still leaves authoring
  in a non-clone); changing `find_repo_root` (breaks lifecycle commands that must target primary).

## Finding 4 — over-render + placeholder summaries (F4)

- **F4a (over-render) is by design, not a bug**: `catalog.references` is fully derived;
  `compile_charter` recomputes it each run. The observed ~119/71 churn is drift from the #4784
  hand-edit, not a defect. **Decision**: keep the whole-derived-section recompile (single
  authority) and add a determinism/no-churn contract (NFR-005 canonical order; `generated_at`
  preserved when the catalog is byte-unchanged). **Reject** a minimal one-entry writer (C-004).
- **F4b (silent placeholders) is real**: `_render_kind_references` (`compiler.py:1094-1125`)
  does `repository.get(raw_id)`; the DRG transitive closure surfaces directive ids the
  activation-filtered typed repository cannot resolve → miss → `_doctrine_yaml_reference(source=None)`
  → the literal `"Definition unavailable in bundled doctrine."` (`compiler.py:1489`). Two lenses
  gave complementary mechanisms (DRG bare-id vs canonical-key mismatch; a project-dir
  `directive/` singular vs `directives/` plural loader split). The debugger confirmed the
  placeholder count is **activation-dependent** (5 on a lean baseline vs the issue's 16), which
  points at the transitive-reach-vs-repository-key mismatch.
- **Decision**: pin the exact mechanism with a red-first repro at implement time; resolve
  DRG-surfaced ids to the canonical repository key (reuse the existing `resolve_config_id` /
  `normalize_directive_id` bridge) so directives with a bundled definition resolve, and route a
  genuinely-absent id through the existing `graph.unresolved` diagnostics channel
  (`compiler.py:1233-1235`) instead of a silent placeholder. Also delete the dead, uncalled
  `_build_references_from_yaml` (`compiler.py:1030`) so nobody patches the wrong copy.
- **Rationale**: the spec contracts the observable outcome (no silent placeholders for
  directives that have a definition), and the fix is a single-point resolution correction, not a
  fallback-string widening.

## Related tickets (disposition)

- **#4250** — CLI-charter-write half FOLDED into F3; hosted-binding-recovery half + saas#1713
  cross-referenced, out of scope.
- **#2519** (parent epic, P1, 4.0.0) — F1 partially discharges its reconciler scope; cross-ref.
- **#4042 / #4226** — synthesize-family recovery bugs; cross-ref (F2 fresh-gate relieves #4042's
  "synthesize is the only recompile" dead-end).
- **#4618 / #4615 / #4614** — generate over-render + honesty siblings; cross-ref.
- **#3292** (closed) — fixed a DIFFERENT "Definition unavailable" manifestation (second-run
  degradation), not F4b's first-render gap.

## Adversarial evidence (Planning)

No dependency added/upgraded → the supply-chain adversarial-evidence gate is N/A this mission.
The post-spec adversarial squad (reviewer-renata) surfaced 2 blockers + 5 should-fixes; all
dispositions = **changed** (folded into the spec at commit `21f26ce`): SC-004/FR-008 rescoped to
the `catalog.references` section (B1); NFR-005 deterministic ordering added (B2); C-006 test
reconciliation added (S1); NFR-001 made a measured value (S2); FR-007 oracle named (S3); FR-006
enumerates `deactivate` + pins fail-closed (S4/S5); N1 recorded (`from_interview=False`). No
contested finding was dropped.
