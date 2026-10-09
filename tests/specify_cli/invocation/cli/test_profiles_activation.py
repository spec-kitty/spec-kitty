"""Activation-aware profile surface tests (WP04 — FR-011..015).

Covers:
- FR-011: ``profile list`` defaults to activated-only by *filtering* the
  existing ``ProfileRegistry.list_all()`` rows; unconfigured projects are
  byte-identical (NFR-001).
- FR-012: ``--all`` / ``--show-available`` annotate rows by source + state.
- FR-013: ``profile show <id>`` renders the full resolved definition (+ ``--json``).
- FR-014: ``show`` is activation-gated; non-activated → ``profile_not_activated``
  structured error (exit 1); ``--all`` bypasses for inspection.
- FR-015: lineage Option A — resolution traverses non-activated abstract base
  profiles and emits a user-facing warning naming them.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli import app as cli_app

# Marked for mutmut sandbox skip — subprocess-style CLI invocation.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]

runner = CliRunner()

# A pair of real built-in profiles; reviewer-renata is unrelated to the
# implementer lineage, so it is a safe "activated candidate" anchor.
_ACTIVATED_ID = "reviewer-renata"
_OTHER_ID = "implementer-ivan"
_PROJECT_ID = "local-lena"
_ORG_ID = "org-olivia"


def _extract_json(output: str) -> object:
    """Parse JSON from CLI output, tolerating a leading readiness banner line.

    A connected-teamspace dev environment can prepend a single
    ``spec-kitty: logged_out_on_connected_teamspace ...`` banner line to
    stdout via CliRunner's mixed stderr. That banner is environment-specific
    and unrelated to the command payload, so we strip any leading non-JSON
    lines before decoding.
    """
    stripped = output.lstrip()
    start = min(
        (i for i in (stripped.find("["), stripped.find("{")) if i != -1),
        default=-1,
    )
    if start == -1:
        raise AssertionError(f"No JSON payload found in output: {output!r}")
    return json.loads(stripped[start:])


def _write_config(repo_root: Path, data: dict[str, object]) -> None:
    """Write a ``.kittify/config.yaml`` with the given mapping."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _write_project_doctrine_profile(repo_root: Path, profile_id: str = _PROJECT_ID) -> None:
    """Write a project-doctrine profile under the charter synthesis path."""
    profiles_dir = repo_root / ".kittify" / "charter-packs" / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    source = Path("packs/built-in/agent_profiles/reviewer-renata.agent.yaml")
    text = source.read_text(encoding="utf-8")
    text = text.replace("profile-id: reviewer-renata", f"profile-id: {profile_id}")
    text = text.replace("name: Reviewer Renata", "name: Local Lena")
    (profiles_dir / f"{profile_id}.agent.yaml").write_text(text, encoding="utf-8")


def _write_org_doctrine_profile(repo_root: Path, profile_id: str = _ORG_ID) -> Path:
    """Write an org-pack profile and return the org doctrine root."""
    org_root = repo_root / "org-pack"
    profiles_dir = org_root / "agent_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    source = Path("packs/built-in/agent_profiles/reviewer-renata.agent.yaml")
    text = source.read_text(encoding="utf-8")
    text = text.replace("profile-id: reviewer-renata", f"profile-id: {profile_id}")
    text = text.replace("name: Reviewer Renata", "name: Org Olivia")
    (profiles_dir / f"{profile_id}.agent.yaml").write_text(text, encoding="utf-8")
    return org_root


def _invoke(project: Path, args: list[str]):
    with patch(
        "specify_cli.cli.commands.profiles_cmd.find_repo_root", return_value=project
    ):
        return runner.invoke(cli_app, args)


# ---------------------------------------------------------------------------
# FR-011 / NFR-001 — list filtering + byte-identity
# ---------------------------------------------------------------------------


class TestListActivationFilter:
    def test_unconfigured_project_lists_all_profiles(self, tmp_path: Path) -> None:
        """No config.yaml → activated_agent_profiles is None → all profiles (NFR-001)."""
        (tmp_path / ".kittify").mkdir(parents=True)
        result = _invoke(tmp_path, ["profiles", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = _extract_json(result.output)
        assert isinstance(data, list)
        ids = {d["profile_id"] for d in data}
        # Several built-ins must be present (catalog not filtered).
        assert _ACTIVATED_ID in ids
        assert _OTHER_ID in ids
        # Default schema preserved: no 'state' key on the default rows.
        assert all("state" not in d for d in data)

    def test_unconfigured_output_is_byte_identical_to_unfiltered_descriptors(
        self, tmp_path: Path
    ) -> None:
        """NFR-001: default JSON for an unconfigured project == unfiltered baseline.

        Baseline: descriptors built directly from the registry (the pre-WP04
        data source and schema).

        Restored (landing-fold regression fix, charter-sole-door-bypass-
        closure-01KZ3WAA): WP01 unified ``ProfileRegistry``'s builder to
        always compute ``active_languages=infer_repo_languages(repo_root)``.
        A prior revision of that unification made ``infer_repo_languages``
        return an *explicitly empty* list for an unconfigured project (no
        ``charter.yaml``, no interview answers), which narrowed
        ``ProfileRegistry``'s catalog down to language-agnostic profiles only
        (e.g. ``frontend-freddy`` dropped out) — breaking byte-identity with
        the unfiltered baseline and forcing this test to stop using
        ``ProfileRegistry`` as the stand-in. ``infer_repo_languages`` now
        resolves that "truly nothing configured yet" case to ``None``
        ("unknown" — admits every scoped profile) instead, so
        ``ProfileRegistry(tmp_path).list_all()`` is byte-identical to a bare
        ``AgentProfileRepository().list_all()`` again for an unconfigured
        project, and the original, stricter, non-fakeable baseline (built
        from the real data source the CLI itself composes from) is restored.
        """
        (tmp_path / ".kittify").mkdir(parents=True)

        # Baseline: descriptors built directly from the registry (the pre-WP04
        # data source and schema).
        from specify_cli.cli.commands.profiles_cmd import _build_descriptor
        from specify_cli.invocation.registry import ProfileRegistry

        registry = ProfileRegistry(tmp_path)
        expected = [_build_descriptor(p) for p in registry.list_all()]

        result = _invoke(tmp_path, ["profiles", "list", "--json"])
        assert result.exit_code == 0, result.output
        actual = _extract_json(result.output)
        assert actual == expected

    def test_configured_project_filters_to_activated_only(self, tmp_path: Path) -> None:
        """FR-011: explicit activated_agent_profiles → only those rows survive."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = _extract_json(result.output)
        ids = {d["profile_id"] for d in data}
        assert ids == {_ACTIVATED_ID}

    def test_empty_activation_set_lists_nothing(self, tmp_path: Path) -> None:
        """Explicit empty list → nothing activated → empty (or 'No profiles')."""
        _write_config(tmp_path, {"activated_agent_profiles": []})
        result = _invoke(tmp_path, ["profiles", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = _extract_json(result.output)
        assert data == []

    def test_project_doctrine_profile_can_be_listed_when_activated(
        self, tmp_path: Path
    ) -> None:
        """``list`` and ``show`` share the project-doctrine profile surface."""
        _write_project_doctrine_profile(tmp_path)
        _write_config(tmp_path, {"activated_agent_profiles": [_PROJECT_ID]})

        result = _invoke(tmp_path, ["profiles", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = _extract_json(result.output)

        assert [row["profile_id"] for row in data] == [_PROJECT_ID]
        assert data[0]["source"] == "project_local"

        shown = _invoke(tmp_path, ["profiles", "show", _PROJECT_ID, "--json"])
        assert shown.exit_code == 0, shown.output
        payload = _extract_json(shown.output)
        assert payload["profile_id"] == _PROJECT_ID
        assert payload["source_layer"] == "project"

    def test_org_doctrine_profile_can_be_listed_when_activated(
        self, tmp_path: Path
    ) -> None:
        """Configured org-pack profiles are part of list/show activation surface."""
        org_root = _write_org_doctrine_profile(tmp_path)
        _write_config(
            tmp_path,
            {
                "charter_packs": {
                    "org": {
                        "packs": [
                            {"name": "acme", "local_path": str(org_root)},
                        ]
                    }
                },
                "activated_agent_profiles": [_ORG_ID],
            },
        )

        result = _invoke(tmp_path, ["profiles", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = _extract_json(result.output)

        assert [row["profile_id"] for row in data] == [_ORG_ID]
        assert data[0]["source"] == "org"

        shown = _invoke(tmp_path, ["profiles", "show", _ORG_ID, "--json"])
        assert shown.exit_code == 0, shown.output
        payload = _extract_json(shown.output)
        assert payload["profile_id"] == _ORG_ID
        assert payload["source_layer"] == "org"


# ---------------------------------------------------------------------------
# FR-012 — --all / --show-available annotation
# ---------------------------------------------------------------------------


class TestListAllAndShowAvailable:
    def test_all_includes_non_activated_with_state(self, tmp_path: Path) -> None:
        """--all shows the full catalog annotated by activated|available state."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "list", "--all", "--json"])
        assert result.exit_code == 0, result.output
        data = _extract_json(result.output)
        by_id = {d["profile_id"]: d for d in data}
        # Full catalog is present (not filtered).
        assert _ACTIVATED_ID in by_id
        assert _OTHER_ID in by_id
        # State annotation reflects activation.
        assert by_id[_ACTIVATED_ID]["state"] == "activated"
        assert by_id[_OTHER_ID]["state"] == "available"

    def test_show_available_adds_state_column(self, tmp_path: Path) -> None:
        """--show-available annotates rows with state without dropping any."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "list", "--show-available", "--json"])
        assert result.exit_code == 0, result.output
        data = _extract_json(result.output)
        assert all("state" in d for d in data)
        states = {d["profile_id"]: d["state"] for d in data}
        assert states[_ACTIVATED_ID] == "activated"
        assert states[_OTHER_ID] == "available"


# ---------------------------------------------------------------------------
# FR-013 / FR-014 — show render + activation gate + not-found schema
# ---------------------------------------------------------------------------


class TestShowRenderAndGate:
    def test_show_activated_renders_full_definition_json(self, tmp_path: Path) -> None:
        """FR-013: activated id renders the resolved profile payload."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "show", _ACTIVATED_ID, "--json"])
        assert result.exit_code == 0, result.output
        payload = _extract_json(result.output)
        assert payload["profile_id"] == _ACTIVATED_ID
        # Rendered fields per data-model.md.
        for key in (
            "name",
            "role",
            "initialization_declaration",
            "specialization",
            "collaboration",
            "mode_defaults",
            "directive_references",
            "tactic_references",
            "source_layer",
            "warnings",
        ):
            assert key in payload
        assert payload["source_layer"] == "builtin"
        assert payload["warnings"] == []

    def test_show_json_is_sorted_key(self, tmp_path: Path) -> None:
        """NFR-004: --json output uses sorted keys."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "show", _ACTIVATED_ID, "--json"])
        assert result.exit_code == 0, result.output
        payload = _extract_json(result.output)
        top_keys = list(payload.keys())
        assert top_keys == sorted(top_keys)

    def test_get_alias_routes_to_show(self, tmp_path: Path) -> None:
        """FR-013: the ``get`` alias behaves like ``show``."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "get", _ACTIVATED_ID, "--json"])
        assert result.exit_code == 0, result.output
        payload = _extract_json(result.output)
        assert payload["profile_id"] == _ACTIVATED_ID

    def test_show_non_activated_emits_profile_not_activated(self, tmp_path: Path) -> None:
        """FR-014: a non-activated leaf id → structured error, exit 1."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "show", _OTHER_ID, "--json"])
        assert result.exit_code == 1, result.output
        payload = _extract_json(result.output)
        assert payload == {
            "error": "profile_not_activated",
            "profile_id": _OTHER_ID,
            "activated_candidates": [_ACTIVATED_ID],
        }

    def test_not_activated_candidates_are_sorted(self, tmp_path: Path) -> None:
        """activated_candidates is sorted ascending (data-model.md contract)."""
        _write_config(
            tmp_path,
            {"activated_agent_profiles": [_ACTIVATED_ID, "curator-carla", "planner-priti"]},
        )
        result = _invoke(tmp_path, ["profiles", "show", _OTHER_ID, "--json"])
        assert result.exit_code == 1, result.output
        payload = _extract_json(result.output)
        candidates = payload["activated_candidates"]
        assert candidates == sorted(candidates)
        assert set(candidates) == {_ACTIVATED_ID, "curator-carla", "planner-priti"}

    def test_show_unknown_id_is_not_activated(self, tmp_path: Path) -> None:
        """An id that does not exist at all is surfaced as not-activated, exit 1."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "show", "does-not-exist", "--json"])
        assert result.exit_code == 1, result.output
        payload = _extract_json(result.output)
        assert payload["error"] == "profile_not_activated"
        assert payload["profile_id"] == "does-not-exist"

    def test_show_all_bypasses_gate(self, tmp_path: Path) -> None:
        """FR-014: --all renders a non-activated profile for inspection (exit 0)."""
        _write_config(tmp_path, {"activated_agent_profiles": [_ACTIVATED_ID]})
        result = _invoke(tmp_path, ["profiles", "show", _OTHER_ID, "--all", "--json"])
        assert result.exit_code == 0, result.output
        payload = _extract_json(result.output)
        assert payload["profile_id"] == _OTHER_ID


# ---------------------------------------------------------------------------
# FR-015 — lineage Option A + non-activated-parent warning
# ---------------------------------------------------------------------------


def _profile_with_parent() -> tuple[str, str] | None:
    """Return (child_id, parent_id) for a built-in profile that has a lineage parent.

    Returns ``None`` if the shipped DRG declares no agent-profile lineage, in
    which case the lineage-warning tests skip (the warning path is exercised
    only when real lineage exists).
    """
    from charter.offering.agent_profiles.repository import AgentProfileRepository

    repo = AgentProfileRepository()
    for profile_id in sorted(p.profile_id for p in repo.list_all()):
        ancestors = repo.get_ancestors(profile_id)
        if ancestors:
            return profile_id, ancestors[0]
    return None


class TestLineageWarning:
    def test_child_resolves_with_warning_when_parent_not_activated(
        self, tmp_path: Path
    ) -> None:
        """FR-015: activated child whose abstract parent is not activated → warning."""
        pair = _profile_with_parent()
        if pair is None:
            pytest.skip("No agent-profile lineage in the shipped DRG.")
        child, parent = pair
        # Activate the child only; the parent stays a non-activated abstract base.
        _write_config(tmp_path, {"activated_agent_profiles": [child]})
        result = _invoke(tmp_path, ["profiles", "show", child, "--json"])
        assert result.exit_code == 0, result.output
        payload = _extract_json(result.output)
        assert payload["profile_id"] == child
        assert payload["warnings"], "expected a non-activated-parent warning"
        assert parent in payload["warnings"][0]
        assert "abstract base profiles" in payload["warnings"][0]

    def test_no_warning_when_parent_also_activated(self, tmp_path: Path) -> None:
        """No warning fires when every traversed ancestor is activated."""
        pair = _profile_with_parent()
        if pair is None:
            pytest.skip("No agent-profile lineage in the shipped DRG.")
        child, parent = pair
        _write_config(tmp_path, {"activated_agent_profiles": [child, parent]})
        result = _invoke(tmp_path, ["profiles", "show", child, "--json"])
        assert result.exit_code == 0, result.output
        payload = _extract_json(result.output)
        assert payload["warnings"] == []

    def test_show_non_activated_parent_is_gated_without_all(
        self, tmp_path: Path
    ) -> None:
        """A non-activated parent (abstract base) is itself gated unless --all."""
        pair = _profile_with_parent()
        if pair is None:
            pytest.skip("No agent-profile lineage in the shipped DRG.")
        child, parent = pair
        _write_config(tmp_path, {"activated_agent_profiles": [child]})
        result = _invoke(tmp_path, ["profiles", "show", parent, "--json"])
        assert result.exit_code == 1, result.output
        payload = _extract_json(result.output)
        assert payload["error"] == "profile_not_activated"
        assert payload["profile_id"] == parent
        # --all bypasses the gate for the abstract base.
        result_all = _invoke(tmp_path, ["profiles", "show", parent, "--all", "--json"])
        assert result_all.exit_code == 0, result_all.output
        payload_all = _extract_json(result_all.output)
        assert payload_all["profile_id"] == parent
