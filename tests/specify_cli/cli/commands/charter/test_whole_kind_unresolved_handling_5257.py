"""Operator-facing handling of the whole-kind fail-closed compile error (#5257).

``compile_charter`` refuses to build a catalog when every activated reference of
one tracked kind is unresolvable. Three CLI surfaces reach it and each must
translate it, not crash with a traceback:

- ``charter activate`` / ``charter deactivate`` recompile opportunistically
  AFTER the config write succeeded -> a yellow "Catalog not recompiled" notice,
  exit 0, nothing written to the catalog;
- ``charter pack apply --compile`` was explicitly asked to compile -> a clean
  error and exit 1.

The ghost-node fixtures are shared with the ``charter generate`` CLI tests,
which pin the third surface (fail closed, exit 1).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests.specify_cli.cli.commands.charter.test_activate_recompile_4785 import (
    _REAL_DIRECTIVE_STEM,
    _write_config,
    _write_established_catalog,
)
from tests.specify_cli.cli.commands.test_charter_generate_autotrack import _git_init
from tests.specify_cli.cli.commands.test_charter_generate_drg_transitive_missing_cli import (
    _write_project_drg_overlay,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_GHOST_ID = "ghost-drg-transitive-01M3M1KF"
_SECOND_DIRECTIVE_STEM = "003-decision-documentation-requirement"
_PARADIGM = "domain-driven-design"


def _project_with_unresolvable_toolguide(project_root: Path, *directives: str) -> Path:
    """Established catalog + a DRG overlay whose only toolguide has no artifact.

    *directives* is the explicit ``activated_directives`` set; only
    ``_REAL_DIRECTIVE_STEM`` (whose closure holds no real toolguide) may remain
    after the command under test, or a real toolguide keeps the kind resolvable.
    """
    _git_init(project_root)
    # EXPLICIT directive set: activating into an absent one would first expand
    # it to every effective built-in.
    listed = "".join(f"- {stem}\n" for stem in directives)
    # ``activated_tactics: []`` keeps the built-in packs from seeding tactics
    # (their closures reach real toolguides) -- ``apply`` never overwrites a
    # key already present without ``--force``.
    kittify = _write_config(project_root, f"activated_directives:\n{listed}activated_tactics: []\n")
    _write_established_catalog(kittify)
    _write_project_drg_overlay(project_root, kind="toolguide", ghost_id=_GHOST_ID)
    return kittify / "charter" / "charter.yaml"


def _activated_key(project_root: Path, key: str) -> list[str]:
    loaded = YAML(typ="safe").load((project_root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    return list(loaded.get(key, []))


def test_activate_keeps_config_write_and_prints_notice_when_whole_kind_unresolved(tmp_path: Path) -> None:
    catalog_path = _project_with_unresolvable_toolguide(tmp_path, _REAL_DIRECTIVE_STEM)
    catalog_before = catalog_path.read_bytes()

    result = runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(tmp_path), "paradigm", _PARADIGM],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "not recompiled" in result.output.lower(), result.output
    assert "toolguide" in result.output, "the notice must name the kind that could not be resolved"
    assert _GHOST_ID in result.output
    assert _PARADIGM in _activated_key(tmp_path, "activated_paradigms"), "the config write already succeeded and must be kept"
    assert catalog_path.read_bytes() == catalog_before, "a failed recompile must not touch the catalog"


def test_deactivate_prints_notice_when_whole_kind_unresolved(tmp_path: Path) -> None:
    catalog_path = _project_with_unresolvable_toolguide(tmp_path, _REAL_DIRECTIVE_STEM, _SECOND_DIRECTIVE_STEM)
    catalog_before = catalog_path.read_bytes()

    result = runner.invoke(
        charter_app,
        ["deactivate", "--repo-root", str(tmp_path), "directive", _SECOND_DIRECTIVE_STEM],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "not recompiled" in result.output.lower(), result.output
    assert "toolguide" in result.output
    assert _SECOND_DIRECTIVE_STEM not in _activated_key(tmp_path, "activated_directives")
    assert catalog_path.read_bytes() == catalog_before


def test_pack_apply_compile_exits_cleanly_when_whole_kind_unresolved(tmp_path: Path) -> None:
    _project_with_unresolvable_toolguide(tmp_path, _REAL_DIRECTIVE_STEM)

    result = runner.invoke(
        charter_app,
        ["pack", "apply", "minimal", "--repo-root", str(tmp_path), "--compile"],
        catch_exceptions=True,
    )

    assert result.exit_code == 1, result.output
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, RuntimeError), "the error must be translated, not escape as a raw RuntimeError"
    assert isinstance(result.exception, SystemExit), result.exception
    assert "toolguide" in result.output
    assert _GHOST_ID in result.output


def test_pack_apply_compile_json_error_carries_the_unresolved_records(tmp_path: Path) -> None:
    _project_with_unresolvable_toolguide(tmp_path, _REAL_DIRECTIVE_STEM)

    result = runner.invoke(
        charter_app,
        ["pack", "apply", "minimal", "--repo-root", str(tmp_path), "--compile", "--json"],
        catch_exceptions=True,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert "toolguide" in payload["error"]
    assert any(entry["kind"] == "toolguide" and entry["id"] == _GHOST_ID for entry in payload["unresolved_references"])
