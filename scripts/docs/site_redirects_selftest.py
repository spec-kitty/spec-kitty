"""Prove the redirect coverage gate's own verdicts on the built site (#6933; ADR 2026-10-31-1 D-5).

The docs-site job runs ``dockitty-check-redirect-coverage`` twice: once with ``--docs`` and the
declared map, and once with neither. The second run is the one that excuses nothing. Both are
green on a good build. This self-test then makes sure each still fails where it must. On a
hard-linked copy of the built site (the real ``site/dist`` is never touched), it plants three
mutants and runs the real gate both ways on each:

* ``dead-target``: the page a redirect lands on is gone. Both runs must fail (1, 1).
* ``missing-key``: a legacy URL's redirect stub is gone. Both runs must fail (1, 1).
* ``draft-excused``: a stub is gone and the declared map sends that URL to a draft page.
  The ``--docs`` run excuses it as unpublished (0); the run without ``--docs`` must not (1).
  This proves why the second run exists.

Any other verdict, including a usage error (exit 2), fails the self-test, so a gate that
stops failing, or a flag the gate stops understanding, cannot leave the job green.

Usage (from the repository root, after the build and both gate runs)::

    PYTHONPATH=.:src python3 -m scripts.docs.site_redirects_selftest site/dist

Exit 0 when every verdict matches, 1 with one line per mismatch.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# Runnable bare: resolve `scripts.*` from the script, not the cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.docs._dockitty_contract import is_in_draft_folder, route_of  # noqa: E402

__all__ = ["EXPECTED", "Gate", "Mutant", "main", "plant", "selftest"]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_SITE: Final[Path] = REPO_ROOT / "site"
_GATE: Final[tuple[str, ...]] = ("pnpm", "exec", "dockitty-check-redirect-coverage")
_MAP_NAME: Final[str] = "legacy-redirects.json"
_BASELINE_NAME: Final[str] = "url-baseline.txt"
_ASTRO_CONFIG: Final[tuple[str, str]] = ("--astro-config", "astro.config.mjs")
_INDEX_HTML: Final[str] = "index.html"
_MD_SUFFIX: Final[str] = ".md"

#: The gate's exit code per mutant: (the run with ``--docs`` and the declared map, the run without).
EXPECTED: Final[Mapping[str, tuple[int, int]]] = {
    "dead-target": (1, 1),
    "missing-key": (1, 1),
    "draft-excused": (0, 1),
}

#: Runs the gate with these arguments (``site/`` is the working directory) and returns its exit code.
Gate = Callable[[Sequence[str]], int]


@dataclass(frozen=True, slots=True)
class Mutant:
    """One planted defect: the copied ``dist`` and the declared map the gate reads for it."""

    name: str
    dist: Path
    declared: Path


def _run_pnpm_gate(args: Sequence[str]) -> int:
    # The mutants' FAILED reports are expected, so the gate's output is captured, not echoed into
    # the job log; a mismatch is reported by mutant and exit codes, and rerunning the gate by hand
    # on the named mutant shows the detail.
    return subprocess.run([*_GATE, *args], cwd=_SITE, check=False, capture_output=True).returncode  # noqa: S603  (fixed argv, no shell)


def _link_copy(dist: Path, into: Path) -> Path:
    """A hard-linked copy of *dist*: cheap, and unlinking a file never touches the original."""
    shutil.copytree(dist, into, copy_function=os.link)
    return into


def _page_file(dist: Path, route: str) -> Path:
    return dist / route.strip("/") / _INDEX_HTML if route != "/" else dist / _INDEX_HTML


def _pick_key(mapping: Mapping[str, str], dist: Path) -> tuple[str, str]:
    """The first key (sorted) whose stub exists and whose target is a built page other than the root."""
    for key, target in sorted(mapping.items()):
        if target != "/" and (dist / key.lstrip("/")).is_file() and _page_file(dist, target).is_file():
            return key, target
    raise SystemExit("site redirects self-test: no key with a built stub and a built target page")


def _draft_route(docs: Path) -> str:
    for path in sorted(docs.rglob(f"*{_MD_SUFFIX}")):
        rel = path.relative_to(docs).as_posix()
        if is_in_draft_folder(rel):
            return route_of(rel)
    raise SystemExit("site redirects self-test: no draft page to point a mutant at")


def plant(name: str, *, dist: Path, docs: Path, declared: Path, work: Path) -> Mutant:
    """Plant the mutant *name* on a hard-linked copy of *dist* under *work*."""
    mapping: dict[str, str] = json.loads(declared.read_text(encoding="utf-8"))
    copy = _link_copy(dist, work / name / "dist")
    key, target = _pick_key(mapping, dist)
    if name == "dead-target":
        _page_file(copy, target).unlink()
        return Mutant(name, copy, declared)
    (copy / key.lstrip("/")).unlink()
    if name == "missing-key":
        return Mutant(name, copy, declared)
    if name == "draft-excused":
        mutated = work / name / _MAP_NAME
        mutated.write_text(json.dumps({**mapping, key: _draft_route(docs)}, indent=2) + "\n", encoding="utf-8")
        return Mutant(name, copy, mutated)
    raise ValueError(f"unknown mutant {name!r}")


def _verdicts(mutant: Mutant, baseline: Path, docs: Path, gate: Gate) -> tuple[int, int]:
    common = [str(baseline), str(mutant.dist)]
    with_docs = gate([*common, "--docs", str(docs), "--declared-redirects", str(mutant.declared), *_ASTRO_CONFIG])
    without = gate([*common, *_ASTRO_CONFIG])
    return with_docs, without


def selftest(*, dist: Path, docs: Path, declared: Path, baseline: Path, gate: Gate | None = None) -> list[str]:
    """Every mutant whose gate verdicts differ from :data:`EXPECTED` (empty when all match).

    *gate* defaults to the real ``pnpm exec dockitty-check-redirect-coverage`` run in ``site/``.
    """
    run = gate if gate is not None else _run_pnpm_gate
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="redirect-selftest-") as tmp:
        for name, expected in EXPECTED.items():
            mutant = plant(name, dist=dist, docs=docs, declared=declared, work=Path(tmp))
            actual = _verdicts(mutant, baseline, docs, run)
            if actual != expected:
                problems.append(f"{name}: gate exited {actual} (with --docs, without); expected {expected}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("dist", type=Path, help="the built site (site/dist); never modified")
    parser.add_argument("--docs", type=Path, default=REPO_ROOT / "docs", help="the docs tree (default: docs)")
    parser.add_argument("--declared", type=Path, default=_SITE / _MAP_NAME, help="the declared map (default: site/legacy-redirects.json)")
    parser.add_argument("--baseline", type=Path, default=_SITE / _BASELINE_NAME, help="the URL baseline (default: site/url-baseline.txt)")
    args = parser.parse_args(argv)
    paths = {"dist": args.dist.resolve(), "docs": args.docs.resolve(), "declared": args.declared.resolve(), "baseline": args.baseline.resolve()}
    problems = selftest(**paths)
    for problem in problems:
        print(f"site redirects self-test: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"site redirects self-test: {len(EXPECTED)} mutant(s), every gate verdict as expected ({', '.join(EXPECTED)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
