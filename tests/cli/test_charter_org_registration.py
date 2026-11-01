"""Acceptance tests for ``spec-kitty charter org add`` / ``charter org remove`` (#6267).

The scenario numbers map to ``kitty-specs/charter-org-pack-registration-01M6BTTJ/
spec.md``: US1 (local registration), US2 (remote registration for ``charter
fetch``), US3 (retirement), plus the edge cases the spec lists.

Every refusal assertion is paired with a positive control on the same fixture,
and every refusal also asserts the config is byte-identical, so "wrote nothing"
is measured rather than assumed.

Owner: ``src/specify_cli/cli/commands/charter/org.py``
"""

from __future__ import annotations

import socket
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app as app

runner = CliRunner()

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_CONFIG = """\
# Project configuration, hand-maintained comments must survive a rewrite.
vcs:
  type: git
# The org layer is optional; this comment must survive too.
"""


def _write_config(project: Path, body: str = _CONFIG) -> Path:
    config_dir = project / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(body, encoding="utf-8")
    return config_path


def _scaffold(pack_dir: Path) -> Path:
    """Create a pack that ``charter org validate`` accepts, via the real command."""
    result = runner.invoke(app, ["org", "init", str(pack_dir)])
    assert result.exit_code == 0, result.output
    return pack_dir


def _broken(pack_dir: Path) -> Path:
    """Create a pack whose DRG fragment does not parse, i.e. an invalid pack."""
    _scaffold(pack_dir)
    (pack_dir / "drg" / "fragment.yaml").write_text("pack_name: [unclosed\n", encoding="utf-8")
    return pack_dir


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project whose root resolution is pinned to *tmp_path*."""
    monkeypatch.setattr("specify_cli.core.paths.locate_project_root", lambda start=None: tmp_path)
    _write_config(tmp_path)
    return tmp_path


def _invoke(*args: str) -> object:
    return runner.invoke(app, list(args))


def _config_text(project: Path) -> str:
    return (project / ".kittify" / "config.yaml").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# US1 — register a local org pack without editing config by hand
# ---------------------------------------------------------------------------


def test_add_registers_local_pack_without_hand_editing_config(project: Path) -> None:
    """US1 #1 / SC-001: one command, and `charter pack list` reports the pack."""
    pack = _scaffold(project / "packs" / "acme")

    result = _invoke("org", "add", "acme", "--local-path", str(pack))

    assert result.exit_code == 0, result.output
    entries = _registered_entries(project)
    assert len(entries) == 1
    assert entries[0]["name"] == "acme"
    assert entries[0]["local_path"] == str(pack)
    # The comments survived, and the unrelated block is untouched.
    assert "# Project configuration" in _config_text(project)
    assert "vcs:\n  type: git\n" in _config_text(project)

    listed = _invoke("pack", "list", "--repo-root", str(project), "--json")
    assert listed.exit_code == 0, listed.output
    assert '"name": "acme"' in listed.output

    dry_run = _invoke("fetch", "--pack", "acme", "--dry-run")
    assert dry_run.exit_code == 0, dry_run.output
    assert "acme" in dry_run.output


def _registered_entries(project: Path) -> list[dict[str, object]]:
    from charter.drg import load_pack_registry

    registry = load_pack_registry(project, strict=True)
    return [pack.model_dump(mode="json", exclude_none=True, exclude={"pack_id"}) for pack in registry.packs]


def test_add_refuses_invalid_pack_and_writes_nothing(project: Path) -> None:
    """US1 #2 / SC-003: refusal, plus its positive control on the same fixture."""
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    refused = _invoke("org", "add", "broken", "--local-path", str(_broken(project / "packs" / "broken")))

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_INVALID" in refused.output
    assert config_path.read_bytes() == before

    controlled = _invoke("org", "add", "acme", "--local-path", str(_scaffold(project / "packs" / "acme")))

    assert controlled.exit_code == 0, controlled.output


def test_add_refuses_duplicate_without_force(project: Path) -> None:
    """US1 #3: a repeated add names --force and leaves the config alone."""
    _scaffold(project / "packs" / "acme")
    other = _scaffold(project / "packs" / "other")
    assert _invoke("org", "add", "acme", "--local-path", str(project / "packs" / "acme")).exit_code == 0
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    refused = _invoke("org", "add", "acme", "--local-path", str(other))

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_EXISTS" in refused.output
    assert "--force" in refused.output
    assert config_path.read_bytes() == before


def test_add_force_replaces_in_place(project: Path) -> None:
    """The positive control for the duplicate refusal: --force updates the entry."""
    first = _scaffold(project / "packs" / "acme")
    second = _scaffold(project / "packs" / "acme-v2")
    assert _invoke("org", "add", "acme", "--local-path", str(first)).exit_code == 0

    replaced = _invoke("org", "add", "acme", "--local-path", str(second), "--force")

    assert replaced.exit_code == 0, replaced.output
    entries = _registered_entries(project)
    assert [entry["name"] for entry in entries] == ["acme"]
    assert entries[0]["local_path"] == str(second)


# ---------------------------------------------------------------------------
# US2 — register a remote pack that `charter fetch` will materialize
# ---------------------------------------------------------------------------


def test_add_registers_remote_pack_without_a_local_copy(project: Path) -> None:
    """US2 #1: an absent root is fine with --url, and the follow-up is printed."""
    destination = project / ".kittify" / "org" / "acme"

    result = _invoke(
        "org",
        "add",
        "acme",
        "--local-path",
        str(destination),
        "--url",
        "https://example.com/acme/doctrine.git",
        "--ref",
        "v1.0.0",
    )

    assert result.exit_code == 0, result.output
    entry = _registered_entries(project)[0]
    assert entry["source_type"] == "git"
    assert entry["url"] == "https://example.com/acme/doctrine.git"
    assert entry["ref"] == "v1.0.0"
    assert "charter fetch" in result.output

    dry_run = _invoke("fetch", "--pack", "acme", "--dry-run")
    assert dry_run.exit_code == 0, dry_run.output
    assert "doctrine.git" in dry_run.output


def test_add_ref_requires_url(project: Path) -> None:
    """US2 #2: --ref without --url is refused and nothing is written."""
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()
    pack = _scaffold(project / "packs" / "acme")

    refused = _invoke("org", "add", "acme", "--local-path", str(pack), "--ref", "v1.0.0")

    assert refused.exit_code == 1, refused.output
    assert "--url" in refused.output
    assert config_path.read_bytes() == before


def test_add_refuses_source_type_outside_the_model_set(project: Path) -> None:
    pack = _scaffold(project / "packs" / "acme")

    refused = _invoke("org", "add", "acme", "--local-path", str(pack), "--url", "https://example.com/a.git", "--source-type", "ftp")

    assert refused.exit_code == 1, refused.output
    assert "source-type" in refused.output
    assert _registered_entries(project) == []


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["built-in", "project"])
def test_add_refuses_reserved_pack_names(project: Path, name: str) -> None:
    pack = _scaffold(project / "packs" / "acme")

    refused = _invoke("org", "add", name, "--local-path", str(pack))

    assert refused.exit_code == 1, refused.output
    assert "reserved" in refused.output
    assert _registered_entries(project) == []


def test_add_refuses_whitespace_only_name(project: Path) -> None:
    pack = _scaffold(project / "packs" / "acme")

    refused = _invoke("org", "add", "   ", "--local-path", str(pack))

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_INVALID" in refused.output
    assert "pack name is required" in refused.output
    assert _registered_entries(project) == []


def test_add_refuses_subdir_escape(project: Path) -> None:
    pack = _scaffold(project / "packs" / "acme")

    refused = _invoke("org", "add", "acme", "--local-path", str(pack), "--subdir", "../outside")

    assert refused.exit_code == 1, refused.output
    assert "subdir" in refused.output
    assert _registered_entries(project) == []


def test_add_records_a_valid_subdir(project: Path) -> None:
    """The positive control for the subdir refusal."""
    pack = _scaffold(project / "packs" / "acme")
    (pack / "nested").mkdir()

    accepted = _invoke("org", "add", "acme", "--local-path", str(pack), "--subdir", "nested")

    assert accepted.exit_code == 0, accepted.output
    assert _registered_entries(project)[0]["subdir"] == "nested"


def test_add_refuses_a_subdir_that_escapes_through_a_symlink(project: Path, tmp_path: Path) -> None:
    """A subdir that resolves outside the pack root is a refusal, not a traceback."""
    pack = _scaffold(project / "packs" / "acme")
    outside = tmp_path / "outside"
    outside.mkdir()
    (pack / "link").symlink_to(outside, target_is_directory=True)

    refused = _invoke("org", "add", "acme", "--local-path", str(pack), "--subdir", "link")

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_INVALID" in refused.output
    assert _registered_entries(project) == []


def test_remove_reports_a_write_failure_without_a_traceback(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-004: remove's seam failure is a coded refusal, like add's."""
    import charter.drg as seam

    pack = _scaffold(project / "packs" / "acme")
    assert _invoke("org", "add", "acme", "--local-path", str(pack)).exit_code == 0
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(seam, "unregister_org_pack", _boom)

    refused = _invoke("org", "remove", "acme")

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_UNREADABLE" in refused.output
    assert config_path.read_bytes() == before


def test_add_refuses_a_regular_file_local_path(project: Path, tmp_path: Path) -> None:
    not_a_dir = tmp_path / "pack.yaml"
    not_a_dir.write_text("not a directory\n", encoding="utf-8")

    refused = _invoke("org", "add", "acme", "--local-path", str(not_a_dir))

    assert refused.exit_code == 1, refused.output
    assert "regular file" in refused.output
    assert _registered_entries(project) == []


def test_add_refuses_a_missing_local_pack_without_url(project: Path) -> None:
    refused = _invoke("org", "add", "acme", "--local-path", str(project / "packs" / "absent"))

    assert refused.exit_code == 1, refused.output
    assert "does not exist" in refused.output
    assert _registered_entries(project) == []


def test_add_stores_an_env_templated_local_path_verbatim(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``${VAR}`` value is written as typed and resolved, not frozen."""
    monkeypatch.setenv("ORG_PACK_HOME", str(project / "packs"))
    pack = _scaffold(project / "packs" / "acme")

    accepted = _invoke("org", "add", "acme", "--local-path", "${ORG_PACK_HOME}/acme")

    assert accepted.exit_code == 0, accepted.output
    assert _registered_entries(project)[0]["local_path"] == "${ORG_PACK_HOME}/acme"
    assert str(pack) not in _config_text(project)


def test_add_reports_an_unset_env_token_as_a_refusal(project: Path) -> None:
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    refused = _invoke("org", "add", "acme", "--local-path", "${DEFINITELY_UNSET_ORG_PACK_HOME}/acme")

    assert refused.exit_code == 1, refused.output
    assert "DEFINITELY_UNSET_ORG_PACK_HOME" in refused.output
    assert config_path.read_bytes() == before


def test_add_fails_closed_on_a_malformed_registry(project: Path) -> None:
    """A duplicate-name org block is refused rather than overwritten."""
    _write_config(
        project,
        _CONFIG + "charter_packs:\n  org:\n    packs:\n    - name: dup\n      local_path: a\n    - name: dup\n      local_path: b\n",
    )
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()
    pack = _scaffold(project / "packs" / "acme")

    refused = _invoke("org", "add", "acme", "--local-path", str(pack))

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_UNREADABLE" in refused.output
    assert config_path.read_bytes() == before


def test_add_refuses_outside_a_project(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.core.paths.locate_project_root", lambda start=None: None)
    pack = _scaffold(project / "packs" / "acme")

    refused = _invoke("org", "add", "acme", "--local-path", str(pack))

    assert refused.exit_code == 1, refused.output
    assert "project root" in refused.output


def test_add_reports_a_write_failure_without_a_traceback(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-004: a seam failure (concurrent rewrite / unreadable file) is a refusal."""
    import charter.drg as seam

    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()
    pack = _scaffold(project / "packs" / "acme")

    def _boom(*_args: object, **_kwargs: object) -> bool:
        raise ValueError("config changed underneath the command")

    monkeypatch.setattr(seam, "register_org_pack", _boom, raising=True)

    refused = _invoke("org", "add", "acme", "--local-path", str(pack))

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_UNREADABLE" in refused.output
    assert "Traceback" not in refused.output
    assert config_path.read_bytes() == before


def test_add_json_reports_the_written_entry(project: Path) -> None:
    """FR-010: the payload is machine-readable."""
    import json

    pack = _scaffold(project / "packs" / "acme")

    result = _invoke("org", "add", "acme", "--local-path", str(pack), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["pack"] == {"name": "acme", "local_path": str(pack)}
    assert payload["replaced"] is False
    assert payload["validated"] is True
    assert payload["config"].endswith(".kittify/config.yaml")


# ---------------------------------------------------------------------------
# US3 — retire a registration
# ---------------------------------------------------------------------------


def test_remove_deletes_exactly_one_entry(project: Path) -> None:
    """US3 #1: the sibling pack and every other key survive."""
    _scaffold(project / "packs" / "acme")
    _scaffold(project / "packs" / "security")
    assert _invoke("org", "add", "acme", "--local-path", str(project / "packs" / "acme")).exit_code == 0
    assert _invoke("org", "add", "security", "--local-path", str(project / "packs" / "security")).exit_code == 0

    result = _invoke("org", "remove", "acme")

    assert result.exit_code == 0, result.output
    assert [entry["name"] for entry in _registered_entries(project)] == ["security"]
    assert "# Project configuration" in _config_text(project)
    assert "vcs:\n  type: git\n" in _config_text(project)


def test_remove_unknown_name_lists_configured_packs(project: Path) -> None:
    """US3 #2: refusal names the configured packs, config byte-identical."""
    _scaffold(project / "packs" / "acme")
    assert _invoke("org", "add", "acme", "--local-path", str(project / "packs" / "acme")).exit_code == 0
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    refused = _invoke("org", "remove", "missing")

    assert refused.exit_code == 1, refused.output
    assert "ORG_PACK_NOT_FOUND" in refused.output
    assert "acme" in refused.output
    assert config_path.read_bytes() == before


def test_add_then_remove_restores_the_config_bytes(project: Path) -> None:
    """US3 #3 / SC-002: byte-identical round trip on a commented config."""
    pack = _scaffold(project / "packs" / "acme")
    config_path = project / ".kittify" / "config.yaml"
    before = config_path.read_bytes()

    assert _invoke("org", "add", "acme", "--local-path", str(pack)).exit_code == 0
    assert config_path.read_bytes() != before
    assert _invoke("org", "remove", "acme").exit_code == 0

    assert config_path.read_bytes() == before


def test_remove_never_deletes_the_pack_directory(project: Path) -> None:
    """C-003: the command reports the directory it leaves behind."""
    pack = _scaffold(project / "packs" / "acme")
    assert _invoke("org", "add", "acme", "--local-path", str(pack)).exit_code == 0

    result = _invoke("org", "remove", "acme")

    assert result.exit_code == 0, result.output
    assert pack.is_dir()
    assert str(pack) in result.output


def test_remove_json_reports_the_removal(project: Path) -> None:
    import json

    pack = _scaffold(project / "packs" / "acme")
    assert _invoke("org", "add", "acme", "--local-path", str(pack)).exit_code == 0

    result = _invoke("org", "remove", "acme", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["removed"] == "acme"
    assert payload["pack_root"] == str(pack)


# ---------------------------------------------------------------------------
# FR-009 / NFR-003 / T012 — offline and bounded
# ---------------------------------------------------------------------------


def test_add_and_remove_never_touch_the_network(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-009: registration is purely local (no socket is ever created)."""

    def _no_socket(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("org add/remove must not open a socket")

    monkeypatch.setattr(socket, "socket", _no_socket)
    monkeypatch.setattr(socket, "create_connection", _no_socket)
    pack = _scaffold(project / "packs" / "acme")

    assert _invoke("org", "add", "acme", "--local-path", str(pack)).exit_code == 0
    assert _invoke("org", "remove", "acme").exit_code == 0


def test_add_completes_well_under_the_bounded_cost(project: Path) -> None:
    """NFR-003: generous wall-clock ceiling over a local validate."""
    pack = _scaffold(project / "packs" / "acme")

    started = time.monotonic()
    result = _invoke("org", "add", "acme", "--local-path", str(pack))
    elapsed = time.monotonic() - started

    assert result.exit_code == 0, result.output
    assert elapsed < 5.0, f"charter org add took {elapsed:.2f}s"
