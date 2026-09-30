"""Tests for documentation generators."""

import pytest

from specify_cli.doc_analysis.doc_generators import (
    JSDocGenerator,
    SphinxGenerator,
    RustdocGenerator,
)

pytestmark = [pytest.mark.integration]


# T062: Test JSDoc Detection
def test_jsdoc_detects_package_json(tmp_path):
    """Test JSDoc detects projects with package.json."""
    (tmp_path / "package.json").write_text('{"name": "test"}')

    generator = JSDocGenerator()
    assert generator.detect(tmp_path) is True


def test_jsdoc_detects_js_files(tmp_path):
    """Test JSDoc detects projects with .js files."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.js").write_text("// JavaScript file")

    generator = JSDocGenerator()
    assert generator.detect(tmp_path) is True


def test_jsdoc_detects_ts_files(tmp_path):
    """Test JSDoc detects projects with .ts files."""
    (tmp_path / "app.ts").write_text("// TypeScript file")

    generator = JSDocGenerator()
    assert generator.detect(tmp_path) is True


def test_jsdoc_does_not_detect_python_project(tmp_path):
    """Test JSDoc does not detect Python projects."""
    (tmp_path / "setup.py").write_text("# Python project")

    generator = JSDocGenerator()
    assert generator.detect(tmp_path) is False


# T063: Test Sphinx Detection
def test_sphinx_detects_setup_py(tmp_path):
    """Test Sphinx detects projects with setup.py."""
    (tmp_path / "setup.py").write_text("# setup.py")

    generator = SphinxGenerator()
    assert generator.detect(tmp_path) is True


def test_sphinx_detects_pyproject_toml(tmp_path):
    """Test Sphinx detects projects with pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text("[project]")

    generator = SphinxGenerator()
    assert generator.detect(tmp_path) is True


def test_sphinx_detects_py_files(tmp_path):
    """Test Sphinx detects projects with .py files."""
    (tmp_path / "main.py").write_text("# Python file")

    generator = SphinxGenerator()
    assert generator.detect(tmp_path) is True


def test_sphinx_does_not_detect_js_project(tmp_path):
    """Test Sphinx does not detect JavaScript projects."""
    (tmp_path / "package.json").write_text("{}")

    generator = SphinxGenerator()
    assert generator.detect(tmp_path) is False


# T064: Test rustdoc Detection
def test_rustdoc_detects_cargo_toml(tmp_path):
    """Test rustdoc detects projects with Cargo.toml."""
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"')

    generator = RustdocGenerator()
    assert generator.detect(tmp_path) is True


def test_rustdoc_detects_rs_files(tmp_path):
    """Test rustdoc detects projects with .rs files."""
    (tmp_path / "main.rs").write_text("// Rust file")

    generator = RustdocGenerator()
    assert generator.detect(tmp_path) is True


def test_rustdoc_does_not_detect_python_project(tmp_path):
    """Test rustdoc does not detect Python projects."""
    (tmp_path / "setup.py").write_text("# Python")

    generator = RustdocGenerator()
    assert generator.detect(tmp_path) is False
