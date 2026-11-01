# Research: Anchor the sdist README include

Full evidence: [`research/code-grounding.md`](research/code-grounding.md).

## R-1 Hatchling pattern semantics

- **Decision:** anchor with a leading `/` (`/README.md`, `/CHANGELOG.md`).
- **Rationale:** hatchling builds include/exclude/artifacts specs with `pathspec.GitIgnoreSpec.from_lines`. Gitignore semantics: a pattern with no slash matches at any depth; a leading slash anchors to the root. Verified with the installed pathspec (`/README.md` matches `README.md`, not `docs/README.md`), and hatchling anchors `packages` the same way.
- **Alternatives considered:** excluding `docs/**`, `kitty-specs/**`, `scripts/**`, `tests/**` one by one (rejected: leaves the class open for every new tree, which is how `services/**`, `contracts/**`, `packs/internal/**` and `packages/**` piled up); `only-include` (rejected: changes the selection model of the whole table, far beyond the fix).

## R-2 Test placement and shape

- **Decision:** extend `tests/cross_cutting/packaging/test_packaging_safety.py` with a pure helper (`sdist_stray_tree_members`), a planted self-test (no build), and an archive test on the shared `build_artifacts` fixture with a same-archive positive control.
- **Rationale:** mirrors the module's existing `service_binary_leaks` / `companion_leaks` pattern and `test_sdist_excludes_the_mission_status_service_and_the_contract_tree`; reuses the once-per-run build (NFR-001).
- **Alternatives considered:** a config-level-only assertion on `pyproject.toml` (rejected as the sole check: the issue requires the BUILT archive; a config twin for `site/**` is kept as a cheap second check).

## R-3 Sequencing with PR #7004

- **Decision:** touch only the two include lines and append `site/**` after `packages/**`.
- **Rationale:** #7004 rewrites the `services/**` / `contracts/**` lines and comment; disjoint hunks keep the rebase trivial in either landing order.

## Supply chain

No dependency is added, upgraded or removed; DIRECTIVE_051 controls do not apply.
