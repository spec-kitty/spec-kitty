# Research — Built-in re-vendor pin + vendor command + drift gate (#3504)

Phase 0 decisions. Grounded on the §1 grounding squad (architect / brownfield / alignment) and
the live re-seed just done (open-packs PR #38 + tag `v0.1.0`). ADR `2026-08-16-2` (amended
2026-10-11) is binding; this is cite-and-implement, no new amendment.

## D1 — Pin lockfile: location, direction, schema

- **Location**: `packs/built-in.source.yaml` — a sibling of `packs/built-in/`, so it is **outside**
  the digested tree (it is the pin, authored in core; it must not be part of what the digest covers).
- **Direction (document to avoid confusion)**: core's `packs/built-in.source.yaml` records
  **open-packs → core** ("which open-packs SHA core vendored from"). open-packs' *own*
  `built-in.source.yaml` records the opposite anchor (**core → open-packs**, "which core commit the
  open-packs built-in tree was seeded from"). Same schema shape, opposite provenance direction —
  the loader/docstring must state this plainly.
- **Schema**: `repository` (open-packs URL), `commit` (open-packs **SHA**; a tag is resolved to a
  SHA and never stored — FR-002), `tree_digest` {`algorithm`, `value`}, `requires_core` (PEP 440
  range). Mirrors the open-packs file's fields so the two can be cross-checked.

## D2 — Digest: `clean_tree_digest` is the gate's authority (pollution-immune)

- **Decision**: the pin's integrity value and the drift gate use
  `charter.offering.packs.pack_clean_digest.clean_tree_digest(pack_root, level=BUILT_IN)` — a
  **declared-file-set** digest (never `rglob`), LF-normalized, reproducible across a git-archive
  export, a `__pycache__`-polluted worktree, and an installed copy.
- **Why, not `snapshot_sha256`**: the live re-seed exposed exactly the failure mode `snapshot_sha256`
  is vulnerable to — core carried a stray git-ignored `assets/__pycache__/*.pyc`, so
  `snapshot_sha256` over the raw worktree returned `9c96178e` while the clean tree is `99e5e97c`. A
  gate that may run in a developer's polluted worktree must not red on untracked bytecode.
  `clean_tree_digest` enumerates only declared files, so it is immune. ADR decision 2 names
  "`charter.offering.packs` hashing (`snapshot_sha256` and the manifest hash)"; `clean_tree_digest`
  is the same family, kept separate precisely for this robustness (NFR-001/NFR-004). We MAY also
  record `snapshot_sha256` in the lockfile as a secondary cross-check against open-packs'
  `built-in.source.yaml`, but the gate's verdict is `clean_tree_digest`.
- **One producer (ADR decision 3)**: `clean_tree_digest` is deterministic from the tree, so core and
  open-packs compute the same value from the same bytes — no producer conflict; core verifies, never
  regenerates vendored content.

## D3 — Fetch + SHA resolution + subtree scoping

- **Reuse** `src/specify_cli/charter_packs/sources/git_source.py` — it already clones and pins a git
  ref; the vendor command resolves the pin's ref to a SHA and checks out that SHA, then copies the
  **`built-in` subtree only** of the open-packs ref (C-006 — content elsewhere in open-packs must not
  affect the pin/digest; open-packs uses a per-pack `packs/<name>/` layout, built-in lives at its own
  path, confirm the exact subpath at implement time against the tagged `v0.1.0` tree).
- **Fail-closed (FR-006)**: an unreachable/unverifiable ref, a digest mismatch, or an incompatible
  `requires_core` leaves `packs/built-in/` untouched and exits non-zero. Never a partial/empty write.
- **Supply-chain posture (DIRECTIVE_051)**: the open-packs ref is a dependency fetched at pin-bump
  time; integrity is pin-by-SHA + verify-by-content-digest + fail-closed. No consumer-runtime fetch
  (that is Option C / #3022). This satisfies `supply-chain-install-safety` for this dependency.

## D4 — Drift gate placement + offline

- `.github/workflows/packs.yml` built-in lane runs `spec-kitty charter pack vendor --check`; it
  compares the committed tree to the committed lockfile — **offline, no network** (NFR-004). The
  acceptance test drives the **same command** on a drifting-tree fixture (non-vacuity; not a YAML
  text assertion) and asserts non-zero + the FR-010 remedy message. Red-first: the fixture reds
  before the gate/command exists.

## D5 — Release re-verification placement

- `.github/workflows/release.yml` and `RELEASE_CHECKLIST.md` run the verify step **before**
  `python -m build` ("before the distribution build", per the amendment's note that release uses
  `python -m build`, not `hatch build`). A post-build assertion (reusing the
  `tests/charter_offering/test_packaging_parity.py` pattern + the existing build fixtures) confirms
  the built wheel's `packs/built-in/` matches the pin. Force-include and the `packs/internal/`
  exclusion are unchanged.

## D6 — No ADR amendment; cite only

- The 2026-10-11 amendment already settles decisions 1–4 (committed tree + drift gate; SHA + digest
  pin; one producer; `requires_core` compat) and defers the authoring flip (decision 6). This mission
  implements them. File a fresh ADR only if the lockfile schema or gate placement introduces a
  decision the amendment does not cover — not anticipated. Cite ADR `2026-08-16-2`, `2026-08-16-3`
  (internal stays in core), `2026-10-11-2` (pack_level), `2026-08-16-1` (manifest hash).

## Adversarial evidence (planning)

No new runtime dependency is added (the git fetch reuses existing machinery; no new PyPI package).
The only "dependency decision" is the open-packs ref, handled by D3's pin-by-SHA + verify-by-digest +
fail-closed posture. No contested supply-chain finding outstanding.
