"""NFR-003: a deny list adds little to ``charter deactivate`` (WP04, F18; restated by WP09).

This test measures the **cost of the deny list**, not a regression against the
base: on the same code, in the same process, ``charter deactivate`` runs on a
fixture whose ledger already holds a deny list and on one without, and the
median ratio must stay at or below :data:`_MAX_RATIO`. An absolute wall-clock
budget is not asserted: it is load-sensitive, and the repository-scale latency
is the pre-existing gap #6506. NFR-003's no-regression-against-base check is a
separate, manual measurement (interleaved base and head runs on this
repository, medians recorded in the PR's *Tests run* section).

Fixture: a ledger-seeded project declaring two org packs with ``required_*``
lists, so every run walks the strict required floor. The whole ``spec-kitty``
app is invoked in-process with ``CliRunner`` (root callback included), on a
fresh copy of the fixture each run, the two fixtures interleaved. Run serially:
``pytest -m timing -n0``.
"""

from __future__ import annotations

import shutil
import statistics
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.timing]

_RUNNER = CliRunner()
_RUNS = 5
_MAX_RATIO = 1.25
_TARGET = "003-decision-documentation-requirement"
_ALREADY_DENIED = ["010-specification-fidelity-requirement", "024-locality-of-change", "025-boy-scout-rule"]


def _fixture(root: Path, **ledger: list[str]) -> Path:
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name in ("acme", "acme-two"):
        pack = root / "org-packs" / name
        pack.mkdir(parents=True)
        (pack / "org-charter.yaml").write_text(
            "schema_version: 1\nrequired_directives: [DIRECTIVE_001]\nrequired_tactics: [adversarial-qa-handoff]\n", encoding="utf-8"
        )
        lines += [f"      - name: {name}", f"        local_path: org-packs/{name}"]
    (root / ".kittify").mkdir(parents=True)
    (root / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _timed_deactivate(template: Path, project: Path, expected: list[str]) -> float:
    shutil.copytree(template, project)
    start = time.perf_counter()
    result = _RUNNER.invoke(app, ["charter", "deactivate", "--no-compile", "--repo-root", str(project), "directive", _TARGET], catch_exceptions=False)
    elapsed = time.perf_counter() - start
    assert result.exit_code == 0, result.output
    assert read_activation_ledger(project)["deactivated_directives"] == expected
    return elapsed


def test_a_deny_list_adds_little_to_deactivate(tmp_path: Path) -> None:
    plain_template = _fixture(tmp_path / "plain")
    denied_template = _fixture(tmp_path / "denied", deactivated_directives=_ALREADY_DENIED)
    plain: list[float] = []
    denied: list[float] = []
    for run in range(_RUNS):
        plain.append(_timed_deactivate(plain_template, tmp_path / f"plain-{run}", [_TARGET]))
        denied.append(_timed_deactivate(denied_template, tmp_path / f"denied-{run}", sorted([*_ALREADY_DENIED, _TARGET])))

    ratio = statistics.median(denied) / statistics.median(plain)
    print(f"deactivate median: deny-free {statistics.median(plain):.3f}s, deny-present {statistics.median(denied):.3f}s, ratio {ratio:.3f}")
    assert ratio <= _MAX_RATIO, {"ratio": ratio, "deny_free": plain, "deny_present": denied}
