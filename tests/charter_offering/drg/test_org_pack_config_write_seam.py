"""Write seam for the ``charter_packs.org.packs`` registry (#6267).

``register_org_pack`` / ``unregister_org_pack`` are the only writers of the
org-pack registry block. They read the existing config strictly (an unreadable
or malformed org block is never rewritten), mutate only that list, and write
through :func:`kernel.atomic.atomic_write` with the same round-trip YAML dumper
``.kittify/config.yaml`` itself is written with — so comments, quoting, key
order and every unrelated section survive byte-for-byte.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.org_pack_config import (
    OrgPackConfig,
    load_pack_registry,
    register_org_pack,
    unregister_org_pack,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_COMMENTED_CONFIG = """\
# Project configuration, hand-maintained comments must survive a rewrite.
vcs:
  type: git
agents:
  available:
  - claude
  - codex
  auto_commit: false
# The org layer is optional; this comment must survive too.
charter_packs:
  org:
    packs:
    - name: existing
      local_path: packs/existing
      source_type: git
      url: https://example.com/existing.git
      ref: v1.0.0
"""


def _write_config(repo_root: Path, text: str) -> Path:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    _write_config(tmp_path, _COMMENTED_CONFIG)
    return tmp_path


def _local_pack(name: str = "acme", local_path: str = "packs/acme") -> OrgPackConfig:
    return OrgPackConfig(name=name, local_path=Path(local_path))


def test_register_appends_entry_and_preserves_comments(project: Path) -> None:
    replaced = register_org_pack(project, _local_pack())

    assert replaced is False
    text = (project / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "# Project configuration, hand-maintained comments must survive a rewrite." in text
    assert "# The org layer is optional; this comment must survive too." in text
    assert load_pack_registry(project).names() == ["existing", "acme"]


def test_register_is_idempotent_only_with_replace(project: Path) -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_org_pack(project, _local_pack(name="existing", local_path="packs/other"))

    # Positive control on the same fixture: replace=True rewrites the entry in place.
    replaced = register_org_pack(project, _local_pack(name="existing", local_path="packs/other"), replace=True)

    assert replaced is True
    registry = load_pack_registry(project)
    assert registry.names() == ["existing"]
    entry = registry.get("existing")
    assert entry is not None
    assert entry.local_path == Path("packs/other")
    # Declaration order is untouched by a replacement.
    assert registry.names() == ["existing"]


def test_replace_keeps_declaration_order(project: Path) -> None:
    register_org_pack(project, _local_pack())
    register_org_pack(
        project,
        _local_pack(
            name="existing",
            local_path="packs/elsewhere",
        ),
        replace=True,
    )

    assert load_pack_registry(project).names() == ["existing", "acme"]


def test_register_then_unregister_restores_bytes(project: Path) -> None:
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    register_org_pack(project, _local_pack())
    assert config_path.read_bytes() != before

    unregister_org_pack(project, "acme")

    assert config_path.read_bytes() == before


def test_register_then_unregister_restores_bytes_the_cli_wrote(tmp_path: Path) -> None:
    """Add-then-remove must be byte-exact on a config the CLI itself dumped.

    The CLI's own config writer (``specify_cli.core.agent_config``) uses plain
    ``YAML()``, so an over-width scalar is re-emitted wrapped, with ruamel's
    trailing-space artifact after the key. Dumping through any other settings (a
    wider width, or the whitespace normalization in
    ``kernel.yaml_io.serialize_mapping``) rewrites that span on the *add* and can
    never restore it on the *remove*.
    """
    from io import StringIO

    from ruamel.yaml import YAML

    document = {
        "vcs": {"type": "git"},
        "charter_packs": {
            "org": {
                "packs": [
                    {
                        "name": "existing",
                        "local_path": "packs/existing",
                        "url": "https://example.com/a/very/long/repository/path/that/goes/past/eighty/columns/doctrine.git",
                        "ref": "v1.0.0",
                    }
                ]
            }
        },
    }
    stream = StringIO()
    cli_yaml = YAML()
    cli_yaml.preserve_quotes = True
    cli_yaml.dump(document, stream)
    config_path = _write_config(tmp_path, stream.getvalue())
    before = config_path.read_bytes()
    assert "url: \n" in before.decode("utf-8")  # the artifact this test exists for

    register_org_pack(tmp_path, _local_pack())
    unregister_org_pack(tmp_path, "acme")

    assert config_path.read_bytes() == before


def test_unregister_removes_exactly_one_entry(project: Path) -> None:
    register_org_pack(project, _local_pack())

    removed = unregister_org_pack(project, "acme")

    assert removed.name == "acme"
    assert load_pack_registry(project).names() == ["existing"]


def test_unregister_refuses_when_the_raw_block_vanished(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A concurrent rewrite must fail loudly, never report a removal it did not do."""
    from charter.offering.drg import org_pack_config as module

    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()
    monkeypatch.setattr(module, "_find_org_packs_container", lambda _data: None)

    with pytest.raises(ValueError, match="no longer declares"):
        unregister_org_pack(project, "existing")

    assert config_path.read_bytes() == before


def test_unregister_refuses_when_the_raw_entry_vanished(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same guard for a registry entry the raw document no longer carries."""
    from charter.offering.drg import org_pack_config as module

    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()
    monkeypatch.setattr(module, "_named_entry_index", lambda _packs, _name: None)

    with pytest.raises(ValueError, match="carries no matching entry"):
        unregister_org_pack(project, "existing")

    assert config_path.read_bytes() == before


def test_unregister_unknown_name_lists_configured_packs(project: Path) -> None:
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    with pytest.raises(ValueError, match="not registered") as excinfo:
        unregister_org_pack(project, "missing")

    assert "existing" in str(excinfo.value)
    assert config_path.read_bytes() == before


def test_unregister_last_entry_drops_empty_scaffolding(tmp_path: Path) -> None:
    _write_config(tmp_path, _COMMENTED_CONFIG)
    register_org_pack(tmp_path, _local_pack())
    unregister_org_pack(tmp_path, "existing")
    unregister_org_pack(tmp_path, "acme")

    text = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "charter_packs" not in text
    assert load_pack_registry(tmp_path).names() == []


def test_register_creates_block_when_absent(tmp_path: Path) -> None:
    _write_config(tmp_path, "vcs:\n  type: git\n")

    register_org_pack(tmp_path, _local_pack())

    text = (tmp_path / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    assert "vcs:" in text
    assert load_pack_registry(tmp_path).names() == ["acme"]


def test_register_stores_templated_local_path_verbatim(tmp_path: Path) -> None:
    _write_config(tmp_path, "vcs:\n  type: git\n")

    register_org_pack(tmp_path, OrgPackConfig(name="acme", local_path=Path("${SPEC_KITTY_PACK_HOME}/acme")))

    entry = load_pack_registry(tmp_path).get("acme")
    assert entry is not None
    assert str(entry.local_path) == "${SPEC_KITTY_PACK_HOME}/acme"


@pytest.mark.parametrize(
    "text",
    [
        "charter_packs:\n  org:\n    packs:\n    - name: dup\n      local_path: a\n    - name: dup\n      local_path: b\n",
        "charter_packs:\n  org:\n    local_path: packs/legacy\n",
        "charter_packs: not-a-mapping\n",
    ],
    ids=["duplicate-names", "unnamed-single-pack", "section-not-a-mapping"],
)
def test_register_fails_closed_on_unreadable_org_config(tmp_path: Path, text: str) -> None:
    config_path = _write_config(tmp_path, text)
    before = config_path.read_bytes()

    with pytest.raises(ValueError, match="Invalid org-pack config"):
        register_org_pack(tmp_path, _local_pack())

    assert config_path.read_bytes() == before


def test_register_fails_closed_on_unparseable_yaml(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "charter_packs: [unclosed\n")
    before = config_path.read_bytes()

    with pytest.raises(ValueError, match="Failed to read"):
        register_org_pack(tmp_path, _local_pack())

    assert config_path.read_bytes() == before


def test_write_failure_leaves_original_bytes(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.offering.drg import org_pack_config as module

    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(module, "atomic_write", boom)

    with pytest.raises(OSError, match="disk full"):
        register_org_pack(project, _local_pack())

    assert config_path.read_bytes() == before
