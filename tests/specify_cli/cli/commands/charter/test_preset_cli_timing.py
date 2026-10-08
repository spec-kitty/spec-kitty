"""NFR-003: ``charter activate --preset`` and ``charter pack list`` within 1.5x ``charter list`` (#3732 WP08).

Same fixture shape and measurement as the acceptance check
(``tests/acceptance/charter_pack_cutover``): the built-in pack plus two org
packs, the whole ``spec-kitty`` app invoked in-process with ``CliRunner`` (what
an operator runs, root callback included), median of 5 runs each. Run
serially: ``pytest -m timing -n0``.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli import app

pytestmark = [pytest.mark.timing]

runner = CliRunner()
_RUNS = 5
_BUDGET = 1.5


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _org_pack(root: Path, name: str) -> None:
    pack = root / "org-packs" / name
    _write(
        pack / "directives" / f"{name}-gate.directive.yaml",
        f'schema_version: "1.0"\nid: {name.upper()}-GATE\ntitle: gate\nintent: Org policy.\nenforcement: required\n',
    )
    _write(
        pack / "tactics" / f"{name}-pairing.tactic.yaml",
        f'schema_version: "1.0"\nid: {name}-pairing\nname: pairing\npurpose: Pair.\nsteps:\n  - title: Act\n    description: Do it.\n',
    )


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    for name in ("acme", "acme-two"):
        _org_pack(tmp_path, name)
    config = {
        "charter_packs": {"org": {"packs": [{"name": n, "local_path": f"org-packs/{n}"} for n in ("acme", "acme-two")]}},
        "mission_type_activations": ["software-dev"],
    }
    (tmp_path / ".kittify").mkdir()
    with (tmp_path / ".kittify" / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump(config, fh)
    return tmp_path


def _median(argv: list[str], check: Callable[[Any], None]) -> float:
    samples: list[float] = []
    for _ in range(_RUNS):
        start = time.perf_counter()
        result = runner.invoke(app, ["charter", *argv], catch_exceptions=False)
        samples.append(time.perf_counter() - start)
        check(result)
    return statistics.median(samples)


def test_preset_and_pack_list_within_budget_of_charter_list(project: Path) -> None:
    root = ["--repo-root", str(project)]

    def ok(result: Any) -> None:
        assert result.exit_code == 0, result.output

    def lists_both_org_packs(result: Any) -> None:
        ok(result)
        assert {"acme", "acme-two"} <= {row["name"] for row in json.loads(result.output)["packs"]}

    def preset_written(result: Any) -> None:
        ok(result)
        assert "activated_directives" in (project / ".kittify" / "config.yaml").read_text(encoding="utf-8")

    baseline = _median(["list", *root], ok)
    preset = _median(["activate", "--preset", "minimal", "--force", "--no-compile", *root], preset_written)
    pack_list = _median(["pack", "list", "--json", *root], lists_both_org_packs)

    assert preset <= _BUDGET * baseline, (preset, baseline)
    assert pack_list <= _BUDGET * baseline, (pack_list, baseline)
