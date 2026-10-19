"""Heuristic code-reading collector for charter synthesis.

Walks the project repository up to a configurable depth, detects the primary
language / framework / test-framework stack, and returns a ``CodeSignals``
dataclass suitable for injection into an ``EvidenceBundle``.

No external runtime dependencies — stdlib ``pathlib`` and ``os.walk`` only.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field
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
    "build.gradle.kts": "java",
    "settings.gradle": "java",
    "settings.gradle.kts": "java",
    "gradlew": "java",
    "mvnw": "java",
    "Gemfile": "ruby",
    "composer.json": "php",
    # package.json is handled separately (js vs ts disambiguation)
    PACKAGE_JSON: "javascript",
}

# Source-file extension → language (used to break same-depth manifest ties)
SOURCE_EXT_LANG: dict[str, str] = {
    ".py": "python",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "java",
    ".rb": "ruby",
    ".php": "php",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
}

TSCONFIG_JSON = "tsconfig.json"

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

    indicator_depths: dict[str, int]
    source_files: list[str]
    test_files: list[str]
    ts_files: int
    js_files: int
    ext_counts: Counter[str] = field(default_factory=Counter)

    @property
    def indicator_files(self) -> set[str]:
        """All observed basenames."""
        return set(self.indicator_depths)


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


def _observe(scan: _TreeScan, filename: str, rel_path: str, depth: int) -> None:
    """Record one file into *scan* (shallowest depth per basename, counts, buckets)."""
    known = scan.indicator_depths.get(filename)
    if known is None or depth < known:
        scan.indicator_depths[filename] = depth

    ext = os.path.splitext(filename)[1]
    if ext in SOURCE_EXT_LANG:
        scan.ext_counts[SOURCE_EXT_LANG[ext]] += 1
    if ext in (".ts", ".tsx"):
        scan.ts_files += 1
    elif ext in (".js", ".jsx", ".mjs"):
        scan.js_files += 1

    if _is_test_file(rel_path, filename):
        scan.test_files.append(rel_path)
    else:
        scan.source_files.append(rel_path)


def _js_or_ts(scan: _TreeScan, package_depth: int) -> str:
    """Pick typescript vs javascript for a ``package.json`` at *package_depth*."""
    if scan.indicator_depths.get(TSCONFIG_JSON) == package_depth:
        return "typescript"
    total = scan.ts_files + scan.js_files
    if total > 0 and scan.ts_files / total > 0.5:
        return "typescript"
    return "javascript"


def _break_tie(languages: list[str], ext_counts: Counter[str]) -> str:
    """Return the language with most source files; ties keep indicator order."""
    return max(languages, key=lambda lang: (ext_counts[lang], -languages.index(lang)))


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

        language = self._detect_language(scan)
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
        scan = _TreeScan(
            indicator_depths={}, source_files=[], test_files=[], ts_files=0, js_files=0
        )
        root_str = str(self._repo_root)

        for dirpath, dirnames, filenames in os.walk(root_str):
            rel = os.path.relpath(dirpath, root_str)
            depth = 0 if rel == "." else rel.count(os.sep) + 1
            if depth > self._max_depth:
                dirnames.clear()
                continue

            # Prune excluded directories in-place so os.walk skips them
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

            for filename in filenames:
                abs_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(abs_path, root_str).replace(os.sep, "/")
                _observe(scan, filename, rel_path, depth)

        return scan

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

    @staticmethod
    def _detect_language(scan: _TreeScan) -> str:
        """Return the primary language, preferring the shallowest manifests.

        Manifests at the shallowest depth win; several languages at that depth
        are resolved by source-file counts, then indicator order.
        """
        hits = {
            name: depth
            for name, depth in scan.indicator_depths.items()
            if name in LANGUAGE_INDICATORS
        }
        if not hits:
            return "unknown"

        top = min(hits.values())
        languages: list[str] = []
        for indicator, lang in LANGUAGE_INDICATORS.items():
            if hits.get(indicator) != top:
                continue
            if indicator == PACKAGE_JSON:
                lang = _js_or_ts(scan, top)
            if lang not in languages:
                languages.append(lang)

        if len(languages) == 1:
            return languages[0]
        return _break_tie(languages, scan.ext_counts)

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
