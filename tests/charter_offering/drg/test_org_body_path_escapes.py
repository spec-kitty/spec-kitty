"""An authored org fragment node whose ``body_path`` escapes its pack is a finding (#6418).

``spec-kitty doctor charter-packs`` reported an org pack healthy (RC=0) when its
``drg/fragment.yaml`` declared a node with ``body_path: ../../../../etc/hostname``
or ``/etc/hostname``. The predicate under test, :func:`find_body_path_escapes`,
judges each *authored* node through the one containment authority
(``resolve_relative_path_within_root``); :func:`find_org_body_path_escapes`
pairs every loaded fragment with its pack's effective root from the registry.

RED before the fix: neither name existed, so this module failed to import.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from charter.activation.drg_activation import find_org_body_path_escapes, load_org_drg
from charter.offering.drg.org_pack_loader import BodyPathEscape, find_body_path_escapes, load_org_pack

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PACK_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


def _make_pack(pack_root: Path, nodes: list[dict[str, str]], name: str = "acme") -> Path:
    """Write a minimal org pack (``pack.yaml`` + ``drg/fragment.yaml``) under *pack_root*."""
    (pack_root / "drg").mkdir(parents=True, exist_ok=True)
    (pack_root / "pack.yaml").write_text(f"pack_id: {_PACK_ID}\nname: {name}\npack_level: org\n", encoding="utf-8")
    (pack_root / "drg" / "fragment.yaml").write_text(yaml.safe_dump({"nodes": nodes, "edges": []}), encoding="utf-8")
    return pack_root


def _escapes(pack_root: Path, *body_paths: str | None) -> list[BodyPathEscape]:
    nodes: list[dict[str, str]] = []
    for index, body_path in enumerate(body_paths):
        node = {"id": f"node-{index}", "kind": "assets", "title": f"Node {index}"}
        if body_path is not None:
            node["body_path"] = body_path
        nodes.append(node)
    _make_pack(pack_root, nodes)
    return find_body_path_escapes(load_org_pack("acme", pack_root, 1), pack_root)


def test_dot_dot_body_path_is_an_escape(tmp_path: Path) -> None:
    escapes = _escapes(tmp_path / "pack", "../../../../etc/hostname")

    assert len(escapes) == 1
    escape = escapes[0]
    assert (escape.pack, escape.node, escape.kind, escape.body_path) == ("acme", "node-0", "assets", "../../../../etc/hostname")
    assert ".." in escape.reason
    assert escape.message == (f"org pack 'acme': node 'node-0' (assets) body_path '../../../../etc/hostname' escapes the pack root: {escape.reason}")
    assert escape.as_dict() == {
        "pack": "acme",
        "node": "node-0",
        "kind": "assets",
        "body_path": "../../../../etc/hostname",
        "reason": escape.reason,
    }


def test_absolute_body_path_is_an_escape(tmp_path: Path) -> None:
    escapes = _escapes(tmp_path / "pack", "/etc/hostname")

    assert [e.body_path for e in escapes] == ["/etc/hostname"]
    assert "absolute" in escapes[0].reason


@pytest.mark.parametrize("body_path", ["C:\\Windows\\x", "..\\x", "\\\\server\\share\\x"])
def test_windows_form_escapes_on_every_os(tmp_path: Path, body_path: str) -> None:
    escapes = _escapes(tmp_path / "pack", body_path)

    assert [e.body_path for e in escapes] == [body_path]


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="os.symlink unavailable")
def test_symlink_resolving_outside_the_pack_is_an_escape(tmp_path: Path) -> None:
    pack_root = tmp_path / "pack"
    outside = tmp_path / "outside"
    outside.mkdir()
    pack_root.mkdir()
    try:
        (pack_root / "inside.md").symlink_to(outside)
    except OSError as exc:  # pragma: no cover - platform without symlink privilege
        pytest.skip(f"cannot create symlink: {exc}")

    escapes = _escapes(pack_root, "inside.md")

    assert [e.body_path for e in escapes] == ["inside.md"]
    assert "outside" in escapes[0].reason


@pytest.mark.parametrize("materialise", [False, True], ids=["missing-target", "present-target"])
def test_contained_body_path_is_not_an_escape(tmp_path: Path, materialise: bool) -> None:
    pack_root = tmp_path / "pack"
    if materialise:
        (pack_root / "bodies").mkdir(parents=True)
        (pack_root / "bodies" / "x.md").write_text("body\n", encoding="utf-8")

    assert _escapes(pack_root, "bodies/x.md") == []


def test_node_without_body_path_is_not_checked(tmp_path: Path) -> None:
    assert _escapes(tmp_path / "pack", None) == []


def test_discovered_artifact_node_is_not_checked(tmp_path: Path) -> None:
    """Only authored fragment nodes are judged; a discovered node's validator owns its body."""
    pack_root = _make_pack(tmp_path / "pack", [])
    (pack_root / "directives").mkdir()
    (pack_root / "directives" / "foo.directive.yaml").write_text(yaml.safe_dump({"id": "FOO_001", "title": "Foo", "body_path": "../../x"}), encoding="utf-8")
    fragment = load_org_pack("acme", pack_root, 1)
    # Guard the premise: the discovered node really carries the escaping string.
    assert [n.body_path for n in fragment.nodes] == ["../../x"]

    assert find_body_path_escapes(fragment, pack_root) == []


def test_every_escaping_node_is_reported_once_in_authored_order(tmp_path: Path) -> None:
    escapes = _escapes(tmp_path / "pack", "/etc/a", "bodies/ok.md", "../b", None, "../../c")

    assert [(e.node, e.body_path) for e in escapes] == [("node-0", "/etc/a"), ("node-2", "../b"), ("node-4", "../../c")]


def _write_registry(repo: Path, packs: list[dict[str, str]]) -> None:
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text(yaml.safe_dump({"charter_packs": {"org": {"packs": packs}}}), encoding="utf-8")


def test_registry_aware_check_names_only_the_escaping_pack(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    bad = _make_pack(tmp_path / "bad", [{"id": "team-asset", "kind": "assets", "body_path": "../../../../etc/hostname"}], name="bad")
    good = _make_pack(tmp_path / "good", [{"id": "fine", "kind": "assets", "body_path": "bodies/fine.md"}], name="good")
    _write_registry(repo, [{"name": "bad", "local_path": str(bad)}, {"name": "good", "local_path": str(good)}])

    escapes = find_org_body_path_escapes(repo, load_org_drg(repo))

    assert [(e.pack, e.node) for e in escapes] == [("bad", "team-asset")]


def test_registry_aware_check_uses_the_subdir_effective_root(tmp_path: Path) -> None:
    """With ``subdir`` set, containment is judged against the effective root, not the checkout."""
    repo = tmp_path / "repo"
    checkout = tmp_path / "checkout"
    # ``../sibling.md`` stays inside the checkout but escapes the ``inner`` effective root.
    _make_pack(checkout / "inner", [{"id": "n", "kind": "assets", "body_path": "../sibling.md"}, {"id": "ok", "kind": "assets", "body_path": "b.md"}])
    _write_registry(repo, [{"name": "acme", "local_path": str(checkout), "subdir": "inner"}])

    escapes = find_org_body_path_escapes(repo, load_org_drg(repo))

    assert [(e.pack, e.node) for e in escapes] == [("acme", "n")]


def test_registry_aware_check_with_symlink_in_effective_root(tmp_path: Path) -> None:
    """A symlink resolving into the checkout but outside the subdir root escapes too."""
    if not hasattr(os, "symlink"):  # pragma: no cover
        pytest.skip("os.symlink unavailable")
    repo = tmp_path / "repo"
    checkout = tmp_path / "checkout"
    pack_root = _make_pack(checkout / "inner", [{"id": "n", "kind": "assets", "body_path": "link.md"}])
    (checkout / "elsewhere.md").write_text("x\n", encoding="utf-8")
    try:
        (pack_root / "link.md").symlink_to(checkout / "elsewhere.md")
    except OSError as exc:  # pragma: no cover
        pytest.skip(f"cannot create symlink: {exc}")
    _write_registry(repo, [{"name": "acme", "local_path": str(checkout), "subdir": "inner"}])

    escapes = find_org_body_path_escapes(repo, load_org_drg(repo))

    assert [(e.pack, e.node) for e in escapes] == [("acme", "n")]
