"""#6462 — a persona render parses only the doctrine domains it reads.

The reported symptom was "every CLI call re-renders the full charter context". On
current ``main`` the magnitude is seconds rather than minutes, but the mechanism is
measurable: a render enumerates **every** built-in domain (265 documents in this
repository's pack), while ``resolve_project_governance`` reads only paradigms,
directives and template sets (52 documents) and hard-codes
``tactics/styleguides/toolguides/procedures`` to ``[]``.

These are census guards, not latency tests: they count shipped documents actually
parsed (the work), never seconds. Absolute timing on a shared host is reported in the
mission traces and never asserted here (same rule as #6858).
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.charter._render_census import UNUSED_BY_PERSONA_RENDER, RenderCensus, census

pytestmark = [pytest.mark.integration]

#: A persona render may parse the domains its governance resolution reads (paradigms,
#: directives) plus headroom for small additions; it must never approach the full pack.
RENDER_PARSE_CEILING = 60

#: Every action shares one governance payload shape; the census asserts on two
#: representative ones (one bootstrap-heavy, one delivery-heavy) so the guard does
#: not spend eight minutes re-rendering six identical read sets in CI.
_CENSUS_ACTIONS = ("plan", "implement")
_PARITY_ACTIONS = ("specify", "implement")
_ACTIONS = ("specify", "plan", "tasks", "implement", "review", "merge")


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".kittify" / "charter").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root with .kittify/charter")


def _make_project(root: Path) -> Path:
    """Copy this checkout's activated charter into an isolated project at ``root``.

    Mirrors ``tests/charter/test_every_load_delivery.py``: the built-in pack ships in
    the package, so only the project-local activation surface needs copying for the
    render to resolve exactly as it does in the checkout.
    """
    src = _repo_root()
    dst_kittify = root / ".kittify"
    dst_kittify.mkdir()
    shutil.copytree(
        src / ".kittify" / "charter",
        dst_kittify / "charter",
        ignore=shutil.ignore_patterns("context-state.json"),
    )
    shutil.copy(src / ".kittify" / "config.yaml", dst_kittify / "config.yaml")
    # The project config declares the org pack by its repo-relative ``local_path``
    # (``packs/internal``). Without it the render degrades to a "Charter Pack(s) ...
    # do NOT exist on disk" bootstrap error, which is a fixture artefact, not the
    # behaviour under test. Link the checkout's fetched packs so the copy resolves
    # exactly as the checkout does.
    (root / "packs").symlink_to(src / "packs", target_is_directory=True)
    subprocess.run(["git", "init", "--quiet", str(root)], check=False, capture_output=True)
    return root


def _warm_steady_state(project: Path) -> None:
    """Record one load *per action* so every later render takes the steady-state path.

    The *first* render for an action is the bootstrap render, which deliberately
    delivers the full text of every activated artifact (that is its purpose, and a
    once-per-action cost). The reported defect is about every *subsequent* call, so
    the census measures the steady-state render: exactly what an operator pays for
    the second and following CLI invocations.
    """
    from charter.activation.context import build_charter_context

    for action in _ACTIONS:
        build_charter_context(project, action=action, mark_loaded=True)


@pytest.fixture(scope="module")
def project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """One project copy for the whole module, warmed to the steady-state render path."""
    root = _make_project(tmp_path_factory.mktemp("render-scope"))
    _warm_steady_state(root)
    yield root


def _render(project: Path, action: str) -> str:
    from charter.activation.context import build_charter_context

    context = build_charter_context(project, action=action)
    assert context.mode == "compact", (
        f"the fixture must be warmed to the steady-state render for `{action}` (got mode={context.mode!r}); "
        "this census measures what the second and following CLI calls pay"
    )
    return context.text


def _census_render(project: Path, action: str) -> tuple[str, RenderCensus]:
    with census() as state:
        text = _render(project, action)
    return text, state


class TestPersonaRenderReadSet:
    @pytest.mark.parametrize("action", _CENSUS_ACTIONS)
    def test_render_enumerates_no_unused_domain(self, project: Path, action: str) -> None:
        """A render must not parse tactic/styleguide/toolguide/procedure/profile docs.

        Red on unmodified ``main``: all 265 catalog documents are parsed for every
        action, including 121 tactic, 25 styleguide, 18 toolguide, 23 procedure and 26
        agent-profile documents that the resolution never reads.
        """
        _, state = _census_render(project, action)
        unused = state.for_kinds(UNUSED_BY_PERSONA_RENDER)
        assert unused == 0, (
            f"`{action}` render parsed {unused} document(s) from domains its governance "
            f"resolution does not read ({UNUSED_BY_PERSONA_RENDER}): {state.describe()}"
        )

    @pytest.mark.parametrize("action", _CENSUS_ACTIONS)
    def test_render_parses_at_most_the_scoped_ceiling(self, project: Path, action: str) -> None:
        """The full pack is 265 documents; a persona render may parse at most 60."""
        _, state = _census_render(project, action)
        assert state.total() <= RENDER_PARSE_CEILING, (
            f"`{action}` render parsed {state.total()} shipped documents, over the "
            f"{RENDER_PARSE_CEILING} ceiling: {state.describe()}"
        )

    def test_positive_control_unscoped_catalog_parses_more(self, project: Path) -> None:
        """The census can observe the difference it asserts (guard non-vacuity).

        An unscoped ``load_offering_catalog()`` must parse strictly more documents than
        the scoped render. If the counter were broken, both numbers would be equal (and
        the ceilings above would pass for the wrong reason).
        """
        scoped_text, scoped = _census_render(project, "implement")

        from charter.activation import catalog as catalog_module

        with census() as unscoped:
            catalog_module.load_offering_catalog()

        assert scoped_text  # the scoped render still produced governance context
        assert unscoped.total() > scoped.total(), (
            f"unscoped catalog parsed {unscoped.describe()} but the scoped render parsed "
            f"{scoped.describe()} -- the census is not observing the read set"
        )


class TestScopedRenderParity:
    """The scope may change what is read, never what is produced (spec NFR-003)."""

    @pytest.mark.parametrize("action", _PARITY_ACTIONS)
    def test_render_text_identical_without_the_scope(self, project: Path, action: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Forcing the pre-change unscoped read yields byte-identical context."""
        from charter.activation import resolver as resolver_module

        scoped_text = _render(project, action)

        monkeypatch.setattr(resolver_module, "GOVERNANCE_CATALOG_DOMAINS", None)
        unscoped_text = _render(project, action)

        assert scoped_text == unscoped_text, f"`{action}` render text changed when the catalog scope was widened"

    def test_resolved_governance_identical_without_the_scope(self, project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Resolved selections, diagnostics and template set are unchanged."""
        from charter.activation import resolver as resolver_module

        scoped = resolver_module.resolve_project_governance(project)
        monkeypatch.setattr(resolver_module, "GOVERNANCE_CATALOG_DOMAINS", None)
        unscoped = resolver_module.resolve_project_governance(project)

        assert scoped.paradigms == unscoped.paradigms
        assert scoped.directives == unscoped.directives
        assert scoped.template_set == unscoped.template_set
        assert [d.message for d in scoped.diagnostics] == [d.message for d in unscoped.diagnostics]


class TestScopeDeclarations:
    """A caller's declared scope must be exactly the domains it reads (contract S-5)."""

    def test_governance_scope_is_the_three_domains_it_reads(self) -> None:
        from charter.activation import resolver as resolver_module

        assert resolver_module.GOVERNANCE_CATALOG_DOMAINS == ("paradigms", "directives", "template_sets")

    def test_interview_scope_is_the_two_domains_it_reads(self) -> None:
        from charter.activation import interview as interview_module

        assert interview_module.INTERVIEW_CATALOG_DOMAINS == ("paradigms", "directives")

    def test_governance_resolution_never_populates_the_unscoped_kinds(self) -> None:
        """If a resolution ever starts reading another kind, its scope must widen.

        ``GovernanceResolution`` returns empty lists for tactics/styleguides/toolguides/
        procedures by construction; this pins that, so a future edit that fills one of
        them fails here instead of silently reading an empty catalog field.
        """
        project = _repo_root()
        from charter.activation import resolver as resolver_module

        resolution = resolver_module.resolve_project_governance(project)

        assert resolution.tactics == []
        assert resolution.styleguides == []
        assert resolution.toolguides == []
        assert resolution.procedures == []
