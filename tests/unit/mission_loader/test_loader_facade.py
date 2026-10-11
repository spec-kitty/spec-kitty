"""Loader facade tests (T012): precedence, shadow warning, reserved-key
exemption for the built-in tier, mission-pack manifest discovery (FR-002 /
FR-011 / R-002 / R-007).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from specify_cli.mission_loader import (
    LoaderErrorCode,
    LoaderWarningCode,
    validate_custom_mission,
)
from runtime.next._internal_runtime.discovery import DiscoveryContext

# A minimal valid custom mission body. Every step has a profile binding and
# the last step is the retrospective marker, so structural checks pass.

pytestmark = [pytest.mark.unit]

_VALID_BODY = """
mission:
  key: {key}
  name: {name}
  version: "1.0.0"
steps:
  - id: plan
    title: Plan
    agent_profile: planner
  - id: retrospective
    title: Retrospective
    agent_profile: retro
"""


def _isolated_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    explicit_paths: list[Path] | None = None,
    builtin_roots: list[Path] | None = None,
    project_dir: Path | None = None,
) -> DiscoveryContext:
    monkeypatch.delenv("SPEC_KITTY_MISSION_PATHS", raising=False)
    user_home = tmp_path / "fake-home"
    user_home.mkdir(exist_ok=True)
    return DiscoveryContext(
        project_dir=project_dir if project_dir is not None else tmp_path,
        explicit_paths=list(explicit_paths or []),
        user_home=user_home,
        builtin_roots=list(builtin_roots or []),
    )


def _write_mission(
    base: Path, layer: str, key: str, *, name: str | None = None
) -> Path:
    body = _VALID_BODY.format(key=key, name=name or key.replace("-", " ").title())
    mission_dir = base / layer / key
    mission_dir.mkdir(parents=True, exist_ok=True)
    file = mission_dir / "mission.yaml"
    file.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return file


# ---------------------------------------------------------------------------
# Precedence tests
# ---------------------------------------------------------------------------


def test_loads_from_kittify_missions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_mission(tmp_path, ".kittify/missions", "foo")
    ctx = _isolated_context(tmp_path, monkeypatch)
    report = validate_custom_mission("foo", ctx)
    assert report.ok, f"expected ok=True, errors={report.errors}"
    assert report.template is not None
    assert report.discovered is not None
    assert report.discovered.precedence_tier == "project_legacy"
    assert report.warnings == []


def test_loads_from_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_mission(tmp_path, ".kittify/overrides/missions", "foo")
    ctx = _isolated_context(tmp_path, monkeypatch)
    report = validate_custom_mission("foo", ctx)
    assert report.ok, f"expected ok=True, errors={report.errors}"
    assert report.discovered is not None
    assert report.discovered.precedence_tier == "project_override"


def test_explicit_paths_win_over_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    explicit_root = tmp_path / "explicit-root"
    env_root = tmp_path / "env-root"
    _write_mission(explicit_root, ".", "foo", name="From Explicit")
    _write_mission(env_root, ".", "foo", name="From Env")
    monkeypatch.setenv("SPEC_KITTY_MISSION_PATHS", str(env_root))

    ctx = DiscoveryContext(
        project_dir=tmp_path / "no-project-here",  # nothing under .kittify
        explicit_paths=[explicit_root],
        user_home=tmp_path / "fake-home",
        builtin_roots=[],
    )
    (tmp_path / "fake-home").mkdir(exist_ok=True)
    report = validate_custom_mission("foo", ctx)
    assert report.ok
    assert report.discovered is not None
    assert report.discovered.precedence_tier == "explicit"


def test_project_override_wins_over_legacy_with_shadow_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy_path = _write_mission(tmp_path, ".kittify/missions", "foo", name="Legacy")
    override_path = _write_mission(
        tmp_path, ".kittify/overrides/missions", "foo", name="Override"
    )
    ctx = _isolated_context(tmp_path, monkeypatch)
    report = validate_custom_mission("foo", ctx)
    assert report.ok
    assert report.discovered is not None
    assert report.discovered.precedence_tier == "project_override"
    # Exactly one shadow warning, pointing at the legacy path.
    shadow_warnings = [
        w for w in report.warnings if w.code is LoaderWarningCode.MISSION_KEY_SHADOWED
    ]
    assert len(shadow_warnings) == 1
    details = shadow_warnings[0].details
    assert details["mission_key"] == "foo"
    assert details["selected_tier"] == "project_override"
    assert str(override_path.resolve()) == details["selected_path"]
    assert any(
        str(legacy_path.resolve()) == p for p in details["shadowed_paths"]
    )


def test_user_global_lower_than_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    user_home = tmp_path / "user-home"
    user_home.mkdir()
    _write_mission(project_root, ".kittify/missions", "foo", name="Project")
    _write_mission(user_home, ".kittify/missions", "foo", name="UserGlobal")

    monkeypatch.delenv("SPEC_KITTY_MISSION_PATHS", raising=False)
    ctx = DiscoveryContext(
        project_dir=project_root,
        user_home=user_home,
        builtin_roots=[],
    )
    report = validate_custom_mission("foo", ctx)
    assert report.ok
    assert report.discovered is not None
    assert report.discovered.precedence_tier == "project_legacy"
    shadow_warnings = [
        w for w in report.warnings if w.code is LoaderWarningCode.MISSION_KEY_SHADOWED
    ]
    assert len(shadow_warnings) == 1
    assert shadow_warnings[0].details["selected_tier"] == "project_legacy"


# ---------------------------------------------------------------------------
# Mission-pack manifest discovery (R-007)
# ---------------------------------------------------------------------------


def test_loads_from_mission_pack_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.kittify/config.yaml` declares a mission pack containing 'foo'."""
    pack_root = tmp_path / "vendor-pack"
    pack_root.mkdir()
    # Mission YAML inside the pack.
    mission_dir = pack_root / "missions" / "foo"
    mission_dir.mkdir(parents=True)
    body = _VALID_BODY.format(key="foo", name="From Pack")
    (mission_dir / "mission.yaml").write_text(
        textwrap.dedent(body).lstrip(), encoding="utf-8"
    )
    # Pack manifest.
    (pack_root / "mission-pack.yaml").write_text(
        textwrap.dedent(
            """
            pack:
              name: vendor-pack
              version: "1.0.0"
            missions:
              - key: foo
                path: missions/foo/mission.yaml
            """
        ).lstrip(),
        encoding="utf-8",
    )
    # Project config points at the pack.
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text(
        textwrap.dedent(
            """
            mission_packs:
              - vendor-pack
            """
        ).lstrip(),
        encoding="utf-8",
    )

    ctx = _isolated_context(tmp_path, monkeypatch)
    report = validate_custom_mission("foo", ctx)
    assert report.ok, f"errors={report.errors}, warnings={report.warnings}"
    assert report.discovered is not None
    assert report.discovered.precedence_tier == "project_config"


# ---------------------------------------------------------------------------
# Reserved-key rejection vs. built-in exemption
# ---------------------------------------------------------------------------


def test_reserved_key_shadow_rejected_with_MISSION_KEY_RESERVED(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writing a 'software-dev' under .kittify/missions/ must reject."""
    _write_mission(tmp_path, ".kittify/missions", "software-dev", name="Custom")
    ctx = _isolated_context(tmp_path, monkeypatch)
    report = validate_custom_mission("software-dev", ctx)
    assert report.errors
    assert report.errors[0].code is LoaderErrorCode.MISSION_KEY_RESERVED
    assert report.template is None


def test_builtin_software_dev_not_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reserved key declared by the BUILT-IN tier must load OK."""
    builtin_root = tmp_path / "builtin-root"
    _write_mission(builtin_root, ".", "software-dev", name="Built-in software-dev")
    ctx = _isolated_context(
        tmp_path,
        monkeypatch,
        builtin_roots=[builtin_root],
        # project_dir=None so no .kittify scan can interfere
        project_dir=tmp_path / "empty-project",
    )
    report = validate_custom_mission("software-dev", ctx)
    assert report.ok, f"expected ok=True, errors={report.errors}"
    assert report.discovered is not None
    assert report.discovered.precedence_tier == "built-in"
