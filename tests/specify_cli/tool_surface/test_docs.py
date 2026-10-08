"""Integration + CI-level tests for the docs contract linter (WP08, FR-017).

Marked ``integration`` (WP04, #1942) so that CI's ``integration-tests-core-misc``
``specify-cli-rest`` shard actually collects it. The companion wiring change adds
``tests/specify_cli/tool_surface/**`` and ``src/specify_cli/tool_surface/**`` to
the ``core_misc`` paths-filter list, which is the glob the shard's ``if:`` gate
evaluates — without both halves the docs-contract gate stays uncollected.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.tool_surface.docs import (
    FINDING_UNREGISTERED_PATH,
    DocsLinter,
    RegistryPathIndex,
    format_findings,
)
from specify_cli.tool_surface.enums import (
    ActivationMode,
    InstallScope,
    RequiredPolicy,
    SourceKind,
    ToolSurfaceKind,
)
from specify_cli.tool_surface.model import SurfaceDefinition
from specify_cli.tool_surface.registry import ToolSurfaceRegistry
from specify_cli.tool_surface.service import (
    build_docs_linter,
    lint_docs_directory,
)

import pytest

pytestmark = [pytest.mark.integration]

_REPO_ROOT = Path(__file__).resolve()
while not (_REPO_ROOT / "pyproject.toml").exists():
    _REPO_ROOT = _REPO_ROOT.parent

_COMMAND_SKILL_PATTERN = ".agents/skills/spec-kitty.{command}/SKILL.md"
_PROFILE_PATTERN = ".claude/agents/{profile_id}.md"
_SENTINEL_PATTERN = "<session-presence>"
_MANIFEST_PATTERN = ".kittify/skills-manifest.json:{installed_path}"


def _definition(path_pattern: str, kind: ToolSurfaceKind) -> SurfaceDefinition:
    return SurfaceDefinition(
        kind=kind,
        source_kind=SourceKind.GENERATED,
        install_scope=InstallScope.PROJECT,
        path_pattern=path_pattern,
        required_policy=RequiredPolicy.REQUIRED,
        activation_mode=ActivationMode.ALWAYS,
        provider_key="test",
        repair_hint="repair",
    )


def _registry() -> ToolSurfaceRegistry:
    registry = ToolSurfaceRegistry()
    registry.register_definition("claude", _definition(_COMMAND_SKILL_PATTERN, ToolSurfaceKind.COMMAND_SKILL))
    registry.register_definition("claude", _definition(_PROFILE_PATTERN, ToolSurfaceKind.AGENT_PROFILE))
    # Sentinel + manifest-embedded patterns must be excluded from validation.
    registry.register_definition("claude", _definition(_SENTINEL_PATTERN, ToolSurfaceKind.CONTEXT_FILE))
    registry.register_definition("claude", _definition(_MANIFEST_PATTERN, ToolSurfaceKind.CHARTER_SKILL))
    return registry


# --- RegistryPathIndex -------------------------------------------------------


def test_registry_path_index_matches_pattern() -> None:
    index = RegistryPathIndex(_registry())
    assert index.is_registered_path(".agents/skills/spec-kitty.plan/SKILL.md")
    assert index.is_registered_path(".claude/agents/architect-alphonso.md")


def test_registry_path_index_no_match() -> None:
    index = RegistryPathIndex(_registry())
    assert not index.is_registered_path(".agents/skills/nonexistent/SKILL.md")
    assert not index.is_registered_path(".claude/agents/nested/too/deep.md")


def test_registry_path_index_excludes_sentinel_patterns() -> None:
    index = RegistryPathIndex(_registry())
    # Sentinel + manifest patterns are not validatable; they must not appear as
    # a static prefix that traps unrelated doc references.
    assert not index.looks_like_surface_path("<session-presence>")
    assert not index.looks_like_surface_path(".kittify/skills-manifest.json")


def test_registry_path_index_looks_like_surface_path() -> None:
    index = RegistryPathIndex(_registry())
    assert index.looks_like_surface_path(".agents/skills/spec-kitty.plan/SKILL.md")
    assert not index.looks_like_surface_path(".kittify/config.yaml")
    assert not index.looks_like_surface_path("src/specify_cli/foo.py")


def test_registry_path_index_suggest_correction() -> None:
    index = RegistryPathIndex(_registry())
    suggestion = index.suggest_correction(".agents/skills/wrong/SKILL.md")
    assert suggestion == _COMMAND_SKILL_PATTERN
    assert index.suggest_correction(".kittify/config.yaml") is None


# --- DocsLinter --------------------------------------------------------------


def _write(tmp_path: Path, body: str) -> Path:
    doc = tmp_path / "doc.md"
    doc.write_text(body, encoding="utf-8")
    return doc


def test_docs_linter_finds_unregistered_path(tmp_path: Path) -> None:
    doc = _write(tmp_path, "See `.agents/skills/nonexistent/SKILL.md` for details.\n")
    findings = DocsLinter(_registry()).lint_file(doc)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding == FINDING_UNREGISTERED_PATH
    assert finding.referenced_path == ".agents/skills/nonexistent/SKILL.md"
    assert finding.line_number == 1
    assert _COMMAND_SKILL_PATTERN in finding.detail


def test_docs_linter_passes_registered_path(tmp_path: Path) -> None:
    doc = _write(tmp_path, "Run `.agents/skills/spec-kitty.plan/SKILL.md` now.\n")
    assert DocsLinter(_registry()).lint_file(doc) == []


def test_docs_linter_empty_for_no_surface_paths(tmp_path: Path) -> None:
    doc = _write(
        tmp_path,
        "Edit `.kittify/config.yaml` and `src/specify_cli/__init__.py`.\n",
    )
    assert DocsLinter(_registry()).lint_file(doc) == []


def test_docs_linter_ignore_annotation(tmp_path: Path) -> None:
    doc = _write(
        tmp_path,
        "Legacy `.agents/skills/nonexistent/SKILL.md`. <!-- tool-surface: ignore -->\n",
    )
    assert DocsLinter(_registry()).lint_file(doc) == []


def test_docs_linter_skips_doc_wildcards(tmp_path: Path) -> None:
    doc = _write(
        tmp_path,
        "Pattern `.agents/skills/spec-kitty.*/SKILL.md` and `.agents/skills/spec-kitty.<command>/SKILL.md` are placeholders.\n",
    )
    assert DocsLinter(_registry()).lint_file(doc) == []


def test_docs_linter_lint_directory(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("`.agents/skills/spec-kitty.plan/SKILL.md`\n", encoding="utf-8")
    bad = tmp_path / "nested"
    bad.mkdir()
    (bad / "bad.md").write_text("`.agents/skills/bogus/SKILL.md`\n", encoding="utf-8")
    findings = DocsLinter(_registry()).lint_directory(tmp_path)
    assert len(findings) == 1
    assert findings[0].referenced_path == ".agents/skills/bogus/SKILL.md"


def test_format_findings_renders_each_finding(tmp_path: Path) -> None:
    doc = _write(tmp_path, "`.agents/skills/bogus/SKILL.md`\n")
    findings = DocsLinter(_registry()).lint_file(doc)
    rendered = format_findings(findings)
    assert FINDING_UNREGISTERED_PATH in rendered
    assert ".agents/skills/bogus/SKILL.md" in rendered


# --- Service wiring ----------------------------------------------------------


def test_build_docs_linter_indexes_builtin_patterns(tmp_path: Path) -> None:
    linter = build_docs_linter()
    # A concrete command-skill path with a valid {command} segment is registered.
    ok = tmp_path / "ok.md"
    ok.write_text("`.agents/skills/spec-kitty.plan/SKILL.md`\n", encoding="utf-8")
    assert linter.lint_file(ok) == []
    # An unregistered shape is flagged.
    bad = tmp_path / "bad.md"
    bad.write_text("`.agents/skills/bogus/SKILL.md`\n", encoding="utf-8")
    assert len(linter.lint_file(bad)) == 1


# --- CI-level docs contract assertion (T040) ---------------------------------


def test_docs_contract_lint() -> None:
    """No doc file may reference an unregistered tool surface path (FR-017)."""
    docs_dir = _REPO_ROOT / "docs"
    findings = lint_docs_directory(docs_dir)
    assert not findings, "Docs drift found:\n" + format_findings(findings)


def test_docs_contract_lint_catches_injected_drift(tmp_path: Path) -> None:
    """A newly introduced *unregistered* path must fail the contract lint.

    The assertion pins the REAL ``FINDING_UNREGISTERED_PATH`` constant (value
    ``"UNREGISTERED_PATH"``, ``docs.py``), not a prose string and not merely
    ``len(findings) > 0`` — so the gate fails specifically on tool-surface drift
    rather than on incidental lint noise.
    """
    drifted = tmp_path / "drifted.md"
    drifted.write_text(
        "New surface at `.agents/skills/totally-made-up/SKILL.md`.\n",
        encoding="utf-8",
    )
    findings = lint_docs_directory(tmp_path)
    assert findings, "Injected drift should have produced a finding"
    assert findings[0].finding == FINDING_UNREGISTERED_PATH


def test_docs_contract_lint_discriminates_drift_from_noise(tmp_path: Path) -> None:
    """A *registered* path injected the same way yields ZERO findings.

    Paired with :func:`test_docs_contract_lint_catches_injected_drift`, this
    proves the gate fails on drift *and only on drift*: the identical injection
    mechanism over a registered command-skill surface must not produce a finding
    (no false positives that would mask the real signal).
    """
    registered = tmp_path / "registered.md"
    registered.write_text(
        "Existing surface at `.agents/skills/spec-kitty.plan/SKILL.md`.\n",
        encoding="utf-8",
    )
    assert lint_docs_directory(tmp_path) == []
