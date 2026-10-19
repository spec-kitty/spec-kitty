"""T033 (WP06, #2532) — focused unit tests for the 5 service/profile-
resolution seams extracted from ``charter.activation.context``: ``context_json``,
``org_pack_discovery``, ``action_governance_bundle``, ``profile_resolution``,
and ``active_charter_service_builder``.

Each seam module is imported from its NEW home (not re-exported through
``charter.activation.context``) so these tests pin the seam itself, independent of the
FR-009 preserved-surface re-export — mirroring the WP04/WP05 precedent
(``tests/charter/test_context_leaf_seams.py`` /
``tests/charter/test_context_render_seams.py``). Also doubles as the
seam-existence manifest's real-consumer wiring for ``context_json``,
``action_governance_bundle``, and ``active_charter_service_builder`` — the 3 seams
whose only OTHER consumer is a lazy, function-local import from
``charter.activation.context`` itself (see ``tests/charter/test_context_decomposition_completion.py``).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from charter.activation.action_governance_bundle import (
    _load_action_governance_bundle,
)
from charter.activation.context_json import (
    _bundle_root_for_json,
    _load_project_directives,
    _local_directive_entry,
    _relative_json_path,
)
from charter.activation.active_charter_service_builder import _build_offering_service
from charter.activation.org_pack_discovery import (
    _enumerate_org_pack_paths,
    _load_governance_charter_config,
    _missing_pack_diagnostic,
    _read_org_required_selections,
)
from charter.offering.drg.migration.id_normalizer import normalize_directive_id
from charter.activation.profile_resolution import (
    _existing_org_roots,
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


class TestBundleRootForJson:
    def test_uses_canonical_root_from_sync_result(self, tmp_path: Path) -> None:
        canonical = tmp_path / "canonical"
        canonical.mkdir()
        result = type("SyncResult", (), {"canonical_root": canonical})()
        with patch("charter.activation.sync.ensure_charter_bundle_fresh", return_value=result):
            assert _bundle_root_for_json(tmp_path) == canonical


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


def test_org_discovery_and_profile_roots_are_empty_without_config(tmp_path: Path) -> None:
    assert _enumerate_org_pack_paths(tmp_path) == []
    assert _missing_pack_diagnostic(tmp_path) is None
    result = _read_org_required_selections(tmp_path)
    assert result["directives"] == []
    assert set(result) >= {"directives", "tactics", "agent_profiles"}
    assert _load_governance_charter_config(tmp_path).selected_directives == []
    assert _existing_org_roots(tmp_path) == []


# ---------------------------------------------------------------------------
# action_governance_bundle.py
# ---------------------------------------------------------------------------


class TestLoadActionGovernanceBundleTypeless:
    def test_typeless_mission_degrades_to_empty_bundle(self, tmp_path: Path) -> None:
        """FR-003a: no mission_type and no feature_dir -> no DRG action node
        is resolved; the bundle is empty rather than defaulting to
        software-dev."""
        bundle = _load_action_governance_bundle(
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


def test_normalize_directive_id_single_normaliser() -> None:
    """The single normaliser (``charter.offering.drg.migration.id_normalizer``)."""
    assert normalize_directive_id("10") == "DIRECTIVE_010"
    assert normalize_directive_id("024-locality-of-change") == "DIRECTIVE_024"
    assert normalize_directive_id("DIRECTIVE_024") == "DIRECTIVE_024"
    # Slug-named hub directives normalize to their UPPER_SNAKE node id, so the
    # fallback folds hyphens to underscores (#3009) -- matching id_normalizer.
    assert normalize_directive_id("some-slug") == "SOME_SLUG"
    assert normalize_directive_id("use-c4-model-techniques") == "USE_C4_MODEL_TECHNIQUES"


# ---------------------------------------------------------------------------
# active_charter_service_builder.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("org_roots_given", [False, True])
def test_build_offering_service_threads_org_roots_only_when_present(tmp_path: Path, org_roots_given: bool) -> None:
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
        _build_offering_service(tmp_path, org_roots=[org_root] if org_roots_given else None)
    if org_roots_given:
        assert calls["org_roots"] == [org_root]
    else:
        assert "org_roots" not in calls
