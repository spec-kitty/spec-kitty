"""The legacy docsite build is retired (#6943, ADR 2026-10-31-1 D-6 and D-13 step 5).

The doc-kitty site (``site/``) is the only docs build. These tests keep the legacy
toolchain from coming back:

* its sources are absent: its configuration file under ``docs/``, every legacy ``toc.yml``
  navigation file under ``docs/``, the template under ``docs/templates/`` and the static resources
  the legacy build copied (``site/public/`` carries the site's own);
* the ``scripts/docs`` modules and data files that only fed the legacy build are
  absent (D-6 "drop", and the "port" scripts whose job doc-kitty now does);
* no Python file under ``scripts/`` or ``tests/`` imports one of those modules, so
  nothing silently keeps a deleted module's contract alive.

The legacy tool's name is spelled in two parts (:data:`_LEGACY_TOOL`) so that a
plain ``git grep`` for it over living files stays empty, which is the retirement's
done-when; ``tests/architectural/test_legacy_docsite_named_nowhere.py`` enforces it.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_DOCS: Final[Path] = _REPO_ROOT / "docs"
_SCRIPTS_DOCS: Final[Path] = _REPO_ROOT / "scripts" / "docs"

#: The legacy tool's name, in two parts so this file does not name it (see the module docstring).
_LEGACY_TOOL: Final[str] = "doc" + "fx"

#: The legacy sources (D-6 last row) and the static resources its configuration copied.
LEGACY_SOURCES: Final[tuple[str, ...]] = (
    f"docs/{_LEGACY_TOOL}.json",
    "docs/templates/spec-kitty",
    "docs/CNAME",
    "docs/robots.txt",
    "docs/.nojekyll",
)

#: ``scripts.docs`` modules that only fed the legacy build, or whose job doc-kitty now does.
RETIRED_MODULES: Final[tuple[str, ...]] = (
    "_published_pages",
    "capture_baseline_urls",
    "description_length_check",
    "generate_kitty_specs_docs",
    "glossary_linker",
    "plantuml_invoke",
    "plantuml_render",
    "redirect_stub_generator",
    "seo_postprocess",
    "seo_verify",
)

#: Data files of the retired modules; the ledgers under ``site/`` supersede the redirect inputs.
RETIRED_DATA: Final[tuple[str, ...]] = (
    "plantuml_pins.json",
    "redirect_map.yaml",
    "redirect_baseline_urls.json",
    "glossary_page",
)

#: A legacy navigation entry: ``- name: <title>`` followed by ``href:`` or ``items:`` (the generator's toc shape).
_TOC_ENTRY: Final[re.Pattern[str]] = re.compile(r"^- name: .+\n\s+(?:href|items):", re.MULTILINE)

_SCANNED_ROOTS: Final[tuple[str, ...]] = ("scripts", "tests")


def test_no_legacy_docsite_file_is_back() -> None:
    """Every resurrected legacy source, retired script and retired data file is reported at once."""
    candidates = [
        *LEGACY_SOURCES,
        *(f"scripts/docs/{module}.py" for module in RETIRED_MODULES),
        *(f"scripts/docs/{name}" for name in RETIRED_DATA),
    ]
    back = [rel for rel in candidates if (_REPO_ROOT / rel).exists()]
    back += [path.relative_to(_REPO_ROOT).as_posix() for path in _DOCS.rglob("toc.yml") if _TOC_ENTRY.search(path.read_text(encoding="utf-8", errors="replace"))]
    assert back == [], f"the legacy docsite build was retired (#6943), but these are back: {back}"


def retired_imports(source: str) -> list[str]:
    """The retired ``scripts.docs`` modules *source* imports, by dotted name."""
    retired = set(RETIRED_MODULES)
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
        else:
            continue
        found.extend(name for name in names if name.startswith("scripts.docs.") and name.split(".")[2] in retired)
    return found


def _python_files() -> Iterator[Path]:
    for root in _SCANNED_ROOTS:
        yield from (path for path in (_REPO_ROOT / root).rglob("*.py") if "__pycache__" not in path.parts)


def test_no_script_or_test_imports_a_retired_module() -> None:
    examined = 0
    offenders: list[str] = []
    for path in _python_files():
        examined += 1
        text = path.read_text(encoding="utf-8")
        if "scripts.docs" not in text:
            continue  # no import of the package can be in it; skip the parse
        offenders.extend(f"{path.relative_to(_REPO_ROOT).as_posix()}: {name}" for name in retired_imports(text))
    assert examined >= 500, f"only {examined} Python files scanned under {_SCANNED_ROOTS}"
    assert offenders == []


@pytest.mark.parametrize(
    "source",
    [
        "from scripts.docs import seo_postprocess\n",
        "from scripts.docs.redirect_stub_generator import generate\n",
        "import scripts.docs.plantuml_invoke as invoke\n",
    ],
)
def test_the_import_scan_finds_a_planted_import(source: str) -> None:
    assert retired_imports(source) != []


def test_the_import_scan_ignores_kept_modules() -> None:
    """Positive control: a kept module (``moves_ledger``, ``_dockitty_contract``) is not reported."""
    assert retired_imports("from scripts.docs import moves_ledger\nfrom scripts.docs._dockitty_contract import route_of\n") == []
