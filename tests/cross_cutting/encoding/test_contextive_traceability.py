"""Tests for the Contextive glossary generator (scripts/generate_contextive_glossaries.py)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

# Import generator under test via the canonical `scripts` namespace package
# (repo root is already on sys.path via pytest's rootdir prepend, since
# `tests/__init__.py` exists) rather than inserting `scripts/` directly.
import scripts.generate_contextive_glossaries as gen

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


SAMPLE_CONTEXT_MD = textwrap.dedent("""\
    ## Context: TestDomain

    Terms describing the test domain model.

    ### Alpha Term

    | | |
    |---|---|
    | **Definition** | First test term definition. |
    | **Context** | TestDomain |
    | **Status** | canonical |
    | **Applicable to** | `1.x`, `2.x` |

    ---

    ### Beta Term

    | | |
    |---|---|
    | **Definition** | Second test term definition with [a link](./other.md#anchor). |
    | **Context** | TestDomain |
    | **Status** | candidate |

    ---
""")


@pytest.fixture()
def sample_md_file(tmp_path: Path) -> Path:
    f = tmp_path / "testdomain.md"
    f.write_text(SAMPLE_CONTEXT_MD, encoding="utf-8")
    return f


@pytest.fixture()
def sample_map_yaml(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        context_base_dir: "src/.contextive"
        scopes:
          - path: "src/alpha"
            contexts:
              - testdomain
            description: "Alpha package"
    """)
    f = tmp_path / "contextive-map.yaml"
    f.write_text(content, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def test_parse_context_name(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    assert ctx.name == "TestDomain"


def test_parse_context_description(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    assert "test domain" in ctx.description.lower()


def test_parse_terms_count(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    assert frozenset(t.name for t in ctx.terms) == frozenset({"Alpha Term", "Beta Term"})


def test_parse_terms_sorted_alphabetically(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    names = [t.name for t in ctx.terms]
    assert names == sorted(names, key=str.lower)


def test_parse_term_definition(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    alpha = next(t for t in ctx.terms if t.name == "Alpha Term")
    assert alpha.definition == "First test term definition."


def test_parse_term_status(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    alpha = next(t for t in ctx.terms if t.name == "Alpha Term")
    assert alpha.status == "canonical"


def test_parse_strips_markdown_links_from_definition(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    beta = next(t for t in ctx.terms if t.name == "Beta Term")
    # Link text preserved, URL removed
    assert "a link" in beta.definition
    assert "other.md" not in beta.definition


def test_parse_context_slug(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    assert ctx.slug == "testdomain"


# ---------------------------------------------------------------------------
# YAML rendering tests
# ---------------------------------------------------------------------------


def test_render_context_yaml_contains_generated_header(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    yaml_str = gen.render_context_yaml(ctx)
    assert "GENERATED FILE" in yaml_str


def test_render_context_yaml_contains_source_ref(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    yaml_str = gen.render_context_yaml(ctx)
    assert "testdomain.md" in yaml_str


def test_render_context_yaml_contains_context_name(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    yaml_str = gen.render_context_yaml(ctx)
    assert "TestDomain" in yaml_str


def test_render_context_yaml_contains_all_terms(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    yaml_str = gen.render_context_yaml(ctx)
    assert "Alpha Term" in yaml_str
    assert "Beta Term" in yaml_str


def test_render_context_yaml_is_deterministic(sample_md_file: Path) -> None:
    ctx = gen.parse_context_file(sample_md_file)
    first_yaml = gen.render_context_yaml(ctx)
    second_yaml = gen.render_context_yaml(ctx)
    assert first_yaml == second_yaml


def test_render_scope_yaml_contains_imports(tmp_path: Path) -> None:
    scope_path = tmp_path / "src" / "pkg"
    context_base = tmp_path / "src" / ".contextive"
    yaml_str = gen.render_scope_yaml(scope_path, context_base, ["lexical", "orchestration"])
    assert "imports:" in yaml_str
    assert "lexical.yml" in yaml_str
    assert "orchestration.yml" in yaml_str


def test_render_scope_yaml_contains_header(tmp_path: Path) -> None:
    scope_path = tmp_path / "src" / "pkg"
    context_base = tmp_path / "src" / ".contextive"
    yaml_str = gen.render_scope_yaml(scope_path, context_base, ["lexical"])
    assert "GENERATED FILE" in yaml_str


def test_render_scope_yaml_slugs_sorted(tmp_path: Path) -> None:
    scope_path = tmp_path / "src" / "pkg"
    context_base = tmp_path / "src" / ".contextive"
    yaml_str = gen.render_scope_yaml(scope_path, context_base, ["orchestration", "lexical"])
    lex_pos = yaml_str.index("lexical.yml")
    orch_pos = yaml_str.index("orchestration.yml")
    assert lex_pos < orch_pos, "imports should be sorted alphabetically"


def test_render_scope_yaml_uses_relative_path(tmp_path: Path) -> None:
    """Import paths must be relative — no absolute filesystem paths."""
    scope_path = tmp_path / "src" / "pkg"
    context_base = tmp_path / "src" / ".contextive"
    yaml_str = gen.render_scope_yaml(scope_path, context_base, ["lexical"])
    # Should not contain the tmp_path prefix
    assert str(tmp_path) not in yaml_str


# ---------------------------------------------------------------------------
# Map loading & validation tests
# ---------------------------------------------------------------------------


def test_load_map(sample_map_yaml: Path) -> None:
    tmap = gen.load_map(sample_map_yaml)
    assert tmap.context_base_dir == "src/.contextive"
    assert frozenset(s.path for s in tmap.scopes) == frozenset({"src/alpha"})
    assert tmap.scopes[0].contexts == ["testdomain"]


def test_validate_map_missing_context_file(tmp_path: Path, sample_map_yaml: Path) -> None:
    # Override GLOSSARY_CONTEXTS_DIR to tmp_path (no files)
    original = gen.GLOSSARY_CONTEXTS_DIR
    gen.GLOSSARY_CONTEXTS_DIR = tmp_path  # type: ignore[assignment]
    try:
        tmap = gen.load_map(sample_map_yaml)
        errors = gen.validate_map(tmap)
        assert any("testdomain" in e for e in errors)
    finally:
        gen.GLOSSARY_CONTEXTS_DIR = original  # type: ignore[assignment]


def test_validate_map_no_errors_when_files_present(tmp_path: Path, sample_map_yaml: Path) -> None:
    # Create the expected context file
    (tmp_path / "testdomain.md").write_text("## Context: TestDomain\n\n", encoding="utf-8")
    original = gen.GLOSSARY_CONTEXTS_DIR
    gen.GLOSSARY_CONTEXTS_DIR = tmp_path  # type: ignore[assignment]
    try:
        tmap = gen.load_map(sample_map_yaml)
        errors = gen.validate_map(tmap)
        assert errors == []
    finally:
        gen.GLOSSARY_CONTEXTS_DIR = original  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Integration: generate + check mode
# ---------------------------------------------------------------------------


def _make_integration_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Build a minimal repo tree for integration tests."""
    # Glossary source
    contexts_dir = tmp_path / "docs" / "context"
    contexts_dir.mkdir(parents=True)
    (contexts_dir / "testdomain.md").write_text(SAMPLE_CONTEXT_MD, encoding="utf-8")

    # Map file
    map_dir = tmp_path / ".kittify" / "traceability"
    map_dir.mkdir(parents=True)
    map_file = map_dir / "contextive-map.yaml"
    map_file.write_text(
        textwrap.dedent("""\
        context_base_dir: "src/.contextive"
        scopes:
          - path: "src/alpha"
            contexts:
              - testdomain
    """),
        encoding="utf-8",
    )

    # Create scope dir
    (tmp_path / "src" / "alpha").mkdir(parents=True)

    return tmp_path, map_file


def test_generate_creates_context_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, map_file = _make_integration_tree(tmp_path)
    monkeypatch.setattr(gen, "GLOSSARY_CONTEXTS_DIR", repo_root / "docs" / "context")
    monkeypatch.setattr(gen, "REPO_ROOT", repo_root)

    tmap = gen.load_map(map_file)
    output = gen.generate(repo_root, tmap)

    context_yml = repo_root / "src" / ".contextive" / "testdomain.yml"
    assert context_yml in output
    assert "TestDomain" in output[context_yml]


def test_generate_creates_scope_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, map_file = _make_integration_tree(tmp_path)
    monkeypatch.setattr(gen, "GLOSSARY_CONTEXTS_DIR", repo_root / "docs" / "context")
    monkeypatch.setattr(gen, "REPO_ROOT", repo_root)

    tmap = gen.load_map(map_file)
    output = gen.generate(repo_root, tmap)

    scope_yml = repo_root / "src" / "alpha" / ".contextive.yml"
    assert scope_yml in output
    assert "testdomain.yml" in output[scope_yml]


def test_check_mode_passes_after_generate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, map_file = _make_integration_tree(tmp_path)
    monkeypatch.setattr(gen, "GLOSSARY_CONTEXTS_DIR", repo_root / "docs" / "context")
    monkeypatch.setattr(gen, "REPO_ROOT", repo_root)
    monkeypatch.setattr(gen, "MAP_FILE", map_file)

    tmap = gen.load_map(map_file)
    # Generate first
    assert gen.cmd_generate(repo_root, tmap) == 0
    # Check should pass
    assert gen.cmd_check(repo_root, tmap) == 0


def test_check_mode_fails_when_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, map_file = _make_integration_tree(tmp_path)
    monkeypatch.setattr(gen, "GLOSSARY_CONTEXTS_DIR", repo_root / "docs" / "context")
    monkeypatch.setattr(gen, "REPO_ROOT", repo_root)
    monkeypatch.setattr(gen, "MAP_FILE", map_file)

    tmap = gen.load_map(map_file)
    # Do NOT generate — check should fail
    assert gen.cmd_check(repo_root, tmap) == 1


def test_check_mode_fails_when_file_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, map_file = _make_integration_tree(tmp_path)
    monkeypatch.setattr(gen, "GLOSSARY_CONTEXTS_DIR", repo_root / "docs" / "context")
    monkeypatch.setattr(gen, "REPO_ROOT", repo_root)
    monkeypatch.setattr(gen, "MAP_FILE", map_file)

    tmap = gen.load_map(map_file)
    assert gen.cmd_generate(repo_root, tmap) == 0

    # Corrupt one file
    stale_path = repo_root / "src" / "alpha" / ".contextive.yml"
    stale_path.write_text("stale content\n", encoding="utf-8")

    assert gen.cmd_check(repo_root, tmap) == 1


# ---------------------------------------------------------------------------
# Real glossary contexts smoke test
# ---------------------------------------------------------------------------


def test_real_glossary_contexts_parse() -> None:
    """Every *registered* glossary context parses with at least one term.

    Discovery is map-driven — the registered context slugs in
    ``contextive-map.yaml`` — the same authoritative source the generator
    (:func:`gen.cmd_generate`) uses. This
    deliberately does **not** blind-glob ``docs/context/*.md``: that directory is
    a mixed documentation section that also holds prose Explanation pages (e.g.
    ``charter-overview.md``) which are not glossary contexts and carry no terms.
    A blind glob would assert the directory layout rather than the glossary
    contract, and would break whenever a non-context doc lands there.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    contexts_dir = repo_root / "docs" / "context"
    map_file = repo_root / ".kittify" / "traceability" / "contextive-map.yaml"
    assert contexts_dir.exists(), f"Glossary contexts dir not found: {contexts_dir}"
    assert map_file.exists(), f"Traceability map not found: {map_file}"

    tmap = gen.load_map(map_file)
    registered = sorted({slug for scope in tmap.scopes for slug in scope.contexts})
    assert registered, "no glossary contexts registered in contextive-map.yaml"

    for slug in registered:
        md_file = contexts_dir / f"{slug}.md"
        assert md_file.is_file(), f"registered context '{slug}' has no {md_file.name}"
        ctx = gen.parse_context_file(md_file)
        assert ctx.name, f"No context name parsed from {md_file.name}"
        assert ctx.terms, f"No terms parsed from {md_file.name}"
        for term in ctx.terms:
            assert term.name, f"Term with empty name in {md_file.name}"
