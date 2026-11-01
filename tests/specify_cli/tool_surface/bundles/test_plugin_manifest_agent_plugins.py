"""Agent Plugins 1.0.0 conformance for the shared plugin manifest payload.

Issue #6479: the Copilot/VS Code projection emitted ``version: 0.0.0``, a
``distribution_target`` key the Agent Plugins schema does not define, no
``$schema`` at all, and a description that read as a staging artefact. Those
manifests are never read as the portable format.

The pinned external requirements live in
``spec-kitty-internal-plugins#2`` §2.2 (Agent Plugins ``plugin.json`` is a closed
schema over ``$schema``, ``name``, ``version``, ``description``, ``author``,
``homepage``, ``repository``, ``license``, ``keywords`` and ``extensions``).
They are asserted here through the production projectors.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from specify_cli.tool_surface.bundles._builder import to_semver
from specify_cli.tool_surface.bundles.copilot import CopilotBundleProjector
from specify_cli.tool_surface.bundles.vscode import VsCodeBundleProjector

from ._support import full_plans

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: The pinned Agent Plugins 1.0.0 manifest schema const (clients never fetch it).
AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"

#: The closed key set the pinned schema defines. An extra key is a rejection.
AGENT_PLUGINS_KEYS = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)

_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?$")


def _project(projector: type, tmp_path: Path) -> dict[str, object]:
    """Project a full bundle through the production entry point and read its manifest."""
    project = tmp_path / "proj"
    out = tmp_path / "dist"
    projector().project(full_plans(project), project, out)
    return json.loads((out / "plugin.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("projector", "label"),
    [(CopilotBundleProjector, "copilot"), (VsCodeBundleProjector, "vscode")],
)
def test_manifest_declares_the_pinned_agent_plugins_schema(tmp_path: Path, projector: type, label: str) -> None:
    """The root manifest must select the portable format by its schema const."""
    payload = _project(projector, tmp_path)

    # Positive control on the same fixture: the probe sees a key that must exist,
    # so the schema assertion below cannot pass because the manifest is empty.
    assert payload["name"] == "spec-kitty", label
    assert payload["$schema"] == AGENT_PLUGINS_SCHEMA, label


@pytest.mark.parametrize(
    ("projector", "label"),
    [(CopilotBundleProjector, "copilot"), (VsCodeBundleProjector, "vscode")],
)
def test_manifest_carries_only_schema_defined_keys(tmp_path: Path, projector: type, label: str) -> None:
    """The pinned schema is closed; an undeclared key is a directory rejection."""
    payload = _project(projector, tmp_path)
    assert payload, label
    unknown = set(payload) - AGENT_PLUGINS_KEYS
    assert not unknown, f"{label} manifest carries keys the schema does not define: {sorted(unknown)}"
    assert "distribution_target" not in payload, label


@pytest.mark.parametrize(
    ("projector", "label"),
    [(CopilotBundleProjector, "copilot"), (VsCodeBundleProjector, "vscode")],
)
def test_manifest_identity_and_links(tmp_path: Path, projector: type, label: str) -> None:
    """Identity plus the links a directory needs to resolve the plugin."""
    payload = _project(projector, tmp_path)

    version = payload["version"]
    assert isinstance(version, str) and _SEMVER.match(version), f"{label} version {version!r} is not SemVer"
    assert version != "0.0.0", f"{label} manifest still carries the placeholder version"

    description = payload["description"]
    assert isinstance(description, str)
    assert "staging" not in description.lower(), f"{label} description still reads as a staging artefact"

    author = payload["author"]
    assert isinstance(author, dict) and author.get("name") == "Spec Kitty", label

    assert payload["homepage"] == "https://spec-kitty.ai/", label
    assert payload["repository"] == "https://github.com/spec-kitty/spec-kitty", label
    assert payload["license"] == "MIT", label


# ---------------------------------------------------------------------------
# PEP 440 -> SemVer projection (one authority for every target)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pep440", "expected"),
    [
        ("4.0.0", "4.0.0"),
        ("4.0.0rc8", "4.0.0-rc8"),
        ("4.0.0.rc8", "4.0.0-rc8"),
        ("4.0.0a1", "4.0.0-a1"),
        ("4.0.0b2", "4.0.0-b2"),
        ("4.0.0.dev1", "4.0.0-dev1"),
        ("4.0.0.post1", "4.0.0-post1"),
        ("4.0.0+dev", "4.0.0+dev"),
        ("4.0.0rc8.dev3", "4.0.0-rc8.dev3"),
    ],
)
def test_to_semver_projects_pep440(pep440: str, expected: str) -> None:
    assert to_semver(pep440) == expected


def test_to_semver_never_raises_on_an_unparseable_version() -> None:
    """A build must not fail because a local install reports an odd version."""
    assert to_semver("not-a-version") == "not-a-version"


def test_to_semver_is_idempotent() -> None:
    """A already-SemVer string passes through the projection unchanged."""
    assert to_semver("4.0.0-rc8") == "4.0.0-rc8"
