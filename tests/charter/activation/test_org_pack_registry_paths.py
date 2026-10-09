"""Tests for the org pack registry (``charter.offering.drg.org_pack_config``).

Moved from ``tests/specify_cli/doctrine/test_config.py`` (mission
``charter-pack-cutover-01M491G6``, FR-010): the registry half. Covers:

* Load: multi-pack, legacy single, absent key, no file, duplicate names,
  tilde expansion.
* Save: new block, merge with existing ``vcs``/``agents`` keys.
* ``resolve_org_roots`` ordering.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

from charter.offering.drg.org_pack_config import (
    OrgPackConfig,
    PackRegistry,
    load_pack_registry,
    resolve_org_roots,
    save_pack_registry,
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
            doctrine:
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

    def test_load_legacy_single_pack(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            doctrine:
              org:
                local_path: /opt/legacy
                source_type: https
                url: https://example.com/bundle.tar.gz
            """,
        )
        registry = load_pack_registry(tmp_path)
        assert len(registry.packs) == 1
        only = registry.packs[0]
        assert only.name == "default"
        assert only.local_path == Path("/opt/legacy")
        assert only.source_type == "https"

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
            doctrine:
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
            doctrine:
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
            doctrine:
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
            doctrine:
              org:
                packs:
                  - name: acme
                    local_path: {pack_dir}
            """,
        )

        assert [pack.name for pack in load_pack_registry(tmp_path).packs] == ["acme"]
        assert [fragment.pack_name for fragment in load_org_drg(tmp_path)] == ["acme"]
        assert [name for name, _path in _enumerate_org_pack_paths(tmp_path)] == ["acme"]

    def test_legacy_top_level_config_visible_to_all_org_pack_consumers(self, tmp_path: Path) -> None:
        """Legacy ``organisation_packs`` is read through the same shared parser."""
        from charter.activation.org_pack_discovery import _enumerate_org_pack_paths
        from charter.activation.drg_activation import load_org_drg

        pack_dir = tmp_path / "legacy-acme"
        (pack_dir / "drg").mkdir(parents=True)
        (pack_dir / "drg" / "fragment.yaml").write_text(
            "nodes: []\nedges: []\n",
            encoding="utf-8",
        )
        _write_config(
            tmp_path,
            f"""
            organisation_packs:
              - name: acme
                source: local_path
                path: {pack_dir}
            """,
        )

        with pytest.warns(DeprecationWarning, match="organisation_packs"):
            assert [pack.name for pack in load_pack_registry(tmp_path).packs] == ["acme"]
        with pytest.warns(DeprecationWarning, match="organisation_packs"):
            assert [fragment.pack_name for fragment in load_org_drg(tmp_path)] == ["acme"]
        with pytest.warns(DeprecationWarning, match="organisation_packs"):
            assert [name for name, _path in _enumerate_org_pack_paths(tmp_path)] == ["acme"]

    def test_legacy_organisation_packs_env_var_indirection(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T004: legacy ``organisation_packs[].path`` inherits env-var
        indirection through the shared ``OrgPackConfig`` constructor — no
        parallel expansion logic."""
        pack_dir = tmp_path / "legacy-acme"
        pack_dir.mkdir()
        monkeypatch.setenv("SPEC_KITTY_PACK_HOME", str(tmp_path))
        _write_config(
            tmp_path,
            """
            organisation_packs:
              - name: acme
                source: local_path
                path: ${SPEC_KITTY_PACK_HOME}/legacy-acme
            """,
        )

        with pytest.warns(DeprecationWarning, match="organisation_packs"):
            registry = load_pack_registry(tmp_path)
        assert len(registry.packs) == 1
        pack = registry.packs[0]
        # Stored value stays literal (unexpanded).
        assert str(pack.local_path) == "${SPEC_KITTY_PACK_HOME}/legacy-acme"
        # Resolution-time expansion matches the canonical-shape behaviour.
        assert pack.effective_root(tmp_path) == pack_dir.resolve(strict=False)


# ----------------------------------------------------------------------
# save_pack_registry
# ----------------------------------------------------------------------
class TestSavePackRegistry:
    def test_save_config_new_block(self, tmp_path: Path) -> None:
        registry = PackRegistry(
            packs=[
                OrgPackConfig(
                    name="security",
                    local_path=Path("/opt/sec"),
                    source_type="git",
                    url="git@example.com:sec.git",
                ),
            ]
        )
        save_pack_registry(tmp_path, registry)

        data = yaml.safe_load((tmp_path / ".kittify" / "config.yaml").read_text())
        assert data["charter_packs"]["org"]["packs"] == [
            {
                "name": "security",
                "local_path": "/opt/sec",
                "source_type": "git",
                "url": "git@example.com:sec.git",
            }
        ]

    def test_save_config_merge(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            vcs:
              provider: github
            agents:
              available: [claude, codex]
            doctrine:
              other_setting: keep_me
            """,
        )
        registry = PackRegistry(packs=[OrgPackConfig(name="security", local_path=Path("/opt/sec"))])
        save_pack_registry(tmp_path, registry)

        data: dict[str, Any] = yaml.safe_load((tmp_path / ".kittify" / "config.yaml").read_text())
        assert data["vcs"] == {"provider": "github"}
        assert data["agents"] == {"available": ["claude", "codex"]}
        assert data["doctrine"]["other_setting"] == "keep_me"
        assert data["charter_packs"]["org"]["packs"][0]["name"] == "security"

    def test_round_trip(self, tmp_path: Path) -> None:
        original = PackRegistry(
            packs=[
                OrgPackConfig(name="a", local_path=Path("/opt/a"), source_type="git", url="git@x:a.git"),
                OrgPackConfig(name="b", local_path=Path("/opt/b")),
            ]
        )
        save_pack_registry(tmp_path, original)
        reloaded = load_pack_registry(tmp_path)
        assert reloaded.names() == ["a", "b"]
        assert reloaded.get("a").source_type == "git"
        assert reloaded.get("b").source_type is None


# ----------------------------------------------------------------------
# resolve_org_roots
# ----------------------------------------------------------------------
class TestResolveOrgRoots:
    def test_returns_ordered_paths(self, tmp_path: Path) -> None:
        _write_config(
            tmp_path,
            """
            doctrine:
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
