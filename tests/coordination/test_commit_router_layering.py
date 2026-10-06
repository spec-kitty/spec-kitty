"""Layering tests for commit_router (WP02 / T009 — #2061).

Two concerns:
(a) Byte-identical classification: paths under ``.worktrees/`` are classified
    the same way by ``is_under_worktrees_segment`` (used inside commit_router)
    and by the direct primitive from ``coordination.surface_resolver``.

(b) Import-direction assertion: ``coordination.commit_router`` must have ZERO
    ``from specify_cli.cli`` imports.  The test is written to fail if the
    reach-in returns.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# (a) Byte-identical classification test
# ---------------------------------------------------------------------------


class TestWorktreesClassificationByteIdentical:
    """is_under_worktrees_segment classifies paths in commit_router identically
    to the direct primitive from surface_resolver."""

    def _classify_via_surface_resolver(self, path: Path) -> bool:
        from specify_cli.coordination.surface_resolver import is_under_worktrees_segment

        return is_under_worktrees_segment(path)

    @pytest.mark.parametrize(
        "rel_path,expected",
        [
            # Paths that ARE under .worktrees
            (Path(".worktrees/my-mission-lane-1/kitty-specs/spec.md"), True),
            (Path(".worktrees/slug-ABCD1234-lane-2"), True),
            (Path("parent/.worktrees/nested/file.txt"), True),
            # Paths that are NOT under .worktrees
            (Path("kitty-specs/mission/tasks/WP01.md"), False),
            (Path("src/specify_cli/coordination/commit_router.py"), False),
            (Path(".kittify/config.yaml"), False),
            (Path("worktrees-adjacent/file.txt"), False),  # no leading dot
        ],
    )
    def test_classification_matches_primitive(
        self, tmp_path: Path, rel_path: Path, expected: bool
    ) -> None:
        """Classification result matches what surface_resolver.is_under_worktrees_segment returns."""
        # The primitive is the same function commit_router now calls directly.
        result = self._classify_via_surface_resolver(rel_path)
        assert result is expected, (
            f"is_under_worktrees_segment({rel_path!r}) returned {result!r}; expected {expected!r}"
        )

    def test_worktrees_staging_path(self, tmp_path: Path) -> None:
        """A realistic staging path rooted under .worktrees classifies as True."""
        # Shape that appears in _stage_finalize_artifacts_in_coord_worktree
        staging_rel = Path(".worktrees") / "my-mission-01ABCDEF-lane-a" / "kitty-specs" / "tasks.md"
        assert self._classify_via_surface_resolver(staging_rel) is True

    def test_non_worktrees_planning_path(self, tmp_path: Path) -> None:
        """A planning artifact path NOT under .worktrees classifies as False."""
        planning_rel = Path("kitty-specs") / "my-mission-01ABCDEF" / "tasks.md"
        assert self._classify_via_surface_resolver(planning_rel) is False


# ---------------------------------------------------------------------------
# (b) Import-direction assertion: zero `from specify_cli.cli` in commit_router
# ---------------------------------------------------------------------------


class TestCommitRouterImportDirection:
    """commit_router.py must not import from specify_cli.cli (inverted-layering guard)."""

    def _get_commit_router_source(self) -> str:
        spec = importlib.util.find_spec("specify_cli.coordination.commit_router")
        assert spec is not None, "specify_cli.coordination.commit_router not found on sys.path"
        assert spec.origin is not None, "commit_router has no origin path"
        return Path(spec.origin).read_text(encoding="utf-8")

    def test_no_from_specify_cli_cli_imports(self) -> None:
        """commit_router.py contains ZERO 'from specify_cli.cli' import statements.

        This test fails if the inverted-layering reach-in is re-introduced — it is
        the enforcement gate for #2061.
        """
        source = self._get_commit_router_source()
        tree = ast.parse(source)

        cli_imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("specify_cli.cli"):
                    cli_imports.append(
                        f"  line {node.lineno}: from {module} import "
                        + ", ".join(alias.name for alias in node.names)
                    )

        assert not cli_imports, (
            "coordination/commit_router.py has forbidden 'specify_cli.cli' imports "
            "(inverted layering — coordination must not reach into cli):\n"
            + "\n".join(cli_imports)
        )

    def test_has_surface_resolver_import(self) -> None:
        """commit_router.py imports is_under_worktrees_segment from surface_resolver
        (positive check — confirms the correct seam is wired)."""
        source = self._get_commit_router_source()
        tree = ast.parse(source)

        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "specify_cli.coordination.surface_resolver":
                    names = [alias.name for alias in node.names]
                    if "is_under_worktrees_segment" in names:
                        found = True
                        break

        assert found, (
            "coordination/commit_router.py does NOT import is_under_worktrees_segment "
            "from specify_cli.coordination.surface_resolver — the seam may be broken."
        )


# ---------------------------------------------------------------------------
# (c) No-CLI import guard for the implement-degod seams (C-004)
# ---------------------------------------------------------------------------
#
# Lower-package modules that receive code moved out of the ``implement`` command
# must never import the CLI layer (``specify_cli.cli*``), ``typer`` or ``rich`` (the
# console): they return typed results or raise typed errors, and only the command
# package prints. Each work package that moves code into a lower module adds
# that module here.

_NO_CLI_SEAM_MODULES: tuple[str, ...] = (
    # WP03: context reads (find_wp_file, resolve_lane_state_dir, resolve_mission_target_branch)
    "specify_cli.workspace.context",
    # WP03: claim-precondition decision (ensure_wp_claim_preconditions)
    "specify_cli.core.dependency_graph",
    # WP04: planning-commit decisions (partition, guard, demotion verdict, identifiers)
    "specify_cli.coordination.planning_commit",
    # WP05: git_stdout (public leaf the planning-commit adapter and the base-ref code import).
    # #5715 drained its last lazy ``cli.console`` import: the guard now has no exceptions.
    "specify_cli.lanes.implement_support",
    # WP08: claim_policy_metadata (the claim triple shared by implement and the workflow executor)
    "specify_cli.status.emit",
)

#: Third-party packages that are presentation by nature: ``typer`` (exits, prompts) and ``rich``
#: (console rendering, C-004 forbids printing below the command package).
_CLI_TOP_LEVEL_PACKAGES = frozenset({"typer", "rich"})


def _resolve_relative_module(node: ast.ImportFrom, package: str) -> str:
    """The absolute dotted module a ``from <dots><module> import ...`` statement names.

    *package* is the dotted package the scanned file lives in (``specify_cli.coordination`` for
    ``specify_cli/coordination/x.py``); each extra leading dot climbs one package.
    """
    if node.level == 0:
        return node.module or ""
    anchor = package.split(".")[: len(package.split(".")) - (node.level - 1)]
    return ".".join([*anchor, *([node.module] if node.module else [])])


def _cli_layer_imports(source: str, package: str = "") -> list[str]:
    """Every import of ``specify_cli.cli*``, ``typer`` or ``rich`` in *source*, at any nesting depth.

    ``ast.walk`` descends into function bodies, so a lazy (function-local) import is caught too.
    Relative imports (``from ..cli import x``) are resolved against *package* before the test.
    """
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            module = _resolve_relative_module(node, package)
            names = [f"{module}.{alias.name}" for alias in node.names]
            candidates = [module, *names]
        elif isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        else:
            continue
        for candidate in candidates:
            top = candidate.split(".")[0]
            if top in _CLI_TOP_LEVEL_PACKAGES or candidate == "specify_cli.cli" or candidate.startswith("specify_cli.cli."):
                offenders.append(f"line {node.lineno}: {candidate}")
                break
    return offenders


def _seam_cli_layer_imports(module_name: str) -> list[str]:
    """``_cli_layer_imports`` over *module_name*'s source, relative imports resolved against its package.

    ``spec.parent`` is the package relative imports resolve against: the module's parent package for
    a submodule, and the package itself for a package ``__init__`` (where ``rpartition`` would climb
    one level too far).
    """
    spec = importlib.util.find_spec(module_name)
    assert spec is not None and spec.origin is not None, f"{module_name} not found on sys.path"
    return _cli_layer_imports(Path(spec.origin).read_text(encoding="utf-8"), spec.parent or "")


def _lanes_package_modules() -> list[str]:
    """Every module of the ``specify_cli.lanes`` package, the package ``__init__`` included."""
    import specify_cli.lanes as lanes_package

    return ["specify_cli.lanes", *sorted(info.name for info in pkgutil.walk_packages(lanes_package.__path__, "specify_cli.lanes."))]


class TestSeamModulesHaveNoCliImports:
    """The seams the ``implement`` command delegates to stay free of CLI-layer imports."""

    @pytest.mark.parametrize("module_name", _NO_CLI_SEAM_MODULES)
    def test_seam_module_imports_no_cli_layer(self, module_name: str) -> None:
        offenders = _seam_cli_layer_imports(module_name)

        assert not offenders, (
            f"{module_name} imports the CLI layer (C-004: lower packages return typed results or "
            "raise typed errors; only the command package prints):\n  " + "\n  ".join(offenders)
        )

    @pytest.mark.parametrize(
        "source",
        [
            "from specify_cli.cli.console import console\n",
            "from specify_cli.cli import StepTracker\n",
            "from specify_cli import cli\n",
            "import specify_cli.cli.commands.implement\n",
            "import typer\n",
            "from typer import Exit\n",
            "import rich\n",
            "from rich.panel import Panel\n",
            "def f():\n    from rich.console import Console\n    return Console()\n",
            "def f():\n    from specify_cli.cli.console import console\n    return console\n",
        ],
    )
    def test_scanner_flags_every_cli_import_form(self, source: str) -> None:
        """Non-vacuity: the scanner catches module-level, lazy, ``import`` and ``from`` forms."""
        assert _cli_layer_imports(source)

    def test_scanner_resolves_a_package_init_against_the_package_itself(self) -> None:
        """Non-vacuity for ``spec.parent``: ``specify_cli/cli/__init__.py``'s ``from .step_tracker import``
        is ``specify_cli.cli.step_tracker`` (CLI layer), not ``specify_cli.step_tracker``."""
        assert "line 10: specify_cli.cli.step_tracker" in _seam_cli_layer_imports("specify_cli.cli")

    @pytest.mark.parametrize("module_name", _lanes_package_modules())
    def test_lanes_package_imports_no_cli_layer(self, module_name: str) -> None:
        """#5715: no module of ``specify_cli.lanes`` imports the CLI layer (empty allow-list).

        The lanes seam returns typed results (e.g. ``LaneWorkspaceResult.hook_backup_path``) and the
        ``implement`` command package prints them.
        """
        offenders = _seam_cli_layer_imports(module_name)

        assert not offenders, (
            f"{module_name} imports the CLI layer (#5715: the lanes seam returns typed results; the command layer prints):\n  " + "\n  ".join(offenders)
        )

    def test_lanes_package_scan_is_not_vacuous(self) -> None:
        """Non-vacuity: the lanes sweep covers the seam ``implement`` delegates to."""
        assert "specify_cli.lanes.implement_support" in _lanes_package_modules()

    @pytest.mark.parametrize(
        "source",
        [
            "from specify_cli.status import Lane\n",
            "from specify_cli.core.dependency_graph import parse_wp_dependencies\n",
            "import specify_cli.clients\n",
        ],
    )
    def test_scanner_ignores_non_cli_imports(self, source: str) -> None:
        assert not _cli_layer_imports(source)

    @pytest.mark.parametrize(
        ("source", "package"),
        [
            ("from ..cli import StepTracker\n", "specify_cli.coordination"),
            ("from ..cli.console import console\n", "specify_cli.coordination"),
            ("from .. import cli\n", "specify_cli.coordination"),
            ("from ...cli import x\n", "specify_cli.coordination.sub"),
            ("def f():\n    from ..cli.console import console\n", "specify_cli.workspace"),
        ],
    )
    def test_scanner_flags_relative_cli_imports(self, source: str, package: str) -> None:
        """Non-vacuity: a relative import that resolves into ``specify_cli.cli`` is caught."""
        assert _cli_layer_imports(source, package)

    @pytest.mark.parametrize(
        ("source", "package"),
        [
            ("from ..status import Lane\n", "specify_cli.coordination"),
            ("from . import coherence\n", "specify_cli.coordination"),
            ("from .coherence import is_coord_residue_churn\n", "specify_cli.coordination"),
        ],
    )
    def test_scanner_ignores_relative_non_cli_imports(self, source: str, package: str) -> None:
        assert not _cli_layer_imports(source, package)
