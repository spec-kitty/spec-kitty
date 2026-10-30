# Discovery — pack file-name collision diagnostic (#6743)

Mission: `pack-file-name-collision-diagnostic-01M66YTQ`
Grounded on `origin/main@512567eee7`.

## The defect, reproduced

A repo-configured org pack that ships a directive file named like the built-in
`024-locality-of-change.directive.yaml` but declaring `ACME_024`:

* `spec-kitty charter pack validate /tmp/collide/acme-pack` → `Pack validation: 0 errors, 0 advisories`, exit 0.
* `spec-kitty doctor charter-packs` (same repo) → `Collisions: none — every artifact resolves from a single layer.`.
* `IdentityIndex.stored_spelling(DIRECTIVE, "ACME_024")` on the same tree →
  `ActivationIdCollisionError` naming the org file, the built-in file and both ids.

So the runtime refusal exists; only the authoring diagnostics are missing. Not
superseded: `git log -S "file_name_collision"` shows only the #6527 writer slice
(`a8dd1812a6`), and no changelog entry references #6743.

## Decisions

1. **Detection belongs in `charter.activation.identity_index.IdentityIndex`.**
   It already owns pack-layer identity: `_scan(kind)` produces
   `IdentityEntry(kind, stem, declared_id, layer, path)` for every scanned layer
   and `_KindTable` already groups entries per kind with `ids_by_stem`. A new
   query over those tables adds no directory walk and no second YAML read
   (NFR-001). `collision_error()` already computes the same "every file with this
   stem, in precedence order" set, so the new record and the writer refusal are
   two views of one computation.

2. **Severity: error, no opt-in** (C-003). The operator's ruling
   (`file_name_collision`, activate-output-and-identity) makes it a pack-content
   error, and every writer refuses such an id. A *deliberate* override of a
   built-in keeps the same declared id and is declared through DRG
   `overrides`/`enhances` intent, already governed by
   `same_id_collision`/`unknown_target` (pack_validator FR-011..FR-013). A
   different id under a taken file name is never a legitimate override, so
   there is nothing to opt in to.

3. **Validate compares the pack under validation with the built-in layer
   only** (C-004). `charter pack validate <path>` takes a bare directory (docs
   show `validate ./my-pack`) and may run outside any repository, so it must not
   read `.kittify/config.yaml`. The chain case (org vs project, issue comment 1)
   is what `doctor charter-packs` covers, which is exactly the split the issue
   asks for ("for the pack being validated" vs "across the configured chain").

4. **Wiring point for validate: `charter/activation/org_charter.validate_pack_with_org_charter`.**
   That function is documented as "the CLI's validation door" and already owns
   the activation-layer leg (the org-charter check). `charter.offering` must not
   import `charter.activation` (no module there does today), so the leg cannot
   live inside `pack_validator.py` (C-002). The `ValidationResult` /
   `ValidationIssue` record types are reused unchanged, so `--json` output needs
   no new schema.

5. **Wiring point for doctor: a `_run_file_name_collision_check(report, repo_root)`
   leg** in `_charter_pack_collect.py`, following the existing
   `_run_cross_grain_check` / `_run_operating_procedures_check` pattern: append a
   human message to `org_drg["errors"]` (which already drives
   `CharterPackHealthReport.healthy` → RC=1) plus a structured
   `org_drg["file_name_collisions"]` list for `--json`, and a renderer. No new
   health field, no parallel report assembly.

6. **The message shape mirrors `ActivationIdCollisionError`** — file name,
   `(layer file path, declared id)` per participating file in precedence order,
   and a rename instruction that names the non-built-in file(s) when a built-in
   file takes part. One builder, used by both surfaces, so wording cannot drift
   (FR-004).

## Evidence gathered

* `src/charter/activation/identity_index.py` — `_KindTable`, `_scan`, `collision_error`, `stored_spelling`.
* `src/charter/activation/activation_engine.py::ActivationIdCollisionError` — current message and `declarations`/`rename` shape.
* `src/charter/offering/packs/pack_validator.py::validate_pack` — `ValidationIssue(category=...)`; existing categories documented in the module docstring.
* `src/charter/activation/org_charter.py::validate_pack_with_org_charter` — CLI door.
* `src/specify_cli/cli/commands/_charter_pack_collect.py` — `_collect_layer_collisions` (a *different* collision sense: same id shadowing across layers, rendered as "Collisions"), `_run_cross_grain_check` pattern.
* `src/specify_cli/cli/commands/_charter_pack_health.py::CharterPackHealthReport.healthy` — `org_drg["errors"]` flips RC to 1.
* Test harnesses to extend: `tests/charter/activation/test_identity_index.py` (fixture builder for org + project layers), `tests/specify_cli/cli/commands/test_doctor_charter_packs_collisions.py` (`contextlib.chdir` + `.kittify/config.yaml`), `tests/charter/packs/test_org_charter_hooks.py`, `tests/specify_cli/cli/commands/charter/test_charter_pack_tooling.py`.

## Open questions

* None that block specification. Resolved while grounding: severity (error),
  opt-in (none), validate's layer scope (pack + built-in), and where the
  detection lives (IdentityIndex).
