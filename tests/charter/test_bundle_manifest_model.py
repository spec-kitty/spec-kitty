"""Tests for CharterBundleManifest v2.0.0.

Pins the v2.0.0 manifest contract (``kitty-specs/consolidate-charter-bundle-
01KXSYB9/contracts/manifest-v2.md``). Regressions here indicate scope creep
or a change in the tracked/derived/content-hash invariants.

⚠ Landmine 1 (data-model.md): ``charter.yaml`` is tracked-not-derived. The
``_validate`` disjointness rule (``tracked ∩ derived = ∅``) is UNCHANGED —
these tests prove that invariant still holds under the v2 shape, not that
it was relaxed.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from charter.bundle import (
    ACTIVATION_YAML,
    BUNDLE_CONTENT_HASH_FILES,
    CANONICAL_MANIFEST,
    CHARTER_MD,
    CHARTER_YAML,
    CharterBundleManifest,
    SCHEMA_VERSION,
)


pytestmark = [pytest.mark.unit]


def test_schema_version_is_2_0_0() -> None:
    assert SCHEMA_VERSION == "2.0.0"
    assert CANONICAL_MANIFEST.schema_version == "2.0.0"


def test_bundle_content_hash_files_is_charter_yaml_only() -> None:
    assert BUNDLE_CONTENT_HASH_FILES == ("charter.yaml",)


def test_canonical_manifest_tracked_files_include_charter_md_and_charter_yaml() -> None:
    assert CANONICAL_MANIFEST.tracked_files == [CHARTER_MD, CHARTER_YAML]


def test_canonical_manifest_derived_files_is_empty() -> None:
    """M1/Landmine 1: nothing in the charter bundle is generated-and-
    gitignored anymore — charter.yaml is tracked/authored."""
    assert CANONICAL_MANIFEST.derived_files == []
    assert CANONICAL_MANIFEST.derivation_sources == {}


def test_charter_yaml_is_not_in_derived_files() -> None:
    """Landmine 1 pin: charter.yaml must appear ONLY in tracked_files."""
    assert CHARTER_YAML in CANONICAL_MANIFEST.tracked_files
    assert CHARTER_YAML not in CANONICAL_MANIFEST.derived_files


def test_content_hash_files_is_distinct_field_set_to_charter_yaml() -> None:
    """M1: content_hash_files is a field DISTINCT from derived_files."""
    assert CANONICAL_MANIFEST.content_hash_files == [CHARTER_YAML]
    # Distinctness: content_hash_files is non-empty while derived_files is
    # empty — proves they are not the same field under two names.
    assert CANONICAL_MANIFEST.content_hash_files != CANONICAL_MANIFEST.derived_files


def test_gitignore_required_entries_is_empty() -> None:
    """The four legacy bundle files are retired; charter.yaml is tracked,
    so nothing needs a .gitignore entry anymore."""
    assert CANONICAL_MANIFEST.gitignore_required_entries == []


def test_validator_rejects_overlap() -> None:
    """M2: the tracked ∩ derived = ∅ invariant is untouched."""
    with pytest.raises(ValidationError):
        CharterBundleManifest(
            schema_version="2.0.0",
            tracked_files=[Path("a")],
            derived_files=[Path("a")],
            derivation_sources={},
            content_hash_files=[],
            gitignore_required_entries=[],
        )


def test_validator_rejects_charter_yaml_in_both_tracked_and_derived() -> None:
    """Concrete regression pin: charter.yaml specifically triggers the
    disjointness rule if a future edit mistakenly double-lists it."""
    with pytest.raises(ValidationError):
        CharterBundleManifest(
            schema_version="2.0.0",
            tracked_files=[CHARTER_YAML],
            derived_files=[CHARTER_YAML],
            derivation_sources={},
            content_hash_files=[CHARTER_YAML],
            gitignore_required_entries=[],
        )


def test_validator_rejects_orphan_derivation_source() -> None:
    with pytest.raises(ValidationError):
        CharterBundleManifest(
            schema_version="2.0.0",
            tracked_files=[Path("src.md")],
            derived_files=[Path("out.yaml")],
            derivation_sources={Path("out.yaml"): Path("missing.md")},
            content_hash_files=[],
            gitignore_required_entries=[],
        )


def test_schema_version_regex_enforced() -> None:
    with pytest.raises(ValidationError):
        CharterBundleManifest(
            schema_version="not-semver",
            tracked_files=[Path("a.md")],
            derived_files=[],
            derivation_sources={},
            content_hash_files=[],
            gitignore_required_entries=[],
        )


def test_content_hash_files_accepts_arbitrary_paths_independent_of_tracked() -> None:
    """content_hash_files is not constrained to be a subset of tracked_files
    by the model — it is the independent content-hash input set (M1)."""
    manifest = CharterBundleManifest(
        schema_version="2.0.0",
        tracked_files=[Path("a.md")],
        derived_files=[],
        derivation_sources={},
        content_hash_files=[Path("a.md")],
        gitignore_required_entries=[],
    )
    assert manifest.content_hash_files == [Path("a.md")]


# ---------------------------------------------------------------------------
# persistent-deactivation-ledger WP09 (FR-018, data-model.md §10): the ledger is
# an OPTIONAL tracked member, so ``tracked_files`` (required presence) is unchanged.
# ---------------------------------------------------------------------------


def test_canonical_manifest_lists_the_ledger_as_optional_tracked() -> None:
    assert CANONICAL_MANIFEST.optional_tracked_files == [ACTIVATION_YAML]
    assert ACTIVATION_YAML not in CANONICAL_MANIFEST.tracked_files
    assert ACTIVATION_YAML not in CANONICAL_MANIFEST.derived_files


def test_optional_tracked_files_defaults_to_empty() -> None:
    manifest = CharterBundleManifest(
        schema_version="2.0.0",
        tracked_files=[Path("a.md")],
        derived_files=[],
        derivation_sources={},
        gitignore_required_entries=[],
    )
    assert manifest.optional_tracked_files == []


@pytest.mark.parametrize("field", ["tracked_files", "derived_files"])
def test_validator_rejects_optional_overlap(field: str) -> None:
    lists: dict[str, list[Path]] = {"tracked_files": [Path("a.md")], "derived_files": []}
    lists[field] = [*lists[field], Path("opt.yaml")]
    with pytest.raises(ValidationError, match="optional"):
        CharterBundleManifest(
            schema_version="2.0.0",
            derivation_sources={},
            optional_tracked_files=[Path("opt.yaml")],
            gitignore_required_entries=[],
            **lists,
        )
