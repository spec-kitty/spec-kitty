"""Always-on gate: every ``load_meta`` call site is accounted for (FR-007 / NFR-003 / D10).

The scanner and the ledger live in :mod:`tests.architectural._load_meta_census`
(the single home since #5138). This module is the always-on gate over them: an
AST scan of the LIVE source tree cross-referenced against the ledger, so a NEW
unwrapped call site, a call count that grows inside an already-accounted
function, or a STALE ledger row (the site was routed away but the row was not
deleted) all fail loudly -- plus the non-vacuity proofs for the scanner itself.

The behavioural half -- driving ACTUAL routed-reader product functions against
corrupt/non-dict ``meta.json`` payloads -- stays in
``tests/specify_cli/test_meta_fail_closed_full_census_contract.py``, recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` (#4374).
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file
from tests.architectural._load_meta_census import ACCOUNTED_SITES, ROUTE_HINT, scan_load_meta_call_sites

pytestmark = [pytest.mark.architectural]

_SRC_ROOT = Path(__file__).resolve().parents[2] / "src"


def test_no_unaccounted_load_meta_call_sites() -> None:
    """A ``load_meta`` call site outside the frozen ledger FAILS the build.

    This is the anti-scope-creep guard for the whole of IC-03. It compares an
    AST scan of the LIVE tree against :data:`~tests.architectural._load_meta_census.ACCOUNTED_SITES` in BOTH
    directions, so neither a new unwrapped reader nor a stale ledger row can
    hide.
    """
    live = scan_load_meta_call_sites(_SRC_ROOT)

    unaccounted = {key: n for key, n in live.items() if key not in ACCOUNTED_SITES}
    assert not unaccounted, (
        "NEW unaccounted `load_meta` call site(s) detected (FR-007 / NFR-003 / D10):\n"
        + "\n".join(f"  {rel}::{qual}  x{n}" for (rel, qual), n in sorted(unaccounted.items()))
        + f"\n\n{ROUTE_HINT}"
    )

    grew = {key: (live[key], expected) for key, (expected, _reason) in ACCOUNTED_SITES.items() if live.get(key, 0) > expected}
    assert not grew, (
        "EXTRA `load_meta` call(s) added inside an already-accounted function:\n"
        + "\n".join(f"  {rel}::{qual}  live={got} accounted={exp}" for (rel, qual), (got, exp) in sorted(grew.items()))
        + f"\n\n{ROUTE_HINT}"
    )

    stale = {key: expected for key, (expected, _reason) in ACCOUNTED_SITES.items() if live.get(key, 0) < expected}
    assert not stale, (
        "STALE ACCOUNTED_SITES row(s): the live scan no longer finds these.\n"
        "If you just ROUTED the site, delete its row (a stale row would mask a "
        "future reader re-added at the same place):\n"
        + "\n".join(f"  {rel}::{qual}  accounted={exp}, live={live.get((rel, qual), 0)}" for (rel, qual), exp in sorted(stale.items()))
    )


@pytest.mark.parametrize(
    ("label", "source"),
    [
        (
            "plain import",
            "from specify_cli.mission_metadata import load_meta\ndef reader(d):\n    return load_meta(d)\n",
        ),
        (
            "aliased import (the grep blind spot)",
            "from specify_cli.mission_metadata import load_meta as _lm\ndef reader(d):\n    return _lm(d)\n",
        ),
        (
            "deferred in-function aliased import",
            "def reader(d):\n    from specify_cli.mission_metadata import load_meta as _x\n    return _x(d)\n",
        ),
        (
            "module-qualified attribute call",
            "import specify_cli.mission_metadata as mm\ndef reader(d):\n    return mm.load_meta(d)\n",
        ),
    ],
)
def test_scanner_detects_every_call_form(tmp_path: Path, label: str, source: str) -> None:
    """The scanner must see all four binding forms, not just the literal name.

    Without the aliased cases this gate is forgeable: reverting a routed site
    to an aliased ``load_meta`` import would slip past a text-grep scan.
    """
    pkg = tmp_path / "src" / "probe_pkg"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text(source, encoding="utf-8")

    found = scan_load_meta_call_sites(tmp_path / "src")

    assert found.get(("src/probe_pkg/mod.py", "reader")) == 1, f"scanner missed the {label} call form"


def test_scanner_ignores_unrelated_calls(tmp_path: Path) -> None:
    """Negative control: similarly-named symbols are NOT counted."""
    pkg = tmp_path / "src" / "probe_pkg"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text(
        "from specify_cli.core.paths import load_meta_fail_closed\n"
        "def reader(d):\n"
        "    # load_meta( in a comment is not a call site\n"
        '    """load_meta( in a docstring is not one either."""\n'
        "    return load_meta_fail_closed(d)\n",
        encoding="utf-8",
    )

    assert scan_load_meta_call_sites(tmp_path / "src") == Counter()


@pytest.mark.parametrize("broken", [b"def broken(:\n", b"\xff\xfe x = 1\n"], ids=["syntax-error", "undecodable"])
def test_scanner_fails_closed_on_unparseable_source(tmp_path: Path, broken: bytes) -> None:
    """#4362: an unparseable ``src/**/*.py`` must RED the scan, never be skipped.

    A silently-dropped file would take its call sites out of the census and
    let the gate pass over code it never read.
    """
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (pkg / "broken.py").write_bytes(broken)

    with pytest.raises(AssertionError, match=r"src/pkg/broken\.py"):
        scan_load_meta_call_sites(tmp_path / "src")


def _defines_census(tree: ast.Module) -> bool:
    """True when ``tree`` binds a ``load_meta`` census scanner or ledger at any level."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.lstrip("_") == "scan_load_meta_call_sites":
            return True
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id.lstrip("_") == "ACCOUNTED_SITES" for t in targets):
            return True
    return False


def test_census_has_exactly_one_home() -> None:
    """#5138: the scanner and the ledger are defined once, in ``_load_meta_census``.

    Two hand-maintained copies drifted (#5135). A second definition anywhere
    under ``tests/`` -- annotated or not, public or ``_``-prefixed -- re-opens
    that split-brain, so it fails here.
    """
    tests_root = _SRC_ROOT.parent / "tests"
    homes = sorted(
        path.relative_to(tests_root.parent).as_posix() for path in tests_root.rglob("*.py") if "__pycache__" not in path.parts and _defines_census(parse_file(path))
    )
    assert homes == ["tests/architectural/_load_meta_census.py"], homes


@pytest.mark.parametrize(
    "source",
    [
        "ACCOUNTED_SITES = {}\n",
        "_ACCOUNTED_SITES: dict[tuple[str, str], tuple[int, str]] = {}\n",
        "def _scan_load_meta_call_sites(root):\n    return {}\n",
    ],
    ids=["unannotated", "private-annotated", "private-scanner"],
)
def test_single_home_guard_sees_every_second_definition(source: str) -> None:
    assert _defines_census(ast.parse(source))
