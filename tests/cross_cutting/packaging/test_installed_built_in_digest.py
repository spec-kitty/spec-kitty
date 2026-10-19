"""FR-015 / NFR-003 / C-001: the installed wheel's ``packs/built-in`` has the pinned clean-tree digest.

The wheel is unpacked (a wheel is a zip laid out as site-packages) and a fresh
interpreter resolves ``built_in_root()`` from *that* copy, so the digest is taken
over exactly the tree a consumer would get.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from charter.offering.packs.pack_pin import load_pack_pin

pytestmark = [pytest.mark.slow, pytest.mark.distribution, pytest.mark.integration]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROBE = (
    "import json, charter, kernel;"
    "from pathlib import Path;"
    "from charter.offering.pack_paths import built_in_root;"
    "from charter.offering.packs.pack_clean_digest import clean_tree_digest;"
    "root = built_in_root();"
    "print(json.dumps({'root': str(root), 'charter': charter.__file__,"
    " 'digest': clean_tree_digest(root, level='built-in'),"
    " 'files': sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())}))"
)


@pytest.fixture(scope="module")
def installed_site(build_artifacts: dict[str, Path], tmp_path_factory: pytest.TempPathFactory) -> Path:
    site = tmp_path_factory.mktemp("installed-site")
    with zipfile.ZipFile(build_artifacts["wheel"]) as zf:
        zf.extractall(site)
    return site


@pytest.fixture(scope="module")
def probe(installed_site: Path) -> dict[str, object]:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("SPEC_KITTY", "PYTHONPATH"))}
    env["PYTHONPATH"] = str(installed_site)
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=installed_site,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    payload: dict[str, object] = json.loads(result.stdout.strip().splitlines()[-1])
    return payload


def test_installed_built_in_digest_equals_the_pin(probe: dict[str, object]) -> None:
    pin = load_pack_pin(_REPO_ROOT / "packs" / "built-in.source.yaml")
    assert probe["digest"] == pin.tree_digest.value


def test_installed_built_in_sits_at_the_unchanged_site_packages_path(probe: dict[str, object], installed_site: Path) -> None:
    """C-001: ``packs/built-in`` is a site-packages sibling of ``charter``, exactly as before."""
    assert Path(str(probe["root"])).resolve() == (installed_site / "packs" / "built-in").resolve()
    assert Path(str(probe["charter"])).resolve().is_relative_to(installed_site.resolve()), "probe imported charter from outside the wheel"
    assert probe["files"], "installed built-in pack is empty"


def test_installed_tree_has_no_internal_pack(installed_site: Path) -> None:
    assert not (installed_site / "packs" / "internal").exists()


# Resolver-specific text only: broad words such as "Connection" would also match a genuine
# build-hook failure and hide it behind a skip.
_NETWORK_MARKERS = ("Could not find a version", "No matching distribution", "Temporary failure in name resolution")
# A failure carrying any of these comes from this repository's own build hook, never from the network.
_HOOK_FAILURE_MARKERS = ("hatch_build", "PACK_")


def _is_network_unavailable(stderr: str) -> bool:
    if any(marker in stderr for marker in _HOOK_FAILURE_MARKERS):
        return False
    return any(marker in stderr for marker in _NETWORK_MARKERS)


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("ERROR: Could not find a version that satisfies the requirement hatchling", True),
        ("ERROR: No matching distribution found for hatchling==1.31.0", True),
        ("WARNING: Temporary failure in name resolution", True),
        ("Max retries exceeded with url", False),
        ("Connection refused by the pack remote", False),
        ("hatch_build.py: PACK_SYNC_UNAVAILABLE ... Temporary failure in name resolution", False),
        ("PACK_DIGEST_MISMATCH while No matching distribution", False),
    ],
)
def test_network_skip_classifier_is_resolver_specific(stderr: str, expected: bool) -> None:
    assert _is_network_unavailable(stderr) is expected


@pytest.fixture(scope="module")
def editable_probe(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    """``pip install -e`` this checkout into a fresh venv and run the same probe there (T047)."""
    venv_dir = tmp_path_factory.mktemp("editable-venv")
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, capture_output=True)
    python = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-e", str(_REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=420,
    )
    if install.returncode != 0 and _is_network_unavailable(install.stderr):
        pytest.skip("editable install needs the package index (build backend and dependencies); network unavailable")
    assert install.returncode == 0, install.stderr[-2000:]
    env = {key: value for key, value in os.environ.items() if not key.startswith(("SPEC_KITTY", "PYTHONPATH"))}
    result = subprocess.run([str(python), "-c", _PROBE], cwd=venv_dir, env=env, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    payload: dict[str, object] = json.loads(result.stdout.strip().splitlines()[-1])
    return payload


def test_editable_install_resolves_the_pinned_built_in_tree(editable_probe: dict[str, object]) -> None:
    pin = load_pack_pin(_REPO_ROOT / "packs" / "built-in.source.yaml")
    assert Path(str(editable_probe["root"])).resolve() == (_REPO_ROOT / "packs" / "built-in").resolve()
    assert Path(str(editable_probe["charter"])).resolve().is_relative_to((_REPO_ROOT / "src").resolve())
    assert editable_probe["digest"] == pin.tree_digest.value
