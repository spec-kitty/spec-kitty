"""Lane test invocation and probe (mission lane-code-verification, WP01).

Pins the user-observable behaviour of :mod:`specify_cli.lanes.lane_invocation`:

* the invocation a lane's tests run under loads the lane's own source, also in
  a grandchild process (SC-001, FR-003);
* the probe reports where the lane's tracked source packages load from:
  ``verified`` inside ``<lane>/src``, ``foreign`` elsewhere (FR-002, the #1907
  case), ``unverified`` when it cannot tell, and never raises (FR-010);
* interpreter redirects inherited from the caller are stripped (FR-004);
* containment is portable across path flavours (NFR-004);
* the evidence tree records path, HEAD, dirty flag and probe.

Every negative assertion has a positive control on the same fixture.
The fixture is a scratch project with a real linked worktree and a
``python -m venv --without-pip`` whose ``.pth`` plays the editable install;
it never uses this repository's own environment for the code under test.
"""

from __future__ import annotations

import dataclasses
import ntpath
import os
import posixpath
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

from kernel.paths import is_windows
from specify_cli.lanes.lane_invocation import (
    INTERPRETER_REDIRECT_KEYS,
    EvidenceTree,
    LaneTestInvocation,
    ProbeResult,
    ProbeStatus,
    build_lane_test_invocation,
    capture_evidence_tree,
    origin_inside,
    probe_lane_imports,
    run_environment,
)

_PKG = "scratchlanepkg"
_MISSION = "m-01ABCDEF"
_LANE = "lane-a"
_GIT_ID = ("-c", "user.name=Lane Test", "-c", "user.email=lane@test.invalid")

posix_only = pytest.mark.skipif(is_windows(), reason="stub interpreters are POSIX shell scripts")


@dataclass(frozen=True)
class ScratchProject:
    root: Path
    lane: Path
    root_python: Path


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(["git", *_GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _venv_python(venv: Path) -> Path:
    return venv / "Scripts" / "python.exe" if is_windows() else venv / "bin" / "python"


def _make_venv(venv: Path, pth_target: Path | None) -> Path:
    """Create a pip-less venv; a ``.pth`` naming *pth_target* plays the editable install."""
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    python = _venv_python(venv)
    if pth_target is not None:
        (_site_packages(python) / "_editable_scratch.pth").write_text(f"{pth_target}\n", encoding="utf-8")
    return python


def _site_packages(python: Path) -> Path:
    out = subprocess.run(
        [str(python), "-c", "import sysconfig;print(sysconfig.get_path('purelib'))"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(out.stdout.strip())


def _clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in INTERPRETER_REDIRECT_KEYS}
    env.update(extra)
    return env


@pytest.fixture
def scratch_project(tmp_path: Path) -> ScratchProject:
    root = tmp_path / "root"
    pkg = root / "src" / _PKG
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("V = 1\n", encoding="utf-8")
    (pkg / "mod.py").write_text("X = 0\n", encoding="utf-8")
    loose = root / "src" / "loose"
    loose.mkdir()
    (loose / "foo.py").write_text("Y = 0\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "scratch")
    lane = tmp_path / "lane"
    _git(root, "worktree", "add", "-q", "-b", _LANE, str(lane))
    (lane / "src" / _PKG / "__init__.py").write_text("V = 2\n", encoding="utf-8")
    root_python = _make_venv(root / ".venv", root / "src")
    return ScratchProject(root=root, lane=lane, root_python=root_python)


def _origins(probe: ProbeResult) -> dict[str, str | None]:
    return dict(probe.origins)


# --- 1. Planted change (SC-001, FR-003) ------------------------------------


@pytest.mark.git_repo
def test_invocation_loads_the_lane_source_in_child_and_grandchild(scratch_project: ScratchProject) -> None:
    inv = build_lane_test_invocation(scratch_project.lane, command="pytest -q", mission_slug=_MISSION, lane_id=_LANE)
    script = (
        "import subprocess, sys\n"
        f"import {_PKG}\n"
        f"print({_PKG}.V)\n"
        f"print(subprocess.run([sys.executable, '-c', 'import {_PKG};print({_PKG}.V)'],"
        " capture_output=True, text=True, check=True).stdout.strip())\n"
    )
    child = subprocess.run(
        [str(scratch_project.root_python), "-c", script],
        cwd=inv.cwd,
        env=run_environment(inv, _clean_env()),
        capture_output=True,
        text=True,
        check=True,
    )
    assert child.stdout.split() == ["2", "2"]

    # Negative control, same fixture: the root venv with the inherited
    # environment loads the root checkout's source although cwd is the lane.
    bare = subprocess.run(
        [str(scratch_project.root_python), "-c", f"import {_PKG};print({_PKG}.V)"],
        cwd=scratch_project.lane,
        env=_clean_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert bare.stdout.strip() == "1"


@pytest.mark.git_repo
def test_invocation_fields(scratch_project: ScratchProject) -> None:
    inv = build_lane_test_invocation(scratch_project.lane, command="pytest -q {output_file}", mission_slug=_MISSION, lane_id=_LANE)
    assert inv.cwd == scratch_project.lane
    assert inv.command == "pytest -q {output_file}"
    assert dict(inv.env_set)["PYTHONPATH"] == str(scratch_project.lane / "src")
    assert "SPEC_KITTY_TEST_DB_NAME" in dict(inv.env_set)
    assert inv.env_unset == INTERPRETER_REDIRECT_KEYS
    assert inv.probe is None


@pytest.mark.git_repo
def test_invocation_without_lane_identity_has_no_db_name(scratch_project: ScratchProject) -> None:
    inv = build_lane_test_invocation(scratch_project.lane, command=None)
    assert "SPEC_KITTY_TEST_DB_NAME" not in dict(inv.env_set)
    assert inv.command is None
    empty = build_lane_test_invocation(scratch_project.lane, command=None, mission_slug="", lane_id=_LANE)
    assert "SPEC_KITTY_TEST_DB_NAME" not in dict(empty.env_set)


# --- 2. Probe verified -------------------------------------------------------


@pytest.mark.git_repo
def test_probe_verified_for_lane_without_venv(scratch_project: ScratchProject) -> None:
    inv = build_lane_test_invocation(scratch_project.lane, command=None)
    probe = probe_lane_imports(inv, base_env=_clean_env())
    assert probe.status is ProbeStatus.VERIFIED, probe.reason
    origins = _origins(probe)
    assert set(origins) == {_PKG}, "only tracked regular packages are probed ('loose' has no __init__.py)"
    origin = origins[_PKG]
    assert origin is not None
    assert origin_inside(origin, scratch_project.lane / "src")
    assert probe.foreign == ()
    assert probe.interpreter == sys.executable


# --- 3. Probe foreign / verified pair (FR-002, #1907) -----------------------


@pytest.mark.git_repo
def test_probe_foreign_when_lane_venv_points_at_root(scratch_project: ScratchProject) -> None:
    lane_python = _make_venv(scratch_project.lane / ".venv", scratch_project.root / "src")
    inv = build_lane_test_invocation(scratch_project.lane, command=None)
    assert "PYTHONPATH" not in dict(inv.env_set), "a lane with its own venv gets no PYTHONPATH"

    probe = probe_lane_imports(inv, base_env=_clean_env())
    assert probe.status is ProbeStatus.FOREIGN
    assert probe.foreign == (_PKG,)
    origin = _origins(probe)[_PKG]
    assert origin is not None
    assert origin_inside(origin, scratch_project.root / "src")
    assert probe.interpreter == str(lane_python)

    # Positive control, same fixture: repoint the install at the lane.
    (_site_packages(lane_python) / "_editable_scratch.pth").write_text(f"{scratch_project.lane / 'src'}\n", encoding="utf-8")
    assert probe_lane_imports(inv, base_env=_clean_env()).status is ProbeStatus.VERIFIED


# --- 4. Lane-venv copy is foreign (squad T3) --------------------------------


@pytest.mark.git_repo
def test_probe_foreign_for_copy_inside_lane_venv(scratch_project: ScratchProject) -> None:
    lane_python = _make_venv(scratch_project.lane / ".venv", None)
    site = _site_packages(lane_python)
    shutil.copytree(scratch_project.lane / "src" / _PKG, site / _PKG)
    inv = build_lane_test_invocation(scratch_project.lane, command=None)
    probe = probe_lane_imports(inv, base_env=_clean_env())
    assert probe.status is ProbeStatus.FOREIGN
    origin = _origins(probe)[_PKG]
    assert origin is not None
    assert origin_inside(origin, scratch_project.lane), "the copy lives inside the lane root ..."
    assert not origin_inside(origin, scratch_project.lane / "src"), "... but not inside <lane>/src"


# --- 5. Redirect stripping (FR-004), half by half ---------------------------


@pytest.mark.git_repo
def test_run_environment_strips_venv_redirects(scratch_project: ScratchProject) -> None:
    root = scratch_project.root
    base = _clean_env(PYTHONPATH=str(root / "src"), VIRTUAL_ENV=str(root / ".venv"), UV_PROJECT_ENVIRONMENT=str(root / ".venv"))
    inv = build_lane_test_invocation(scratch_project.lane, command="pytest", mission_slug=_MISSION, lane_id=_LANE)
    env = run_environment(inv, base)
    assert "VIRTUAL_ENV" not in env
    assert "UV_PROJECT_ENVIRONMENT" not in env
    assert env["SPEC_KITTY_TEST_DB_NAME"]
    assert env["PYTHONPATH"] == str(scratch_project.lane / "src")
    assert base["VIRTUAL_ENV"] == str(root / ".venv"), "the base mapping is not mutated"


@pytest.mark.git_repo
def test_inherited_pythonpath_is_stripped_for_lane_with_venv(scratch_project: ScratchProject) -> None:
    _make_venv(scratch_project.lane / ".venv", scratch_project.lane / "src")
    base = _clean_env(PYTHONPATH=str(scratch_project.root / "src"))
    inv = build_lane_test_invocation(scratch_project.lane, command=None)
    assert "PYTHONPATH" not in run_environment(inv, base)
    assert probe_lane_imports(inv, base_env=base).status is ProbeStatus.VERIFIED

    # Positive control, same fixture: without the strip the inherited
    # PYTHONPATH wins and the probe sees the root checkout.
    unstripped = dataclasses.replace(inv, env_unset=())
    assert probe_lane_imports(unstripped, base_env=base).status is ProbeStatus.FOREIGN


# --- 6. Unverified, never raises (FR-010) -----------------------------------


@pytest.mark.git_repo
def test_probe_unverified_without_source_packages(tmp_path: Path) -> None:
    project = tmp_path / "nosrc"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "README").write_text("x\n", encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "x")
    inv = build_lane_test_invocation(project, command=None)
    assert "PYTHONPATH" not in dict(inv.env_set)
    probe = probe_lane_imports(inv, base_env=_clean_env())
    assert probe.status is ProbeStatus.UNVERIFIED
    assert probe.reason == "no tracked source-layout packages to probe"


@pytest.mark.fast
def test_probe_unverified_outside_git(tmp_path: Path) -> None:
    (tmp_path / "src" / "untracked").mkdir(parents=True)
    (tmp_path / "src" / "untracked" / "__init__.py").write_text("", encoding="utf-8")
    probe = probe_lane_imports(build_lane_test_invocation(tmp_path, command=None), base_env=_clean_env())
    assert probe.status is ProbeStatus.UNVERIFIED
    assert probe.reason


def _stub_lane_python(lane: Path, body: str, *, executable: bool = True) -> Path:
    python = _venv_python(lane / ".venv")
    python.parent.mkdir(parents=True)
    python.write_text(body, encoding="utf-8")
    python.chmod(0o755 if executable else 0o644)
    return python


@posix_only
@pytest.mark.git_repo
def test_probe_unverified_when_interpreter_cannot_run(scratch_project: ScratchProject) -> None:
    _stub_lane_python(scratch_project.lane, "not a program\n", executable=False)
    probe = probe_lane_imports(build_lane_test_invocation(scratch_project.lane, command=None), base_env=_clean_env())
    assert probe.status is ProbeStatus.UNVERIFIED
    assert probe.reason
    assert len(probe.reason) <= 200


@posix_only
@pytest.mark.git_repo
def test_probe_unverified_on_timeout(scratch_project: ScratchProject) -> None:
    _stub_lane_python(scratch_project.lane, "#!/bin/sh\nexec sleep 10\n")
    inv = build_lane_test_invocation(scratch_project.lane, command=None)
    probe = probe_lane_imports(inv, base_env=_clean_env(), timeout=0.5)
    assert probe.status is ProbeStatus.UNVERIFIED
    assert probe.reason is not None
    assert "timed out" in probe.reason


@posix_only
@pytest.mark.git_repo
@pytest.mark.parametrize(
    "body",
    [
        pytest.param("#!/bin/sh\necho not-json\n", id="non-json"),
        pytest.param("#!/bin/sh\necho boom >&2\nexit 3\n", id="non-zero-exit"),
        pytest.param("#!/bin/sh\necho '[1, 2]'\n", id="json-not-an-object"),
    ],
)
def test_probe_unverified_on_bad_child_output(scratch_project: ScratchProject, body: str) -> None:
    _stub_lane_python(scratch_project.lane, body)
    probe = probe_lane_imports(build_lane_test_invocation(scratch_project.lane, command=None), base_env=_clean_env())
    assert probe.status is ProbeStatus.UNVERIFIED
    assert probe.reason
    assert len(probe.reason) <= 200


@pytest.mark.git_repo
def test_probe_unverified_when_package_not_importable(scratch_project: ScratchProject) -> None:
    # A lane venv with no install of the package: find_spec returns None.
    _make_venv(scratch_project.lane / ".venv", None)
    probe = probe_lane_imports(build_lane_test_invocation(scratch_project.lane, command=None), base_env=_clean_env())
    assert probe.status is ProbeStatus.UNVERIFIED
    assert probe.reason is not None
    assert _PKG in probe.reason


@pytest.mark.git_repo
def test_probe_never_raises_from_runner(scratch_project: ScratchProject) -> None:
    def exploding_runner(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("no such interpreter")

    inv = build_lane_test_invocation(scratch_project.lane, command=None)
    probe = probe_lane_imports(inv, base_env=_clean_env(), runner=exploding_runner)
    assert probe.status is ProbeStatus.UNVERIFIED
    assert probe.reason is not None
    assert "no such interpreter" in probe.reason


# --- 7. origin_inside (NFR-004) ---------------------------------------------


@pytest.mark.fast
@pytest.mark.parametrize(
    ("pathmod", "origin", "root", "expected"),
    [
        pytest.param(posixpath, "/a/src/pkg/__init__.py", "/a/src", True, id="posix-inside"),
        pytest.param(posixpath, "/a/src", "/a/src", True, id="posix-equal"),
        pytest.param(posixpath, "/b/src/pkg/__init__.py", "/a/src", False, id="posix-outside"),
        pytest.param(posixpath, "/a/src2/pkg/__init__.py", "/a/src", False, id="posix-sibling-prefix"),
        pytest.param(posixpath, "/a/src/../other/pkg.py", "/a/src", False, id="posix-dotdot-escape"),
        pytest.param(posixpath, "/A/src/pkg.py", "/a/src", False, id="posix-case-sensitive"),
        pytest.param(ntpath, "C:\\Lane\\src\\pkg\\__init__.py", "c:\\lane\\src", True, id="nt-case-insensitive-drive"),
        pytest.param(ntpath, "C:/Lane/src\\pkg/__init__.py", "c:\\lane\\src\\", True, id="nt-mixed-separators"),
        pytest.param(ntpath, "C:\\Lane\\src2\\pkg.py", "C:\\Lane\\src", False, id="nt-sibling-prefix"),
        pytest.param(ntpath, "D:\\Lane\\src\\pkg.py", "C:\\Lane\\src", False, id="nt-other-drive"),
    ],
)
def test_origin_inside(pathmod: ModuleType, origin: str, root: str, expected: bool) -> None:
    assert origin_inside(origin, root, pathmod=pathmod) is expected


@pytest.mark.fast
def test_origin_inside_resolves_symlinks_on_the_host(tmp_path: Path) -> None:
    real = tmp_path / "real" / "src"
    (real / "pkg").mkdir(parents=True)
    link = tmp_path / "link"
    try:
        link.symlink_to(tmp_path / "real", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not available")
    assert origin_inside(link / "src" / "pkg", real)
    assert not origin_inside(tmp_path / "elsewhere" / "pkg", real)


# --- 8. Evidence tree ---------------------------------------------------------


@pytest.mark.git_repo
def test_capture_evidence_tree(scratch_project: ScratchProject, tmp_path: Path) -> None:
    lane = scratch_project.lane
    probe = probe_lane_imports(build_lane_test_invocation(lane, command=None), base_env=_clean_env())
    tree = capture_evidence_tree(lane, probe, repo_root=tmp_path)
    assert tree.head == _git(lane, "rev-parse", "HEAD")
    assert tree.dirty is True
    assert tree.path == "lane"
    assert tree.probe == probe

    # Not under repo_root: absolute path.
    outside = capture_evidence_tree(lane, probe, repo_root=scratch_project.root)
    assert outside.path == str(lane)
    assert capture_evidence_tree(lane, probe).path == str(lane)

    # Positive control for dirty: commit the planted change.
    _git(lane, "commit", "-q", "-am", "plant")
    assert capture_evidence_tree(lane, probe).dirty is False


@pytest.mark.git_repo
def test_capture_evidence_tree_relative_path_is_posix(scratch_project: ScratchProject) -> None:
    nested = scratch_project.root / ".worktrees" / "lane-b"
    _git(scratch_project.root, "worktree", "add", "-q", "-b", "lane-b", str(nested))
    probe = ProbeResult(status=ProbeStatus.UNVERIFIED, origins=(), foreign=(), reason="x", interpreter=None)
    assert capture_evidence_tree(nested, probe, repo_root=scratch_project.root).path == ".worktrees/lane-b"


@pytest.mark.fast
def test_capture_evidence_tree_outside_git_never_raises(tmp_path: Path) -> None:
    probe = ProbeResult(status=ProbeStatus.UNVERIFIED, origins=(), foreign=(), reason="x", interpreter=None)
    tree = capture_evidence_tree(tmp_path / "missing", probe)
    assert tree.head is None
    assert tree.dirty is None


# --- 9. to_dict() shape (contracts/lane-test-invocation.md) -----------------


@pytest.mark.git_repo
def test_to_dict_shapes_match_the_contract(scratch_project: ScratchProject) -> None:
    inv = build_lane_test_invocation(scratch_project.lane, command="make test", mission_slug=_MISSION, lane_id=_LANE)
    bare = inv.to_dict()
    assert set(bare) == {"cwd", "command", "env_set", "env_unset", "probe"}
    assert bare["probe"] is None
    assert bare["cwd"] == str(scratch_project.lane)
    assert bare["env_unset"] == ["PYTHONPATH", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV"]
    assert isinstance(bare["env_set"], Mapping)

    probed = inv.with_probe(probe_lane_imports(inv, base_env=_clean_env()))
    assert isinstance(probed, LaneTestInvocation)
    payload = probed.to_dict()
    probe_dict = payload["probe"]
    assert isinstance(probe_dict, dict)
    assert set(probe_dict) == {"status", "origins", "foreign", "reason", "interpreter"}
    assert probe_dict["status"] == "verified"
    assert isinstance(probe_dict["origins"], dict)
    assert probe_dict["foreign"] == []

    tree = capture_evidence_tree(scratch_project.lane, probed.probe or ProbeResult(ProbeStatus.UNVERIFIED, (), (), "x", None))
    assert isinstance(tree, EvidenceTree)
    tree_dict = tree.to_dict()
    assert set(tree_dict) == {"path", "head", "dirty", "probe"}
    assert tree_dict["probe"] == probe_dict


# --- Close-out folds (aggregate review of mission lane-code-verification) ----


def _wrap_venv_python_rejecting_dash_p(python: Path) -> None:
    """Make *python* behave like a pre-3.11 interpreter: ``-P`` is an unknown option."""
    real = python.with_name("python-real")
    python.rename(real)
    python.write_text(
        f'#!/bin/sh\nfor a in "$@"; do [ "$a" = "-P" ] && {{ echo "Unknown option: -P" >&2; exit 2; }}; done\nexec "{real}" "$@"\n',
        encoding="utf-8",
    )
    python.chmod(0o755)


@posix_only
@pytest.mark.git_repo
def test_probe_works_on_an_interpreter_without_dash_p(scratch_project: ScratchProject) -> None:
    lane = scratch_project.lane
    python = _make_venv(lane / ".venv", lane / "src")
    inv = build_lane_test_invocation(lane, command=None)
    # Positive control on the same fixture: the real venv interpreter verifies.
    assert probe_lane_imports(inv, base_env=_clean_env()).status is ProbeStatus.VERIFIED
    _wrap_venv_python_rejecting_dash_p(python)
    probe = probe_lane_imports(inv, base_env=_clean_env())
    assert probe.status is ProbeStatus.VERIFIED, probe.reason


@pytest.mark.git_repo
def test_probe_ignores_a_decoy_package_in_the_working_directory(scratch_project: ScratchProject) -> None:
    lane = scratch_project.lane
    decoy = lane / _PKG
    decoy.mkdir()
    (decoy / "__init__.py").write_text("V = 99\n", encoding="utf-8")
    probe = probe_lane_imports(build_lane_test_invocation(lane, command=None), base_env=_clean_env())
    assert probe.status is ProbeStatus.VERIFIED, probe.reason
    origin = _origins(probe)[_PKG]
    assert origin is not None
    assert origin_inside(origin, lane / "src")


@pytest.mark.git_repo
def test_capture_evidence_tree_records_repository_relative_origins(scratch_project: ScratchProject, tmp_path: Path) -> None:
    lane = scratch_project.lane
    probe = probe_lane_imports(build_lane_test_invocation(lane, command=None), base_env=_clean_env())
    recorded = capture_evidence_tree(lane, probe, repo_root=tmp_path).probe
    assert dict(recorded.origins)[_PKG] == f"lane/src/{_PKG}/__init__.py"
    assert recorded.status is probe.status
    # Positive control: without a repository root nothing is rewritten.
    assert capture_evidence_tree(lane, probe).probe == probe


@pytest.mark.fast
def test_git_reads_carry_a_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import specify_cli.lanes.lane_invocation as module

    seen: dict[str, object] = {}

    def _spy(name: str) -> Callable[..., tuple[()]]:
        def _record(*args: object, **kwargs: object) -> tuple[()]:
            seen[name] = kwargs.get("timeout")
            raise module.GitCommandError(argv=("x",), cwd=tmp_path, returncode=1, stderr="")

        return _record

    monkeypatch.setattr(module, "tracked_paths", _spy("tracked_paths"))
    monkeypatch.setattr(module, "run_git", _spy("run_git"))
    monkeypatch.setattr(module, "status_entries", _spy("status_entries"))
    probe = module.probe_lane_imports(build_lane_test_invocation(tmp_path, command=None))
    module.capture_evidence_tree(tmp_path, probe)
    assert set(seen) == {"tracked_paths", "run_git", "status_entries"}
    assert all(isinstance(value, (int, float)) and value > 0 for value in seen.values()), seen
