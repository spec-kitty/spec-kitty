# Tooling friction — Silent Destructive-Write Hardening

(Appended during implementation as friction is encountered.)

## WP01 (#4908)

- **T001 regression-test fixture trap**: reproducing the bug against a totally
  fresh, never-activated project (no `.kittify/config.yaml` at all) makes
  `catalog.references` shrink hugely on the very first `charter activate`
  call (268 -> 165 in one probe) for a reason that has NOTHING to do with
  #4908 -- `compiler.py`'s `_resolve_config_activated_roots` (FR-018,
  WP07/T038) deliberately narrows from an "unconfigured -> all-built-ins
  fallback" convenience default to a strict config-governed set the moment a
  project gains its first `activated_<kind>` key. That state transition looks
  identical to the mission-flip symptom the issue reports (same rough
  magnitude) and will make a naive "references must not shrink" assertion
  fail even with the real fix applied. Fix: seed
  `.kittify/config.yaml` with at least one `activated_directives` entry
  *before* the first `charter generate`, so the project is already
  "configured" going into the repro and the before/after reference-count
  comparison isolates the recompile behavior from the unrelated FR-018
  transition. Also: the directive picked for the repro (`025-boy-scout-rule`)
  can already be transitively pulled into the catalog by an unrelated
  DRG `requires`/tension edge from another activated artifact (e.g. the
  `minimal` built-in pack's directive set) -- confirm the target id is
  genuinely absent from the baseline catalog before asserting growth, or the
  "added" assertion is vacuously true.
- **`mypy --strict` + `charter.*` `follow_imports = "skip"`**: any narrow,
  single-file mypy run on a `specify_cli` module that reads an attribute off
  a `charter.*`-typed return value (e.g. `CharterInterview.mission`) sees
  that value as `Any`, because `pyproject.toml`'s `[tool.mypy]` overrides
  skip following `charter.*` for exactly this kind of check (and separately
  skip `specify_cli.*` to avoid dragging in the CLI bootstrap graph). A
  function with a concrete `-> str` return type that returns such an
  attribute directly trips `no-any-return`. Fix is an explicit `str(...)`
  narrowing at the return site (a real, safe conversion given the field's
  runtime type, not a suppression) rather than reaching for `# type: ignore`.

