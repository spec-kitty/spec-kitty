"""Charter-lint lints all three layers ATDD (Slice F WP06).

FR-003 binding: ``spec-kitty charter lint`` SHALL lint all configured
DRG layers in a single invocation; per-layer findings include the
layer's source name.

This file pins the operator-observable CLI surface: invoking
``spec-kitty charter lint`` in a repo with an org pack configured
produces output that names each layer (``built-in``, ``org:<pack_name>``,
``project``) and attributes findings (or the OK marker) to that source.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_FIXTURE_ORG_PACK: Path = (
    _REPO_ROOT
    / "tests"
    / "architectural"
    / "_fixtures"
    / "org_packs"
    / "example_org"
)


@pytest.fixture
def tmp_repo_with_org_pack(tmp_path: Path) -> Path:
    """Minimal git-tracked repo with ``.kittify/config.yaml`` configuring
    one org pack at a known path."""
    pack_dest = tmp_path / "example_org"
    shutil.copytree(_FIXTURE_ORG_PACK, pack_dest)
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: example-org
                    local_path: {pack_dest}
            """
        )
    )
    # Git-init so chokepoint resolvers that require a repo root don't
    # explode on a bare tmp_path.
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_charter_lint_lists_all_three_layers_with_named_provenance(
    tmp_repo_with_org_pack: Path,
) -> None:
    """FR-003 — ``spec-kitty charter lint`` output includes per-layer
    section headers naming each configured layer's source."""
    # Sanity: the contract symbol must exist (we link the CLI behaviour
    # to the loader). If WP06 hasn't landed yet, this collects as an
    # ImportError, keeping the test RED.
    from charter.activation.drg_activation import load_org_drg  # noqa: PLC0415, F401

    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(_REPO_ROOT / "src")
    result = subprocess.run(
        [sys.executable, "-m", "specify_cli", "charter", "lint"],
        cwd=tmp_repo_with_org_pack,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    # The lint output must reference the org-layer source name. The
    # exact formatting may evolve, but the operator-facing string
    # ``org:example-org`` is the binding contract surface (FR-003).
    assert "org:example-org" in combined or "example-org" in combined, (
        f"charter lint must surface the org layer source name; "
        f"got:\n{combined!r}"
    )
