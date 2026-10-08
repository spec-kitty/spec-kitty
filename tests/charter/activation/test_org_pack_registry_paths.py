"""Tests for the org pack registry (``charter.offering.drg.org_pack_config``).

Moved from ``tests/specify_cli/doctrine/test_config.py`` (mission
``charter-pack-cutover-01M491G6``, FR-010): the registry half. Covers:

* Load: multi-pack, absent key, no file, duplicate names, tilde expansion
  (the retired keys are covered by
  ``tests/doctrine/drg/test_org_pack_config_cr04_charter_packs.py``).
* ``resolve_org_roots`` ordering.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.offering.drg.org_pack_config import (
    load_pack_registry,
    resolve_org_roots,
)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_config(repo_root: Path, body: str) -> Path:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "config.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# load_pack_registry
# ----------------------------------------------------------------------
class TestLoadPackRegistry:
    def test_load_packs_list(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            charter_packs:
              org:
                packs:
                  - name: security
                    local_path: /opt/sec
                    source_type: git
                    url: git@example.com:sec/charter.offering.git
                    ref: v1.0.0
                  - name: architecture
                    local_path: /opt/arch
            """,
        )
        registry = load_pack_registry(tmp_path)
        assert registry.names() == ["security", "architecture"]
        security = registry.get("security")
        assert security is not None
        assert security.source_type == "git"
        assert security.ref == "v1.0.0"

    def test_load_config_absent_key(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            agents:
              available: [claude]
            """,
        )
        registry = load_pack_registry(tmp_path)
        assert registry.packs == []

    def test_load_config_no_file(self, tmp_path: Path) -> None:
        registry = load_pack_registry(tmp_path)
        assert registry.packs == []

    def test_duplicate_pack_names(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            charter_packs:
              org:
                packs:
                  - name: security
                    local_path: /opt/sec1
                  - name: security
                    local_path: /opt/sec2
            """,
        )
        with pytest.warns(UserWarning, match="Duplicate pack names"):
            registry = load_pack_registry(tmp_path)
        assert registry.packs == []

    def test_tilde_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Tilde expansion happens at ``effective_root()`` resolution time
        (WP01 T001) — the stored ``local_path`` keeps the literal ``~`` form
        so config.yaml round-trips it unexpanded."""
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        _write_config(
            tmp_path,
            """
            charter_packs:
              org:
                packs:
                  - name: security
                    local_path: "~/.kittify/org/security/"
            """,
        )
        registry = load_pack_registry(tmp_path)
        pack = registry.packs[0]
        # Stored value is preserved literally (not eagerly expanded).
        assert str(pack.local_path) == "~/.kittify/org/security"
        # Resolution-time expansion still produces the expected absolute path.
        resolved = pack.effective_root(tmp_path)
        assert "~" not in str(resolved)
        assert str(resolved).startswith(str(fake_home))

    def test_empty_file_returns_empty_registry(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "")
        registry = load_pack_registry(tmp_path)
        assert registry.packs == []

    def test_unexpected_extra_field_yields_empty_registry(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            charter_packs:
              org:
                packs:
                  - name: sec
                    local_path: /opt/sec
                    bogus_field: oops
            """,
        )
        with pytest.warns(UserWarning, match="Invalid org-pack config"):
            registry = load_pack_registry(tmp_path)
        assert registry.packs == []

    def test_canonical_config_visible_to_all_org_pack_consumers(self, tmp_path: Path) -> None:
        """One canonical config shape must drive registry, DRG, and context paths."""
        from charter.activation.org_pack_discovery import _enumerate_org_pack_paths
        from charter.activation.drg_activation import load_org_drg

        pack_dir = tmp_path / "acme"
        (pack_dir / "drg").mkdir(parents=True)
        (pack_dir / "drg" / "fragment.yaml").write_text(
            "nodes: []\nedges: []\n",
            encoding="utf-8",
        )
        _write_config(
            tmp_path,
            f"""
            charter_packs:
              org:
                packs:
                  - name: acme
                    local_path: {pack_dir}
            """,
        )

        assert [pack.name for pack in load_pack_registry(tmp_path).packs] == ["acme"]
        assert [fragment.pack_name for fragment in load_org_drg(tmp_path)] == ["acme"]
        assert [name for name, _path in _enumerate_org_pack_paths(tmp_path)] == ["acme"]


# ----------------------------------------------------------------------
# resolve_org_roots
# ----------------------------------------------------------------------
class TestResolveOrgRoots:
    def test_returns_ordered_paths(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            charter_packs:
              org:
                packs:
                  - name: a
                    local_path: /opt/a
                  - name: b
                    local_path: /opt/b
            """,
        )
        roots = resolve_org_roots(tmp_path)
        assert roots == [Path("/opt/a"), Path("/opt/b")]

    def test_empty_when_unconfigured(self, tmp_path: Path) -> None:
        assert resolve_org_roots(tmp_path) == []
