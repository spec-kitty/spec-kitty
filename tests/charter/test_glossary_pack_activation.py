"""WP04 T023 — glossary-pack default-on + generic cascade end-to-end.

Covers the two DoD items T023 owns:

* **Default-on, no manual activation** (FR-007, SC-003): with a project that
  has never run ``charter activate``, the built-in ``spec-kitty-core``
  glossary pack still resolves as *active* through the same
  ``PackContext`` -> ``filter_graph_by_activation`` seam every other
  built-in artifact kind uses. A negative control (an explicit
  ``activated_kinds`` list that omits ``glossary_packs``) proves the
  positive assertion is not vacuous.
* **Generic cascade** (FR-009): ``spec-kitty charter activate/deactivate
  glossary-pack spec-kitty-core --cascade all`` round-trips through the
  existing CLI + engine + cascade seam with NO glossary-pack-specific
  branch anywhere in that path (per the WP04 boundary: cascade is
  kind-agnostic, driven entirely by DRG `requires`/`suggests` edges).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger
from click.testing import Result
from typer.testing import CliRunner

from charter.drg import load_built_in_graph
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.pack_context import PackContext
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.fast]

_PACK_URN = "glossary_pack:spec-kitty-core"

runner = CliRunner()


def _write_config(tmp_path: Path, content: str) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Default-on, no manual `charter activate` (FR-007, SC-003)
# ---------------------------------------------------------------------------


class TestGlossaryPackDefaultOnEndToEnd:
    """The built-in pack resolves as active with zero manual activation."""

    def test_no_config_at_all_resolves_glossary_pack_active(
        self, tmp_path: Path
    ) -> None:
        """No ``.kittify/config.yaml`` whatsoever -> full built-in fallback.

        ``PackContext.from_config`` on a directory with no config file at
        all still yields ``activated_kinds == _BUILTIN_ARTIFACT_KINDS``
        (backward-compat default), which must now include
        ``glossary_packs`` for the built-in pack to survive the filter.

        A minimal ``config.yaml`` carrying ONLY ``mission_type_activations``
        is written here -- WP04 (C-A1) fail-closes ``from_config`` on that
        key's absence regardless of ``activated_kinds``, which this test
        does not exercise; no ``activated_kinds`` key is written, so the
        default-on behaviour under test is untouched.
        """
        _write_config(tmp_path, "mission_type_activations:\n  - software-dev\n")
        pack_context = PackContext.from_config(tmp_path)
        graph = load_built_in_graph()
        filtered = filter_graph_by_activation(graph, pack_context)

        urns = {node.urn for node in filtered.nodes}
        assert _PACK_URN in urns, (
            f"{_PACK_URN} did not survive the activation filter on a project "
            "with NO config.yaml at all -- the built-in glossary pack is "
            "not shipping active by default."
        )

    def test_minimal_config_with_no_activation_keys_resolves_active(
        self, tmp_path: Path
    ) -> None:
        """A real ``config.yaml`` present, but no ``activated_kinds`` key.

        This is the shape every un-migrated / freshly-bootstrapped project
        actually has (see also ``test_pack_context.py::_MINIMAL_CONFIG``).
        """
        _write_config(
            tmp_path,
            "vcs:\n  type: git\nagents:\n  available:\n    - claude\n"
            "mission_type_activations:\n  - software-dev\n",
        )
        pack_context = PackContext.from_config(tmp_path)
        assert "glossary_packs" in pack_context.activated_kinds

        graph = load_built_in_graph()
        filtered = filter_graph_by_activation(graph, pack_context)
        urns = {node.urn for node in filtered.nodes}
        assert _PACK_URN in urns

    def test_negative_control_explicit_activated_kinds_without_glossary_packs(
        self, tmp_path: Path
    ) -> None:
        """Non-vacuity proof: an explicit ``activated_kinds`` that OMITS
        ``glossary_packs`` (but includes other kinds) must filter the
        built-in pack node OUT.

        Without this negative control, the positive assertions above could
        pass merely because ``filter_graph_by_activation`` never filters
        anything -- this proves the filter is actually kind-sensitive for
        glossary packs specifically.
        """
        _write_config(
            tmp_path,
            "vcs:\n  type: git\nactivated_kinds:\n  - directives\n  - tactics\n"
            "mission_type_activations:\n  - software-dev\n",
        )
        pack_context = PackContext.from_config(tmp_path)
        assert "glossary_packs" not in pack_context.activated_kinds

        graph = load_built_in_graph()
        filtered = filter_graph_by_activation(graph, pack_context)
        urns = {node.urn for node in filtered.nodes}
        assert _PACK_URN not in urns, (
            f"{_PACK_URN} survived the filter even though 'glossary_packs' "
            "was explicitly excluded from activated_kinds -- the filter is "
            "not actually kind-sensitive for glossary packs (this guard "
            "would not have caught a missing charter.drg kind-map entry)."
        )
        # Sanity: the control must still keep OTHER kinds' nodes, otherwise
        # it would prove nothing about this kind specifically.
        assert any(u.startswith("directive:") for u in urns)


# ---------------------------------------------------------------------------
# Generic cascade activate/deactivate (FR-009)
# ---------------------------------------------------------------------------


def _invoke(project_root: Path, *args: str) -> Result:
    return runner.invoke(
        charter_app,
        [*args[:1], "--repo-root", str(project_root), *args[1:]],
        catch_exceptions=False,
    )


class TestGlossaryPackCascadeIsGeneric:
    """``--cascade all`` round-trips through the SAME engine every other
    kind uses -- no glossary-pack-specific branch anywhere in the path.
    """

    @pytest.fixture()
    def project_root(self, tmp_path: Path) -> Path:
        """A ledger project: a deactivation records a deny entry, which only the ledger holds (FR-017)."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "config.yaml").write_text("# no activation keys\n", encoding="utf-8")
        seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"])
        return tmp_path

    def test_activate_glossary_pack_with_cascade_all_writes_config(
        self, project_root: Path
    ) -> None:
        result = _invoke(
            project_root,
            "activate",
            "glossary-pack",
            "spec-kitty-core",
            "--cascade",
            "all",
        )
        assert result.exit_code == 0, result.output

        data = read_activation_ledger(project_root)
        assert "spec-kitty-core" in data["activated_glossary_packs"]

    def test_deactivate_glossary_pack_with_cascade_all_removes_from_config(
        self, project_root: Path
    ) -> None:
        _invoke(
            project_root,
            "activate",
            "glossary-pack",
            "spec-kitty-core",
            "--cascade",
            "all",
        )
        result = _invoke(
            project_root,
            "deactivate",
            "glossary-pack",
            "spec-kitty-core",
            "--cascade",
            "all",
        )
        assert result.exit_code == 0, result.output

        data = read_activation_ledger(project_root)
        assert "spec-kitty-core" not in data.get("activated_glossary_packs", [])

    def test_activate_unknown_glossary_pack_id_exits_1_without_mutating(
        self, project_root: Path
    ) -> None:
        """Same fail-closed contract every other kind gets -- proves no
        glossary-pack-specific shortcut bypasses ID validation."""
        result = runner.invoke(
            charter_app,
            [
                "activate",
                "--repo-root",
                str(project_root),
                "glossary-pack",
                "not-a-real-pack",
            ],
        )
        assert result.exit_code == 1
        assert "Unknown glossary-pack ID" in result.output

        data = read_activation_ledger(project_root)
        assert "activated_glossary_packs" not in data
