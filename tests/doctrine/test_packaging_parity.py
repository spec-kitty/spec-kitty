"""Packaging parity for the built-in doctrine packs (mission
``relocate-builtin-doctrine-packs-01KYT87F``, WP05 — FR-007 / NFR-002).

``packs/built-in/`` must ship **completely** in BOTH the monolith wheel and the
sdist, and a clean-venv install must be able to ``import charter.offering`` and resolve
the built-in pack root to a real, complete on-disk tree.

The parity contract is **live-tree**: the built artifact's ``packs/built-in/``
contents must equal the live source tree (the git-tracked ``packs/built-in/``
inventory hatchling ``force-include``s). This deliberately replaces the earlier
frozen 469-entry ``content-manifest.json`` snapshot, which was a relocation-era
change-detector that falsely reddened on every legitimate ``packs/built-in/``
addition.

Why this test builds real artifacts (not a config assertion): the pre-spec
adversarial squad proved a build can exit 0 while shipping an *empty or partial*
artifact. So the acceptance gate is the built artifacts' **contents** and a live
import, never "build exited 0" or a `>=` count (a `>=` passes on duplication).

Marked ``@pytest.mark.distribution`` (slow: builds a wheel + an sdist + creates a
clean venv + installs the wheel) and ``@pytest.mark.integration``. It does not run
in the fast gate::

    pytest tests/doctrine/test_packaging_parity.py -m distribution -v
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import venv
import zipfile
from pathlib import Path

import pytest

from tests._support.shared_package_deferral import clean_install_acceptance_deferred

pytestmark = [pytest.mark.distribution, pytest.mark.integration, pytest.mark.git_repo, pytest.mark.corpus]

_THIS = Path(__file__).resolve()
REPO_ROOT = _THIS.parents[2]

_PACKS_PREFIX = "packs/built-in/"


# --------------------------------------------------------------------------- #
# Expected set: the LIVE source tree, not a frozen inventory
# --------------------------------------------------------------------------- #


def _expected_pack_paths() -> set[str]:
    """Derive the expected ``packs/built-in/...`` file set from the **live source
    tree** — specifically the VCS inventory that hatchling's ``force-include``
    ships.

    ``pyproject.toml`` uses ``force-include = { "packs/built-in" = "packs/built-in" }``
    (scoped so maintainer-only org packs such as ``packs/internal/`` never ship),
    so the wheel/sdist auto-ship the tracked ``packs/built-in/`` tree; hatchling's
    VCS-respecting selection rule ships exactly the git-tracked, non-ignored
    files (e.g. the ``__pycache__/*.pyc`` under ``packs/built-in`` is
    ``.gitignore``-d and never shipped). ``git ls-files`` reproduces that same
    rule and already emits repo-root-relative, forward-slash paths carrying the
    ``packs/built-in/`` prefix.

    Anti-tautology: this expectation comes from the **git index**, an
    independent source from the built artifact the actual-side reads (the wheel
    zip / sdist tar). A build that drops, renames, or mangles a shipped file
    diverges from this set and reds — the two sides never share provenance. This
    replaces the retired relocation-era frozen ``content-manifest.json`` +
    move-set transform, which was a change-detector: every legitimate addition
    under ``packs/built-in/`` (e.g. new doctrine files) read as "extra" and
    falsely reddened even though nothing had regressed.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", _PACKS_PREFIX.rstrip("/")],
        cwd=str(REPO_ROOT),
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    expected = {entry for entry in out.split("\0") if entry}
    assert expected, f"no tracked files under {_PACKS_PREFIX} — derivation broken"
    assert all(p.startswith(_PACKS_PREFIX) for p in expected), sorted(expected)[:5]
    return expected


# --------------------------------------------------------------------------- #
# Build both artifacts once (expensive) and share across tests
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def built_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build wheel + sdist from the repo tree into a temp dir; return (whl, sdist)."""
    dist = tmp_path_factory.mktemp("wp05-dist")
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(dist), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist.glob("spec_kitty_cli-*.whl"))
    sdists = list(dist.glob("spec_kitty_cli-*.tar.gz"))
    assert len(wheels) == 1, f"expected exactly one wheel, found {wheels}"
    assert len(sdists) == 1, f"expected exactly one sdist, found {sdists}"
    return wheels[0], sdists[0]


def _wheel_pack_paths(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as zf:
        return {
            name
            for name in zf.namelist()
            if name.startswith(_PACKS_PREFIX) and not name.endswith("/")
        }


def _sdist_pack_paths(sdist: Path) -> set[str]:
    """Return the ``packs/built-in/...`` members of the sdist, stripped of the
    single ``spec_kitty_cli-<version>/`` top-level component sdists prepend."""
    found: set[str] = set()
    with tarfile.open(sdist) as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            _root, _, rel = member.name.partition("/")
            if rel.startswith(_PACKS_PREFIX):
                found.add(rel)
    return found


# --------------------------------------------------------------------------- #
# NFR-002 acceptance 1 — exact set-equality in EACH artifact
# --------------------------------------------------------------------------- #


def test_wheel_ships_built_in_packs_at_exact_parity(
    built_artifacts: tuple[Path, Path],
) -> None:
    wheel, _sdist = built_artifacts
    expected = _expected_pack_paths()
    actual = _wheel_pack_paths(wheel)
    missing = expected - actual
    extra = actual - expected
    assert actual == expected, (
        f"wheel packs/built-in mismatch — missing: {sorted(missing)}, "
        f"extra: {sorted(extra)}"
    )


def test_sdist_ships_built_in_packs_at_exact_parity(
    built_artifacts: tuple[Path, Path],
) -> None:
    _wheel, sdist = built_artifacts
    expected = _expected_pack_paths()
    actual = _sdist_pack_paths(sdist)
    missing = expected - actual
    extra = actual - expected
    assert actual == expected, (
        f"sdist packs/built-in mismatch — missing: {sorted(missing)}, "
        f"extra: {sorted(extra)}"
    )


# --------------------------------------------------------------------------- #
# NFR-002 acceptance 2 (packaging truth only) — clean-venv import + resolve
#
# Scope guard: this WP depends only on WP03. The loader repoint that makes
# ``load_built_in_graph()`` read the relocated fragments is WP04, and the
# full-graph (326/922) proof from a clean install lives in WP07. Here we assert
# ONLY packaging truth: ``import charter.offering`` succeeds and
# ``resolve_pack_root("built-in")`` yields a complete, real on-disk tree.
# --------------------------------------------------------------------------- #


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":  # pragma: no cover — CI runs on Linux
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


@pytest.mark.skipif(
    clean_install_acceptance_deferred(),
    reason="clean-venv wheel installation is deferred until #828's shared packages are published",
)
def test_clean_venv_install_imports_and_resolves_built_in(
    built_artifacts: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """Install the wheel into a clean venv (declared deps only, no repo ``src/``)
    and prove ``import charter.offering`` + ``resolve_pack_root('built-in')`` reach a
    complete installed tree with 0 missing live-tree files."""
    wheel, _sdist = built_artifacts
    venv_dir = tmp_path / "clean-venv"
    venv.create(venv_dir, with_pip=True, clear=True)
    py = _venv_python(venv_dir)

    subprocess.run(
        [str(py), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [str(py), "-m", "pip", "install", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )

    expected = _expected_pack_paths()
    # Relative-to-root paths (drop the leading ``packs/built-in/``) so the child
    # can check each one exists under the resolved pack root.
    rel_under_root = sorted(p[len(_PACKS_PREFIX) :] for p in expected)

    probe = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "import charter.offering  # noqa: F401 — import must succeed from the wheel\n"
        "from charter.offering.pack_paths import resolve_pack_root\n"
        "root = resolve_pack_root('built-in')\n"
        "assert root.is_dir(), f'pack root not a dir: {root}'\n"
        "# Fail-closed contract: never resolve into a src/charter/offering/ tree.\n"
        "assert 'src/doctrine' not in root.as_posix(), root.as_posix()\n"
        "rels = json.loads(sys.argv[1])\n"
        "missing = [r for r in rels if not (root / r).is_file()]\n"
        "assert not missing, f'{len(missing)} missing files, e.g. {missing[:5]}'\n"
        "print(json.dumps({'root': str(root), 'checked': len(rels)}))\n"
    )

    # Run from a cwd OUTSIDE the repo worktree, and strip any packs-root override,
    # so resolution can only reach the *installed* tree — never the repo checkout.
    child_env = {k: v for k, v in os.environ.items() if k != "SPEC_KITTY_PACKS_ROOT"}
    result = subprocess.run(
        [str(py), "-c", probe, json.dumps(rel_under_root)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=child_env,
    )
    assert result.returncode == 0, (
        "clean-venv import/resolve failed.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["checked"] == len(rel_under_root)
    assert _PACKS_PREFIX.rstrip("/") in payload["root"]
