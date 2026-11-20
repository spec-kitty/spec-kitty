"""Per-mission-type path conventions and the narrow waivers at the accept seam (#7748, #7566).

Mission path-conventions-per-type-01M7VRQM, WP02. Drives the single caller of
``validate_mission_paths`` -- ``summary_core.evaluate_path_conventions`` -- with the
real packaged missions and an on-disk fixture shaped like spec-kitty-open-packs: a
content repository with ``packs/`` and ``docs/`` and no ``src/``. Precedence per key
is the Mission type's section, then the flat value, then the mission default
(contracts/precedence-contract.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import specify_cli
from specify_cli.acceptance import summary_core
from specify_cli.acceptance.summary_core import evaluate_path_conventions
from specify_cli.config.path_conventions import ProjectPathConventions
from specify_cli.mission import Mission

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PACKAGED_MISSIONS_DIR = Path(specify_cli.__file__).resolve().parent / "missions"

_OPEN_PACKS_CONFIG = """\
project:
  path_conventions:
    software-dev:
      workspace: packs/
      tests: packs/
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _open_packs_repo(tmp_path: Path, config: str = _OPEN_PACKS_CONFIG) -> Path:
    """A content repository: ``packs/``, ``docs/`` and ``scripts/``, no ``src/``, ``tests/`` or ``research/``."""
    repo_root = tmp_path / "open-packs"
    for directory in ("packs", "docs", "scripts"):
        (repo_root / directory).mkdir(parents=True)
    _write(repo_root / ".kittify" / "config.yaml", config)
    return repo_root


def _mission_dir(repo_root: Path, mission_type: str, meta_extra: dict[str, object] | None = None) -> Path:
    feature_dir = repo_root / "kitty-specs" / f"{mission_type}-mission-01M7VRQM"
    meta: dict[str, object] = {"mission_type": mission_type, **(meta_extra or {})}
    _write(feature_dir / "meta.json", json.dumps(meta) + "\n")
    return feature_dir


def _evaluate(
    repo_root: Path,
    mission_type: str,
    *,
    strict: bool = True,
    meta_extra: dict[str, object] | None = None,
    reason: str | None = None,
) -> tuple[list[str], str | None, frozenset[str]]:
    feature_dir = _mission_dir(repo_root, mission_type, meta_extra)
    mission = Mission(_PACKAGED_MISSIONS_DIR / mission_type)
    return evaluate_path_conventions(
        mission,
        repo_root,
        feature_dir,
        feature_dir,
        strict_metadata=strict,
        path_conventions_waiver_reason=reason,
    )


_NO_CONTRACTS = {"contracts": "none", "contracts_rationale": "content repository; no interfaces"}


def test_software_dev_accepts_through_its_per_type_section(tmp_path: Path) -> None:
    """SC-001: the software-dev Mission is checked against ``packs/`` and passes strictly."""
    violations, _warning, _tokens = _evaluate(_open_packs_repo(tmp_path), "software-dev", meta_extra=_NO_CONTRACTS)
    assert violations == []


def test_documentation_keeps_its_default_beside_a_software_dev_section(tmp_path: Path) -> None:
    """SC-001: documentation still checks ``docs/`` (present), so it passes ..."""
    violations, _warning, _tokens = _evaluate(_open_packs_repo(tmp_path), "documentation")
    assert violations == []


def test_documentation_is_not_remapped_by_another_types_section(tmp_path: Path) -> None:
    """... and with ``docs/`` absent it names ``docs/``, never the software-dev ``packs/``."""
    repo_root = _open_packs_repo(tmp_path)
    (repo_root / "docs").rmdir()
    violations, _warning, _tokens = _evaluate(repo_root, "documentation")
    assert len(violations) == 1
    assert "workspace path: docs/" in violations[0]
    assert "packs/" not in violations[0].split("If this project")[0]


def test_research_keeps_its_default_beside_a_software_dev_section(tmp_path: Path) -> None:
    """SC-001: research still expects its own ``research/`` (under its deliverables prefix)."""
    violations, _warning, _tokens = _evaluate(_open_packs_repo(tmp_path), "research")
    assert len(violations) == 1
    head = violations[0].split("If this project")[0]
    assert "research/" in head
    assert "packs/" not in head


def test_per_type_value_beats_flat_for_its_type_only(tmp_path: Path) -> None:
    config = "project:\n  path_conventions:\n    workspace: apps/\n    software-dev:\n      workspace: packs/\n"
    repo_root = _open_packs_repo(tmp_path, config)
    (repo_root / "tests").mkdir()
    software_dev, _w, _t = _evaluate(repo_root, "software-dev", meta_extra=_NO_CONTRACTS)
    assert software_dev == []  # packs/ exists; flat apps/ does not
    documentation, _w, _t = _evaluate(repo_root, "documentation")
    assert len(documentation) == 1
    assert "workspace path: apps/" in documentation[0]


def test_per_type_remap_to_a_missing_directory_still_blocks(tmp_path: Path) -> None:
    """Non-fakeable (#3783 / SC-006 of the original override): the remap changes the checked directory only."""
    config = "project:\n  path_conventions:\n    software-dev:\n      workspace: content/\n"
    violations, _w, _t = _evaluate(_open_packs_repo(tmp_path, config), "software-dev", meta_extra=_NO_CONTRACTS)
    assert len(violations) == 1
    assert "workspace path: content/" in violations[0]


def test_meta_json_waiver_makes_path_misses_advisory(tmp_path: Path) -> None:
    repo_root = _open_packs_repo(tmp_path, "project:\n  slug: open-packs\n")
    meta = {**_NO_CONTRACTS, "path_conventions": "waived", "path_conventions_rationale": "content repository"}
    violations, warning, _t = _evaluate(repo_root, "software-dev", meta_extra=meta)
    assert violations == []
    assert warning is not None
    assert "workspace path: src/" in warning
    assert "path conventions waived by meta.json (path_conventions: waived): content repository" in warning


def test_malformed_meta_json_waiver_waives_nothing_and_warns(tmp_path: Path) -> None:
    repo_root = _open_packs_repo(tmp_path, "project:\n  slug: open-packs\n")
    meta = {**_NO_CONTRACTS, "path_conventions": "waived"}
    violations, _warning, _t = _evaluate(repo_root, "software-dev", meta_extra=meta)
    assert len(violations) == 1
    assert "'path_conventions_rationale'" in violations[0]


def test_per_run_reason_makes_path_misses_advisory(tmp_path: Path) -> None:
    repo_root = _open_packs_repo(tmp_path, "project:\n  slug: open-packs\n")
    violations, warning, _t = _evaluate(repo_root, "software-dev", meta_extra=_NO_CONTRACTS, reason="layout migration")
    assert violations == []
    assert warning is not None
    assert "path conventions waived for this run (--waive-path-conventions): layout migration" in warning


def test_blank_per_run_reason_waives_nothing(tmp_path: Path) -> None:
    repo_root = _open_packs_repo(tmp_path, "project:\n  slug: open-packs\n")
    violations, _w, _t = _evaluate(repo_root, "software-dev", meta_extra=_NO_CONTRACTS, reason="   ")
    assert len(violations) == 1


def test_config_is_read_once_per_evaluation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001."""
    calls: list[Path] = []
    real = summary_core.load_project_path_conventions

    def _spy(repo_root: Path) -> ProjectPathConventions:
        calls.append(repo_root)
        return real(repo_root)

    monkeypatch.setattr(summary_core, "load_project_path_conventions", _spy)
    repo_root = _open_packs_repo(tmp_path)
    _evaluate(repo_root, "software-dev", meta_extra=_NO_CONTRACTS)
    assert calls == [repo_root]
