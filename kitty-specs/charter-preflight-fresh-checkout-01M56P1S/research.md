# Research: Fix charter preflight blocking `next` on a fresh checkout (#6366)

## R1 — Root cause bisect (confirmed live, not "plausibly")

- **Decision**: The parity break is commit `712aee06a9` ("chore(charter): activate charter-offering
  scenario doctrine for this project"), a `spec-kitty charter activate … --cascade all` run that edited
  `.kittify/charter/charter.yaml` **and** regenerated the derived graph/provenance sidecars, but did
  **not** re-stamp `.kittify/charter/synthesis-manifest.yaml`'s `bundle_content_hash`.
- **Evidence**: Across the 10-12→10-15 window the pack rename/revendor suspects all MATCH parity:
  `c3fc8aa349` (10-12) stamped == recompute (`sha256:6a188326…`); `904ca4241d` (10-11) MATCH. Current
  `main` (`ee6cdb7edc`) DRIFTS: committed stamp `sha256:6a188326…` vs recompute
  `sha256:649ee217…`. The only post-`c3fc8aa349` commit touching `charter.yaml` (and not the manifest)
  is `712aee06a9`.
- **Alternatives considered**: The issue's named suspects (rename/revendor). Rejected — they preserve
  parity; the activate-cascade write path is the real write-side defect.

## R2 — Why `next` goes terminal instead of auto-healing

- **Decision**: `preflight.auto_refresh` **defaults to `False`** (`preflight/config.py`), and
  `run_preflight_or_abort` calls `run_charter_preflight(auto_refresh=cfg.auto_refresh)`. With it off,
  no heal is attempted, so a committed-drifted `synthesized_drg: stale` becomes a terminal
  `CHARTER_PREFLIGHT_FAILED` (exit 1). Even when on, the existing heal spawns a heavy
  `generate→synthesize→bundle validate` subprocess chain, gated on a clean worktree.
- **Evidence (live)**: `load_preflight_config(.)` → `enabled=True, auto_refresh=False`;
  `compute_freshness(.).synthesized_drg == {state: stale, remediation: "spec-kitty charter synthesize"}`.
- **Implication**: The fix must introduce a **default-on, lightweight, in-process** re-stamp heal,
  independent of `auto_refresh`, not a change to the heavy opt-in sequence.

## R3 — The "derived consistent" predicate already exists: `manifest.verify(repo)`

- **Decision**: Use `charter.activation.synthesizer.manifest.verify(manifest, repo_root)` as the
  safe-heal predicate. It checks every manifest artifact entry exists on disk with a matching
  per-artifact `content_hash` (KD-2 authority rule). If it passes, the derived graph/artifacts are
  consistent and only the `bundle_content_hash` stamp lags → safe to re-stamp. If it raises
  `ManifestIntegrityError`, the derived state is genuinely inconsistent → do NOT heal (FR-003/NFR-002).
- **Rationale**: Reuses an existing authority (single-source), avoids inventing a parallel consistency
  check, and cleanly separates authoring-only stamp lag from genuine drift.
- **Alternatives considered**: Re-running a full `synthesize` to detect drift (too heavy, violates
  NFR-001); comparing graph mtimes (unreliable). Rejected.

## R4 — Where the heal must live (layer discipline)

- **Decision**: Heal in `specify_cli.charter_runtime.preflight` (the `references_refresh` helper +
  `runner`), NOT in `freshness/computer.py`. `computer.py` is a side-effect-free observer by contract
  (NFR). The enforced layer direction `charter <- specify_cli` holds: the heal (an application concern)
  consumes `charter.*` authorities; it does not invert the direction.
- **Rationale**: `references_refresh.py` is already the documented references-parity heal extension
  point keyed on the `synthesized_drg` layer — the lightweight re-stamp is its natural home.

## R5 — Read-only query must not mutate

- **Decision**: Thread an `allow_heal` flag through `run_charter_preflight`.
  `run_preflight_or_abort` (advancing `next` / `implement`) passes `allow_heal=True`;
  `run_preflight_warn_only` (read-only query `next`) passes `allow_heal=False`. Query mode therefore
  never writes the manifest and still continues (warn-only).
- **Rationale**: Preserves the read-only contract of query mode; the heal is a mutation.

## R6 — Concurrency safety

- **Decision**: The re-stamp is idempotent (same `charter.yaml` → same `bundle_content_hash`), written
  atomically (temp + rename via the manifest write path), under the existing coordination write
  discipline so concurrent `next` runs on one owned root converge. The failing nightly e2e runs 4
  concurrent `next` commands against two owned roots — the heal must be safe there.
- **Open item for implementation**: confirm the exact lock/atomic-write seam the manifest writer uses
  and that a re-stamp racing another `next` cannot tear the file.

## R7 — Write-side seam (activate/cascade + scaffold)

- **Decision**: `activation_engine.commit_plan` writes only `config.yaml`; the `charter.yaml` recompile
  that `activate`/`--cascade` triggers (regenerating catalog/activation + graph/provenance) is the site
  that must re-stamp `bundle_content_hash` via `finalize_manifest` at the single authority. The
  fresh-project scaffold (`_fresh_project_layer.py`) already does this (`built_in_only=False`,
  `bundle_content_hash=compute_bundle_content_hash(repo)`); the activate/cascade recompile must reach
  the same guarantee.
- **Open item for implementation**: pin the exact recompile persistence function for activate/cascade.

## R8 — Supply-chain / dependency posture

- **Decision**: N/A — this mission adds, upgrades, or removes **no** dependencies. DIRECTIVE_051 /
  `supply-chain-install-safety` controls are not triggered; no adversarial dependency-decision pass
  required. Recorded here per the plan contract (silence is not compliance).

## R9 — Test scope and CI home

- **Decision**: Red-first per-PR twin in `tests/charter_runtime/` (deterministic: construct a repo
  whose manifest stamp lags but artifacts are consistent; assert `next`/preflight passes at rc=0;
  positive control: a genuinely-inconsistent fixture still blocks). The nightly e2e
  (`tests/e2e/test_worktree_owned_root_concurrency.py`) stays **unchanged** as the saturation
  acceptance authority. #3343 (governed CI home for that e2e) is referenced only, not opened here.
- **Guardrails**: run `tests/charter_runtime/`, `tests/charter/` + `tests/charter_offering/`, the e2e,
  and `make test-fast`. Do NOT run `make test-full`; do NOT regenerate `.github/ci-shard-timings.json`.

## Decisions settled with the operator (specify)

- DM `01M56P2XQJVJB43TQBGQGCTY9D`: **both** — auto-heal (primary) + close write-side gap.
- DM `01M56P2ZKF2JAZV1GY7K4ZNM27`: **yes** — re-stamp the committed manifest too.
