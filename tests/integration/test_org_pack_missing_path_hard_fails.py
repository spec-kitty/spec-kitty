"""Org pack missing-path hard-fail ATDD (Slice F WP06).

Scenario 1 exception path / FR-004: when an operator configures an
``charter_packs.org.packs`` entry whose ``local_path`` does not exist, the
runtime hard-fails with a named, operator-actionable error.

Mirrors Mission B FR-015 (missing org pack hard-fail). No silent fallback.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

pytestmark = [pytest.mark.integration]


@pytest.fixture
def tmp_repo_with_dangling_pack(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: acme-compliance
                    local_path: {tmp_path}/does-not-exist/dangling-pack
            """
        )
    )
    return tmp_path


def test_org_pack_with_missing_local_path_raises_named_error(
    tmp_repo_with_dangling_pack: Path,
) -> None:
    """FR-004 — missing ``local_path`` raises ``OrgPackMissingError`` whose
    message names the pack and the configured path."""
    from charter.drg import OrgPackMissingError
    from charter.activation.drg_activation import load_org_drg

    with pytest.raises(OrgPackMissingError) as exc_info:
        load_org_drg(tmp_repo_with_dangling_pack)

    msg = str(exc_info.value)
    assert "acme-compliance" in msg, (
        "operator-actionable error must name the configured pack"
    )
    assert "dangling-pack" in msg, (
        "operator-actionable error must echo the configured path"
    )
    # FR-004 binding: no silent fallback. The exception type matters.
    assert isinstance(exc_info.value, OrgPackMissingError)
