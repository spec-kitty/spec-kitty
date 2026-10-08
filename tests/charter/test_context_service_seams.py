"""T033 (WP06, #2532) — focused unit tests for the 5 service/profile-
resolution seams extracted from ``charter.activation.context``: ``context_json``,
``org_pack_discovery``, ``action_doctrine_bundle``, ``profile_resolution``,
and ``active_charter_service_builder``.

Each seam module is imported from its NEW home (not re-exported through
``charter.activation.context``) so these tests pin the seam itself, independent of the
FR-009 preserved-surface re-export — mirroring the WP04/WP05 precedent
(``tests/charter/test_context_leaf_seams.py`` /
``tests/charter/test_context_render_seams.py``). Also doubles as the
seam-existence manifest's real-consumer wiring for ``context_json``,
``action_doctrine_bundle``, and ``active_charter_service_builder`` — the 3 seams
whose only OTHER consumer is a lazy, function-local import from
``charter.activation.context`` itself (see ``tests/charter/test_context_decomposition_completion.py``).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.action_doctrine_bundle import (
    _ActionDoctrineBundle,
    _load_action_doctrine_bundle,
)
from charter.activation.context_json import (
    _EMPTY_ORG_CHARTER,
    _bundle_root_for_json,
    _load_project_directives,
    _local_directive_entry,
    _project_charter_json_block,
    _relative_json_path,
)
from charter.activation.active_charter_service_builder import _build_offering_service
from charter.activation.org_pack_discovery import (
    _enumerate_org_pack_paths,
    _load_doctrine_selection,
    _missing_pack_diagnostic,
    _read_org_required_selections,
)
from charter.activation.profile_resolution import (
    _existing_org_roots,
    _normalize_directive_id,
    _reset_agent_profile_cache,
)

pytestmark = [pytest.mark.fast, pytest.mark.unit]


# ---------------------------------------------------------------------------
# context_json.py
# ---------------------------------------------------------------------------


class TestRelativeJsonPath:
    def test_relative_path_is_posix_formatted(self, tmp_path: Path) -> None:
        root = tmp_path
        target = tmp_path / "sub" / "file.txt"
        assert _relative_json_path(target, root) == "sub/file.txt"

    def test_unrelated_path_falls_back_to_str(self, tmp_path: Path) -> None:
        other_root = tmp_path / "elsewhere"
        target = tmp_path / "sub" / "file.txt"
        assert _relative_json_path(target, other_root) == str(target)


class TestLocalDirectiveEntry:
    def test_carries_title_and_summary_when_present(self) -> None:
        local = type("Local", (), {"title": "My Title", "description": "My summary"})()
        entry = _local_directive_entry("DIRECTIVE_099", local)
        assert entry == {
            "id": "DIRECTIVE_099",
            "source": "project",
            "title": "My Title",
            "summary": "My summary",
        }

    def test_omits_blank_title_and_summary(self) -> None:
        local = type("Local", (), {"title": "", "description": None})()
        entry = _local_directive_entry("DIRECTIVE_099", local)
        assert entry == {"id": "DIRECTIVE_099", "source": "project"}


def test_empty_org_charter_shape() -> None:
    assert _EMPTY_ORG_CHARTER == {"present": False, "packs": []}


class TestBundleRootForJson:
    def test_falls_back_to_repo_root_when_sync_raises(self, tmp_path: Path) -> None:
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", side_effect=RuntimeError("boom")):
            assert _bundle_root_for_json(tmp_path) == tmp_path

    def test_uses_canonical_root_from_sync_result(self, tmp_path: Path) -> None:
        canonical = tmp_path / "canonical"
        canonical.mkdir()
        result = type("SyncResult", (), {"canonical_root": canonical})()
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=result):
            assert _bundle_root_for_json(tmp_path) == canonical


class TestProjectCharterJsonBlock:
    def test_absent_charter_reports_present_false(self, tmp_path: Path) -> None:
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=None):
            block = _project_charter_json_block(tmp_path)
        assert block["present"] is False
        assert "bytes" not in block


class TestLoadProjectDirectives:
    def test_raising_loader_falls_back_to_resolver_and_empty_local(self, tmp_path: Path) -> None:
        def _raise(_repo_root: Path) -> object:
            raise RuntimeError("no config")

        with patch(
            "charter.activation.resolver.resolve_project_governance",
            return_value=type("Res", (), {"directives": ["DIRECTIVE_001"]})(),
        ):
            local_by_id, directive_ids = _load_project_directives(tmp_path, _raise)
        assert local_by_id == {}
        assert directive_ids == ["DIRECTIVE_001"]


# ---------------------------------------------------------------------------
# org_pack_discovery.py
# ---------------------------------------------------------------------------


class TestEnumerateOrgPackPaths:
    def test_no_config_yields_empty_list(self, tmp_path: Path) -> None:
        assert _enumerate_org_pack_paths(tmp_path) == []


class TestMissingPackDiagnostic:
    def test_no_packs_configured_returns_none(self, tmp_path: Path) -> None:
        assert _missing_pack_diagnostic(tmp_path) is None


class TestReadOrgRequiredSelections:
    def test_no_packs_returns_empty_kind_map(self, tmp_path: Path) -> None:
        result = _read_org_required_selections(tmp_path)
        assert result["directives"] == []
        assert set(result) >= {"directives", "tactics", "agent_profiles"}


class TestLoadDoctrineSelection:
    def test_missing_governance_yields_default_selection(self, tmp_path: Path) -> None:
        selection = _load_doctrine_selection(tmp_path)
        assert selection.selected_directives == []


# ---------------------------------------------------------------------------
# action_doctrine_bundle.py
# ---------------------------------------------------------------------------


class TestActionDoctrineBundle:
    def test_optional_fields_default_empty(self) -> None:
        bundle = _ActionDoctrineBundle(
            mission="software-dev",
            directive_ids=[],
            tactic_ids=[],
            styleguide_ids=[],
            toolguide_ids=[],
            procedure_ids=[],
            asset_ids=[],
            service=object(),
        )
        assert bundle.merged is None
        assert bundle.roots == ()
        assert bundle.bridge_urns == ()


class TestLoadActionDoctrineBundleTypeless:
    def test_typeless_mission_degrades_to_empty_bundle(self, tmp_path: Path) -> None:
        """FR-003a: no mission_type and no feature_dir -> no DRG action node
        is resolved; the bundle is empty rather than defaulting to
        software-dev."""
        bundle = _load_action_doctrine_bundle(
            repo_root=tmp_path,
            action="implement",
            effective_depth=2,
            mission_type=None,
            feature_dir=None,
        )
        assert bundle.mission == ""
        assert bundle.directive_ids == []
        assert bundle.merged is None
        assert bundle.roots == ()


# ---------------------------------------------------------------------------
# profile_resolution.py
# ---------------------------------------------------------------------------


class TestNormalizeDirectiveId:
    def test_bare_numeral_normalises(self) -> None:
        assert _normalize_directive_id("10") == "DIRECTIVE_010"

    def test_slug_prefix_normalises(self) -> None:
        assert _normalize_directive_id("024-locality-of-change") == "DIRECTIVE_024"

    def test_canonical_form_passes_through(self) -> None:
        assert _normalize_directive_id("DIRECTIVE_024") == "DIRECTIVE_024"

    def test_non_numeric_uppercases_and_folds_hyphens(self) -> None:
        # Slug-named hub directives normalize to their UPPER_SNAKE node id, so the
        # fallback folds hyphens to underscores (#3009) -- matching id_normalizer.
        assert _normalize_directive_id("some-slug") == "SOME_SLUG"
        assert _normalize_directive_id("use-c4-model-techniques") == "USE_C4_MODEL_TECHNIQUES"


class TestExistingOrgRoots:
    def test_no_config_yields_empty_list(self, tmp_path: Path) -> None:
        assert _existing_org_roots(tmp_path) == []


def test_reset_agent_profile_cache_clears_both_stores() -> None:
    import charter.activation.profile_resolution as pr

    pr._ACTIVATION_AWARE_PROFILE_MAPS[Path("/some/repo")] = {}
    _reset_agent_profile_cache()
    assert pr._DEFAULT_AGENT_PROFILE_REPO is None
    assert pr._ACTIVATION_AWARE_PROFILE_MAPS == {}


# ---------------------------------------------------------------------------
# active_charter_service_builder.py
# ---------------------------------------------------------------------------


class TestBuildOfferingService:
    def test_org_roots_kwarg_omitted_when_empty(self, tmp_path: Path) -> None:
        calls: dict[str, object] = {}

        class _StubOfferingService:
            def __init__(self, **kwargs: object) -> None:
                calls.update(kwargs)

        built_in_root = tmp_path / "built-in"
        built_in_root.mkdir()
        with (
            patch("charter.activation.catalog.resolve_offering_root", return_value=built_in_root),
            patch("charter.offering.service.CharterOfferingService", _StubOfferingService),
            patch("charter.activation.context.infer_repo_languages", return_value=["python"]),
        ):
            _build_offering_service(tmp_path, org_roots=None)
        assert "org_roots" not in calls

    def test_org_roots_kwarg_threaded_when_present(self, tmp_path: Path) -> None:
        calls: dict[str, object] = {}

        class _StubOfferingService:
            def __init__(self, **kwargs: object) -> None:
                calls.update(kwargs)

        built_in_root = tmp_path / "built-in"
        built_in_root.mkdir()
        org_root = tmp_path / "org"
        with (
            patch("charter.activation.catalog.resolve_offering_root", return_value=built_in_root),
            patch("charter.offering.service.CharterOfferingService", _StubOfferingService),
            patch("charter.activation.context.infer_repo_languages", return_value=["python"]),
        ):
            _build_offering_service(tmp_path, org_roots=[org_root])
        assert calls["org_roots"] == [org_root]
