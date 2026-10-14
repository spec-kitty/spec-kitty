"""The ledger-projection posture reader (``core/ledger_posture.py``).

Exercises the real, file-based ``ledger_posture`` reader: it gates only the
local ``.kittify/derived/`` execution-state projection and defaults to enabled
(fail-open to ``True``) on an absent key, a missing file, or an unparseable
value. Split out of the former ``core/hosted_posture.py`` when the hosted drain
surface was removed from open-core (#6164).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.ledger_posture import ledger_posture

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _repo(tmp_path: Path, *, yaml_text: str | None = None) -> Path:
    """A tmp-path repo with a ``.kittify/`` marker and an optional config.yaml."""
    root = tmp_path / "repo"
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    if yaml_text is not None:
        (kittify / "config.yaml").write_text(yaml_text, encoding="utf-8")
    return root


class TestLedgerPosture:
    def test_default_true_when_key_absent(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        posture = ledger_posture(project_root=repo)
        assert posture.enabled is True

    def test_false_when_projection_is_false(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text="ledger:\n  projection: false\n")
        posture = ledger_posture(project_root=repo)
        assert posture.enabled is False

    def test_default_true_with_a_warning_when_non_boolean(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text='ledger:\n  projection: "nope"\n')
        with pytest.warns(UserWarning, match=r"ledger\.projection is not a boolean"):
            posture = ledger_posture(project_root=repo)
        assert posture.enabled is True

    def test_default_true_when_config_file_missing(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)  # .kittify/ exists but config.yaml itself does not
        posture = ledger_posture(project_root=repo)
        assert posture.enabled is True

    def test_malformed_yaml_defaults_true_with_one_warning(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        (repo / ".kittify" / "config.yaml").write_text("ledger: [unterminated\n", encoding="utf-8")
        with pytest.warns(UserWarning, match="could not parse YAML") as caught:
            posture = ledger_posture(project_root=repo)
        assert posture.enabled is True
        assert len(caught) == 1

    def test_non_mapping_top_level_yaml_defaults_true(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text="- a\n- list\n")
        posture = ledger_posture(project_root=repo)
        assert posture.enabled is True


class TestNoResolvableRoot:
    def test_ledger_posture_with_no_resolvable_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.core.ledger_posture.locate_project_root", lambda: None)
        posture = ledger_posture()
        assert posture.enabled is True
        assert posture.source == "no repository root resolved"
