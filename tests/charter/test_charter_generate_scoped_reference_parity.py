"""Issue #5257 regression: ``charter generate`` drops scoped activated references.

Red-first, FR-005 (mission ``charter-generation-drops-scoped-references-01M3M1KF``).

Root cause (see ``plan.md``'s Summary and User Story 1): ``_render_kind_references``/
``_build_references_from_service`` (``src/charter/activation/compiler.py``) look up
every DRG-backed activated reference id against ``_raw_kind_repository`` -- which
strips only the *activation-config* filter. The underlying per-kind repository was
already constructed with ``active_languages=infer_repo_languages(repo_root)`` baked
in, so an id that is present on disk but excluded solely by language/scope filtering
misses the lookup exactly like a genuinely nonexistent id: the miss is recorded as an
opaque ``"Unresolved reference: <kind>/<id>"`` diagnostics-list string and the
reference silently vanishes from ``catalog.references`` (#5257 / #5253).

This test drives the real ``compile_charter``/``charter generate`` production entry
point (via the ``charter_app`` CLI, per plan.md's ATDD-First Discipline section --
NOT an internal helper function) against a fixture repo that activates the six
#5257 ids plus one additional, differently language-scoped id (styleguide/
drupal-conventions, php/twig-scoped -- C-002: proves the general mechanism, not six
special cases), then feeds the result through ``run_consistency_check`` directly
(spec.md Acceptance Scenario 3), rather than
``tests/doctrine/test_activation_parity_guard.py::test_this_project_charter_pack_is_coherent``,
which is hardcoded to this checkout's own ``_REPO_ROOT`` and cannot be conditioned on
an arbitrary fixture path.

Precedent extended, not rebuilt (plan.md IC-04): ``_git_init``/``_invoke_generate``/
``_read_catalog``/``_write_curated_charter_md`` are imported from
``tests/charter/test_active_languages_idempotency.py`` (issue #3292, the same defect
class -- a language-scoped doctrine artifact silently degrading rather than
resolving), whose fixture machinery already builds a real ``tmp_path`` git repo and
drives the real ``charter_app`` ``generate`` CLI via ``typer.testing.CliRunner``.

Confirmed RED against this mission's base commit
``af847be71d97c8a126e91c31a7d05629c69c93ba`` (and against the current, unfixed
``compiler.py`` on this lane): the six #5257 ids plus ``styleguide/drupal-conventions``
are all present, real, on-disk built-in doctrine artifacts (each has a real DRG node --
see ``packs/built-in/styleguide.graph.yaml``, ``toolguide.graph.yaml``,
``agent_profile.graph.yaml`` -- so each reaches ``_render_kind_references``'s per-id
lookup rather than the unrelated ``graph.unresolved`` bucket), and every one is
excluded from a Python-only active-language set. Pre-fix, all seven vanish from
``catalog.references`` with only an opaque diagnostics string each, so this test
fails on the assertion that every fixture id is present -- not on an ImportError,
AttributeError, or fixture-construction error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.consistency_check import run_consistency_check
from charter.activation.invocation_context import ProjectContext
from tests.charter.test_active_languages_idempotency import (
    _git_init,
    _invoke_generate,
    _read_catalog,
    _write_curated_charter_md,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

#: The six ids named in issue #5257, plus one additional, differently
#: language-scoped id (C-002: proves the general mechanism, not six special
#: cases). ``styleguide/drupal-conventions`` is php/twig-scoped -- distinct
#: from the six's java/typescript scoping -- and has a real DRG node
#: (``packs/built-in/styleguide.graph.yaml``: ``urn: styleguide:drupal-conventions``),
#: so it reaches the same ``_render_kind_references`` per-id lookup path the
#: six do, rather than the unrelated ``graph.unresolved`` bucket.
_FIXTURE_IDS: tuple[tuple[str, str], ...] = (
    ("styleguide", "java-conventions"),
    ("toolguide", "maven-review-checks"),
    ("toolguide", "typescript-mutation-tools"),
    ("agent_profile", "frontend-freddy"),
    ("agent_profile", "java-jenny"),
    ("agent_profile", "node-norris"),
    ("styleguide", "drupal-conventions"),
)


def _write_activation_config(repo: Path) -> None:
    """Write ``.kittify/config.yaml`` activating the fixture ids directly.

    Legacy/unmigrated shape (no ``charter:`` pointer key) -- per
    ``PackContext._load_charter_activation_source``'s two-state resolution,
    an absent pointer means activation is read directly from
    ``config.yaml``'s own top-level ``activated_*`` keys, exactly the shape
    spec.md's Acceptance Scenario 1 describes ("Configure
    ``.kittify/config.yaml`` with a language/scope-filtered id in
    ``activated_styleguides``...").
    """
    config_path = repo / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload = {
        "vcs": {"type": "git"},
        "activated_styleguides": ["java-conventions", "drupal-conventions"],
        "activated_toolguides": ["maven-review-checks", "typescript-mutation-tools"],
        "activated_agent_profiles": ["frontend-freddy", "java-jenny", "node-norris"],
    }
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def _write_python_only_interview(repo: Path) -> None:
    """Persist an interview transcript naming ONLY Python.

    ``infer_repo_languages`` then resolves a real, non-empty active-language
    set (``["python"]``) that excludes java/typescript/php -- the actual
    #5257 defect condition (a present-on-disk id excluded solely by
    language/scope), distinct from the "no signal -> admit all" path
    ``test_active_languages_idempotency.py`` exercises (which never actually
    filters anything on a fixture's first run).
    """
    answers_path = repo / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers_path.parent.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload = {
        "schema_version": "1.0.0",
        "mission": "software-dev",
        "profile": "minimal",
        "answers": {"languages_frameworks": "Python services with pytest and ruff tooling"},
        "selected_paradigms": [],
        "selected_directives": [],
        "selected_tactics": [],
        "available_tools": [],
    }
    with answers_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def test_charter_generate_preserves_language_scope_filtered_activated_references(
    tmp_path: Path,
) -> None:
    """FR-005 / spec.md User Story 1 & 2, Acceptance Scenarios 1 and 3.

    A fresh ``charter generate --force`` against a fixture that activates
    the six #5257 ids plus one additional, differently language-scoped id,
    in a repo whose inferred active-language set is Python-only, must not
    silently drop any of them from ``catalog.references`` -- and the
    resulting charter must be reported coherent by
    ``run_consistency_check`` (not the hardcoded-``_REPO_ROOT``
    ``test_this_project_charter_pack_is_coherent``, which cannot be
    conditioned on this fixture's path).

    RED pre-fix: every id in ``_FIXTURE_IDS`` is dropped, so ``missing``
    below is non-empty and the first assertion fails on real, observed
    content -- not a crash.
    """
    _git_init(tmp_path)
    _write_curated_charter_md(tmp_path)
    _write_activation_config(tmp_path)
    _write_python_only_interview(tmp_path)

    result = _invoke_generate(tmp_path, "--force")
    assert result.exit_code == 0, f"charter generate failed: {result.stdout!r}"

    catalog = _read_catalog(tmp_path)

    # Sanity check the fixture's own precondition: the inferred active
    # language set is real and Python-only, so java/typescript/php-scoped
    # ids are genuinely excluded by scope -- not accidentally still
    # resolvable because no filtering happened at all.
    assert catalog.get("languages") == ["python"], (
        f"expected the fixture's Python-only interview signal to resolve to "
        f"['python'], got {catalog.get('languages')!r} -- the fixture's own "
        f"language-scope precondition is not actually engaged"
    )

    reference_ids = {reference["id"] for reference in catalog["references"]}
    missing = [f"{kind.upper()}:{bare_id}" for kind, bare_id in _FIXTURE_IDS if f"{kind.upper()}:{bare_id}" not in reference_ids]
    assert not missing, f"activated, language/scope-filtered reference(s) silently vanished from catalog.references: {missing}"

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)
    assert report.coherent, (
        f"run_consistency_check reported the fixture NOT coherent: "
        f"unknown_references={report.unknown_references!r} "
        f"missing_from_doctrine={report.missing_from_doctrine!r} "
        f"reference_id_divergences={report.reference_id_divergences!r} "
        f"graph_kind_gaps={report.graph_kind_gaps!r}"
    )
