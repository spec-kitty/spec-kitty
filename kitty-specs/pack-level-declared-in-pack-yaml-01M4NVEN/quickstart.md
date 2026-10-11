# Quickstart — pack-level-declared-in-pack-yaml

How the pieces fit, for an implementer or reviewer.

## The one-paragraph model

A Charter Pack now **declares** its level in `pack.yaml` (`pack_level: built-in|org|project`) instead of being inferred from where it sits. Loading refuses a declared level that disagrees with the configured position (`PACK_LEVEL_MISMATCH`), and `charter pack validate` checks the layout the declared level implies — finding the active-charter and DRG files through one descriptor-first resolution seam. The level vocabulary has exactly one owner, `kernel.pack_tiers`, and after this change the artifact *provenance* value is spelled the same way (`built-in`), so there is a single spelling everywhere. Core also gains the tooling to regenerate and drift-check a pack that lives outside core, so open-packs can vendor the built-in pack.

## Verify locally (targeted — no full suites)

```bash
# Descriptor + load + validate
.venv/bin/python -m pytest tests/charter/ tests/charter_offering/ -q

# Single-authority + authored-field gates (named files only)
.venv/bin/python -m pytest \
  tests/architectural/test_pack_manifest_no_author_edit.py \
  tests/architectural/test_pack_tier_token_single_authority.py \
  tests/architectural/test_pack_level_single_authority.py \
  tests/architectural/test_charter_kind_vocabulary_single_authority.py \
  tests/cross_cutting/packaging/test_packaging_safety.py -q

# Migration
.venv/bin/python -m pytest tests/upgrade/ -q

# Baseline fast tier
make test-fast

# Lint / format / types
ruff check . && uv run --frozen ruff format --check --force-exclude <changed files> && mypy --strict <changed modules>

# After editing packs/** — regenerate the built-in manifest (pack-manifest regen gate)
spec-kitty charter pack regenerate-graph
```

## Try the behaviour

```bash
# A built-in-shaped pack declaring org from an org position → refused by name
spec-kitty charter pack validate <path-to-mismatched-pack>   # PACK_LEVEL_MISMATCH

# Regenerate a vendored built-in copy outside core
spec-kitty charter pack regenerate-graph --pack-root /tmp/open-packs/built-in
spec-kitty charter pack regenerate-graph --pack-root /tmp/open-packs/built-in --check
```

## Landmarks

- Schema: `src/charter/offering/packs/pack_descriptor.py`
- Load/validate + resolution seam: `src/charter/offering/packs/pack_validator.py`
- Vocabulary authority: `src/kernel/pack_tiers.py`
- Provenance emitter: `src/charter/offering/base.py`
- CLI: `src/specify_cli/cli/commands/charter/pack_tooling.py`
- Migration: `src/specify_cli/upgrade/migrations/m_*_pack_level_backfill.py`
- In-repo descriptors: `packs/built-in/pack.yaml`, `packs/internal/pack.yaml`
- Diagram/README: `src/charter/diagrams/`, `src/charter/README.md`
