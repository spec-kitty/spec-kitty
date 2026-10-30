"""``charter org validate`` must refuse a fragment ``body_path`` that escapes its pack (#6733).

``doctor charter-packs`` exits 1 for an authored ``drg/fragment.yaml`` node whose ``body_path``
escapes its pack root (#6418, ``ORG_FRAGMENT_BODY_PATH_ESCAPE``). The pack validator — the surface
an author runs *before* sharing a pack — already reported the asset-sidecar half
(``asset_path_escape``) and silently accepted the fragment half, so the author's own gate was the
weakest one.

RED before this fix: the ``body_path_escape`` category did not exist, ``validate_pack`` returned no
finding for the escaping node, and ``charter org validate`` exited 0 on that fault. The contained,
empty and discovered-node cases are the positive controls: they must stay clean, so a leg that
flagged every node cannot satisfy this module.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from charter.offering.packs.pack_validator import validate_pack
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ESCAPING = "../../../../etc/hostname"
_NODE_ID = "team-asset"
_ASSET_ID = "team-logo"

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures — the canonical scaffolding command builds the pack, one node is added
# ---------------------------------------------------------------------------


def _scaffold_pack(tmp_path: Path) -> Path:
    """A canonically scaffolded org pack (``charter org init``), so nothing is hand-built."""
    pack_dir = tmp_path / "org-pack"
    init_result = runner.invoke(charter_app, ["org", "init", str(pack_dir)])
    assert init_result.exit_code == 0, init_result.output
    return pack_dir


def _fragment(pack_dir: Path) -> Path:
    return pack_dir / "drg" / "fragment.yaml"


def _add_node(pack_dir: Path, **node: str) -> None:
    """Append one authored node to the pack's fragment (``id``/``kind``/``title`` plus extras)."""
    fragment = _fragment(pack_dir)
    data = yaml.safe_load(fragment.read_text(encoding="utf-8"))
    data["nodes"] = [*(data.get("nodes") or []), {"id": _NODE_ID, "kind": "assets", "title": "Team asset", **node}]
    fragment.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _add_escaping_sidecar(pack_dir: Path, path: str) -> None:
    assets = pack_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / f"{_ASSET_ID}.asset.yaml").write_text(yaml.safe_dump({"id": _ASSET_ID, "mime": "text/plain", "path": path}), encoding="utf-8")


def _categories(result: object) -> set[str | None]:
    return {issue.category for issue in result.errors}  # type: ignore[attr-defined]


def _body_path_issues(result: object) -> list[object]:
    return [issue for issue in result.errors if issue.category == "body_path_escape"]  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# validate_pack: the structured finding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("body_path", [_ESCAPING, "/etc/hostname"], ids=["dot-dot", "absolute"])
def test_validate_pack_reports_an_escaping_body_path(tmp_path: Path, body_path: str) -> None:
    """One structured ``body_path_escape`` error per escaping authored node (#6733, FR-004).

    RED before the fix: no such category and no such finding; the asset leg reported only its own.
    """
    pack_dir = _scaffold_pack(tmp_path)
    _add_node(pack_dir, body_path=body_path)

    result = validate_pack(pack_dir)

    issues = _body_path_issues(result)
    assert len(issues) == 1, [issue.to_dict() for issue in result.errors]
    issue = issues[0]
    assert issue.severity == "error"
    assert issue.artifact_type == "drg"
    assert issue.artifact_id == _NODE_ID
    assert issue.file.endswith("drg/fragment.yaml"), issue.file
    assert _NODE_ID in issue.message and body_path in issue.message
    assert "is not contained in the pack root" in issue.message
    assert result.ok is False


def test_validate_pack_reports_nothing_for_a_contained_body_path(tmp_path: Path) -> None:
    """The positive control: a contained ``body_path`` is not a finding (#6733, FR-006).

    The target file is deliberately absent — containment, not existence, is the rule (#6418).
    """
    pack_dir = _scaffold_pack(tmp_path)
    _add_node(pack_dir, body_path="bodies/team-asset.md")

    result = validate_pack(pack_dir)

    assert _body_path_issues(result) == [], [issue.to_dict() for issue in result.errors]


def test_node_without_a_body_path_is_not_judged(tmp_path: Path) -> None:
    """Nothing declared, nothing judged — the predicate's own contract, pinned through the leg."""
    pack_dir = _scaffold_pack(tmp_path)
    _add_node(pack_dir)

    result = validate_pack(pack_dir)

    assert _body_path_issues(result) == [], [issue.to_dict() for issue in result.errors]


def test_a_discovered_artifact_body_path_is_not_judged_here(tmp_path: Path) -> None:
    """A discovered node's ``body_path`` belongs to its own kind's validator (#6418's rule).

    ``find_body_path_escapes`` judges ``authored_nodes`` only; this guards the wiring against a leg
    that re-validated a copy and lost the discovered/authored distinction.
    """
    pack_dir = _scaffold_pack(tmp_path)
    directives = pack_dir / "directives"
    directives.mkdir(exist_ok=True)
    (directives / "team-rule.directive.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "id": "TEAM_RULE",
                "title": "Team rule",
                "intent": "A rule.",
                "enforcement": "advisory",
                "body_path": _ESCAPING,
            }
        ),
        encoding="utf-8",
    )

    result = validate_pack(pack_dir)

    # Guard the premise: the discovered node really carries the escaping string, and the pack
    # really loaded (so "no finding" means "not judged here", not "nothing ran").
    assert _fragment(pack_dir).exists()
    assert _ESCAPING in (directives / "team-rule.directive.yaml").read_text(encoding="utf-8")
    assert _body_path_issues(result) == [], [issue.to_dict() for issue in result.errors]


def test_both_containment_findings_are_reported_together(tmp_path: Path) -> None:
    """Neither half hides the other (#6733, FR-004 acceptance 3)."""
    pack_dir = _scaffold_pack(tmp_path)
    _add_node(pack_dir, body_path=_ESCAPING)
    _add_escaping_sidecar(pack_dir, _ESCAPING)

    result = validate_pack(pack_dir)

    assert {"body_path_escape", "asset_path_escape"} <= _categories(result), [issue.to_dict() for issue in result.errors]


# ---------------------------------------------------------------------------
# The CLI: the author's own gate
# ---------------------------------------------------------------------------


def test_org_validate_cli_exits_non_zero_for_an_escaping_body_path(tmp_path: Path) -> None:
    """``charter org validate`` refuses the pack and names the node (#6733, FR-004 acceptance 1).

    RED before the fix: exit 0 and no mention of the escaping path.
    """
    pack_dir = _scaffold_pack(tmp_path)
    _add_node(pack_dir, body_path=_ESCAPING)

    result = runner.invoke(charter_app, ["org", "validate", str(pack_dir)])

    assert result.exit_code != 0, result.output
    assert _NODE_ID in result.output
    assert _ESCAPING in result.output
    assert "body_path_escape" in result.output


def test_org_validate_cli_accepts_a_contained_body_path(tmp_path: Path) -> None:
    """The CLI stays green for a sound pack (positive control on the same scaffolding path)."""
    pack_dir = _scaffold_pack(tmp_path)
    _add_node(pack_dir, body_path="bodies/team-asset.md")

    result = runner.invoke(charter_app, ["org", "validate", str(pack_dir)])

    assert result.exit_code == 0, result.output
    assert "body_path_escape" not in result.output


def test_org_validate_cli_reports_both_findings(tmp_path: Path) -> None:
    """Both categories appear in one run (#6733, FR-004 acceptance 3)."""
    pack_dir = _scaffold_pack(tmp_path)
    _add_node(pack_dir, body_path=_ESCAPING)
    _add_escaping_sidecar(pack_dir, _ESCAPING)

    result = runner.invoke(charter_app, ["org", "validate", str(pack_dir)])

    assert result.exit_code != 0, result.output
    assert "body_path_escape" in result.output
    assert "asset_path_escape" in result.output
