"""The nightly pip-audit gate audits every dependency group the release job installs (#7704).

``cyclonedx-bom`` moved from the ``lint`` extra to the non-default ``sbom`` group
so dev and CI environments stop paying ``rfc3987-syntax``'s import. ``uv export
--all-extras`` exports only the default groups, so without ``--all-groups`` the
gate would silently stop auditing packages the release ``build`` job still
installs and runs.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE = _REPO_ROOT / "scripts" / "ci" / "pip_audit_gate.sh"
_RELEASE = _REPO_ROOT / ".github" / "workflows" / "release.yml"


def _gate_export_argv() -> list[str]:
    line = next(line for line in _GATE.read_text(encoding="utf-8").splitlines() if line.startswith("uv export "))
    argv = shlex.split(line.split(" -o ", 1)[0])
    return argv


def _exported_names(argv: list[str]) -> set[str]:
    completed = subprocess.run(argv, cwd=_REPO_ROOT, capture_output=True, text=True, timeout=120, check=True)
    return {match.group(1).lower() for match in re.finditer(r"^([A-Za-z0-9_.-]+)==", completed.stdout, re.MULTILINE)}


def _release_groups() -> set[str]:
    return set(re.findall(r"--group (\w+)", _RELEASE.read_text(encoding="utf-8")))


def test_the_release_job_installs_at_least_one_group() -> None:
    """Non-vacuity: the release job does install a dependency group."""
    assert "sbom" in _release_groups()


def test_the_audit_export_covers_every_group_the_release_job_installs() -> None:
    exported = _exported_names(_gate_export_argv())
    for group in sorted(_release_groups()):
        group_only = _exported_names(["uv", "export", "--frozen", "--no-hashes", "--only-group", group, "--no-emit-project", "--no-emit-workspace"])
        missing = sorted(group_only - exported)
        assert not missing, f"pip_audit_gate.sh does not audit release group '{group}': {missing}"
    assert "cyclonedx-bom" in exported
