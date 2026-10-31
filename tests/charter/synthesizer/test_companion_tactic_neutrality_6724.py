"""#6724 — a companion tactic's scope is the project's stack.

The neutrality gate decides whether to lint a synthesized artifact with
``_is_generic_scoped``, which infers scope from the hyphen-separated components of
the artifact slug. That inference is sound for ``<lang>-style-guide`` and
``jvm-build-guide`` and unsound for the companion tactic
``how-we-apply-<directive-id>``: its components name a directive, never a
language. The predicate then falls through to "unknown => generic" and refuses the
companion for naming the project's own test runner.

The cases below are two halves of one fix, built from one shared fixture builder so
they cannot drift:

- a known-scope project promotes the companion (the reported refusal is gone);
- a project with no observed and no declared language still refuses it, which is
  the audience ``charter-ownership-consolidation-and-neutrality-hardening-01KPD880``
  FR-012 protects.

The CLI cases drive the real ``charter synthesize`` command — the entry point the
reporter used — rather than the gate helper alone.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from charter.activation.synthesizer.evidence import CodeSignals, EvidenceBundle
from charter.activation.synthesizer.write_pipeline import _is_generic_scoped
from specify_cli.cli.commands.charter import app
from tests._factories.activation_ledger import seed_activation_ledger

runner = CliRunner()

_GENERATED = Path(".kittify/charter/generated")
_PLURALS = {"directive": "directives", "tactic": "tactics", "styleguide": "styleguides"}

#: The built-in directive the fixture activates. An explicit activation is what makes
#: ``resolve_sections()`` expand a companion-tactic target at all (#2577): on a first run
#: with no activation list, synthesis asks for no companion and the gate never sees one.
_DIRECTIVE_STEM = "003-decision-documentation-requirement"
_DIRECTIVE_ID = "DIRECTIVE_003"
_COMPANION_SLUG = "how-we-apply-directive-003"

#: The line the reporter's harness wrote. ``pytest`` is banned term PY-001.
_COMPANION_STEP = "Run pytest -q before opening the pull request."

_ANSWERS_HEAD = (
    "schema_version: '1'\nmission: software-dev\nprofile: minimal\nanswers:\n"
    "  mission_type: software_dev\n  testing_philosophy: test-driven\n  risk_appetite: moderate\n"
)
_ANSWERS_TAIL = "selected_paradigms: []\nselected_directives: []\navailable_tools: []\n"


def _python_bundle() -> EvidenceBundle:
    """Evidence for a repository whose only observed language is Python."""
    signals = CodeSignals(
        stack_id="python",
        primary_language="python",
        frameworks=(),
        test_frameworks=(),
        scope_tag="python",
        representative_files=(),
        detected_at="2026-10-30T00:00:00+00:00",
    )
    return EvidenceBundle(code_signals=signals)


# ---------------------------------------------------------------------------
# Shared fixture builder (one builder, two opposite expectations)
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _write_generated(
    root: Path,
    kind: str,
    artifact_id: str,
    body: dict[str, Any],
    filename: str | None = None,
) -> None:
    folder = root / _GENERATED / _PLURALS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    name = filename or f"{artifact_id}.{kind}.yaml"
    (folder / name).write_text(
        yaml.safe_dump({"id": artifact_id, "schema_version": "1.0", **body}),
        encoding="utf-8",
    )


def _build_project(root: Path, *, known_language: bool) -> None:
    """Seed a project that activates one built-in directive and writes its companion.

    ``known_language`` decides whether the project's language scope is knowable at
    all: a declared ``language_scope`` plus a real Python source tree, or neither.
    Everything else — the activation, the generated artifacts, the companion body —
    is identical, so the two CLI cases differ in exactly one variable.
    """
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")

    if known_language:
        (root / "pyproject.toml").write_text("[project]\nname = 'app'\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "app.py").write_text("def answer() -> int:\n    return 42\n", encoding="utf-8")

    answers = root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True, exist_ok=True)
    language_line = "  language_scope: [Python]\n" if known_language else ""
    answers.write_text(_ANSWERS_HEAD + language_line + _ANSWERS_TAIL, encoding="utf-8")

    generated = runner.invoke(app, ["generate", "--from-interview"], catch_exceptions=False)
    assert generated.exit_code == 0, generated.output

    _write_generated(
        root,
        "directive",
        "PROJECT_001",
        {"title": "Project Intent Directive", "intent": "Serve the outcome.", "enforcement": "required"},
        filename="001-project-intent-directive.directive.yaml",
    )
    _write_generated(
        root,
        "directive",
        "PROJECT_002",
        {"title": "Risk Appetite Directive", "intent": "Take moderate risks.", "enforcement": "advisory"},
        filename="002-risk-appetite-directive.directive.yaml",
    )
    _write_generated(
        root,
        "tactic",
        _COMPANION_SLUG,
        {
            "name": f"How We Apply {_DIRECTIVE_ID}",
            "purpose": f"Record decisions in this project, per {_DIRECTIVE_ID}.",
            "steps": [{"title": "Verify", "description": _COMPANION_STEP}],
        },
    )
    _write_generated(
        root,
        "tactic",
        "testing-philosophy-tactic",
        {
            "name": "Testing Philosophy",
            "purpose": "Test well.",
            "steps": [{"title": "Unit", "description": "Unit tests first."}],
        },
    )
    _write_generated(
        root,
        "styleguide",
        "testing-style-guide",
        {"title": "Testing", "scope": "code", "principles": ["Be good."]},
    )
    if known_language:
        _write_generated(
            root,
            "styleguide",
            "python-style-guide",
            {"title": "Python", "scope": "code", "principles": ["Run pytest -q before merging."]},
        )

    seed_activation_ledger(root, activated_directives=[_DIRECTIVE_STEM])


def _synthesize() -> Any:
    return runner.invoke(app, ["synthesize", "--json"], catch_exceptions=False)


# ---------------------------------------------------------------------------
# User Story 1 — the reported refusal is gone (SC-001)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_resynthesize_of_the_companion_is_promoted(tmp_path: Path, charter_cwd_isolation) -> None:
    """The other entry point into the same gate: a bounded re-synthesis of the companion.

    ``charter resynthesize`` rebuilds its targets from provenance, so this proves the
    exemption survives the round trip rather than only the first full run.
    """
    root = charter_cwd_isolation(tmp_path)
    _build_project(root, known_language=True)
    first = _synthesize()
    assert first.exit_code == 0, first.output

    result = runner.invoke(
        app,
        ["resynthesize", "--topic", f"tactic:{_COMPANION_SLUG}", "--json"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert f"tactic:{_COMPANION_SLUG}" in json.dumps(payload), payload


@pytest.mark.integration
@pytest.mark.git_repo
def test_companion_tactic_naming_the_project_runner_is_promoted(tmp_path: Path, charter_cwd_isolation) -> None:
    """A known-scope project promotes the companion that names its own test runner."""
    root = charter_cwd_isolation(tmp_path)
    _build_project(root, known_language=True)

    result = _synthesize()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "success"
    slugs = {entry["slug"] for entry in payload["written_artifacts"]}
    assert _COMPANION_SLUG in slugs, payload["written_artifacts"]


# ---------------------------------------------------------------------------
# User Story 2 — an unconfigured project still gets no language default (SC-002)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.git_repo
def test_companion_tactic_in_an_unconfigured_project_is_still_refused(tmp_path: Path, charter_cwd_isolation) -> None:
    """The same companion text, with no scope known, is still refused — same fixture."""
    root = charter_cwd_isolation(tmp_path)
    _build_project(root, known_language=False)

    result = _synthesize()

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["result"] == "failure"
    refusals = [w for w in payload["warnings"] if w.startswith("NeutralityGateViolation")]
    assert refusals, payload["warnings"]
    refusal = refusals[0]
    assert _COMPANION_SLUG in refusal
    assert "pytest" in refusal
    # The staged artifact set is preserved for inspection (unchanged behaviour).
    assert list(root.glob(".kittify/charter/.staging/*.failed"))


# ---------------------------------------------------------------------------
# User Story 3 — the narrowing is exactly one artifact class (SC-003/SC-004)
# ---------------------------------------------------------------------------


def test_companion_section_label_has_one_owner() -> None:
    """The section that expands into companion tactics is imported, never re-spelled."""
    from charter.activation.synthesizer.interview_mapping import (
        COMPANION_TACTIC_SECTION,
        resolve_sections,
    )

    assert COMPANION_TACTIC_SECTION == "selected_directives"
    sections = resolve_sections({"selected_directives": [_DIRECTIVE_ID]})
    companion = [entry for entry in sections if entry[0] == COMPANION_TACTIC_SECTION]
    assert companion, sections
    assert companion[0][1]["source_section"] == COMPANION_TACTIC_SECTION


@pytest.mark.parametrize(
    ("kind", "slug", "source_section", "evidence", "expected"),
    [
        # A companion tactic in a project whose stack is known: the artifact's scope is
        # the project's, so its own test runner is not an unstated assumption.
        ("tactic", _COMPANION_SLUG, "selected_directives", _python_bundle(), False),
        # No scope known: still generic, still linted.
        ("tactic", _COMPANION_SLUG, "selected_directives", None, True),
        # Same section, same slug, a non-tactic kind: the exemption is kind-scoped, so a
        # styleguide can never reach it.
        ("styleguide", _COMPANION_SLUG, "selected_directives", _python_bundle(), True),
        # A non-companion artifact keeps the slug-component rule, in the same project.
        ("tactic", "testing-philosophy", "testing_philosophy", _python_bundle(), True),
        ("styleguide", "java-style-guide", "language_scope", _python_bundle(), True),
        ("tactic", "how-we-apply-directive-003", "testing_philosophy", _python_bundle(), True),
    ],
)
def test_scope_rule(
    kind: str,
    slug: str,
    source_section: str,
    evidence: EvidenceBundle | None,
    expected: bool,
) -> None:
    assert _is_generic_scoped(kind, slug, evidence, (), source_section=source_section) is expected


def test_provenance_without_a_section_keeps_the_old_rule() -> None:
    """No recorded section ⇒ not a companion ⇒ unchanged behaviour (safe fallback)."""
    from charter.activation.synthesizer.write_pipeline import _is_companion_tactic

    assert _is_companion_tactic("tactic", None) is False
    assert _is_generic_scoped("tactic", _COMPANION_SLUG, _python_bundle(), ()) is True
