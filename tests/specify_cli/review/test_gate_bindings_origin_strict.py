"""#4984/#6012: review gate-binding activation fails closed on an unfetched org pack.

``gate_bindings._activated_msc_urns`` is a governed decision surface: acting on a
silently-shortened org-pack chain would let a review proceed without the pack's
gate bindings. A declared-but-unfetched pack must raise, naming the pack and the
``spec-kitty charter fetch`` remedy.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from specify_cli.review import gate_bindings

pytestmark = [pytest.mark.fast, pytest.mark.regression]

_PACK = "unfetched-org-pack"


def _declare_unfetched_pack(repo_root: Path) -> None:
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: {_PACK}
                    local_path: never-fetched/{_PACK}
            """
        ),
        encoding="utf-8",
    )


def test_declared_but_unfetched_pack_fails_closed(tmp_path: Path) -> None:
    _declare_unfetched_pack(tmp_path)

    with pytest.raises(ValueError, match=_PACK) as excinfo:
        gate_bindings._activated_msc_urns(tmp_path, graph_loader=None, pack_resolver=lambda _root: None)

    assert "spec-kitty charter fetch" in str(excinfo.value)


def test_no_declared_pack_does_not_raise(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")

    urns = gate_bindings._activated_msc_urns(tmp_path, graph_loader=None, pack_resolver=lambda _root: None)

    assert isinstance(urns, frozenset)
