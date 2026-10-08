"""Tests for specify_cli.core.wps_manifest.

Covers WorkPackageEntry field validation (id, dependencies, plan_concern_refs,
cross_cutting), WpsManifest parsing, load_wps_manifest(), generate_tasks_md_from_manifest(),
and check_concern_refs_coverage().

T010 — plan_concern_refs field (TestPlanConcernRefs)
T011 — cross_cutting field and rendering (TestCrossCuttingField, TestGenerateTasksMdConcernRefs)
T016 — check_concern_refs_coverage() warning logic (TestCheckConcernRefsCoverage)
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from specify_cli.core.wps_manifest import (
    WorkPackageEntry,
    WpsManifest,
    check_concern_refs_coverage,
    generate_tasks_md_from_manifest,
    load_wps_manifest,
)

# ---------------------------------------------------------------------------
# Marker
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ===========================================================================
# T010 — plan_concern_refs field
# ===========================================================================


class TestPlanConcernRefs:
    """Unit tests for WorkPackageEntry.plan_concern_refs (T010)."""

    def test_valid_single_ref(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="t", plan_concern_refs=["IC-01"])
        assert entry.plan_concern_refs == ["IC-01"]

    def test_valid_multiple_refs(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="t", plan_concern_refs=["IC-01", "IC-23"])
        assert entry.plan_concern_refs == ["IC-01", "IC-23"]

    def test_empty_default(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="t")
        assert entry.plan_concern_refs == []

    def test_invalid_no_leading_zero(self) -> None:
        """IC-1 must be rejected — two digits required."""
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="t", plan_concern_refs=["IC-1"])

    def test_invalid_wrong_prefix(self) -> None:
        """WP01 is not an IC-## ref."""
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="t", plan_concern_refs=["WP01"])

    def test_invalid_lowercase_prefix(self) -> None:
        """ic-01 must be rejected — prefix must be uppercase IC."""
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="t", plan_concern_refs=["ic-01"])

    def test_invalid_three_digit_suffix(self) -> None:
        """IC-001 must be rejected — exactly two digits required."""
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="t", plan_concern_refs=["IC-001"])

    def test_invalid_non_ascii_digits(self) -> None:
        """Non-ASCII unicode digit must be rejected (re.ASCII enforced)."""
        # U+0661 is ARABIC-INDIC DIGIT ONE — looks like '1' but not ASCII.
        with pytest.raises(ValidationError):
            WorkPackageEntry(id="WP01", title="t", plan_concern_refs=["IC-١1"])

    def test_backwards_compat_missing_key(self) -> None:
        """A wps.yaml dict without plan_concern_refs must parse without error."""
        raw = {"work_packages": [{"id": "WP01", "title": "t"}]}
        manifest = WpsManifest.model_validate(raw)
        assert manifest.work_packages[0].plan_concern_refs == []

    def test_load_wps_manifest_with_concern_refs(self, tmp_path: object) -> None:
        """Write a wps.yaml with plan_concern_refs and load it via load_wps_manifest."""
        from pathlib import Path

        feature_dir = Path(str(tmp_path))
        wps_yaml = feature_dir / "wps.yaml"
        wps_yaml.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: Test WP\n"
            "    plan_concern_refs:\n"
            "      - IC-01\n"
            "      - IC-02\n"
        )
        manifest = load_wps_manifest(feature_dir)
        assert manifest is not None
        assert manifest.work_packages[0].plan_concern_refs == ["IC-01", "IC-02"]

    def test_load_wps_manifest_concern_refs_absent_gives_empty_list(
        self, tmp_path: object
    ) -> None:
        """Older wps.yaml without plan_concern_refs key loads with empty list."""
        from pathlib import Path

        feature_dir = Path(str(tmp_path))
        wps_yaml = feature_dir / "wps.yaml"
        wps_yaml.write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: Old WP\n"
        )
        manifest = load_wps_manifest(feature_dir)
        assert manifest is not None
        assert manifest.work_packages[0].plan_concern_refs == []


# ===========================================================================
# T011 — cross_cutting field and rendering
# ===========================================================================


class TestCrossCuttingField:
    """Unit tests for WorkPackageEntry.cross_cutting (T011)."""

    def test_default_false(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="t")
        assert entry.cross_cutting is False

    def test_explicit_true(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="t", cross_cutting=True)
        assert entry.cross_cutting is True

    def test_explicit_false(self) -> None:
        entry = WorkPackageEntry(id="WP01", title="t", cross_cutting=False)
        assert entry.cross_cutting is False

    def test_backwards_compat_missing_key(self) -> None:
        """A dict without cross_cutting must default to False."""
        raw = {"work_packages": [{"id": "WP01", "title": "t"}]}
        manifest = WpsManifest.model_validate(raw)
        assert manifest.work_packages[0].cross_cutting is False

    def test_load_wps_manifest_cross_cutting_true(self, tmp_path: object) -> None:
        """wps.yaml with cross_cutting: true loads correctly."""
        from pathlib import Path

        feature_dir = Path(str(tmp_path))
        (feature_dir / "wps.yaml").write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: Setup harness\n"
            "    cross_cutting: true\n"
        )
        manifest = load_wps_manifest(feature_dir)
        assert manifest is not None
        assert manifest.work_packages[0].cross_cutting is True


class TestGenerateTasksMdConcernRefs:
    """Tests for plan_concern_refs rendering inside generate_tasks_md_from_manifest (T011)."""

    def test_renders_concern_refs_when_present(self) -> None:
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="Test",
                    plan_concern_refs=["IC-01", "IC-03"],
                )
            ]
        )
        output = generate_tasks_md_from_manifest(manifest, "test-mission")
        assert "IC-01" in output
        assert "IC-03" in output
        assert "Plan Concerns" in output

    def test_does_not_render_when_empty(self) -> None:
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(id="WP01", title="Test")
            ]
        )
        output = generate_tasks_md_from_manifest(manifest, "test-mission")
        assert "Plan Concerns" not in output
        assert "IC-" not in output

    def test_renders_for_some_not_all_wps(self) -> None:
        """IC-01 appears once (WP01 only), not for WP02 which has no refs."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="Has refs",
                    plan_concern_refs=["IC-01"],
                ),
                WorkPackageEntry(id="WP02", title="No refs"),
            ]
        )
        output = generate_tasks_md_from_manifest(manifest, "test-mission")
        assert output.count("IC-01") == 1

    def test_renders_concern_refs_label_format(self) -> None:
        """The rendered line should start with **Plan Concerns**."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="Test",
                    plan_concern_refs=["IC-02"],
                )
            ]
        )
        output = generate_tasks_md_from_manifest(manifest, "my-mission")
        assert "**Plan Concerns**: IC-02" in output

    def test_many_to_many_edge_case(self) -> None:
        """Multiple WPs may share the same IC-## ref — each renders independently."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01", title="A", plan_concern_refs=["IC-01", "IC-02"]
                ),
                WorkPackageEntry(
                    id="WP02", title="B", plan_concern_refs=["IC-01", "IC-03"]
                ),
            ]
        )
        output = generate_tasks_md_from_manifest(manifest, "shared-refs-mission")
        # IC-01 appears in both WP01 and WP02 sections
        assert output.count("IC-01") == 2
        assert output.count("IC-02") == 1
        assert output.count("IC-03") == 1


# ===========================================================================
# T016 — check_concern_refs_coverage() warning logic
# ===========================================================================


class TestCheckConcernRefsCoverage:
    """Unit tests for check_concern_refs_coverage() (T016)."""

    def test_no_warnings_when_all_wps_have_refs(self) -> None:
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01", title="Has refs", plan_concern_refs=["IC-01"]
                ),
                WorkPackageEntry(
                    id="WP02", title="Also has refs", plan_concern_refs=["IC-02"]
                ),
            ]
        )
        assert check_concern_refs_coverage(manifest) == []

    def test_no_warnings_for_cross_cutting_wp(self) -> None:
        """A cross-cutting WP with no IC-## refs must NOT produce a warning."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(id="WP01", title="Infra", cross_cutting=True),
            ]
        )
        assert check_concern_refs_coverage(manifest) == []

    def test_warning_when_wp_missing_both(self) -> None:
        """WP with no plan_concern_refs and cross_cutting=False triggers a warning."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(id="WP01", title="Uncovered"),
            ]
        )
        warnings = check_concern_refs_coverage(manifest)
        assert len(warnings) == 1
        assert "WP01" in warnings[0]

    def test_warning_references_remedy(self) -> None:
        """The warning message guides the author toward a fix."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(id="WP01", title="No refs"),
            ]
        )
        warning = check_concern_refs_coverage(manifest)[0]
        # Should mention both remedies
        assert "plan_concern_refs" in warning or "IC-##" in warning
        assert "cross_cutting" in warning

    def test_warning_per_uncovered_wp(self) -> None:
        """One warning is emitted per uncovered WP."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(id="WP01", title="A"),
                WorkPackageEntry(id="WP02", title="B", plan_concern_refs=["IC-01"]),
                WorkPackageEntry(id="WP03", title="C"),
            ]
        )
        warnings = check_concern_refs_coverage(manifest)
        assert len(warnings) == 2
        wp_ids = [w.split()[0] for w in warnings]
        assert "WP01" in wp_ids
        assert "WP03" in wp_ids

    def test_mixed_coverage_no_false_positives(self) -> None:
        """WPs that satisfy either criterion do not appear in warnings."""
        manifest = WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01", title="Has refs", plan_concern_refs=["IC-01"]
                ),
                WorkPackageEntry(id="WP02", title="Cross cutting", cross_cutting=True),
                WorkPackageEntry(id="WP03", title="Missing"),
            ]
        )
        warnings = check_concern_refs_coverage(manifest)
        assert len(warnings) == 1
        assert "WP03" in warnings[0]

    def test_empty_manifest_no_warnings(self) -> None:
        """An empty WP list returns no warnings (not an error)."""
        manifest = WpsManifest(work_packages=[])
        assert check_concern_refs_coverage(manifest) == []

    def test_legacy_loaded_manifest_without_new_fields_has_no_warnings(
        self, tmp_path: object
    ) -> None:
        """FR-010: older wps.yaml files without concern keys stay quiet."""
        from pathlib import Path

        feature_dir = Path(str(tmp_path))
        (feature_dir / "wps.yaml").write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: Legacy WP\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(feature_dir)
        assert manifest is not None
        assert check_concern_refs_coverage(manifest) == []

    def test_loaded_manifest_without_new_fields_warns_when_plan_has_ics(
        self, tmp_path: Path
    ) -> None:
        """New IC-bearing plans require wps.yaml concern coverage."""
        (tmp_path / "plan.md").write_text(
            "# Implementation Plan\n\n"
            "## Implementation Concern Map\n\n"
            "### IC-01 - Runtime boundary\n\n"
            "- **Purpose**: Keep runtime and CLI behavior aligned.\n",
            encoding="utf-8",
        )
        (tmp_path / "wps.yaml").write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: New WP missing concern refs\n",
            encoding="utf-8",
        )

        manifest = load_wps_manifest(tmp_path)

        assert manifest is not None
        warnings = check_concern_refs_coverage(manifest)
        assert len(warnings) == 1
        assert "WP01" in warnings[0]

    def test_loaded_manifest_with_explicit_empty_refs_is_quiet_without_plan_ics(
        self, tmp_path: object
    ) -> None:
        """Empty concern refs are fine when plan.md declares no concerns."""
        from pathlib import Path

        feature_dir = Path(str(tmp_path))
        (feature_dir / "wps.yaml").write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: New WP\n"
            "    plan_concern_refs: []\n",
            encoding="utf-8",
        )
        manifest = load_wps_manifest(feature_dir)
        assert manifest is not None
        assert check_concern_refs_coverage(manifest) == []

    def test_loaded_manifest_with_explicit_empty_refs_warns_when_plan_has_ics(
        self, tmp_path: Path
    ) -> None:
        """Empty refs still warn when plan.md declares implementation concerns."""
        (tmp_path / "plan.md").write_text("### IC-01 - Runtime boundary\n", encoding="utf-8")
        (tmp_path / "wps.yaml").write_text(
            "work_packages:\n"
            "  - id: WP01\n"
            "    title: New WP\n"
            "    plan_concern_refs: []\n",
            encoding="utf-8",
        )

        manifest = load_wps_manifest(tmp_path)

        assert manifest is not None
        warnings = check_concern_refs_coverage(manifest)
        assert len(warnings) == 1
        assert "WP01" in warnings[0]

    def test_wps_schema_accepts_plan_concern_fields(self) -> None:
        """The documented JSON schema accepts the Pydantic manifest fields."""
        schema = json.loads(
            Path("src/specify_cli/schemas/wps.schema.json").read_text(encoding="utf-8")
        )
        instance = {
            "work_packages": [
                {
                    "id": "WP01",
                    "title": "Concern-aware WP",
                    "plan_concern_refs": ["IC-01"],
                    "cross_cutting": False,
                },
                {
                    "id": "WP02",
                    "title": "Shared harness",
                    "plan_concern_refs": [],
                    "cross_cutting": True,
                },
            ]
        }

        jsonschema.Draft202012Validator(schema).validate(instance)
