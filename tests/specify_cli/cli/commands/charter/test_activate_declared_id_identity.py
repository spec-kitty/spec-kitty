"""``charter activate`` / ``deactivate`` by declared id and the allow list's identity (#6423, ruling R3).

Ledger-seeded.
A declared id (``DIRECTIVE_024``, an org ``EVD_003``) is normalised to its stem
before the availability check; an allow list never holds two spellings of one
artifact; deactivating by stem also removes a declared-id spelling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_A = "001-architectural-integrity-standard"
_STEM = "024-locality-of-change"
_DECLARED = "DIRECTIVE_024"
_EVD_STEM = "evd-003-evidence-trail"
_EVD_DECLARED = "EVD_003"


def _project(root: Path, *, org: bool = False, **ledger: list[str]) -> Path:
    config = "{}\n"
    if org:
        pack = root / "org-packs" / "evd"
        (pack / "directives").mkdir(parents=True)
        (pack / "org-charter.yaml").write_text("schema_version: 1\n", encoding="utf-8")
        (pack / "directives" / f"{_EVD_STEM}.directive.yaml").write_text(
            f'schema_version: "1.0"\nid: {_EVD_DECLARED}\ntitle: Evidence trail\nintent: Keep an evidence trail.\nenforcement: required\n',
            encoding="utf-8",
        )
        config = "charter_packs:\n  org:\n    packs:\n      - name: evd\n        local_path: org-packs/evd\n"
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(config, encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _charter(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, [args[0], "--repo-root", str(root), "--no-compile", *args[1:]])


def test_activating_a_builtin_declared_id_writes_its_stem(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_directives=[_A])

    result = _charter(root, "activate", "directive", _DECLARED)

    assert result.exit_code == 0, result.output
    assert read_activation_ledger(root)["activated_directives"] == [_A, _STEM]


def test_activating_an_org_declared_id_writes_its_stem(tmp_path: Path) -> None:
    root = _project(tmp_path, org=True, activated_directives=[_A])

    result = _charter(root, "activate", "directive", _EVD_DECLARED)

    assert result.exit_code == 0, result.output
    assert read_activation_ledger(root)["activated_directives"] == [_A, _EVD_STEM]


def test_activating_by_stem_collapses_a_declared_spelling(tmp_path: Path) -> None:
    root = _project(tmp_path, org=True, activated_directives=[_EVD_DECLARED, _A, _DECLARED])

    result = _charter(root, "activate", "directive", _EVD_STEM)

    assert result.exit_code == 0, result.output
    assert read_activation_ledger(root)["activated_directives"] == [_EVD_STEM, _A, _STEM]


def test_deactivating_by_stem_removes_a_declared_spelling(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_directives=[_A, _DECLARED])

    result = _charter(root, "deactivate", "directive", _STEM)

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert ledger["activated_directives"] == [_A]
    assert ledger["deactivated_directives"] == [_STEM]
    listed = _RUNNER.invoke(charter_app, ["list", "--json", "--repo-root", str(root)])
    row = next(row for row in json.loads(listed.output)["kinds"] if row["kind"] == "directive")
    assert _DECLARED not in row["activated"] and _STEM not in row["activated"]


def test_known_stems_build_no_identity_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation import identity_index
    from charter.activation.pack_manager import _identity_normalised
    from charter.offering.artifact_kinds import ArtifactKind

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the identity index must not be built for known stems (NFR-003)")

    monkeypatch.setattr(identity_index.IdentityIndex, "build", boom)
    data = {"activated_directives": [_A]}

    assert _identity_normalised(tmp_path, ArtifactKind.DIRECTIVE, _STEM, "activated_directives", data, frozenset({_A, _STEM})) == _STEM
    assert data == {"activated_directives": [_A]}
