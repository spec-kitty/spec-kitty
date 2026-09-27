"""Red-first ATDD: ``doc_status: durable`` accepted across the authority chain.

WP01 / IC-01 (FR-002, NFR-001, C-004). ``durable`` is the reserved, never-retire
documentation-lifecycle value for domain throughlines. It has no closed-set
runtime validator today (vocabulary enforcement is deferred), so the machine
guarantee this suite pins is the **directive↔enum agreement** — the two
independent authority sources (directive 042, the authoritative vocabulary, and
``DocStatus``, the enum that mirrors it) must declare the *same* set and both
must contain ``durable``. That cross-source consistency check IS the SC-004 gate.

Assertions:

* **(a) directive↔enum set-equality** (RED-first, the real gate): the vocabulary
  parsed out of ``042-common-docs.directive.yaml`` equals ``{s.value for s in
  DocStatus}`` and both contain ``durable``. Reds on the base (durable in
  neither) and reds under one-sided drift (only directive *or* only enum edited).
* **(b) prose propagation** (RED-first): ``durable`` reaches the common-docs
  styleguide vocabulary prose and all three ``common-docs-*`` tactic
  restatements, plus the freshness-SLA never-stale prose. Reds on base.
* **(c) never point-in-time** (GREEN-on-base regression guard): ``durable`` is
  NOT among ``point_in_time_markers`` — it is the semantic opposite. Reds only if
  a later change wrongly files it there.
* **(d) structural-lint acceptance** (GREEN-on-base guard): a synthetic
  ``durable`` page outside ``plans/`` is neither flagged point-in-time nor
  missing required frontmatter.

The fixture harness (lint-asset load, ``load_config``, ``_write``) mirrors
``tests/docs/test_docs_structural_lint.py`` rather than re-inventing it.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from ruamel.yaml import YAML

from scripts.docs.frontmatter_backfill import DocStatus

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKS = _REPO_ROOT / "packs" / "built-in"

DIRECTIVE_PATH = _PACKS / "directives" / "042-common-docs.directive.yaml"
STYLEGUIDE_PATH = _PACKS / "styleguides" / "common-docs.styleguide.yaml"
FRESHNESS_STYLEGUIDE_PATH = _PACKS / "styleguides" / "docs-freshness-sla.styleguide.yaml"
TACTIC_PATHS = {name: _PACKS / "tactics" / f"common-docs-{name}.tactic.yaml" for name in ("curation", "write", "scaffold")}

#: The reserved never-retire lifecycle value under test.
RESERVED = "durable"


# --- Structural-lint fixture harness (mirrors test_docs_structural_lint.py) ---


def _resolve_lint_asset_path() -> Path:
    """Resolve the shipped structural-lint asset via ``DoctrineService.assets``."""
    from charter.offering.service import DoctrineService

    return DoctrineService().assets.resolve_path("common-docs-structural-lint")


_LINT_ASSET_PATH = _resolve_lint_asset_path()


_LINT_ASSET_MODULE_NAME = "docs_structural_lint_durable_asset"

#: Populated by the autouse ``_lint_module`` fixture below, once per module.
load_config: Callable[..., Any]
check_frontmatter_contract: Callable[..., Any]
check_point_in_time_placement: Callable[..., Any]


@pytest.fixture(scope="module", autouse=True)
def _lint_module() -> Iterator[ModuleType]:
    """Load the structural-lint asset once for this module's tests.

    ``dataclass()`` on a class defined in a dynamically-loaded module looks
    the class up via ``sys.modules[cls.__module__]``, so the module must be
    registered there before ``exec_module`` runs. A module-scoped
    ``pytest.MonkeyPatch.context()`` — not the function-scoped ``monkeypatch``
    fixture, which a module-scoped fixture cannot depend on — keeps that
    registration and undoes it once every test in this module has run.
    """
    global load_config, check_frontmatter_contract, check_point_in_time_placement
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_LINT_ASSET_MODULE_NAME, _LINT_ASSET_PATH)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise RuntimeError(f"cannot load lint asset from {_LINT_ASSET_PATH}")
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _LINT_ASSET_MODULE_NAME, module)
        spec.loader.exec_module(module)
        load_config = module.load_config
        check_frontmatter_contract = module.check_frontmatter_contract
        check_point_in_time_placement = module.check_point_in_time_placement
        yield module


def _write(path: Path, *, frontmatter: dict[str, Any] | None = None, body: str = "# Body\n") -> None:
    """Write a docs page, optionally with a YAML frontmatter block."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if frontmatter is not None:
        lines.append("---")
        lines.extend(f"{key}: {json.dumps(value)}" for key, value in frontmatter.items())
        lines.append("---")
    lines.append(body)
    path.write_text("\n".join(lines), encoding="utf-8")


# --- Authority-source parsers ------------------------------------------------

#: Matches the doc_status vocabulary parenthetical in directive 042. Anchored on
#: the ``doc_status`` bullet so it never picks up the MADR ``(Proposed /
#: Accepted / Deprecated / Superseded)`` decision-status list.
_VOCAB_RE = re.compile(r"doc_status` \(vocabulary\s+([^)]+)\)", re.DOTALL)


def _directive_doc_status_vocab() -> set[str]:
    """Parse directive 042's authoritative ``doc_status`` vocabulary set."""
    text = DIRECTIVE_PATH.read_text(encoding="utf-8")
    match = _VOCAB_RE.search(text)
    assert match is not None, "could not locate the doc_status vocabulary in directive 042"
    return {token.strip() for token in match.group(1).split("/") if token.strip()}


def _styleguide_vocab_prose() -> str:
    """Return the common-docs styleguide's controlled-vocabulary principle prose."""
    yaml = YAML(typ="safe")
    raw = yaml.load(STYLEGUIDE_PATH.read_text(encoding="utf-8"))
    for principle in raw["principles"]:
        if "controlled vocabulary" in principle:
            return str(principle)
    raise AssertionError("no controlled-vocabulary principle found in common-docs styleguide")


# --- (a) directive↔enum agreement — the RED-first gate -----------------------


def test_directive_and_enum_vocabularies_agree_and_include_durable() -> None:
    """The directive vocabulary set and the enum value set are equal and hold durable.

    This is the load-bearing, cross-source consistency gate (SC-004): it reds on
    the base (durable in neither authority) AND reds under one-sided drift
    (durable added to only the directive or only the enum), so it is not a
    constant assertion — it passes only when both authority sources mirror.
    """
    directive_vocab = _directive_doc_status_vocab()
    enum_vocab = {status.value for status in DocStatus}

    assert directive_vocab == enum_vocab, (
        "directive 042 doc_status vocabulary and DocStatus enum disagree — "
        f"only-in-directive={sorted(directive_vocab - enum_vocab)}, "
        f"only-in-enum={sorted(enum_vocab - directive_vocab)}"
    )
    assert RESERVED in directive_vocab
    assert RESERVED in enum_vocab


# --- (b) prose propagation across the authority sites — RED-first ------------


def test_durable_propagated_to_styleguide_and_all_tactics() -> None:
    """``durable`` reaches the styleguide vocabulary prose and all three tactics."""
    assert RESERVED in _styleguide_vocab_prose(), "common-docs styleguide controlled-vocabulary prose omits 'durable'"
    for name, path in TACTIC_PATHS.items():
        assert RESERVED in path.read_text(encoding="utf-8"), f"common-docs-{name} tactic restatement omits 'durable'"


def test_durable_is_documented_never_stale_in_freshness_sla() -> None:
    """The freshness-SLA styleguide records that durable pages are never aged out."""
    assert RESERVED in FRESHNESS_STYLEGUIDE_PATH.read_text(encoding="utf-8"), "docs-freshness-sla styleguide does not mention the durable never-stale policy"


# --- (c) never point-in-time — GREEN-on-base regression guard ----------------


def test_durable_is_not_a_point_in_time_marker() -> None:
    """GUARD (green on base): durable must never be a point_in_time marker.

    durable is the semantic opposite of point-in-time / closeout. This reds only
    if a later change wrongly files durable in ``point_in_time_markers``. The
    existing marker values are asserted present so the block is not silently
    emptied under this guard.
    """
    config = load_config(STYLEGUIDE_PATH)
    marker_values = {marker.frontmatter_value for marker in config.point_in_time_markers}

    assert RESERVED not in marker_values
    assert "point_in_time" in marker_values
    assert "closeout" in marker_values


# --- (d) structural-lint acceptance — GREEN-on-base guard --------------------


def test_durable_page_passes_structural_lint(tmp_path: Path) -> None:
    """GUARD (green on base): a durable page is accepted by the structural lint.

    A ``doc_status: durable`` page outside ``plans/`` is neither flagged
    point-in-time (durable is not a marker and the basename is undated) nor
    missing required frontmatter (it carries doc_status + updated).
    """
    docs = tmp_path / "docs"
    page = docs / "architecture" / "durable-throughline.md"
    _write(page, frontmatter={"doc_status": RESERVED, "updated": "2026-08-12"})
    config = load_config(STYLEGUIDE_PATH)

    point_in_time = check_point_in_time_placement([page], docs, tmp_path, config)
    frontmatter = check_frontmatter_contract([page], docs, tmp_path, config)

    assert point_in_time == []
    assert frontmatter == []
