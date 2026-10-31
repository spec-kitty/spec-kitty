# Research: CharterYaml activation-key parity (#6556)

**Mission**: `charter-yaml-activation-key-parity-01M67HRX`
**Base**: `main` at `512567eee7`

## R1 — Does the defect still reproduce on current `main`?

Yes. The reproduction was run through the pre-existing writer entry point, not by
hand-editing a dict:

1. Copy a sound `charter.yaml` (catalog/governance/directives/metadata) into a temp
   project; write `.kittify/config.yaml` with the `charter:` pointer and one legacy
   activation key (`activated_directives: [DIRECTIVE_001]`); no activation ledger.
2. `resolve_ledger_source()` answers `LEGACY` with `unmigrated_keys` — the state the
   issue describes (a project the ledger migration has not reached).
3. `apply_yaml_write(prepare_activation_write(root, {"activated_skills": ["skill-a"]}))`
   writes `activated_skills` onto `charter.yaml` (`on disk keys: ['activated_skills']`).
4. `CharterYaml.model_validate(load_charter_yaml(...))` raises
   `1 validation error for CharterYaml … Extra inputs are not permitted
   [type=extra_forbidden]`.

Repeated per key the result is the same for `activated_glossary_packs`,
`activated_skills` and `activated_anti_patterns`. A charter with no activation keys
validates, which is why the bug hid.

## R2 — Who is wrong, the writer or the model?

The model. `charter.activation.pack_manager.ACTIVATION_YAML_KEYS` is the single derived
authority for the flat activation-key vocabulary (`("activated_kinds", *YAML_KEY_MAP
.values(), *_TOKENLESS_ACTIVATION_KEYS)`, itself derived from `ArtifactKind` /
`CHARTER_KIND_TOKENS`), and it contains thirteen names. `CharterYaml` declares ten, in a
hand-written block, with no test tying it to the authority. Every other consumer of this
vocabulary (`charter_yaml_io._ACTIVATION_KEYS`, `compiler._legacy_activation_keys`,
`m_unify_charter_activation_finalize.ACTIVATION_KEYS`) was already converted to a derived
lazy accessor and guarded by
`tests/charter/test_activation_vocabulary_setequal.py`; the pydantic model was the one
surface that was never converted, and the docstring still says "the ten `activated_*`
fields".

## R3 — Did #6496 make the model obsolete? (does activation still reach `charter.yaml`?)

No, it made the model's list stale, and the model stays necessary:

- `kernel.activation_ledger_store.resolve_activation_source` answers `LEDGER` for a project
  with `.kittify/charter/activation.yaml` (and for a fresh project with no legacy key), and
  `prepare_activation_write` then writes the ledger, not `charter.yaml`.
- It answers `LEGACY` — with `charter.yaml` (via the `config.yaml` `charter:` pointer) or
  `config.yaml` itself as the write target — inside the upgrade scope and for an unmigrated
  project (legacy keys present, no ledger). In that mode `prepare_activation_write` writes
  the same `ACTIVATION_YAML_KEYS` names onto `charter.yaml` through
  `prepare_charter_yaml_section(target, "activation", …)`.
- So the legacy surface is still a real, written shape, and `CharterYaml` is still described
  (and used by `charter synthesize`'s soundness check, #6415/#6555) as its schema. The
  model must therefore accept the legacy vocabulary; dropping the activation fields as
  "legacy and gone" would break every unmigrated charter instead.

## R4 — `activated_assets`: the issue's fourth key is stale

The issue lists `activated_assets` among the keys `ACTIVATION_YAML_KEYS` contains. On
current `main` it does not, and it must not: `ArtifactKind.ASSET.activatable` is `False`
(asset is a loose-contract blob, never a live governance rule), the authority's
`_TOKENLESS_ACTIVATION_KEYS` derives from `kind.activatable`, and the writer refuses the key
outright — `prepare_activation_write(root, {"activated_assets": ["x"]})` raises
`ValueError: Unknown activation ledger key(s): ['activated_assets']`. The
`persistent-deactivation-ledger` mission recorded the same ruling ("`activated_assets` is
not a ledger key") and `docs/architecture/doctrine-kinds.md` states it. The fix therefore
adds three fields, not four, and a test pins the absence so the stale half of the issue is
not "fixed" later by mistake.

## R5 — Why static fields rather than a derived model

`charter.activation.pack_manager`'s import chain already loads `charter.activation.schemas`
(verified: importing `pack_manager` leaves `charter.activation.schemas` in `sys.modules`),
so importing `ACTIVATION_YAML_KEYS` at module scope *from* `schemas.py` is a circular
import — the same cycle the rest of the codebase breaks with function-scoped lazy imports
(`charter_yaml_io._allow_activation_keys`, `compiler._legacy_activation_keys`,
`m_unify_charter_activation_finalize._activation_keys`). A pydantic model's fields are
created at class-definition time, so a lazy accessor cannot produce them; a
`create_model`-based dynamic model would lose per-field types, docstrings, `model_fields`
ordering and static-analysis visibility for a vocabulary that changes rarely.

Decision: keep static, typed, documented fields and pin equality with the authority in a
test that reports the missing/stray names. This matches the established pattern for the
other three copies of this vocabulary and keeps the authority single.

## R6 — Where the tests belong

- `tests/charter/test_charter_yaml_model.py` already owns "the shape of `charter.yaml`"
  (flat-at-root, three-state, forbid-extra) — the behavioural and end-to-end cases go here.
- `tests/charter/test_activation_vocabulary_setequal.py` already owns "this vocabulary has
  one authority" for the three derived copies — the model joins it as the fourth surface,
  rather than inventing a new architectural test file for one assertion pair.

## R7 — Blast radius

`CharterYaml` is constructed (not validated against disk) by
`src/charter/activation/compiler.py` and
`src/specify_cli/upgrade/migrations/m_unify_charter_activation_finalize.py`; both pass no
activation kwargs, so adding optional fields cannot change their behaviour. Serialization
is key-driven (`_OPTIONAL_EMPTY_OMIT_KEYS`), and the three new fields are never emitted
unless set, so no on-disk bytes change. No reader of `CharterYaml.model_fields` outside the
tests exists (`grep`), so the field-set change is additive for every caller.
