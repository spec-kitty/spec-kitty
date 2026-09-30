"""Heuristic code-reading collector for charter synthesis.

Walks the project repository up to a configurable depth, detects the primary
language / framework / test-framework stack, and returns a ``CodeSignals``
dataclass suitable for injection into an ``EvidenceBundle``.

No external runtime dependencies — stdlib ``pathlib`` and ``os.walk`` only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from charter.activation.synthesizer.evidence import CodeSignals
from kernel.clock import now_utc_iso
from kernel.paths import to_posix

__all__ = [
    "CodeReadingCollector",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".worktrees",
        ".mypy_cache",
        ".tox",
    }
)

# Indicator file → language (order matters for resolution when multiple found)
PACKAGE_JSON = "package.json"


LANGUAGE_INDICATORS: dict[str, str] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "requirements.txt": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
    # package.json is handled separately (js vs ts disambiguation)
    PACKAGE_JSON: "javascript",
}

FRAMEWORK_INDICATORS: dict[str, str] = {
    "manage.py": "django",
    "next.config.ts": "nextjs",
    "next.config.js": "nextjs",
    "angular.json": "angular",
    "svelte.config.js": "svelte",
    "svelte.config.ts": "svelte",
    "nuxt.config.ts": "nuxt",
    "nuxt.config.js": "nuxt",
}

TEST_FRAMEWORK_INDICATORS: dict[str, str] = {
    "pytest.ini": "pytest",
    "conftest.py": "pytest",
    "jest.config.js": "jest",
    "jest.config.ts": "jest",
    "vitest.config.ts": "vitest",
    "vitest.config.js": "vitest",
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CodeReadingError(Exception):
    """Raised when the repository root does not exist."""


# ---------------------------------------------------------------------------
# Internal data
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _TreeScan:
    """Raw file-system observations gathered by a single ``os.walk`` pass."""

    indicator_files: set[str]
    source_files: list[str]
    test_files: list[str]
    ts_files: int
    js_files: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_test_file(rel_path: str, filename: str) -> bool:
    """Return True when *filename* looks like a test file."""
    name = filename.lower()
    # Python patterns
    if name.startswith("test_") and name.endswith(".py"):
        return True
    if name.endswith("_test.py"):
        return True
    # JS/TS patterns
    for suffix in (".test.ts", ".spec.ts", ".test.js", ".spec.js"):
        if name.endswith(suffix):
            return True
    # Directory-based heuristic
    parts = to_posix(rel_path).split("/")
    return "tests" in parts or "__tests__" in parts


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class CodeReadingCollector:
    """Walk a repository and return :class:`~charter.activation.synthesizer.evidence.CodeSignals`.

    Parameters
    ----------
    repo_root:
        Absolute path to the repository root.
    max_depth:
        Maximum directory depth to walk (root = 0).  Defaults to 3.
    """

    def __init__(self, repo_root: Path, max_depth: int = 3) -> None:
        self._repo_root = repo_root
        self._max_depth = max_depth

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(self) -> CodeSignals:
        """Walk the repository and return detected ``CodeSignals``.

        Raises
        ------
        CodeReadingError
            If *repo_root* does not exist.

        Notes
        -----
        All internal detection errors are swallowed; the method returns an
        "unknown" ``CodeSignals`` instance rather than propagating them.
        """
        if not self._repo_root.exists():
            raise CodeReadingError(
                f"Repository root does not exist: {self._repo_root}"
            )

        try:
            return self._detect()
        except Exception:  # noqa: BLE001
            return self._unknown_signals()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect(self) -> CodeSignals:
        scan = self._scan_tree()

        language = self._detect_language(
            scan.indicator_files, scan.ts_files, scan.js_files
        )
        frameworks = self._detect_frameworks(scan.indicator_files)
        test_fws = self._detect_test_frameworks(
            scan.indicator_files, scan.test_files, language
        )
        stack_id = self._build_stack_id(language, frameworks, test_fws)

        # representative files (5 source + 5 test)
        representative: list[str] = scan.source_files[:5] + scan.test_files[:5]

        return CodeSignals(
            stack_id=stack_id,
            primary_language=language,
            frameworks=tuple(frameworks),
            test_frameworks=tuple(test_fws),
            scope_tag=language,
            representative_files=tuple(representative),
            detected_at=now_utc_iso(),
        )

    def _scan_tree(self) -> _TreeScan:
        """Walk the repository tree once and bucket every file it finds.

        Returns indicator filenames (for language/framework detection),
        source vs. test file paths, and TS/JS counts (for the TS-vs-JS
        majority heuristic) — all gathered in a single ``os.walk`` pass.
        """
        indicator_files: set[str] = set()
        source_files: list[str] = []
        test_files: list[str] = []
        ts_files = 0
        js_files = 0

        root_str = str(self._repo_root)

        for dirpath, dirnames, filenames in os.walk(root_str):
            # Compute depth relative to root
            rel = os.path.relpath(dirpath, root_str)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > self._max_depth:
                dirnames.clear()
                continue

            # Prune excluded directories in-place so os.walk skips them
            dirnames[:] = [
                d for d in dirnames if d not in EXCLUDED_DIRS
            ]

            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(abs_path, root_str).replace(
                    os.sep, "/"
                )

                # Track indicator filenames for language/framework detection
                indicator_files.add(filename)

                # Count TS vs JS files for disambiguation
                if filename.endswith((".ts", ".tsx")):
                    ts_files += 1
                elif filename.endswith((".js", ".jsx", ".mjs")):
                    js_files += 1

                # Bucket into source vs test
                if _is_test_file(rel_path, filename):
                    test_files.append(rel_path)
                else:
                    source_files.append(rel_path)

        return _TreeScan(
            indicator_files=indicator_files,
            source_files=source_files,
            test_files=test_files,
            ts_files=ts_files,
            js_files=js_files,
        )

    @staticmethod
    def _detect_frameworks(indicator_files: set[str]) -> list[str]:
        """Return app-framework names whose indicator file was observed."""
        frameworks: list[str] = []
        for indicator, fw in FRAMEWORK_INDICATORS.items():
            if indicator in indicator_files and fw not in frameworks:
                frameworks.append(fw)
        return frameworks

    @staticmethod
    def _detect_test_frameworks(
        indicator_files: set[str],
        test_files: list[str],
        language: str,
    ) -> list[str]:
        """Return test-framework names, falling back to a pytest heuristic.

        When no test-framework indicator file was found but the project is
        Python and at least one test file lives under a ``tests`` directory,
        assume pytest (the de-facto standard).
        """
        test_fws: list[str] = []
        for indicator, tf in TEST_FRAMEWORK_INDICATORS.items():
            if indicator in indicator_files and tf not in test_fws:
                test_fws.append(tf)

        # Pytest fallback: look for tests/test_*.py or tests/*_test.py
        if not test_fws and language == "python":
            for f in test_files:
                parts = f.split("/")
                if "tests" in parts:
                    test_fws.append("pytest")
                    break

        return test_fws

    @staticmethod
    def _build_stack_id(
        language: str,
        frameworks: list[str],
        test_fws: list[str],
    ) -> str:
        """Compose the ``language[+framework][+test_framework]`` stack id."""
        if language == "unknown":
            return "unknown"

        parts_stack: list[str] = [language]
        if frameworks:
            parts_stack.append(frameworks[0])
        if test_fws:
            parts_stack.append(test_fws[0])

        return "+".join(parts_stack)

    def _detect_language(
        self,
        indicator_files: set[str],
        ts_files: int,
        js_files: int,
    ) -> str:
        """Return the primary language string."""
        # TypeScript takes precedence over JavaScript when tsconfig.json present
        if PACKAGE_JSON in indicator_files:
            if "tsconfig.json" in indicator_files:
                return "typescript"
            # Majority-extension heuristic
            total_js_ts = ts_files + js_files
            if total_js_ts > 0 and ts_files / total_js_ts > 0.5:
                return "typescript"
            return "javascript"

        # Check remaining language indicators in priority order
        for indicator, lang in LANGUAGE_INDICATORS.items():
            if indicator == PACKAGE_JSON:
                continue  # handled above
            if indicator in indicator_files:
                return lang

        return "unknown"

    @staticmethod
    def _unknown_signals() -> CodeSignals:
        return CodeSignals(
            stack_id="unknown",
            primary_language="unknown",
            frameworks=(),
            test_frameworks=(),
            scope_tag="unknown",
            representative_files=(),
            detected_at=now_utc_iso(),
        )
