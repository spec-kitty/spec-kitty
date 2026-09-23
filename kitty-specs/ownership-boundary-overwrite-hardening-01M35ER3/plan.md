# Implementation Plan: Ownership-Boundary Overwrite Hardening

**Branch**: `issue-4931-ownership-boundary-overwrite-hardening` | **Date**: 2026-09-22 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/ownership-boundary-overwrite-hardening-01M35ER3/spec.md`

## Summary

Extend the already-landed `asset_preservation` ownership-proof guard from the **removal** seam to the **overwrite/truncate** seam so three package-owned mutating flows stop silently destroying operator-authored bytes while reporting success:

- **#4931 (init)** — re-wire the *existing* removal chokepoint that is mis-fed: `init.py` proves `.kittify/templates/` package-owned by **path name** (`managed_relpaths`) instead of by **this-invocation provenance** (`run_created`), so it deletes a user-authored resolver tier. Also route the second, unguarded full-copy destroyer (`template/manager.py` raw `rmtree`) through the guard.
- **#4926 (research)** — stop fabricating 0-byte "ready" artifacts when no template resolves, and stop `--force` truncating a user-authored `research.md` to empty.
- **#4921 (brief)** — push the "refuse to overwrite a complete brief without authorization" invariant *out of* the duplicated `intake.py` CLI adapter gates and *into* the `write_mission_brief` chokepoint (typed `BriefExistsError`), so no future writer-layer caller can silently clobber a brief.

The overwrite half is unified behind one new primitive, `guard_destructive_overwrite`, a sibling to `guard_destructive_removal` in the same canonical authority package.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich (existing; no new deps)
**Canonical authority**: `src/specify_cli/asset_preservation/` (`guard.py`, `provers.py`, `backup.py`) — the code encoding of charter §463-479, landed by `ownership-boundary-preservation-01M32KEN` (#4859/#4861/#4862). Reused, not re-implemented (C-001).
**Storage**: filesystem (operator project tree); no DB.
**Testing**: pytest; ATDD/red-first per ADR 2026-07-17-1 (C-004). Arch gate `tests/architectural/test_mutation_ownership_routing.py` (C-005 extension → research).
**Project Type**: single (CLI library).
**Performance**: CLI < 2s (charter); the guard adds one `exists()`/proof check per write — negligible.
**Constraints**: reuse the `OwnershipProof`/prover vocabulary; name is not proof (C-002); preserve-on-unprovable, exit success (C-003).

## Charter / Constitution Check

*GATE: must pass before design; re-check after.*

- **Single canonical authority** ✅ — one preservation authority (`asset_preservation`); the new overwrite guard lives beside the removal guard, no second proof vocabulary (C-001).
- **User Customization Preservation §463-479** ✅ — every destructive write in scope proves ownership by content/provenance, not name; unprovable ⇒ preserve+warn, exit success.
- **ATDD-first (C-011 / ADR 2026-07-17-1)** ✅ — each defect lands an issue-pinned RED regression through the pre-existing CLI entry point before its fix.
- **Architectural gate discipline (DIRECTIVE_043)** ✅ — extend the non-vacuous `test_mutation_ownership_routing` gate to the research command (closes the coverage gap the reproduction lens found).
- **Smallest-viable-diff ↔ boy-scout ↔ locality (RECONCILE)** — the shared primitive is justified over three ad-hoc gates by the single-authority principle; cleanup stays inside the touched files. No unrelated refactors.

## Design

### The shared overwrite primitive (foundational)

New in `src/specify_cli/asset_preservation/` (co-located with the removal guard):

```
guard_destructive_overwrite(
    dest: Path, project_path: Path, *,
    replacement_substantive: bool,   # is there real content to write?
    authorized: bool,                # did the operator authorize replacing user content? (e.g. --force)
    prover: OwnershipProver | None = None,   # optional: package-owned dest may be replaced freely
    backup_parent: Path | None = None,       # optional: archive user bytes before an authorized overwrite
) -> OverwriteVerdict
```

Single decision rule (when `dest` holds bytes that are not proven package-owned):

| dest state | replacement_substantive | authorized | verdict |
|---|---|---|---|
| absent | False | — | **refuse** (never fabricate an empty file) |
| absent | True | — | **proceed** (write) |
| exists (user) | False | any | **refuse / preserve** (never truncate to empty, even under --force) |
| exists (user) | True | False | **refuse / preserve** (unauthorized) |
| exists (user) | True | True | **proceed** (optionally archive first) |
| exists (proven package-owned via `prover`) | True | any | **proceed** (package refreshing its own file) |

The caller decides how to surface a `refuse`: `write_mission_brief` raises the typed `BriefExistsError`; `research` reports "no template for mission type X" / preserves. The guard stays pure (no I/O beyond an optional archive), mirroring `guard_destructive_removal`.

A new typed error `BriefExistsError` (module-local to the brief writer or `asset_preservation`, TBD in WP-A) carries the existing operator message so both `intake.py` sites translate one error to one exit-1 path.

### Per-site application

- **FR-003 / #4921** — `write_mission_brief(..., overwrite: bool = False)`: **BEFORE** the XOR partial-state cleanup (`mission_brief.py:73-75`), if `brief_path.exists()` (existence alone — NOT "complete"; a brief-only/sidecar-absent file is the #4910 unknown-provenance case and must still refuse) and `overwrite` is False → `guard_destructive_overwrite(brief_path, repo_root, replacement_substantive=True, authorized=overwrite)` returns refuse → raise `BriefExistsError`. Placing the check before the XOR is load-bearing: otherwise the XOR unlinks a brief-only file and the writer then re-creates it (re-introducing the #4910 loss). When `brief_path` is absent (orphan-sidecar recovery), no refusal fires and the existing XOR recovery proceeds unchanged (NFR-002). The invariant lives in the real chokepoint `_commit_brief` (`intake.py:114-137`, which calls `write_mission_brief` and today has no `force` param) and `_write_brief_from_candidate` (the `--auto` path): both must thread `overwrite=force` down, and the two duplicated `if brief_path.exists() and not force` gates (`:155-157`, `:296-298`) collapse into catching `BriefExistsError` → existing `--force` message + `Exit(1)`.
- **FR-002 / #4926** — `research.py` `_copy_asset` (`:167-188`) and the CSV loop (`:199-216`): compute `substantive = template_path is not None and template_path.is_file()`; route through `guard_destructive_overwrite(dest, project_root, replacement_substantive=substantive, authorized=force)`. On refuse: do **not** `unlink`/`touch`, do **not** append to `created_paths` (kills the false "ready"), and record a skipped/no-template notice; when *no* asset resolves for the mission type, the command reports a clear "no research template for mission type X" outcome instead of a green panel. The `unlink()`+`touch()` fabrication (`:180-182`, `:210-212`) is deleted.
- **FR-001 / #4931 — TWO distinct mechanisms (do not conflate the seams):**
  - **(a) Removal seam** — `init.py` cleanup (`:1561-1598`): drop `.kittify/templates` from `ManagedPathProver(managed_relpaths=...)` so it is no longer proven by name; pass the templates/scratch dirs in `run_created=` **only** when this invocation actually created them (the provenance branch `provers.py:166` already exists and is currently dead at this site). A pre-existing user tree is then unprovable → preserved/archived with the same "not package-owned — left in place" diagnostic the sibling `command-templates` already prints. (init.py's `rmtree` at `:1596` is already routed + allowlisted; the fix is prover configuration, invisible to the routing census — see FR-005.)
  - **(b) Overwrite seam — BOTH full-copy functions** (`memory/`+`missions/` already back up in both; `templates/` is the sole gap in each):
    - `copy_specify_base_from_local:117-120` (`if templates_dest.exists(): shutil.rmtree(templates_dest)` then `copytree`) → back up first via `back_up_operator_subtrees(specify_root, ["templates"])` (the in-file `memory/` precedent at :107, #4759).
    - `copy_specify_base_from_package:193` (`copy_package_tree(templates_resource, templates_dest)` with the DEFAULT `preserve_existing=False` → `rmtree` at :158) — **this is the pip-installed default `init` path** — add `preserve_existing=True`, mirroring `memory/` at :179. Missing this leaves the P0 destroyer live on the most common path, and a repro run inside a spec-kitty checkout resolves to the *local* path and would never exercise it (so the regression MUST force the package path explicitly).
    - Do **not** force either through `guard_destructive_removal` (that models an overwrite as a removal).
- **FR-004 / #4926 — arch-gate extension, scoped honestly.** Add `research.py` to the scanned module set of `tests/architectural/test_mutation_ownership_routing.py` so its raw `unlink` literals must be **routed away** (the census refuses to allowlist a raw user-content op — a leftover un-routed `unlink` fails CI). That is the *only* thing this removal-shaped, line-pinned census can police here. It structurally CANNOT catch: the overwrite/`copy2`/`os.replace` op class (not in its vocabulary), `template/manager.py` (not in its scanned set), or #4931's mis-configured-but-routed prover (a behavioral defect, not a raw literal). Adding `manager.py` to the scanned set is optional and does not help — its destroyer becomes a *routed* op after FR-001(b), so the census would just allowlist it; the real guard there is behavioral.
- **FR-005 / behavioral regression is the durable protection.** Per C-004, each defect lands an issue-pinned `@pytest.mark.regression` test through the real entry point: #4931 (both destroyers — pre-existing user tree preserved via the guard path AND via the full-copy path), #4926 (all four assets: no 0-byte fabrication + no `--force` truncation), #4921 (writer-layer refusal). These are RED before / GREEN after and are what SC-001/SC-003/SC-004 rest on — not the arch gate.

## Project Structure

### Source Code (repository root)

```
src/specify_cli/
├── asset_preservation/
│   ├── guard.py            # + guard_destructive_overwrite, OverwriteVerdict   (WP-A)
│   ├── errors.py (or brief-local)  # + BriefExistsError                        (WP-A)
│   └── provers.py          # unchanged (run_created branch already present)
├── mission_brief.py        # write_mission_brief gains overwrite=; raises BriefExistsError  (WP-A)
├── cli/commands/
│   ├── intake.py           # two gates delegate to the chokepoint error        (WP-A)
│   ├── research.py         # _copy_asset + CSV loop route through the guard     (WP-B)
│   └── init.py             # ManagedPathProver run_created re-wire              (WP-C)
└── template/manager.py     # full-copy rmtree routed through guard_destructive_removal  (WP-C)

tests/
├── architectural/test_mutation_ownership_routing.py   # extended to research   (WP-B)
├── specify_cli/... (brief / research / init regression + unit tests)           (per WP)
└── (asset_preservation overwrite-guard unit tests)                             (WP-A)
```

**Structure Decision**: single project; changes are localized to the three CLI command modules, the shared `asset_preservation` authority, and the brief writer. No new top-level packages.

## Parallel Work Analysis

### Dependency Graph

```
WP-A (#4921 + shared guard_destructive_overwrite + BriefExistsError)   ← foundational
   ├──→ WP-B (#4926 research consumes the guard + arch-gate extension)  (depends on WP-A)
WP-C (#4931 init prover re-wire + manager.py rmtree guard)              ← independent, parallel to WP-A/B
```

- **Sequential**: WP-A must land the overwrite primitive before WP-B consumes it.
- **Parallel streams**: WP-C is fully independent (disjoint files: `init.py`, `template/manager.py`) — runs in parallel with WP-A.
- **Agent assignments (no-overlap ownership map)**:
  - WP-A owns: `asset_preservation/guard.py` (+ errors), `mission_brief.py`, `cli/commands/intake.py`, brief tests.
  - WP-B owns: `cli/commands/research.py`, `tests/architectural/test_mutation_ownership_routing.py`, research tests.
  - WP-C owns: `cli/commands/init.py`, `template/manager.py`, init tests.
  - No file is written by two WPs (WP-B only *imports* the WP-A primitive).

### Coordination Points

- **Integration**: after WP-A/B/C approve, `spec-kitty merge` consolidates the lanes; the three reproduction scripts (#4931/#4926/#4921) run against the consolidated tree as the mission-level acceptance (SC-001), plus the full pre-existing control arms (SC-002).
- **Cross-seam audit** (folded into WP-C): sweep every `guard_destructive_removal` call site (10 migrations + `skills/installer.py` + `init.py`) for other `managed_relpaths`-by-name shortcuts, so #4931's fix does not leave the same defect elsewhere. Coordinate the prover-wiring shape with the claimed sibling #4907 (same removal seam) — record any divergence risk rather than editing #4907's surface.

## Risks

- **R1 — over-refusing legitimate research**: if `substantive` is computed too strictly, a normal templated research run could refuse. Mitigation: `substantive` mirrors the *current* successful copy predicate (`template_path and template_path.is_file()`); NFR-002 control arm (templated run) must stay green.
- **R2 — brief XOR recovery regression**: the new gate must sit *after* the partial-state cleanup so orphan-sidecar recovery is preserved. Covered by an explicit no-regression scenario (US3 #3).
- **R3 — init `run_created` provenance accuracy**: must mark the templates dir run-created *only* when this invocation created it; a false positive re-introduces the deletion. Mitigation: derive `run_created` from the actual create step, plus the #4931 regression proving a pre-existing tree is preserved and US1#3 proving a genuinely-created tree is still cleaned.
- **R4 — arch-gate vacuity**: extending the gate to research must add a concrete floor + a self-mutation check, not a vacuous allowlist entry (DIRECTIVE_043).

## Testing Strategy

- **Per-WP** (targeted, per charter Testing Requirements): each WP runs its own module tests plus its owning subsystem dir. WP-A: brief + asset_preservation tests. WP-B: research tests + `tests/architectural/test_mutation_ownership_routing.py`. WP-C: init + template-manager tests.
- **ATDD/red-first**: each of #4931/#4926/#4921 lands an issue-pinned `@pytest.mark.regression` reproduction that is RED through the pre-existing CLI entry point before the fix; transitional repros become focused unit/functional tests after green (never left `regression`).
- **Mission-level (post-merge)**: the three reproduction scripts + control arms (SC-001/SC-002), and `tests/architectural/` if the arch-gate change is cross-cutting.
