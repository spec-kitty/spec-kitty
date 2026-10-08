"""Tests for `spec-kitty charter pack {list,path,apply}` (#3064 follow-up).

`src/charter/offering/assets/built-in/charter_scaffold_minimal.yml` (+ sidecar) was a
doctrine *asset* despite being structurally a charter pack — the same shape
as `src/charter/activation/packs/default.yaml` (`activated_kinds` /
`mission_type_activations` / `activated_directives` / `activated_tactics`).
It has been relocated to `src/charter/activation/packs/minimal.yaml`, first-class
alongside `default.yaml`, and is now discoverable/applyable via an on-demand
pack CLI instead of `doctrine asset path`.

Covers:
- `pack list` — one row per offering pack with its presets (#3732 WP08).
- `pack path <pack> [--preset <preset>]` — the pack root or the preset file;
  fails closed (exit 1, PACK_NOT_FOUND) on an unknown pack.
- `pack apply <name>` — merges a pack's activation keys into a project's
  `.kittify/config.yaml`; additive by default (User Customization
  Preservation — an existing key is never silently overwritten), full
  replacement of the pack's keys with `--force`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.catalog import load_doctrine_catalog
from charter.activation.pack_context import charter_activated_urns
from specify_cli.cli.commands.charter import charter_app
from specify_cli.invocation.empty_charter import is_charter_empty

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PACKS_DIR = _REPO_ROOT / "src" / "charter" / "activation" / "packs"
_MINIMAL_PATH = _PACKS_DIR / "minimal.yaml"
_DEFAULT_PATH = _PACKS_DIR / "default.yaml"


def _load_yaml(path: Path) -> dict[str, object]:
    yaml = YAML(typ="safe")
    loaded = yaml.load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


# ---------------------------------------------------------------------------
# `pack list` (#3732 WP08: one row per offering pack with its presets)
# ---------------------------------------------------------------------------

_BUILT_IN_PRESETS = _REPO_ROOT / "packs" / "built-in" / "presets"


def _list(repo_root: Path, *extra: str) -> object:
    return runner.invoke(charter_app, ["pack", "list", "--repo-root", str(repo_root), *extra], catch_exceptions=False)


def test_list_shows_built_in_pack_with_default_and_minimal_presets(tmp_path: Path) -> None:
    result = _list(tmp_path)

    assert result.exit_code == 0, result.output
    assert "built-in" in result.output
    assert "default" in result.output
    assert "minimal" in result.output


def test_list_json_rows_are_packs_with_preset_paths(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    result = _list(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    rows = {row["name"]: row for row in json.loads(result.output)["packs"]}
    assert set(rows) == {"built-in", "project"}
    presets = {preset["name"]: Path(preset["path"]) for preset in rows["built-in"]["presets"]}
    assert presets["minimal"] == _BUILT_IN_PRESETS / "minimal.yaml"
    assert presets["default"] == _BUILT_IN_PRESETS / "default.yaml"
    assert rows["project"] == {"name": "project", "tier": "project", "root": str(tmp_path.resolve() / ".kittify" / "charter-packs"), "presets": []}


def test_list_outside_a_project_has_no_project_row(tmp_path: Path) -> None:
    result = _list(tmp_path, "--json")

    assert result.exit_code == 0, result.output
    assert [row["name"] for row in json.loads(result.output)["packs"]] == ["built-in"]


# ---------------------------------------------------------------------------
# `pack path <pack> [--preset <preset>]`
# ---------------------------------------------------------------------------


def _path(repo_root: Path, *args: str) -> object:
    return runner.invoke(charter_app, ["pack", "path", *args, "--repo-root", str(repo_root)], catch_exceptions=False)


def test_path_built_in_resolves_to_the_pack_root(tmp_path: Path) -> None:
    result = _path(tmp_path, "built-in")

    assert result.exit_code == 0, result.output
    assert Path(result.output.strip()) == _REPO_ROOT / "packs" / "built-in"


def test_path_preset_minimal_resolves_to_the_preset_file(tmp_path: Path) -> None:
    result = _path(tmp_path, "built-in", "--preset", "minimal")

    assert result.exit_code == 0, result.output
    resolved = Path(result.output.strip())
    assert resolved == _BUILT_IN_PRESETS / "minimal.yaml"
    assert resolved.is_file()


def test_path_json_built_in_minimal(tmp_path: Path) -> None:
    result = _path(tmp_path, "built-in", "--preset", "minimal", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {"pack": "built-in", "path": str(_BUILT_IN_PRESETS / "minimal.yaml"), "preset": "minimal"}


def test_path_unknown_pack_fails_closed(tmp_path: Path) -> None:
    result = _path(tmp_path, "no-such-pack")

    assert result.exit_code == 1
    assert "PACK_NOT_FOUND" in result.output
    assert "no-such-pack" in result.output
    assert "built-in" in result.output


def test_path_unknown_pack_json_fails_closed(tmp_path: Path) -> None:
    result = _path(tmp_path, "no-such-pack", "--json")

    assert result.exit_code == 1
    error = json.loads(result.output)["error"]
    assert error["code"] == "PACK_NOT_FOUND"
    assert error["pack"] == "no-such-pack"
    assert "built-in" in error["available"]


# ---------------------------------------------------------------------------
# `pack apply <name>` — happy path, activatability
# ---------------------------------------------------------------------------


def _apply(project_root: Path, name: str, *extra: str) -> object:
    return runner.invoke(
        charter_app,
        ["pack", "apply", name, "--repo-root", str(project_root), *extra],
        catch_exceptions=False,
    )


def test_apply_minimal_writes_curated_keys_into_config_yaml(tmp_path: Path) -> None:
    result = _apply(tmp_path, "minimal")

    assert result.exit_code == 0, result.output
    config_path = tmp_path / ".kittify" / "config.yaml"
    assert config_path.is_file()

    written = _load_yaml(config_path)
    expected = _load_yaml(_MINIMAL_PATH)
    assert written["activated_kinds"] == expected["activated_kinds"]
    assert written["mission_type_activations"] == expected["mission_type_activations"]
    assert written["activated_directives"] == expected["activated_directives"]
    assert written["activated_tactics"] == expected["activated_tactics"]


def test_apply_minimal_json_reports_keys_written(tmp_path: Path) -> None:
    result = _apply(tmp_path, "minimal", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["pack"] == "minimal"
    assert "activated_directives" in payload["keys_written"]
    assert "activated_tactics" in payload["keys_written"]
    assert payload["keys_skipped"] == []


def test_apply_unknown_pack_fails_closed(tmp_path: Path) -> None:
    result = _apply(tmp_path, "no-such-pack")

    assert result.exit_code == 1


def test_applied_minimal_activates_urns_but_stays_empty_for_dispatch_until_compiled(
    tmp_path: Path,
) -> None:
    """Real done-line: applying the pack activates URNs (config-level effect),
    but does NOT compile a bundle — so ``is_charter_empty`` correctly still
    reports "empty" (no ``.kittify/charter/charter.yaml``) until
    ``charter generate`` runs.

    NOTE (NFR-004/#3104): pre-fix, this test asserted
    ``is_charter_empty(tmp_path) is False`` right after ``apply`` with no
    compile — that encoded the #3104 defect (``charter pack apply`` writing
    activation keys with no bundle and no profile activation used to flip the
    dispatch net off, producing a bare ``ROUTER_NO_MATCH`` for an unmatched
    request instead of the safe generic-agent fallback). The bundle-presence +
    org-pack-safe predicate in ``specify_cli.invocation.empty_charter``
    decouples "activatable" (config carries activation keys — still true and
    asserted below) from "empty-for-dispatch" (compiled bundle absent — now
    correctly ``True`` here).
    """
    result = _apply(tmp_path, "minimal")
    assert result.exit_code == 0, result.output

    # Applying activates URNs at the config level -- unchanged.
    urns = charter_activated_urns(tmp_path)
    assert urns, "applying minimal must activate at least one URN"
    assert "directive:DIRECTIVE_001" in urns
    assert "tactic:acceptance-test-first" in urns

    # ...but no compiled bundle exists yet, so dispatch correctly still
    # treats the project as empty (NFR-004 bundle-presence predicate).
    assert not (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()
    assert is_charter_empty(tmp_path) is True


def test_applied_minimal_directive_and_tactic_ids_resolve_in_the_built_in_catalog(
    tmp_path: Path,
) -> None:
    """Every id the minimal pack activates must be a REAL built-in artifact."""
    result = _apply(tmp_path, "minimal")
    assert result.exit_code == 0, result.output

    urns = charter_activated_urns(tmp_path)
    catalog = load_doctrine_catalog()
    directive_ids = {urn.split(":", 1)[1] for urn in urns if urn.startswith("directive:")}
    tactic_ids = {urn.split(":", 1)[1] for urn in urns if urn.startswith("tactic:")}

    assert directive_ids, "expected at least one activated directive"
    assert directive_ids <= catalog.directives
    assert tactic_ids, "expected at least one activated tactic"
    assert tactic_ids <= catalog.tactics


# ---------------------------------------------------------------------------
# `pack apply <name>` — User Customization Preservation (no clobber without --force)
# ---------------------------------------------------------------------------


def _existing_project(tmp_path: Path) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "activated_kinds:\n  - directives\n"
        "activated_directives:\n  - 003-decision-documentation-requirement\n",
        encoding="utf-8",
    )
    return tmp_path


def test_apply_without_force_does_not_overwrite_an_existing_key(tmp_path: Path) -> None:
    project_root = _existing_project(tmp_path)

    result = _apply(project_root, "minimal")

    assert result.exit_code == 0, result.output
    config_path = project_root / ".kittify" / "config.yaml"
    data = _load_yaml(config_path)
    # The user's pre-existing activated_directives value is untouched...
    assert data["activated_directives"] == ["003-decision-documentation-requirement"]
    # ...but a key the user never set (activated_tactics) IS written from the pack.
    assert data["activated_tactics"] == _load_yaml(_MINIMAL_PATH)["activated_tactics"]


def test_apply_without_force_reports_skipped_keys(tmp_path: Path) -> None:
    project_root = _existing_project(tmp_path)

    result = _apply(project_root, "minimal", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "activated_directives" in payload["keys_skipped"]
    assert "activated_directives" not in payload["keys_written"]
    assert "activated_tactics" in payload["keys_written"]


def test_apply_with_force_overwrites_the_existing_key(tmp_path: Path) -> None:
    project_root = _existing_project(tmp_path)

    result = _apply(project_root, "minimal", "--force")

    assert result.exit_code == 0, result.output
    config_path = project_root / ".kittify" / "config.yaml"
    data = _load_yaml(config_path)
    assert data["activated_directives"] == _load_yaml(_MINIMAL_PATH)["activated_directives"]


def test_apply_does_not_touch_a_different_pre_existing_user_charter(tmp_path: Path) -> None:
    """Activating the pack in ONE repo must never write to a DIFFERENT project."""
    user_repo = tmp_path / "existing-user-project"
    fresh_repo = tmp_path / "fresh-project"
    user_repo.mkdir()
    fresh_repo.mkdir()
    _existing_project(user_repo)

    user_config = user_repo / ".kittify" / "config.yaml"
    before = user_config.read_bytes()

    result = _apply(fresh_repo, "minimal")
    assert result.exit_code == 0, result.output

    after = user_config.read_bytes()
    assert after == before, "applying the pack elsewhere must not mutate a user's charter"
