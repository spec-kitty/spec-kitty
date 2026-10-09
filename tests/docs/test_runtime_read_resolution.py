"""WP01 — runtime-read resolution tests (Mission B, NFR-005 / C-003).

Mission B folds ``architecture/`` into ``docs/`` and relocates the glossary
(``glossary/contexts/`` → ``docs/context/``) and the shim-registry
(``architecture/2.x/shim-registry.yaml`` → ``docs/migrations/shim-registry.yaml``).

The six *runtime-critical reads* that resolve those paths at runtime must be
re-pointed **before** the tree moves, each staged as a **dual-read** (old ∪
new) so the read resolves both *before* the move (old branch) and *after* it
(new branch). These tests exercise the **real reader** for each of the six
reads against a fixture tree that mirrors the *post-move* layout, proving the
new path resolves — and a companion assertion proving the *old* path no longer
resolves (WP08 dropped the dual-read once the tree landed; new home only).

A test here that merely asserts ``literal == "docs/..."`` would be a
false-green: every case drives the production reader (``render_authority_paths``,
``load_registry`` / ``check_shim_registry``, ``resolve_glossary_contexts_dir``,
``_print_overdue_details``) so a stale literal reds the test.

The six reads (``occurrence_map.yaml`` → ``status.runtime_critical_reads``):

1. ``authority_paths.py`` ADR default       → ``docs/adr/3.x/``
2. ``authority_paths.py`` glossary default  → ``docs/context/``
3. ``compat/doctor.py`` ``check_shim_registry`` → ``docs/migrations/shim-registry.yaml``
4. ``compat/registry.py`` ``load_registry``     → ``docs/migrations/shim-registry.yaml``
5. ``scripts/generate_contextive_glossaries.py`` glossary source → ``docs/context/``
6. ``.kittify/charter/governance.yaml`` ``authority_paths`` (canonical source:
   ``.kittify/charter/charter.md`` — governance.yaml is gitignored/generated)
   → ``docs/context/`` + ``docs/adr/3.x/``
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from ruamel.yaml import YAML

from charter.activation.context_renderers import render_authority_paths
from charter.activation.context_renderers.authority_paths import DEFAULT_AUTHORITY_PATHS
from charter.activation.schemas import GovernanceCharterConfig
from scripts.generate_contextive_glossaries import (
    resolve_glossary_contexts_dir,
)
from specify_cli.cli.commands.doctor import _print_overdue_details
from specify_cli.compat.doctor import (
    ShimRegistryReport,
    ShimStatus,
    ShimStatusEntry,
    check_shim_registry,
)
from specify_cli.compat.registry import ShimEntry, load_registry

# ``scripts`` is a PEP-420 namespace package; the repo root is already on
# ``sys.path`` via pytest's own rootdir-prepend (``tests/__init__.py``), so no
# manual bootstrap is needed for the script import above.
_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.fast


# New (post-move) homes the six reads must resolve to.
NEW_ADR_DIR = "docs/adr/3.x"
NEW_CONTEXT_DIR = "docs/context"
NEW_SHIM_REGISTRY = ("docs", "migrations", "shim-registry.yaml")
# Legacy (pre-move) homes that must keep resolving until WP08 drops them.
OLD_ADR_DIR = "architecture/3.x/adr"
OLD_CONTEXT_DIR = "glossary/contexts"
OLD_SHIM_REGISTRY = ("architecture", "2.x", "shim-registry.yaml")

_VALID_SHIM = {
    "legacy_path": "specify_cli.old_module",
    "canonical_import": "specify_cli.new_module",
    "introduced_in_release": "3.2.0",
    "removal_target_release": "3.3.0",
    "tracker_issue": "#615",
    "grandfathered": False,
}
_PYPROJECT = '[project]\nname = "demo"\nversion = "3.2.5"\n'


def _mkdir(root: Path, relative: str) -> None:
    (root / relative).mkdir(parents=True, exist_ok=True)


def _write_registry(root: Path, parts: tuple[str, ...]) -> Path:
    registry = root.joinpath(*parts)
    registry.parent.mkdir(parents=True, exist_ok=True)
    ruamel = YAML()
    with registry.open("w") as fp:
        ruamel.dump({"shims": [_VALID_SHIM]}, fp)
    return registry


# ---------------------------------------------------------------------------
# Read 1 + 2 — authority_paths.py defaults (ADR + glossary)
# ---------------------------------------------------------------------------


class TestAuthorityPathDefaultsResolveNewHomes:
    def test_adr_default_resolves_docs_adr_3x(self, tmp_path: Path) -> None:
        """Read 1: only the NEW ADR home exists → renderer surfaces it."""
        _mkdir(tmp_path, NEW_ADR_DIR)
        result = render_authority_paths(tmp_path, GovernanceCharterConfig())
        assert f"{NEW_ADR_DIR}/" in result

    def test_glossary_default_resolves_docs_context(self, tmp_path: Path) -> None:
        """Read 2 (the spec's missed 4th read): only NEW glossary home exists."""
        _mkdir(tmp_path, NEW_CONTEXT_DIR)
        result = render_authority_paths(tmp_path, GovernanceCharterConfig())
        assert f"{NEW_CONTEXT_DIR}/" in result

    def test_old_homes_no_longer_resolve(self, tmp_path: Path) -> None:
        """WP08 dropped the dual-read: the legacy homes are no longer defaults."""
        _mkdir(tmp_path, OLD_ADR_DIR)
        _mkdir(tmp_path, OLD_CONTEXT_DIR)
        result = render_authority_paths(tmp_path, GovernanceCharterConfig())
        assert f"{OLD_ADR_DIR}/" not in result
        assert f"{OLD_CONTEXT_DIR}/" not in result

    def test_both_new_homes_are_registered_defaults(self) -> None:
        """The new homes are real default keys, not only fixture artefacts."""
        assert f"{NEW_ADR_DIR}/" in DEFAULT_AUTHORITY_PATHS
        assert f"{NEW_CONTEXT_DIR}/" in DEFAULT_AUTHORITY_PATHS


# ---------------------------------------------------------------------------
# Read 3 + 4 — shim-registry readers (doctor.py + registry.py)
# ---------------------------------------------------------------------------


class TestShimRegistryReadersResolveNewHome:
    def test_load_registry_resolves_docs_migrations(self, tmp_path: Path) -> None:
        """Read 4: registry only at the NEW home → load_registry finds it."""
        _write_registry(tmp_path, NEW_SHIM_REGISTRY)
        entries = load_registry(tmp_path)
        assert frozenset(e.legacy_path for e in entries) == frozenset({"specify_cli.old_module"})
        assert isinstance(entries[0], ShimEntry)

    def test_check_shim_registry_reports_new_home(self, tmp_path: Path) -> None:
        """Read 3: check_shim_registry resolves + reports the NEW home path."""
        _write_registry(tmp_path, NEW_SHIM_REGISTRY)
        (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
        report = check_shim_registry(tmp_path)
        assert report.registry_path == tmp_path.joinpath(*NEW_SHIM_REGISTRY)

    def test_old_home_no_longer_resolves(self, tmp_path: Path) -> None:
        """WP08 dropped the dual-read: the legacy architecture/2.x home is not read."""
        _write_registry(tmp_path, OLD_SHIM_REGISTRY)
        with pytest.raises(FileNotFoundError):
            load_registry(tmp_path)

    def test_new_home_preferred_over_old(self, tmp_path: Path) -> None:
        """When both exist, the NEW home wins (forward-correct resolution)."""
        _write_registry(tmp_path, OLD_SHIM_REGISTRY)
        _write_registry(tmp_path, NEW_SHIM_REGISTRY)
        (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
        report = check_shim_registry(tmp_path)
        assert report.registry_path == tmp_path.joinpath(*NEW_SHIM_REGISTRY)


# ---------------------------------------------------------------------------
# Read 5 (T005) — doctor CLI remediation string lock-step
# ---------------------------------------------------------------------------


class TestRemediationStringNamesNewHome:
    def test_overdue_remediation_names_docs_migrations(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The user-facing remediation must name the NEW shim-registry home."""
        from rich.console import Console

        entry = ShimEntry(
            legacy_path="specify_cli.old_module",
            canonical_import="specify_cli.new_module",
            introduced_in_release="3.2.0",
            removal_target_release="3.2.0",
            tracker_issue="#615",
            grandfathered=False,
        )
        report = ShimRegistryReport(
            entries=[ShimStatusEntry(entry=entry, status=ShimStatus.OVERDUE, shim_exists=True)],
            project_version="3.2.5",
            registry_path=Path("docs/migrations/shim-registry.yaml"),
        )
        _print_overdue_details(report, Console(force_terminal=False))
        out = capsys.readouterr().out
        assert "docs/migrations/shim-registry.yaml" in out
        assert "architecture/2.x/shim-registry.yaml" not in out


# ---------------------------------------------------------------------------
# Read 5 (map) — generate_contextive_glossaries glossary source
# ---------------------------------------------------------------------------


class TestGlossarySourceResolvesNewHome:
    def test_resolves_docs_context(self, tmp_path: Path) -> None:
        """Read 5: only the NEW glossary home exists → resolver returns it."""
        _mkdir(tmp_path, NEW_CONTEXT_DIR)
        resolved = resolve_glossary_contexts_dir(tmp_path)
        assert resolved == tmp_path / NEW_CONTEXT_DIR

    def test_old_home_no_longer_resolves(self, tmp_path: Path) -> None:
        """WP08 dropped the dual-read: the resolver returns only docs/context."""
        _mkdir(tmp_path, OLD_CONTEXT_DIR)
        resolved = resolve_glossary_contexts_dir(tmp_path)
        assert resolved == tmp_path / NEW_CONTEXT_DIR

    def test_new_home_preferred_over_old(self, tmp_path: Path) -> None:
        _mkdir(tmp_path, OLD_CONTEXT_DIR)
        _mkdir(tmp_path, NEW_CONTEXT_DIR)
        resolved = resolve_glossary_contexts_dir(tmp_path)
        assert resolved == tmp_path / NEW_CONTEXT_DIR


# ---------------------------------------------------------------------------
# Read 6 — governance authority_paths (canonical source: charter.md)
# ---------------------------------------------------------------------------


def _charter_authority_paths() -> list[str]:
    """Extract the ``authority_paths`` list from the charter's fenced YAML block.

    ``.kittify/charter/governance.yaml`` is gitignored and regenerated from
    ``charter.md`` by ``spec-kitty charter sync``; ``charter.md`` is therefore
    the durable, tracked source of the authority-path values that flow into the
    runtime ``GovernanceCharterConfig``.
    """
    charter_md = _REPO_ROOT / ".kittify" / "charter" / "charter.md"
    text = charter_md.read_text(encoding="utf-8")
    for block in text.split("```yaml")[1:]:
        body = block.split("```", 1)[0]
        data = yaml.safe_load(body)
        if isinstance(data, dict) and "authority_paths" in data:
            paths = data["authority_paths"]
            assert isinstance(paths, list)
            return [str(p) for p in paths]
    raise AssertionError("charter.md has no authority_paths YAML block")


class TestGovernanceAuthorityPathsRepointed:
    def test_charter_lists_new_homes(self) -> None:
        """Read 6: the canonical governance config names the NEW homes."""
        paths = _charter_authority_paths()
        assert "docs/context/" in paths
        assert "docs/adr/3.x/" in paths

    def test_charter_dropped_legacy_homes_post_fold(self) -> None:
        """Post Common Docs fold: the legacy authority paths are dropped.

        The transitional dual-read (legacy + new homes) is collapsed once the
        docs/ fold lands — the reference sweep removes the dead legacy branches
        (glossary/contexts/, architecture/3.x/adr/, architecture/adrs/) so the
        charter names only the canonical new homes. This inverts the former
        dual-read guard, which asserted the legacy paths were still present.
        """
        paths = _charter_authority_paths()
        assert "glossary/contexts/" not in paths
        assert "architecture/3.x/adr/" not in paths
        assert "architecture/adrs/" not in paths

    def test_charter_declared_new_homes_resolve_through_renderer(self, tmp_path: Path) -> None:
        """The real reader (render_authority_paths) resolves charter values.

        Feed the charter's declared authority paths into the renderer against a
        tree where only the NEW homes exist; the renderer must surface them.
        """
        _mkdir(tmp_path, NEW_CONTEXT_DIR)
        _mkdir(tmp_path, NEW_ADR_DIR)
        selection = GovernanceCharterConfig(authority_paths=_charter_authority_paths())
        result = render_authority_paths(tmp_path, selection)
        assert f"{NEW_CONTEXT_DIR}/" in result
        assert f"{NEW_ADR_DIR}/" in result
