"""Documentation generator integration for spec-kitty.

This module provides a protocol-based interface for integrating documentation
generators (JSDoc, Sphinx, rustdoc) into the documentation mission workflow.

Generators only detect which project languages apply. Configuring and running
the generator tool is the agent's job in the documentation mission's generate
step (``packs/built-in/missions/mission-steps/documentation/generate/``); the
never-wired ``configure()``/``generate()`` methods were removed (dead-code
review 2026-09-30).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class DocGenerator(Protocol):
    """Protocol for documentation generators.

    All generators (JSDoc, Sphinx, rustdoc) implement this interface to provide
    consistent language detection.
    """

    name: str  # Generator identifier (e.g., "jsdoc", "sphinx", "rustdoc")
    languages: list[str]  # Supported languages (e.g., ["javascript", "typescript"])

    def detect(self, project_root: Path) -> bool:
        """Detect if this generator is applicable to the project.

        Args:
            project_root: Root directory of the project to check

        Returns:
            True if generator should be used for this project, False otherwise
        """
        ...


@dataclass
class JSDocGenerator:
    """JSDoc documentation generator for JavaScript/TypeScript projects.

    Generates API reference documentation from JSDoc comments in JavaScript/TypeScript
    code using the JSDoc tool (invoked via npx).
    """

    name: str = "jsdoc"
    languages: list[str] = field(default_factory=lambda: ["javascript", "typescript"])

    def detect(self, project_root: Path) -> bool:
        """Detect if project uses JavaScript/TypeScript.

        Checks for:
        - .js, .jsx, .ts, .tsx files
        - package.json file (Node.js project indicator)
        - node_modules/ directory

        Args:
            project_root: Project root directory

        Returns:
            True if JavaScript/TypeScript files found
        """
        # Check for package.json (strongest indicator)
        if (project_root / "package.json").exists():
            return True

        # Check for JS/TS files in common locations
        return any(list(project_root.glob(f"**/{pattern}")) for pattern in ["*.js", "*.jsx", "*.ts", "*.tsx"])


@dataclass
class SphinxGenerator:
    """Sphinx documentation generator for Python projects.

    Generates API reference documentation from Python docstrings using Sphinx
    with autodoc and napoleon extensions.
    """

    name: str = "sphinx"
    languages: list[str] = field(default_factory=lambda: ["python"])

    def detect(self, project_root: Path) -> bool:
        """Detect if project uses Python.

        Checks for:
        - setup.py (Python package indicator)
        - pyproject.toml (modern Python project)
        - .py files in project

        Args:
            project_root: Project root directory

        Returns:
            True if Python files found
        """
        # Check for Python project indicators
        if (project_root / "setup.py").exists():
            return True
        if (project_root / "pyproject.toml").exists():
            return True

        # Check for Python files
        return bool(list(project_root.glob("**/*.py")))


@dataclass
class RustdocGenerator:
    """rustdoc documentation generator for Rust projects.

    Generates API reference documentation from Rust doc comments using rustdoc
    (invoked via cargo doc).
    """

    name: str = "rustdoc"
    languages: list[str] = field(default_factory=lambda: ["rust"])

    def detect(self, project_root: Path) -> bool:
        """Detect if project uses Rust.

        Checks for:
        - Cargo.toml (Rust project indicator)
        - .rs files in project

        Args:
            project_root: Project root directory

        Returns:
            True if Rust project found
        """
        # Check for Cargo.toml (definitive Rust project indicator)
        if (project_root / "Cargo.toml").exists():
            return True

        # Check for Rust source files
        return bool(list(project_root.glob("**/*.rs")))
