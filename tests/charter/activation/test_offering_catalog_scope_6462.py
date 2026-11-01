"""#6462 — the offering catalog reads only the domains a caller names.

Contract: ``kitty-specs/issue-6462-charter-render-scope-per-call-01M69065/contracts/offering-catalog-scope.md``
(S-1..S-7). These tests pin the loader itself; the render-level guards live in
``tests/charter/test_charter_render_scope_6462.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation import catalog as catalog_module
from tests.charter._render_census import census

pytestmark = [pytest.mark.integration]


class TestDefaultScopePreserved:
    """S-1: no argument keeps today's behaviour for every existing caller."""

    def test_default_scans_every_domain(self) -> None:
        catalog = catalog_module.load_offering_catalog()

        assert catalog.domains_scanned == frozenset(catalog_module.CATALOG_DOMAINS)
        assert catalog.paradigms, "default load must carry paradigms"
        assert catalog.directives, "default load must carry directives"
        assert catalog.tactics, "default load must carry tactics"
        assert catalog.styleguides
        assert catalog.toolguides
        assert catalog.procedures
        assert catalog.agent_profiles
        assert {"paradigms", "directives", "tactics"} <= catalog.domains_present


class TestExplicitScope:
    """S-2/S-4/S-5: a named scope reads exactly those domains and says so."""

    def test_single_domain_reads_only_that_domain(self) -> None:
        with census() as state:
            catalog = catalog_module.load_offering_catalog(domains=["paradigms"])

        assert catalog.paradigms, "the requested domain must be read"
        assert catalog.domains_scanned == frozenset({"paradigms"})
        assert catalog.tactics == frozenset()
        assert catalog.directives == frozenset()
        assert state.for_kinds(("tactic", "directive", "styleguide", "toolguide", "procedure", "agent_profile")) == 0, (
            f"a paradigms-only load parsed other domains: {state.describe()}"
        )

    def test_scope_narrows_the_scan(self) -> None:
        with census() as scoped_state:
            catalog_module.load_offering_catalog(domains=["paradigms"])
        with census() as full_state:
            catalog_module.load_offering_catalog()

        assert scoped_state.total() < full_state.total(), (
            f"scoped load parsed {scoped_state.describe()}; unscoped parsed {full_state.describe()} -- the scope is not narrowing the read"
        )

    def test_empty_scope_reads_nothing(self) -> None:
        with census() as state:
            catalog = catalog_module.load_offering_catalog(domains=[])

        assert state.total() == 0, f"an empty scope must read nothing, parsed: {state.describe()}"
        assert catalog.domains_scanned == frozenset()
        assert catalog.domains_present == frozenset()
        assert catalog.paradigms == frozenset()
        assert catalog.template_sets == frozenset()


class TestUnknownDomainRefused:
    """S-3: a typo fails closed, before any read."""

    def test_unknown_domain_raises_before_reading(self) -> None:
        with census() as state, pytest.raises(ValueError, match="Unknown catalog domain"):
            catalog_module.load_offering_catalog(domains=["paradigms", "tactic"])

        assert state.total() == 0, f"the refusal must happen before any file read, parsed: {state.describe()}"

    def test_error_names_the_known_domains(self) -> None:
        with pytest.raises(ValueError, match="Unknown catalog domain") as excinfo:
            catalog_module.load_offering_catalog(domains=["nonsense"])

        message = str(excinfo.value)
        assert "nonsense" in message
        assert "paradigms" in message and "agent_profiles" in message


class TestAbsentDomainSemantics:
    """S-4: a scoped domain that is not deployed keeps its old meaning."""

    def test_absent_directory_is_not_reported_present(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(catalog_module, "built_in_dir", lambda kind: tmp_path / "missing" / kind.plural)

        catalog = catalog_module.load_offering_catalog(domains=["paradigms", "directives"])

        assert catalog.domains_scanned == frozenset({"paradigms", "directives"})
        assert catalog.domains_present == frozenset(), "an undeployed domain must not be reported present"
        assert catalog.paradigms == frozenset()


class TestLanguageScopeUnchanged:
    """S-7: the language filter still applies inside a scoped read."""

    def test_language_filter_still_filters_within_the_scope(self) -> None:
        unfiltered = catalog_module.load_offering_catalog(domains=["toolguides"])
        filtered = catalog_module.load_offering_catalog(domains=["toolguides"], active_languages=["python"])

        assert unfiltered.toolguides, "the toolguide domain must carry ids without a language filter"
        assert filtered.toolguides < unfiltered.toolguides, "a python-only scope must drop languages the pack does not declare for python"
