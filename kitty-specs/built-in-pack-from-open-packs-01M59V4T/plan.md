# Implementation Plan: Built-in pack sourced from open-packs

**Branch**: `feat/6451-built-in-from-open-packs` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

## Summary

Delete the committed `packs/built-in/` and `packs/internal/` trees. Each pack gets a pin (`packs/<pack>.source.yaml`: repository, commit, subtree, digest). One fetch/verify core in `charter.offering.packs` serves:

- the sync script, which dev, tests and CI use;
- a hatch build hook, which wheels and sdists use;
- the `charter pack vendor` pin-bump helper.

The installed layout is unchanged.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: hatchling (build hook API), git CLI (sparse/shallow fetch), ruamel.yaml (pin I/O), typer (CLI)
**Storage**: Local commit-keyed cache at `${XDG_CACHE_HOME:-~/.cache}/spec-kitty/open-packs/<sha>/<subtree>`, plus the gitignored `packs/<pack>` working trees.
**Testing**: pytest. Unit tests for the pin model and the fetch core use a local bare git repository as the fake open-packs remote. Packaging tests cover the wheel and sdist contents and the digest. Architectural gates cover tracked-tree absence and pin validity.
**Target Platform**: Linux, macOS and Windows dev and CI. No symlinks.
**Project Type**: single (CLI plus build tooling)
**Performance Goals**: warm sync ≤ 5 s, cold sync ≤ 60 s (NFR-001/002)
**Constraints**: no consumer runtime fetch (C-003); internal never shipped (C-002); `built_in_root()` contract unchanged (C-001); no `[tool.uv.sources]` (C-006)
**Scale/Scope**: about 35 files changed and about 600 tracked pack files deleted

### Supply-chain (DIRECTIVE_051)

No new package dependency. hatchling is already the build backend, and git is already a prerequisite. The fetched content is pinned to a 40-hex SHA and verified with a clean-tree SHA-256 digest before use, so an integrity failure blocks the build or sync. The repository URL comes from the committed pin only, and the fetch never takes a URL from the environment. An adversarial pass on the fetch and integrity boundary runs at the post-tasks squad, as the charter cadence requires.

## Charter Check

- Single canonical authority: open-packs becomes the only source, and the duplicate copies go away. ✅
- ATDD-first: each WP starts from a failing acceptance test (tracked-tree gate, digest refusal, offline sdist build). ✅
- Pack tiers: the internal-never-shipped invariant is kept, with a packaging test as the ratchet. ✅
- Canonical sources: CLAUDE.md "edit SOURCE templates" now points to open-packs. That is a governance text change, recorded in the ADR amendment. ✅
- Test policy: run targeted modules plus `tests/charter_offering`, the packaging tests and the specific architectural gates. No full architectural sweep. ✅

## Project Structure

### Documentation (this mission)

```
kitty-specs/built-in-pack-from-open-packs-01M59V4T/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md
├── contracts/ (pin schema, sync CLI contract)
└── tasks/
```

### Source Code (repository root)

```
packs/built-in.source.yaml          # + subtree
packs/internal.source.yaml          # NEW
packs/{built-in,internal}/          # DELETED from git, gitignored
src/charter/offering/packs/
  built_in_pin.py  -> pack_pin.py (PackPin; BuiltInPin alias kept)
  pack_fetch.py    # NEW: fetch/cache/verify/atomic place
src/charter/offering/pack_paths.py  # BuiltInPackMissing actionable error
src/specify_cli/cli/commands/charter/pack_vendor.py  # pin-bump helper
scripts/sync_packs.py               # NEW thin entry point
hatch_build.py                      # NEW build hook
pyproject.toml, Makefile, .gitignore, .gitattributes
.github/workflows/{packs,ci-modules,module-tests,ci-windows}.yml
tests/charter_offering/, tests/cross_cutting/packaging/, tests/architectural/
docs/adr/3.x/2026-08-16-2-*.md (amend), CLAUDE.md
```

## Implementation Concern Map

| Concern | FRs | Notes |
|---|---|---|
| IC-1 Pin model generalised | FR-002, FR-011 | `PackPin` + `subtree`; internal pin minted |
| IC-2 Fetch/cache/verify core | FR-003, FR-004 | Git sparse fetch at SHA, cache, digest, atomic swap |
| IC-3 Sync entry + dev/CI wiring | FR-005, FR-006 | Script, make target, CI steps, missing-pack error |
| IC-4 Build hook + packaging | FR-007, FR-008, FR-009, FR-015 | Hook stages built-in; sdist carries it; internal excluded; clean-install digest check |
| IC-5 Pin-bump helper | FR-010 | `charter pack vendor` writes the pin only |
| IC-6 Gates | FR-001, FR-012, FR-013 | Tracked-tree absence, pin validity, regen/DRG on the fetched tree, drift gate retired |
| IC-7 Governance docs | FR-014 | ADR amendment, CLAUDE.md, packs/README |
| IC-8 Cutover | FR-001 | `git rm` the trees, gitignore them; land last |

## Risks

- **Every test that reads a pack goes red when the tree is absent.** Mitigation: CI syncs before tests, and the cutover lands last in the mission.
- **Hatch skips gitignored files.** Mitigation: the hook stages the tree through `force_include` in `build_data`. Packaging tests prove that `packs/built-in` is in both artifacts.
- **The internal pack digest differs from open-packs.** Mitigation: research finds the matching open-packs commit. If none matches, the open-packs side is published first.
