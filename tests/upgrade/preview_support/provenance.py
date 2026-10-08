"""Verify the actual editable console entry before attaching a measured home."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import sysconfig

from tests.upgrade.preview_support.process import run_process


def active_executables() -> tuple[Path, Path]:
    """Use the interpreter running pytest and its matching console scripts."""
    scripts = sysconfig.get_path("scripts")
    console = shutil.which("spec-kitty", path=scripts)
    if console is None:
        raise RuntimeError(f"spec-kitty console script not found in {scripts}")
    return Path(sys.executable), Path(console)


_PROBE = """
import importlib.metadata, importlib.util, json, sys
dist = importlib.metadata.distribution('spec-kitty-cli')
module = importlib.util.find_spec('specify_cli')
entry = [e.value for e in dist.entry_points if e.group == 'console_scripts' and e.name == 'spec-kitty']
print(json.dumps(dict(module=module.origin, version=dist.version,
                     distribution=str(dist.locate_file('')), interpreter=sys.executable,
                     python=sys.version, entry=entry)))
"""


@dataclass(frozen=True)
class SourceIdentity:
    """Immutable executable/distribution/source receipt."""

    executable: str
    interpreter: str
    module: str
    distribution: str
    version: str
    python: str
    commit: str
    source_diff: str


def identify_source(executable: Path, checkout: Path, env: Mapping[str, str]) -> SourceIdentity:
    """Reject a different editable checkout even if its version is identical."""
    executable = executable.absolute()
    assert executable.is_file(), f"Missing executable: {executable}"
    # Keep the venv path: resolving the Python symlink loses its environment.
    interpreter = executable.parent / "python"
    result = run_process([str(interpreter), "-c", _PROBE], Path(env["TMPDIR"]), env)
    result.require_success()
    data = result.json()
    expected = checkout.resolve() / "src/specify_cli/__init__.py"
    assert Path(data["module"]).resolve() == expected, f"Source mismatch: {data['module']} != {expected}"
    assert data["entry"] == ["specify_cli:main"], f"Unexpected entrypoint: {data['entry']}"
    script = executable.read_text(encoding="utf-8")
    assert "from specify_cli import main" in script, "Console script does not invoke real main"
    assert str(interpreter) in script.split("# -*-", maxsplit=1)[0], "Console interpreter differs from probe"
    commit = run_process(["git", "rev-parse", "HEAD"], checkout, env)
    commit.require_success()
    diff = run_process(["git", "diff", "HEAD", "--", "src", "packs", "pyproject.toml", "uv.lock"], checkout, env)
    assert diff.returncode == 0, diff.stderr
    return SourceIdentity(
        str(executable), str(interpreter), data["module"], data["distribution"], data["version"], data["python"], commit.stdout.strip(), diff.stdout
    )
