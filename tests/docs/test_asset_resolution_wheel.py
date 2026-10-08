"""SC-003 — the clean-environment wheel proof for asset resolution (WP05, T028).

**Why this test exists and why an in-repo test cannot replace it.** In the
development checkout, ``resolve_offering_root()`` /
``AssetRepository._default_built_in_dir()`` fall back to the source tree, so an
in-repo resolution of a shipped asset *always* succeeds and proves nothing about
whether the asset is addressable from a real installation. SC-003 is therefore
falsifiable **only** from a built wheel installed into a fresh environment with
the repository root absent from every resolution input.

This harness:

1. builds ``spec_kitty_cli-*.whl`` from the repository (shared session
   ``installed_wheel_venv`` fixture — ``tests/conftest.py``),
2. installs it into a throwaway virtualenv,
3. invokes the installed ``spec-kitty charter pack asset path`` console entry point
   from a working directory **outside** the repository, with ``PYTHONPATH`` and
   the source-template pointer scrubbed from the child environment, and
4. asserts the shipped asset resolves to a path **inside the venv's
   site-packages** and **not** under the repository root — i.e. it was resolved
   from packaged data, exactly as a downstream operator would experience it.

If the addressing regresses (e.g. resolution silently reaches back through a
repo path), step 4 fails: the resolved path escapes the venv or the command
exits non-zero. This is the criterion's only runnable falsifier.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

# non_sandbox: builds and installs a wheel (>30s). distribution: requires a real
# wheel install with no SPEC_KITTY_TEMPLATE_ROOT pointing back at the source tree.
pytestmark = [pytest.mark.slow, pytest.mark.distribution, pytest.mark.non_sandbox]

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The shipped asset identifier under test (its blob is the structural docs
#: lint). Present in the built-in tier of every installation.
_SHIPPED_ASSET_ID = "common-docs-structural-lint"


def _spec_kitty_script(venv_dir: Path) -> Path:
    """Return the ``spec-kitty`` console entry point inside *venv_dir*."""
    posix = venv_dir / "bin" / "spec-kitty"
    if posix.exists():
        return posix
    return venv_dir / "Scripts" / "spec-kitty.exe"


def _clean_child_env() -> dict[str, str]:
    """Return a child environment with every repo-root back-channel removed.

    Scrubbing ``PYTHONPATH`` and the ``SPEC_KITTY_TEMPLATE_ROOT`` /
    ``SPEC_KITTY_TEST_MODE`` pointers guarantees the installed CLI cannot reach
    the source tree through an inherited variable — the wheel's packaged data is
    the only resolution input left.
    """
    import os

    env = os.environ.copy()
    for var in (
        "PYTHONPATH",
        "SPEC_KITTY_TEMPLATE_ROOT",
        "SPEC_KITTY_TEST_MODE",
        "SPEC_KITTY_CLI_VERSION",
    ):
        env.pop(var, None)
    # Deterministic, colour-free output so path assertions are exact (#2632).
    env["NO_COLOR"] = "1"
    env.pop("FORCE_COLOR", None)
    return env


def test_shipped_asset_resolves_from_clean_wheel_install(
    installed_wheel_venv: dict[str, Path],
    tmp_path: Path,
) -> None:
    """The shipped asset resolves from packaged data with the repo root absent."""
    venv_dir = installed_wheel_venv["venv_dir"]
    script = _spec_kitty_script(venv_dir)
    assert script.exists(), f"spec-kitty entry point missing in venv: {script}"

    # cwd is a fresh temp dir *outside* the repository, so ``locate_project_root``
    # finds no ``.kittify`` up-tree and the resolver runs on the built-in tier
    # only — no project/org overlay, no repo path.
    outside = tmp_path / "clean-cwd"
    outside.mkdir()

    result = subprocess.run(
        [str(script), "charter", "pack", "asset", "path", _SHIPPED_ASSET_ID],
        cwd=str(outside),
        env=_clean_child_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    resolved = Path(result.stdout.strip())
    assert resolved.is_file(), f"resolved asset path does not exist: {resolved}"
    assert resolved.name == "docs_structural_lint.py"

    # The whole point of SC-003: resolution came from the *installed package*,
    # not the repository source tree. The venv holds the wheel's site-packages;
    # the repo root must not appear anywhere in the resolved path.
    resolved_str = str(resolved.resolve())
    assert str(venv_dir.resolve()) in resolved_str, (
        f"expected resolution inside the venv {venv_dir}, got {resolved_str}"
    )
    assert str(REPO_ROOT.resolve()) not in resolved_str, (
        f"resolution leaked back through the repository root: {resolved_str}"
    )

    # SC-003 ran — record it (the criterion's runnable artefact executed).
    print(  # noqa: T201 — intentional run-marker for the SC-003 proof
        f"[SC-003] resolved {_SHIPPED_ASSET_ID} from clean wheel install: {resolved_str}"
    )


def test_unknown_asset_id_exits_nonzero_from_clean_wheel_install(
    installed_wheel_venv: dict[str, Path],
    tmp_path: Path,
) -> None:
    """An unknown id fails closed (A-7) even from the installed console entry."""
    venv_dir = installed_wheel_venv["venv_dir"]
    script = _spec_kitty_script(venv_dir)
    outside = tmp_path / "clean-cwd-unknown"
    outside.mkdir()

    result = subprocess.run(
        [str(script), "charter", "pack", "asset", "path", "no-such-asset-xyz"],
        cwd=str(outside),
        env=_clean_child_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "no-such-asset-xyz" in (result.stdout + result.stderr)
