"""Activation tokens match a file name (stem) first, regardless of layer (#6459).

The index-level test ``test_lookup_is_stem_first_across_layers_then_declared_id``
pins one direction (a lower layer's stem beats a higher layer's declared id).
This module pins the other direction at the resolver: a project-layer file named
``DIRECTIVE_024`` that declares ``id: DIRECTIVE_901`` takes the token
``DIRECTIVE_024``, so the built-in directive that declares ``id: DIRECTIVE_024``
is not admitted. A positive control on the same fixture, without the project
file, shows the built-in directive is admitted by that token.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from charter.activation.active_charter_service_builder import build_active_charter_service
from charter.offering.artifact_kinds import PROJECT_KIND_DIRS, ArtifactKind
from charter.offering.pack_paths import built_in_dir
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_BUILT_IN_ID = "DIRECTIVE_024"
_PROJECT_ID = "DIRECTIVE_901"
_BUILT_IN_FILE = "024-locality-of-change.directive.yaml"


def _project(tmp_path: Path, *, with_project_file: bool) -> Path:
    """A git project activating the token ``DIRECTIVE_024``, optionally with a project file of that name."""
    root = tmp_path / "proj"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    if with_project_file:
        source = (built_in_dir(ArtifactKind.DIRECTIVE) / _BUILT_IN_FILE).read_text(encoding="utf-8")
        assert f"id: {_BUILT_IN_ID}" in source
        text = source.replace(f"id: {_BUILT_IN_ID}", f"id: {_PROJECT_ID}", 1)
        text = text.replace("title:", "title: Project stem-first probe -", 1)
        target = root / ".kittify" / "charter-packs" / PROJECT_KIND_DIRS[ArtifactKind.DIRECTIVE] / f"{_BUILT_IN_ID}.directive.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], activated_directives=[_BUILT_IN_ID])
    return root


def test_positive_control_token_admits_built_in_declared_id(tmp_path: Path) -> None:
    root = _project(tmp_path, with_project_file=False)

    assert sorted(build_active_charter_service(root).directives) == [_BUILT_IN_ID]


def test_project_file_name_beats_built_in_declared_id(tmp_path: Path) -> None:
    root = _project(tmp_path, with_project_file=True)

    assert sorted(build_active_charter_service(root).directives) == [_PROJECT_ID]
