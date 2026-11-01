# Discovery findings — charter synthesize JSON path spelling (#6277)

## Scope statement

Issue #6277 is a single-field-family portability defect: repository-relative path strings
in the `charter synthesize --json` envelope are rendered with `str(Path.relative_to(...))`,
which uses the host separator, so Windows reports `\` where Linux/macOS report `/`. The
mission fixes the rendering rule for that command's reported paths, plus the manifest
paths it persists, and restores the acceptance scenario to assert full paths.

Term disambiguation (the issue uses "paths" in three senses):

- **Reported path** — a string in the JSON envelope or the human-readable output. This is
  what the issue is about; it is data, not a filesystem handle.
- **Access path** — a `Path` used to read/write. Unchanged by this mission; `Path`
  objects remain OS-native.
- **Recorded path** — `ManifestArtifactEntry.path` inside the committed
  `.kittify/charter/synthesis-manifest.yaml`. Same contract as a reported path (it is
  documented as "repo-relative"), and it is the value the real-run envelope projects, so
  it belongs in scope.

## Decisions

### D-001 — Grounded on current main; the defect is still live

Static grounding on `origin/main` (`287a226cfe`) and a local reproduction:

- `src/specify_cli/cli/commands/charter/_fresh_project_layer.py:139-142` returns
  `str(provenance_path.relative_to(repo_root))` and
  `str(manifest_path.relative_to(repo_root))`; `:154-157` does the same for the dry-run
  `files_planned`; `:163-166` for `planned_deletes`.
- `src/specify_cli/cli/commands/charter/synthesize.py:317-390` puts those strings straight
  into `files_written` / `files_planned` / `planned_deletes` / `written_artifacts[].path`.
- `src/charter/activation/synthesizer/write_pipeline.py:654` records
  `ManifestArtifactEntry.path` as `str(live_content.relative_to(repo_root))`, and
  `_load_written_artifacts_from_manifest` (`_synthesis.py:448-508`) projects
  `entry.path` verbatim into the real-run envelope — so the defect is not limited to the
  fresh-seed branch, and the persisted manifest carries the same spelling.
- The direct-write branch already uses `.as_posix()`
  (`_fresh_project_layer.py:226,234`; `_synthesis.py:332,361`), which is why the issue
  reads as a fresh-seed-only defect. It is a split authority, not a deliberate contract.

Supersession check: no later commit fixes the fresh-seed helpers
(`git log -S "relative_to(repo_root))" -- src/specify_cli/cli/commands/charter/`), no
changelog entry mentions #6277, and the only trace is #6266's test relaxation
(`git show 45691a037f`, which switched the acceptance scenario to file-name matching and
wrote "until this is decided" into `tests/scenarios/absorption-ledger.json`).

Local reproduction on Linux shows the POSIX spelling (`.kittify/charter-packs/PROVENANCE.md`),
confirming that a POSIX host cannot show the defect directly — see D-003.

### D-002 — Fix at production, not at each field

The envelope has four emitting shapes and two code paths (fresh seed, manifest
projection). Normalising each `json.dumps` field would be four places today and a
guaranteed regression for the fifth. Instead each site that turns a `Path` into a
repo-relative *string* renders `as_posix()`, and the manifest projection normalises the
string it reads (so an older Windows-written manifest cannot re-leak a backslash). That
keeps one spelling rule: "a repo-relative path is a POSIX string; a `Path` is an access
path".

### D-003 — Red-first needs a Windows simulation, per repo precedent

CI runs on POSIX, where `str(Path)` and `Path.as_posix()` are identical, so a naive
regression test would be green before the fix. The repository already has the precedent
for this class of bug: `tests/runtime/test_windows_readonly_asset_delete.py` simulates
Windows delete semantics on POSIX and includes a control assertion that the simulation
genuinely breaks the unfixed path. The mission follows the same shape: patch
`Path.relative_to` to return a Windows-flavoured path (so `str()` renders `\` and
`as_posix()` still renders `/`), assert the envelope is POSIX, and prove the harness
itself is not vacuous.

`tests/kernel/test_is_windows_seam.py` records why faking `os.name` is not an option
("doing so flips `pathlib`'s `Path` to `WindowsPath` mid-test-run and crashes pytest"), so
the simulation patches the method's return value instead.

### D-004 — Restore the acceptance scenario's full-path assertion

#6266 relaxed `tests/scenarios/charter/charter.feature` from
`.kittify/charter-packs/PROVENANCE.md` to `PROVENANCE.md` precisely because of this bug.
Fixing the bug without restoring the assertion leaves the regression unguarded end to end
and leaves the ledger note stale. The scenario is restored and the ledger note updated to
say why the assertion is safe again.

## Evidence

- Issue #6277 body: the observed Windows envelope, and the nightly run it came from
  (38766592061, acceptance-bdd Windows leg on PR #6266).
- Batch-21 triage comment on #6277 names the exact helper lines and notes that the
  direct-write branch's `as_posix()` does not cover this path.
- `contracts/synthesis-envelope.schema.json` — the envelope contract keeps its shape; only
  string spelling changes.
- `src/specify_cli/cli/commands/charter/_fresh_project_layer.py:226-234` — the
  already-POSIX direct-write projection, i.e. the spelling the rest of the code intends.

## Open questions (resolved during planning)

- Q-001: does `ManifestArtifactEntry.path` belong to this issue or to a follow-up? **In
  scope.** It is the same repo-relative-string contract, and it is the value the real-run
  envelope emits; splitting it would ship a half-fix that the issue explicitly describes
  as the real-run shape.
- Q-002: does the fix need a changelog entry? **Yes** — the JSON envelope is user-facing
  output (agents and scripts consume it), so it goes under `[Unreleased]`.
- Q-003: is a schema/contract change needed? **No.** Field names, types and required set
  are unchanged; only the separator inside a `string`.
