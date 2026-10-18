"""Per-PR built-in drift gate (#3504, FR-008 / FR-010 / SC-001).

CI (``.github/workflows/packs.yml``, job ``built-in-vendor-check``) runs
``spec-kitty charter pack vendor --check``. These tests drive that SAME command, through the real
CLI app, against a copy of the committed ``packs/built-in/`` tree and ``packs/built-in.source.yaml``
pin. They never inspect the workflow text: a vacuous YAML grep would stay green while the gate rotted.

The drifting-tree case is the red/green evidence (non-zero + remedy); the unedited copy is the
positive control proving the harness can pass, which keeps the drift assertion non-vacuous.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.cli.commands.charter import pack_vendor as pack_vendor_module

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_runner = CliRunner()


def _run_gate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Copy the committed tree + pin into ``tmp_path`` and point the command's seam at the copy."""
    packs = tmp_path / "packs"
    live = packs / "built-in"
    shutil.copytree(_REPO_ROOT / "packs" / "built-in", live)
    shutil.copy2(_REPO_ROOT / "packs" / "built-in.source.yaml", packs / "built-in.source.yaml")
    # The app bootstrap needs the real packs root (missions/), so redirect only this command's seam.
    monkeypatch.setattr(pack_vendor_module, "built_in_root", lambda: live)
    return live


def _invoke_check() -> tuple[int, str]:
    result = _runner.invoke(cli_app, ["charter", "pack", "vendor", "--check"])
    if result.exception and not isinstance(result.exception, SystemExit):
        raise result.exception
    return result.exit_code, re.sub(r"\s+", " ", result.output)


def test_committed_tree_matches_pin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Positive control: the unedited committed tree passes the gate."""
    _run_gate(monkeypatch, tmp_path)

    code, out = _invoke_check()

    assert code == 0, out


def test_one_byte_hand_edit_reds_the_gate_with_remedy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A one-byte edit under packs/built-in/ fails the gate and names the FR-010 remedy."""
    live = _run_gate(monkeypatch, tmp_path)
    target = next(p for p in sorted(live.rglob("*.yaml")) if p.name != "pack.yaml")
    target.write_text(target.read_text(encoding="utf-8") + "#", encoding="utf-8")

    code, out = _invoke_check()

    assert code != 0, out
    assert "charter pack vendor" in out
    assert "bump the pin" in out
    assert "do not hand-edit" in out
