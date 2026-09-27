"""SANDBOX behavioral negative test (WP03, NFR-002(a)).

The discriminating, non-fakeable signal is *selective refusal*: the same
network-isolated + SANDBOX pipeline renders a benign diagram fine but **refuses**
(fails closed on) a diagram that references an EXTERNAL resource via ``!include``.
It is therefore not the weak "the build always fails" disjunct — benign diagrams
pass; only egress-attempting ones are rejected, and the external content never
reaches the output.

Note on the classic listener control: PlantUML 1.2025.4 rejects remote includes
at preprocessing under its default/SANDBOX profiles (a local listener is never
contacted even before SANDBOX is considered), so a "listener is hit without
SANDBOX" positive control is not reproducible here. The primary, discriminating
no-egress proof is the network-isolation corpus test
(``test_plantuml_no_egress_corpus.py``): the whole corpus renders under
``--network=none``, so no egress is even possible.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.docs import plantuml_invoke

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.unit

_BENIGN = '@startyaml\ntitle Benign Control\nprofile_id: "x"\nrole: "y"\n@endyaml\n'
_EXTERNAL_INCLUDE = "@startuml\n!include http://127.0.0.1:59777/leak\nBob -> Alice\n@enduml\n"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, check=False).returncode == 0


def _ensure_jar() -> Path:
    # Concurrency-safe: see plantuml_invoke.ensure_jar (WP01 canonical provisioner
    # — a per-process temp download + atomic publish under a cross-process lock,
    # so xdist workers racing on the shared plantuml.jar path never truncate it).
    return plantuml_invoke.ensure_jar(plantuml_invoke.load_pins(), _REPO_ROOT / "plantuml.jar")


_docker = pytest.mark.skipif(not _docker_available(), reason="docker unavailable")


@_docker
def test_benign_diagram_renders_under_sandbox_isolation() -> None:
    """Control: a benign diagram renders fine — so refusal below is selective, not blanket."""
    jar = _ensure_jar()
    pins = plantuml_invoke.load_pins()
    svg = plantuml_invoke.render_startyaml(_BENIGN, workdir=_REPO_ROOT, jar_path=jar, pins=pins)
    assert svg.strip() and not plantuml_invoke.svg_is_error(svg)
    assert b"Benign Control" in svg


@_docker
def test_external_include_is_refused_under_sandbox_isolation() -> None:
    """A diagram referencing an EXTERNAL resource fails closed — external content never emitted."""
    jar = _ensure_jar()
    pins = plantuml_invoke.load_pins()
    with pytest.raises(plantuml_invoke.PlantumlRenderError):
        plantuml_invoke.render_startyaml(_EXTERNAL_INCLUDE, workdir=_REPO_ROOT, jar_path=jar, pins=pins)
