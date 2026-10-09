"""WP06 / FR-013: charter activation resolves org packs from the canonical flat layout.

The charter activation subsystem historically registered org doctrine roots only
when a ``<pack>/doctrine/`` subdirectory existed (``charter.activation.layer_roots.resolve_layer_roots``)
and scanned the nested ``<pack>/doctrine/<plural>/org/`` location
(``pack_manager._scan_layer_dirs``). Runtime, by contrast, resolves org packs from
the *flat* ``<pack>/<plural>/`` layout via
``charter.offering.drg.org_pack_config.resolve_org_roots`` and feeds those roots to
``ActiveCharterService`` — so a runtime-resolvable org profile failed to activate with
"Unknown agent-profile ID".

These tests pin the unified behaviour:

* **T016 (red-first)** — ``charter activate agent-profile <id>`` succeeds against a
  *flat* org pack (``<pack>/agent_profiles/<id>.agent.yaml``). RED before the fix:
  the flat org root is never registered, so the engine raises "Unknown agent-profile ID".
* **T017** — the layout-tolerant resolver prefers flat and still finds nested fixtures
  (covered by the un-owned ``tests/charter/test_pack_manager_catalog.py`` regression).
* **T018** — multi-kind regression (agent-profile + directive) across
  ``list / activate / deactivate`` for the flat layout, including the
  activate -> list-active -> deactivate -> list-inactive round-trip, plus a
  nested-layout backward-compat case (layout-tolerant default).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Realistic fixtures (C-007): production-shaped pack + artifact files
# ---------------------------------------------------------------------------

#: A real-format agent profile body (profile-id is the catalogued id field for
#: agent profiles — see ``pack_manager._ID_FIELD_BY_KIND``).
_AGENT_PROFILE_TEMPLATE = """\
profile-id: {pid}
name: Orgzilla Org Analyst
description: Org-pack specialist analyst contributed by the Orgzilla doctrine pack.
schema-version: "1.0"
roles:
  - analyst
applies_to_languages:
  - python
routing-priority: 50
"""

_DIRECTIVE_TEMPLATE = """\
id: {did}
type: directive
title: {title}
"""


def _write_flat_agent_profile(pack_root: Path, profile_id: str) -> None:
    """Write a flat-layout agent profile: ``<pack>/agent_profiles/<id>.agent.yaml``."""
    profiles_dir = pack_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    (profiles_dir / f"{profile_id}.agent.yaml").write_text(
        _AGENT_PROFILE_TEMPLATE.format(pid=profile_id), encoding="utf-8"
    )


def _write_flat_directive(pack_root: Path, stem: str, declared_id: str) -> None:
    """Write a flat-layout directive: ``<pack>/directives/<stem>.directive.yaml``."""
    directives_dir = pack_root / "directives"
    directives_dir.mkdir(parents=True, exist_ok=True)
    (directives_dir / f"{stem}.directive.yaml").write_text(
        _DIRECTIVE_TEMPLATE.format(did=declared_id, title=stem), encoding="utf-8"
    )


def _write_config_with_org_pack(project_root: Path, pack_local_path: str) -> None:
    """Point ``.kittify/config.yaml`` at a single org pack via the canonical schema.

    Carries ``mission_type_activations`` (WP04, C-A1): the provisioned charter
    is the sole mission-type activation authority, so ``PackContext.from_config``
    fails closed when the key is absent from the activation source -- these
    fixtures must provision it like a real ``spec-kitty init``/``upgrade`` would.
    """
    (project_root / ".kittify" / "config.yaml").write_text(
        "charter_packs:\n"
        "  org:\n"
        "    packs:\n"
        "      - name: orgzilla\n"
        f"        local_path: {pack_local_path}\n"
        "mission_type_activations:\n"
        "  - software-dev\n",
        encoding="utf-8",
    )


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A minimal project with ``.kittify/config.yaml`` and a flat org pack."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("# empty config\n", encoding="utf-8")
    return tmp_path


def _invoke(project_root: Path, *args: str) -> object:
    """Invoke a charter subcommand with ``--repo-root`` before positionals."""
    sub, rest = args[0], args[1:]
    return runner.invoke(
        charter_app,
        [sub, "--repo-root", str(project_root), *rest],
        catch_exceptions=False,
        env={"COLUMNS": "240"},
    )


def _squash(text: str) -> str:
    """Collapse whitespace so Rich table line-wrapping does not break substring checks."""
    return "".join(text.split())


# ---------------------------------------------------------------------------
# T016 — RED activation-layout test (flat org pack must activate)
# ---------------------------------------------------------------------------


class TestFlatLayoutActivation:
    def test_activate_agent_profile_from_flat_org_pack(self, project_root: Path) -> None:
        """``charter activate agent-profile <id>`` succeeds against a flat org pack.

        RED before the fix: ``layer_roots`` won't register the flat org root
        (no ``<pack>/doctrine/`` subdir), so the engine raises
        "Unknown agent-profile ID".
        """
        pack_root = project_root / "org-packs" / "orgzilla"
        _write_flat_agent_profile(pack_root, "orgzilla-org-analyst")
        _write_config_with_org_pack(project_root, "org-packs/orgzilla")

        result = _invoke(project_root, "activate", "agent-profile", "orgzilla-org-analyst")

        assert result.exit_code == 0, result.output
        assert "Unknown agent-profile ID" not in result.output
        assert "Unknown agent_profile ID" not in result.output
        data = yaml.safe_load((project_root / ".kittify" / "config.yaml").read_text())
        assert "orgzilla-org-analyst" in data["activated_agent_profiles"]

    def test_flat_org_profile_listed_with_org_layer(self, project_root: Path) -> None:
        """A flat-layout org profile is surfaced by ``charter list agent-profile``."""
        pack_root = project_root / "org-packs" / "orgzilla"
        _write_flat_agent_profile(pack_root, "orgzilla-org-analyst")
        _write_config_with_org_pack(project_root, "org-packs/orgzilla")

        result = _invoke(project_root, "list", "--all")

        assert result.exit_code == 0, result.output
        assert "orgzilla-org-analyst" in _squash(result.output)


# ---------------------------------------------------------------------------
# T018 — Multi-kind regression (>= 2 kinds) + activate/deactivate round-trip
# ---------------------------------------------------------------------------


class TestMultiKindFlatLayout:
    def test_directive_flat_org_pack_round_trip(self, project_root: Path) -> None:
        """Second kind (directive): activate -> list active -> deactivate -> inactive."""
        pack_root = project_root / "org-packs" / "orgzilla"
        _write_flat_directive(pack_root, "900-orgzilla-rule", "DIRECTIVE_900")
        _write_config_with_org_pack(project_root, "org-packs/orgzilla")

        # activate
        activate = _invoke(project_root, "activate", "directive", "900-orgzilla-rule")
        assert activate.exit_code == 0, activate.output
        data = yaml.safe_load((project_root / ".kittify" / "config.yaml").read_text())
        assert "900-orgzilla-rule" in data["activated_directives"]

        # deactivate round-trips
        deactivate = _invoke(project_root, "deactivate", "directive", "900-orgzilla-rule")
        assert deactivate.exit_code == 0, deactivate.output
        data = yaml.safe_load((project_root / ".kittify" / "config.yaml").read_text())
        assert "900-orgzilla-rule" not in (data.get("activated_directives") or [])

    def test_agent_profile_flat_org_pack_round_trip(self, project_root: Path) -> None:
        """First kind (agent-profile): activate -> deactivate round-trip on flat layout."""
        pack_root = project_root / "org-packs" / "orgzilla"
        _write_flat_agent_profile(pack_root, "orgzilla-org-analyst")
        _write_config_with_org_pack(project_root, "org-packs/orgzilla")

        activate = _invoke(project_root, "activate", "agent-profile", "orgzilla-org-analyst")
        assert activate.exit_code == 0, activate.output

        deactivate = _invoke(
            project_root, "deactivate", "agent-profile", "orgzilla-org-analyst"
        )
        assert deactivate.exit_code == 0, deactivate.output
        data = yaml.safe_load((project_root / ".kittify" / "config.yaml").read_text())
        assert "orgzilla-org-analyst" not in (
            data.get("activated_agent_profiles") or []
        )

    def test_both_kinds_resolve_from_same_flat_pack(self, project_root: Path) -> None:
        """C-006: the flat org-layer scan serves >= 2 kinds from one pack."""
        pack_root = project_root / "org-packs" / "orgzilla"
        _write_flat_agent_profile(pack_root, "orgzilla-org-analyst")
        _write_flat_directive(pack_root, "900-orgzilla-rule", "DIRECTIVE_900")
        _write_config_with_org_pack(project_root, "org-packs/orgzilla")

        listing = _invoke(project_root, "list", "--all")
        assert listing.exit_code == 0, listing.output
        squashed = _squash(listing.output)
        assert "orgzilla-org-analyst" in squashed
        assert "900-orgzilla-rule" in squashed


# ---------------------------------------------------------------------------
# T017 / layout-tolerant default — nested layout stays resolvable (backward-compat)
# ---------------------------------------------------------------------------


class TestNestedLayoutBackwardCompat:
    def test_nested_org_directive_still_activates(self, project_root: Path) -> None:
        """Layout-tolerant fallback: a nested ``<pack>/doctrine/<plural>/org/`` pack
        remains activatable, so the un-owned nested catalog fixtures stay green."""
        pack_root = project_root / "org-packs" / "legacy"
        nested_dir = pack_root / "directives"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "950-legacy-rule.directive.yaml").write_text(
            _DIRECTIVE_TEMPLATE.format(did="DIRECTIVE_950", title="950-legacy-rule"),
            encoding="utf-8",
        )
        _write_config_with_org_pack(project_root, "org-packs/legacy")

        result = _invoke(project_root, "activate", "directive", "950-legacy-rule")

        assert result.exit_code == 0, result.output
        data = yaml.safe_load((project_root / ".kittify" / "config.yaml").read_text())
        assert "950-legacy-rule" in data["activated_directives"]
