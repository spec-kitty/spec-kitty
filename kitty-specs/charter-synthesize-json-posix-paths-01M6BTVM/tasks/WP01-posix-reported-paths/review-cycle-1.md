---
affected_files: []
cycle_number: 1
mission_slug: charter-synthesize-json-posix-paths-01M6BTVM
reproduction_command: spec-kitty agent tasks move-task WP01 --to approved --mission charter-synthesize-json-posix-paths-01M6BTVM --agent user
reviewed_at: '2026-11-01T17:52:36Z'
reviewer_agent: user
wp_id: WP01
---

Approved by user: approval:WP01

Review round 1 — WP01 (fix(6277) POSIX reported paths)

VERDICT: approved after one blocking-on-merge-class finding, fixed in fc1dbb68.

What I read (not just the diff): the whole of _fresh_project_layer.py, synthesize.py's
envelope construction, _synthesis.py::_load_written_artifacts_from_manifest,
write_pipeline.py::promote, kernel/charter_pack_paths.py, kernel/paths.py::to_posix, and
manifest.py's verify/_validate_manifest_path path readers.

Findings and dispositions

1. (fixed, fc1dbb68) The helper hand-rolled the separator swap: `.as_posix()` in
   repo_relative_posix and `PurePosixPath(entry.path.replace("\\", "/"))` at the manifest
   projection. kernel.paths.to_posix is the repo's single normalisation seam and its
   docstring names this exact failure mode (#2836: "scattering str(x).replace(...) across
   the tree re-invited the exact per-site Windows drift"). Both sites now call to_posix;
   the helper only decides *what* is reported.

2. (verified, no change) Recording POSIX paths in synthesis-manifest.yaml cannot break the
   readers: `_validate_manifest_path` already runs the raw path through `to_posix` before
   resolving, so an old backslash manifest and a new POSIX manifest verify identically,
   and `repo_root / <posix string>` is a valid access path on every platform.

3. (verified, no change) No other repository-relative path string in the synthesize
   envelope still renders with str(relative_to(...)); the only remaining string sources are
   the four sites this PR routes through the helper. `_synthesize_project_layer` and the
   direct-write branch already used `.as_posix()`.

4. (out of scope, follow-up filed) `charter generate --json` (`charter_path`) and
   `charter interview --json` (`interview_path`) still render with str(relative_to(...)).
   Different commands, different envelopes; #6277 is scoped to `charter synthesize`.

5. (verified) POSIX-host behaviour is unchanged: every targeted suite passes with no
   expected-value edit, and str(p) == p.as_posix() on POSIX.

6. (verified) The regression harness is honest: the module failed 4 of 5 tests against the
   unfixed source (fresh seed real run, dry run, planned_deletes, manifest projection) and
   the control test asserts that a bare str(relative_to(...)) under the simulation really
   produces a backslash, so the harness cannot pass vacuously.

Test evidence on the reviewed head (fc1dbb68):
- tests/specify_cli/cli/commands/charter/test_synthesize_reported_paths.py — 5 passed
  (red before the fix: 4 failed)
- tests/charter/test_synthesis_provenance_paths.py — 4 passed
- tests/integration/test_charter_synthesize_fresh.py + tests/charter_pack_synthesizer +
  tests/charter/test_bundle_manifest_model.py + tests/charter/test_synthesis_provenance_paths.py
  — 22 passed
- charter synthesis CLI selection (tests/specify_cli/cli/commands/charter -k
  "synthes or resynthes or manifest or envelope or provenance") — 73 passed
- tests/architectural/test_no_legacy_terminology.py — 98 passed (after `make sync-packs`
  in the lane worktree; the pack tree is untracked and absent from a fresh worktree)
- ruff check + ruff format --check clean; mypy clean on the two files touched by the
  follow-up commit (write_pipeline.py keeps its 2 pre-existing no-any-return errors,
  present on origin/main)

Not verified by this round: native Windows execution (no Windows host); the fix is proven
by the simulated-rendering regression and by the platform-independent `to_posix` seam.
