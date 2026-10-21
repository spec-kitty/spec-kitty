"""NFR-003: a deny list adds little to ``charter context --action implement`` (WP05, F18; restated by WP09).

This test measures the **cost of the deny list**, not a regression against the
base: on the same code, in the same process, ``charter context`` runs on a
fixture with a deny list and on one without, and the median ratio must stay at
or below :data:`_MAX_RATIO`. An absolute wall-clock budget is not asserted: it
is load-sensitive, and the repository-scale latency is the pre-existing gap
#6506. NFR-003's no-regression-against-base check is a separate, manual
measurement (interleaved base and head runs on this repository, medians
recorded in the PR's *Tests run* section).

The effective deny is computed once per ``PackContext`` and only for kinds
with a non-empty deny list. Fixture: a ledger-seeded git project declaring two
org packs with ``required_*`` lists (so a deny list makes the read walk the
strict floor). The whole ``spec-kitty`` app is invoked in-process with
``CliRunner`` (root callback included), the two fixtures interleaved. Run
serially: ``pytest -m timing -n0``.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.timing]

_RUNNER = CliRunner()
_RUNS = 5
_MAX_RATIO = 1.25
_DENIED = "010-specification-fidelity-requirement"
_DENIED_ID = "DIRECTIVE_010"
_ARGV = ["charter", "context", "--action", "implement", "--mission-type", "software-dev", "--no-mark-loaded", "--json"]


def _fixture(root: Path, **ledger: list[str]) -> Path:
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name in ("acme", "acme-two"):
        pack = root / "org-packs" / name
        pack.mkdir(parents=True)
        (pack / "org-charter.yaml").write_text(
            "schema_version: 1\nrequired_directives: [DIRECTIVE_001]\nrequired_tactics: [adversarial-qa-handoff]\n", encoding="utf-8"
        )
        lines += [f"      - name: {name}", f"        local_path: org-packs/{name}"]
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    seed_activation_ledger(root, mission_type_activations=["software-dev"], **ledger)
    return root


def _timed_context(project: Path, monkeypatch: pytest.MonkeyPatch, *, expect_denied_served: bool) -> float:
    monkeypatch.chdir(project)
    start = time.perf_counter()
    result = _RUNNER.invoke(app, _ARGV, catch_exceptions=False)
    elapsed = time.perf_counter() - start
    assert result.exit_code == 0, result.output
    served = {entry["id"] for entry in json.loads(result.output)["all_directives"]}
    assert (_DENIED_ID in served) is expect_denied_served
    return elapsed


def test_a_deny_list_adds_little_to_charter_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plain_project = _fixture(tmp_path / "plain")
    denied_project = _fixture(tmp_path / "denied", deactivated_directives=[_DENIED])
    plain: list[float] = []
    denied: list[float] = []
    for _ in range(_RUNS):
        plain.append(_timed_context(plain_project, monkeypatch, expect_denied_served=True))
        denied.append(_timed_context(denied_project, monkeypatch, expect_denied_served=False))

    ratio = statistics.median(denied) / statistics.median(plain)
    print(f"charter context median: deny-free {statistics.median(plain):.3f}s, deny-present {statistics.median(denied):.3f}s, ratio {ratio:.3f}")
    assert ratio <= _MAX_RATIO, {"ratio": ratio, "deny_free": plain, "deny_present": denied}
