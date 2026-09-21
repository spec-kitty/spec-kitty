# Contract: `charter bundle validate` — kind coverage, manifest-driven resolution, corruption honesty

## Kind coverage (#4833) behind one importable SSOT
- `_KIND_SUFFIX` / `_ALL_ARTIFACT_PATTERNS` cover every registration-writing kind: `directive, tactic, styleguide, procedure, agent_profile` (`agent_profile → .agent.yaml`), **derived from** the module-level `DIRECT_WRITE_KINDS` constant.
- **`DIRECT_WRITE_KINDS`** lives in `src/charter/offering/artifact_kinds.py` (leaf module). `scan_project_artifacts` (`project_scan.py`), the `ManifestArtifactEntry.kind` `Literal` (`manifest.py`), and this table all reference it — no hand-duplicated tuple (post-plan squad MEDIUM: the kind list was a non-importable function-local literal).
- **Parity guard (NFR-002)**: a test asserts the validator kind set, the scanner kind set, and the manifest `Literal` all equal `DIRECT_WRITE_KINDS`. Adding a future kind without updating the constant fails the guard (drift closed by construction, DIRECTIVE_043).
- **Behavior**: activating a project agent profile, or registering a project procedure, produces **no** `Provenance file has unknown kind` error.

## Hybrid resolution (#4832 durable) — manifest for registered, filesystem for orphans
- **Positive resolution**: for a *registered* artifact, resolve `(kind, slug, path, provenance_path)` through the synthesis manifest entry — NOT by re-parsing the on-disk filename.
- **Behavior**: a registered directive whose filename is still `LOVE_THY_ENEMY.directive.yaml` (manifest slug `love-thy-enemy`) validates clean — no "has no provenance sidecar", no "references non-existent artifact" — with the file **unmodified** (go-forward: no rename needed).
- **Orphan sweep stays filesystem-driven** (post-plan squad MEDIUM, both directions): compare on-disk sidecars against the manifest `provenance_path` set and on-disk artifacts against the manifest `path` set. The switch is **hybrid**, not "fully manifest-driven" — a manifest-only walk cannot see an on-disk artifact/sidecar absent from the manifest.
- The `<NNN>-` digit-strip in `_kind_and_slug_from_artifact` (and its test `test_bundle_validate_extension.py:500`) is retained for the orphan/legacy path, or retired deliberately with the parse it guards — not silently broken.

## Corruption honesty preserved (NFR-001 — both directions, must not weaken)
- A provenance sidecar with **no** backing artifact still errors ("references non-existent artifact").
- An artifact with **no** provenance sidecar (and **no** manifest entry) still errors ("has no provenance sidecar") — this is the orphan-*artifact* direction the hybrid sweep must keep catching.
- **Tests (guards)**: (a) an orphaned `agent_profile-ghost.yaml` with no `ghost.agent.yaml` still fails; (b) an on-disk `orphan.directive.yaml` absent from the manifest with no sidecar still fails. Both prove the kind-table + manifest switch did not trade a false-positive for a false-negative in either direction.

## Backward compatibility (NFR-003)
- A legacy project with no synthesis state still passes `charter bundle validate` (existing C-012-style contract unchanged).
