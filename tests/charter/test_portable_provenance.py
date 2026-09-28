"""Portable provenance integration tests (T016, C-PRV-1..6).

Exercises the normalizer at the charter catalog emit call sites and the
agent-profile projection manifest, plus the deliberately-excluded manifest
``output_path`` field, which must stay repo-relative (contract
``provenance-and-channel.md`` C-PRV-6 and issue #5253).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from charter.activation.compiler import CharterReference, CompiledCharter, compile_charter
from charter.activation.interview import default_interview

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ATOMIC_DESIGN_TOKEN = "${SPEC_KITTY_PACKS_ROOT}/built-in/paradigms/atomic-design.paradigm.yaml"


def _compile_default() -> CompiledCharter:
    interview = default_interview(mission="software-dev", profile="minimal")
    return compile_charter(mission="software-dev", interview=interview)


def _paradigm_reference(compiled: CompiledCharter, ref_id: str) -> CharterReference:
    match = [r for r in compiled.references if r.id == ref_id]
    assert match, f"expected reference {ref_id!r} in compiled catalog"
    return match[0]


class TestCatalogSourceBecomesToken:
    """C-PRV-1: fresh compile -> catalog source_path is a portable token."""

    def test_paradigm_source_path_is_token_not_absolute(self) -> None:
        compiled = _compile_default()
        ref = _paradigm_reference(compiled, "PARADIGM:atomic-design")

        assert ref.source_path == _ATOMIC_DESIGN_TOKEN
        assert not Path(ref.source_path).is_absolute()

    def test_token_never_leaks_the_local_checkout_path(self) -> None:
        compiled = _compile_default()
        ref = _paradigm_reference(compiled, "PARADIGM:atomic-design")

        assert str(_REPO_ROOT) not in ref.source_path
        assert "/home/" not in ref.source_path
        assert "C:\\" not in ref.source_path


class TestReBakeGate:
    """C-PRV-2: SPEC_KITTY_PACKS_ROOT set at emit time never leaks into the token."""

    def test_source_path_byte_identical_with_packs_root_exported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        baseline = _compile_default()
        baseline_ref = _paradigm_reference(baseline, "PARADIGM:atomic-design")

        # A real, resolvable override (the actual repo's packs/ dir) --
        # still must not change the STORED value, since the normalizer
        # composes a fixed token string and never interpolates the env
        # value it read to locate the built-in root.
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(_REPO_ROOT / "packs"))
        rebaked = _compile_default()
        rebaked_ref = _paradigm_reference(rebaked, "PARADIGM:atomic-design")

        assert rebaked_ref.source_path == baseline_ref.source_path == _ATOMIC_DESIGN_TOKEN


class TestMissionTemplateSourceBecomesToken:
    """Issue #5253: built-in template-set provenance is portable at emit time."""

    def test_mission_template_source_path_is_token_not_absolute(self) -> None:
        compiled = _compile_default()
        template_refs = [r for r in compiled.references if r.kind == "template_set"]

        assert template_refs, "expected a template_set reference in compiled catalog"
        source_path = template_refs[0].source_path
        assert source_path == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")
        assert str(_REPO_ROOT) not in source_path
        assert f"- Source: `{source_path}`" in template_refs[0].content

    def test_mission_template_source_path_is_stable_when_packs_root_is_exported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        baseline = _compile_default()
        baseline_ref = _paradigm_reference(baseline, "TEMPLATE_SET:software-dev-default")

        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(_REPO_ROOT / "packs"))
        rebaked = _compile_default()
        rebaked_ref = _paradigm_reference(rebaked, "TEMPLATE_SET:software-dev-default")

        assert rebaked_ref.source_path == baseline_ref.source_path
        assert rebaked_ref.source_path == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")


class TestExcludedCallersByteUnchanged:
    """The manifest output_path keeps its distinct repo-relative contract."""

    def test_manifest_output_path_stays_repo_relative(self, tmp_path: Path) -> None:
        """``manifest.py``'s ``output_path`` (``relativize_under_root``) is untouched."""
        from specify_cli.tool_surface.model import NativeAgentProfile
        from specify_cli.tool_surface.profiles.manifest import ProfileManifest

        project_root = tmp_path / "project"
        output_path = project_root / ".claude" / "agents" / "example.md"
        output_path.parent.mkdir(parents=True)
        output_path.write_text("# example\n", encoding="utf-8")

        # A built-in-pack SOURCE, deliberately, so this test also proves
        # output_path and source_path diverge in shape on the SAME entry:
        # source_path -> token, output_path -> repo-relative (never a token).
        source_path = _REPO_ROOT / "packs" / "built-in" / "agent_profiles" / "example.agent.yaml"

        manifest = ProfileManifest(project_root / ".kittify" / "agent_profiles_manifest.json")
        manifest.record(
            NativeAgentProfile(
                profile_urn="agent_profile:example",
                source_layer="builtin",
                tool_key="claude",
                output_path=output_path,
                format="markdown",
                file_hash="deadbeef",
                source_path=str(source_path),
                source_hash="cafef00d",
                projection_version=1,
            )
        )
        manifest.save()

        raw = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
        entry = raw["entries"][0]

        assert entry["output_path"] == ".claude/agents/example.md"
        assert not entry["output_path"].startswith("${SPEC_KITTY_PACKS_ROOT}")


class TestManifestSourcePathBecomesToken:
    """The manifest half of the normalizer's two routed call sites (T013)."""

    def test_manifest_source_path_is_token_for_built_in_profile(self, tmp_path: Path) -> None:
        from specify_cli.tool_surface.profiles.projection import _manifest_source_path

        source_path = _REPO_ROOT / "packs" / "built-in" / "agent_profiles" / "example.agent.yaml"

        result = _manifest_source_path(source_path, project_root=tmp_path)

        assert result == "${SPEC_KITTY_PACKS_ROOT}/built-in/agent_profiles/example.agent.yaml"

    def test_manifest_source_path_none_passthrough(self, tmp_path: Path) -> None:
        from specify_cli.tool_surface.profiles.projection import _manifest_source_path

        assert _manifest_source_path(None, project_root=tmp_path) is None

    def test_manifest_source_path_in_tree_stays_repo_relative(self, tmp_path: Path) -> None:
        from specify_cli.tool_surface.profiles.projection import _manifest_source_path

        project_root = tmp_path / "project"
        source_path = project_root / ".kittify" / "agent_profiles" / "custom.agent.yaml"
        source_path.parent.mkdir(parents=True)
        source_path.write_text("id: custom\n", encoding="utf-8")

        result = _manifest_source_path(source_path, project_root=project_root)

        assert result == ".kittify/agent_profiles/custom.agent.yaml"
