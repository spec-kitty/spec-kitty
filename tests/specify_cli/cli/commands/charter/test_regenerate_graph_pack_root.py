"""FR-013 — ``charter pack regenerate-graph --pack-root <dir>``.

``--pack-root`` targets a pack outside core for BOTH the write path and
``--check``; omitting the flag resolves to the built-in pack root and leaves the
committed built-in source byte-unchanged.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.charter.pack_tooling import _built_in_pack_root, regenerate_graph


def _copy_built_in(dest: Path) -> Path:
    shutil.copytree(_built_in_pack_root(), dest)
    return dest


def test_pack_root_write_path_targets_the_given_root(tmp_path: Path) -> None:
    copy = _copy_built_in(tmp_path / "vendored")

    with pytest.raises(typer.Exit) as exc:
        regenerate_graph(check=False, pack_root=copy, json_output=False)
    assert exc.value.exit_code == 0

    assert (copy / "pack-manifest.yaml").is_file()
    assert sorted(copy.glob("*.graph.yaml"))


def test_pack_root_check_reports_freshness_for_the_given_root(tmp_path: Path) -> None:
    copy = _copy_built_in(tmp_path / "vendored")

    # A faithful copy of the committed built-in pack is fresh.
    with pytest.raises(typer.Exit) as exc:
        regenerate_graph(check=True, pack_root=copy, json_output=False)
    assert exc.value.exit_code == 0

    # Drift a committed fragment: --check must now report stale (exit 1).
    fragment = next(iter(sorted(copy.glob("*.graph.yaml"))))
    fragment.write_text(fragment.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    with pytest.raises(typer.Exit) as drifted:
        regenerate_graph(check=True, pack_root=copy, json_output=False)
    assert drifted.value.exit_code == 1


def test_default_no_flag_is_byte_unchanged() -> None:
    root = _built_in_pack_root()
    before = {p.name: p.read_bytes() for p in sorted(root.glob("*.graph.yaml"))}
    before["pack-manifest.yaml"] = (root / "pack-manifest.yaml").read_bytes()

    # --check never writes; the default resolves to the built-in root.
    with pytest.raises(typer.Exit) as exc:
        regenerate_graph(check=True, pack_root=None, json_output=False)
    assert exc.value.exit_code == 0

    after = {p.name: p.read_bytes() for p in sorted(root.glob("*.graph.yaml"))}
    after["pack-manifest.yaml"] = (root / "pack-manifest.yaml").read_bytes()
    assert after == before
