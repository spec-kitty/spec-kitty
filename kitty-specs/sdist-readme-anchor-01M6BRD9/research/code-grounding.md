---
type: reference
updated: 2026-11-01
---

# Code grounding: the sdist README / CHANGELOG include (#6926)

Read-only pass, run on `origin/main` at `7e2ca9fdc` before specifying. Audience: the implementer and the reviewer of this Mission.

## 1. Include and exclude rules

`pyproject.toml`, `[tool.hatch.build.targets.sdist]` (lines 240–287 on the base):

- `artifacts = ["packs/built-in/**"]` re-adds the VCS-ignored, fetched built-in tree.
- `include` holds `src/**/*`, `packs/built-in/**`, `packs/built-in.source.yaml`, `pins/**`, `hatch_build.py`, `src/charter/offering/curation/imports/**/*`, and the bare entries `README.md`, `LICENSE`, `CHANGELOG.md`, `pyproject.toml`.
- `exclude` holds `.kittify/**`, `.kittify/active-mission`, `src/specify_cli/**/tests/**`, `acceptance-jvm/**`, `tests/scenarios/**`, `services/**`, `contracts/**`, `packs/internal/**`, `packs/internal.source.yaml` and `packages/**`.

Hatchling (`hatchling/builders/config.py`) compiles every list with `pathspec.GitIgnoreSpec.from_lines`. In gitignore semantics a pattern with no slash matches at any depth, so `README.md` matches every `README.md` in the tree and `CHANGELOG.md` every `CHANGELOG.md`. A leading `/` anchors the pattern to the project root; hatchling itself relies on this for the `packages` option (`f"/{relative_path}/"`, with the comment "Matching only at the root requires a forward slash").

Checked against the installed pathspec:

| Path | `README.md` | `/README.md` |
|------|-------------|--------------|
| `README.md` | match | match |
| `docs/README.md` | match | no match |
| `kitty-specs/x/README.md` | match | no match |

Three exclude entries (`services/**` + `contracts/**`, `packs/internal/**`, `packages/**`) already exist partly or wholly to cancel this same leak tree by tree. Anchoring the include closes the class instead of adding a fourth tree-by-tree exclude.

## 2. What ships today

`uv build --sdist` on the base: 2,899 members (archive root stripped).

`README.md` / `CHANGELOG.md` files outside the repository root, by top-level tree:

| Tree | Count | Ships because of |
|------|-------|------------------|
| `kitty-specs/` | 698 | bare `README.md` only (stray) |
| `docs/` | 33 (32 `README.md` + `docs/changelog/CHANGELOG.md`) | bare `README.md` / `CHANGELOG.md` only (stray) |
| `tests/` | 11 | bare `README.md` only (stray) |
| `scripts/` | 2 | bare `README.md` only (stray) |
| `packs/` | 17 (16 under `packs/built-in/`, plus `packs/README.md`) | `packs/built-in/**` for the 16; bare `README.md` only for `packs/README.md` |
| `src/` | 23 | `src/**/*` (intended) |
| `pins/` | 1 (`pins/README.md`) | `pins/**` (intended, pinned by `test_pins_readme_ships_in_the_sdist_and_the_wheel`) |

The whole `docs/`, `kitty-specs/`, `scripts/` and `tests/` presence in the archive is these README / CHANGELOG files: no other member of those trees ships. The issue's 2026-10-31 counts (31 and 676) have grown to 33 and 698 in a day.

Expected effect of anchoring: 745 members leave the archive (698 + 33 + 11 + 2 + `packs/README.md`), nothing is added, and the root `README.md` and `CHANGELOG.md`, every `src/**` README, `pins/README.md` and every `packs/built-in/**` member stay. `packs/README.md` is a core-repository explainer of the pin layout, not built-in pack content, so dropping it does not touch the built-in invariant.

## 3. Existing guards

- `tests/cross_cutting/packaging/test_packaging_safety.py` builds once per run through the session fixture `build_artifacts` (`tests/conftest.py`, backed by `tests/_support/shared_build_artifacts.py`, `python -m build --no-isolation`) and reads the archive with `tarfile`. The archive tests are `@pytest.mark.slow` (module mark `integration`). The pattern to mirror is `test_sdist_excludes_the_mission_status_service_and_the_contract_tree`: strip the `<name>-<version>/` root, assert no member under the trees, and keep a same-fixture positive control (`src/specify_cli/` present, `pyproject.toml` at the root). The same module has a pure helper plus a self-test for planted members (`service_binary_leaks`, `companion_leaks`); the new check follows that shape so its logic is testable without a build.
- Config-level readers of the sdist table: `test_wheel_config_only_includes_built_in_pack_skills` (same file; asserts `packs/` entries start with `packs/built-in`), `test_packaging_config_ships_the_whole_pins_directory` (same file; `pins/**` in include), `tests/ci/test_mission_status_api_build.py::packaging_violations` (requires `services/**` and `contracts/**` in exclude), `tests/cross_cutting/packaging/test_companion_version_lock.py::test_the_cli_sdist_excludes_the_companion_tree` (`packages/**` in exclude). None reads the `README.md` / `CHANGELOG.md` entries, so anchoring breaks none of them.
- Other archive readers: `test_package_bundling.py`, `test_sdist_offline_wheel.py` (builds a wheel from the sdist offline; needs `hatch_build.py`, the pins and the built-in tree, all unaffected), `tests/charter_offering/test_pack_full_tree_integrity.py`.
- `tests/architectural/test_pyproject_shape.py` gates the wheel `packages` inventory only, not the sdist table; it is still run as the cheap architectural guard for a `pyproject.toml` change.

## 4. Collision

Open pull requests that touch `pyproject.toml` (heads fetched 2026-11-01):

- **#7004** "[#6915] Cut core over to the pinned events read service" (the events-service cut-over session) edits this exact exclude block: it deletes `services/**` and rewrites the comment above `contracts/**`. This Mission must not touch those two lines or their comment. Its edits sit on the `include` list (two entries) and add one `site/**` line after `packages/**`, so a textual conflict is unlikely; whichever lands second rebases. Once both land, the `contracts/**` exclude is no longer needed for README leakage, but removing it is #7004's call, not this Mission's.
- #7005, #6944, #6903, #6908 show `pyproject.toml` hunks only from merging `main`; none changes the sdist rules.

## 5. Churn

The sdist block (lines 240–287) changed in 7 commits over the last 90 days, all additive tree-by-tree excludes or pack-sourcing changes: #6904 (`packages/**`, 2026-10-31), #6590 (`pins/**`, 2026-10-31), #6451 (built-in artifacts and pin, 2026-10-19), the Mission Status API scaffold (`services/**` / `contracts/**`, 2026-10-13), #6053 (`acceptance-jvm/**`, 2026-10-12), #3664 and the internal-pack scaffold (August). Three of those excludes carry comments explaining the unanchored README leak; the block is hot, so the change stays minimal.

## Consequences for the Mission

1. Fix by anchoring (`/README.md`, `/CHANGELOG.md`), plus `site/**` in `exclude`. No other include or exclude changes.
2. Red-first test reads the built archive and fails on the base (745 stray members today).
3. Before/after archive listings are compared; the expected diff is removal only, with `packs/built-in/**` identical.
