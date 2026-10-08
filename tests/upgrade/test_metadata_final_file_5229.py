"""#5229 -- the final ``.kittify/metadata.yaml`` after ``spec-kitty upgrade``.

Real-git reproduction through the pre-existing entry point (``python -m specify_cli
upgrade --yes`` in a hermetic sandbox, see ``_legacy_upgrade_fixture``). Every writer
that touches the file during an upgrade used to rebuild it from a fixed dict or stamp
only part of it, so the operator ended up without ``project_uuid``, without the
canonical capability map and without their own keys.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specify_cli.migration.schema_version import CURRENT_SCHEMA_CAPABILITIES, CURRENT_SCHEMA_VERSION
from tests.upgrade._legacy_upgrade_fixture import build_legacy, flat, git, run_upgrade

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_LEGACY_ID = "3.0.0_canonical_context"
_OPERATOR_COMMENT = "# operator: do not remove this team note"


def _legacy_metadata(**extra_spec_kitty: object) -> dict[str, object]:
    block: dict[str, object] = {"version": "2.1.0", "initialized_at": "2026-01-01T00:00:00", "custom_flag": True}
    block.update(extra_spec_kitty)
    return {"spec_kitty": block, "operator_note": "keep-me"}


def _write_metadata(project: Path, text: str) -> None:
    (project / ".kittify" / "metadata.yaml").write_text(text, encoding="utf-8")


def _final(project: Path) -> dict[str, object]:
    data = yaml.safe_load((project / ".kittify" / "metadata.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _upgrade_ok(project: Path, env: dict[str, str]) -> None:
    result = run_upgrade(project, env)
    assert result.returncode == 0, flat(result.stdout + result.stderr)


def _applied(data: dict[str, object]) -> dict[str, str]:
    migrations = data["migrations"]
    assert isinstance(migrations, dict)
    return {m["id"]: m["result"] for m in migrations["applied"]}


def _committed_legacy(tmp_path: Path, text: str) -> tuple[Path, dict[str, str]]:
    project, env = build_legacy(tmp_path, agents=["claude"], gitignore=".kittify/workspaces/\n")
    _write_metadata(project, text)
    git(project, env, "add", "--", ".kittify/metadata.yaml")
    git(project, env, "commit", "-q", "-m", "operator metadata")
    return project, env


def test_final_metadata_after_legacy_upgrade_is_canonical_and_keeps_operator_keys(tmp_path: Path) -> None:
    project, env = _committed_legacy(tmp_path, yaml.dump(_legacy_metadata()))

    _upgrade_ok(project, env)

    data = _final(project)
    spec_kitty = data["spec_kitty"]
    assert isinstance(spec_kitty, dict)
    # The legacy migration really ran (a red below is about the final file, not the fixture).
    assert _applied(data).get(_LEGACY_ID) == "success"
    assert spec_kitty["schema_version"] == CURRENT_SCHEMA_VERSION
    assert isinstance(spec_kitty["schema_capabilities"], dict), spec_kitty.get("schema_capabilities")
    assert dict(spec_kitty["schema_capabilities"]) == CURRENT_SCHEMA_CAPABILITIES
    assert isinstance(spec_kitty["project_uuid"], str) and spec_kitty["project_uuid"]
    assert data["operator_note"] == "keep-me"
    assert spec_kitty["custom_flag"] is True


def test_second_upgrade_keeps_the_project_uuid_and_the_file_bytes(tmp_path: Path) -> None:
    project, env = _committed_legacy(tmp_path, yaml.dump(_legacy_metadata()))
    _upgrade_ok(project, env)
    first_bytes = (project / ".kittify" / "metadata.yaml").read_bytes()
    first_uuid = _final(project)["spec_kitty"]["project_uuid"]  # type: ignore[index]

    _upgrade_ok(project, env)

    assert (project / ".kittify" / "metadata.yaml").read_bytes() == first_bytes
    assert _final(project)["spec_kitty"]["project_uuid"] == first_uuid  # type: ignore[index]


def test_already_canonical_project_keeps_its_operator_edited_capability_map(tmp_path: Path) -> None:
    """A project that already carries the canonical map (fresh ``init``) used to lose it, and the operator's edits, on its next upgrade."""
    project, env = _committed_legacy(tmp_path, yaml.dump(_legacy_metadata()))
    _upgrade_ok(project, env)  # settle the project (mission state, charter) so the next run is only about metadata
    flipped = next(iter(CURRENT_SCHEMA_CAPABILITIES))
    caps = {**CURRENT_SCHEMA_CAPABILITIES, flipped: False, "my_cap": True}
    data = _final(project)
    block = data["spec_kitty"]
    assert isinstance(block, dict)
    block.update(version="4.0.0rc4", schema_version=CURRENT_SCHEMA_VERSION, schema_capabilities=caps)
    data["migrations"] = {"applied": []}  # make the later migrations applicable again
    _write_metadata(project, yaml.dump(data, sort_keys=False))
    git(project, env, "commit", "-q", "-m", "fresh-init shaped metadata", "--", ".kittify/metadata.yaml")

    _upgrade_ok(project, env)

    final = _final(project)
    spec_kitty = final["spec_kitty"]
    assert isinstance(spec_kitty, dict)
    assert spec_kitty["version"] != "4.0.0rc4", "the upgrade must have run its save()"
    assert spec_kitty["schema_capabilities"] == caps
    assert final["operator_note"] == "keep-me"


def test_dirty_metadata_with_operator_key_and_comment_keeps_the_key(tmp_path: Path) -> None:
    """A dirty ``metadata.yaml`` is held (not committed) and then warned about -- its content must not be lost.

    The operator key survives. The comment is NOT asserted: ``metadata.yaml`` is a
    machine-written file (header ``DO NOT EDIT MANUALLY``) rewritten through PyYAML, and
    FR-011 promises keys, not comments.
    """
    project, env = _committed_legacy(tmp_path, yaml.dump(_legacy_metadata()))
    dirty = _OPERATOR_COMMENT + "\n" + yaml.dump(_legacy_metadata()) + "dirty_operator_key: added-after-commit\n"
    _write_metadata(project, dirty)

    _upgrade_ok(project, env)

    data = _final(project)
    assert data["dirty_operator_key"] == "added-after-commit"
    assert data["operator_note"] == "keep-me"
    spec_kitty = data["spec_kitty"]
    assert isinstance(spec_kitty, dict)
    assert spec_kitty["schema_version"] == CURRENT_SCHEMA_VERSION
