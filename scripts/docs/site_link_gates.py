"""Run a doc-kitty link gate against the priced link debt (#6932; ADR 2026-10-31-1 D-11).

The docsite's two link gates, ``dockitty-check-links --strict`` (the source tree)
and ``dockitty-assert-no-broken-links`` (the built site), report broken links that
sit inside immutable history: dated ADRs, ``plans/``, ``reports/``, ``changelog/``
and ``archive/`` bodies, which are never rewritten. Those problems are priced debt
(Standing Order #5), listed once in ``site/link-debt.json``; burn-down is tracked in
#7489.

This wrapper runs the gate given after ``--``, echoes its output, parses every
problem (``gate``, ``source`` page under ``docs/``, ``target``) and:

* fails on a problem the debt file does not list;
* fails on a debt entry whose source is not immutable
  (``_dockitty_contract.is_immutable``): an editable page fixes its links instead;
* fails when the gate exits non-zero with no problem it can parse (a crash, a bad flag);
* prints, without failing, entries that no longer occur.

It is not a ratchet: no count, no shrink-only rule.

Usage (from ``site/``)::

    python3 ../scripts/docs/site_link_gates.py check-links -- pnpm exec dockitty-check-links ../docs --strict ...
    python3 ../scripts/docs/site_link_gates.py built-links -- pnpm exec dockitty-assert-no-broken-links dist ...

Standard library only, like ``site_contract.py``.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# Runnable bare (`python3 scripts/docs/site_link_gates.py`): resolve `scripts.*` from the script, not the cwd.
_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
from scripts.docs._dockitty_contract import is_immutable, page_for_slug  # noqa: E402  (after the path bootstrap above)

__all__ = ["DEBT_PATH", "GATES", "RELATIVE_LINKS_GATE", "Problem", "Verdict", "evaluate", "load_debt", "main", "parse"]

DEBT_PATH: Final[Path] = _ROOT / "site" / "link-debt.json"
DOCS_PATH: Final[Path] = _ROOT / "docs"

#: The gates the wrapper knows: ``check-links`` (source tree) and ``built-links`` (built site).
GATES: Final[tuple[str, ...]] = ("check-links", "built-links")

#: The debt file's third gate: dead bare-relative body links, read by
#: ``tests/docs/test_relative_link_fixer.py`` (``scripts/docs/relative_link_fixer.py`` has no allowlist of its own).
RELATIVE_LINKS_GATE: Final[str] = "relative-links"

_MARK: Final[str] = "✖"
_CHECK_LINKS: Final[re.Pattern[str]] = re.compile(rf"^{_MARK} (?P<source>[^:]+): .* → (?P<target>.+)$")
_BUILT_LINKS: Final[re.Pattern[str]] = re.compile(rf"^{_MARK} (?P<page>\S+) → (?P<target>.+?) \(resolved: [^)]*\): .+$")
_INDEX_HTML: Final[str] = "index.html"
_UNPARSED: Final[str] = "?"


@dataclass(frozen=True, slots=True)
class Problem:
    """One broken link a gate reported: its gate, its source page (under ``docs/``) and its target."""

    gate: str
    source: str
    target: str

    def __str__(self) -> str:
        return f"{self.gate}: {self.source} → {self.target}"


@dataclass(slots=True)
class Verdict:
    """``failures`` fail the gate; ``stale`` entries are only reported."""

    failures: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)


def _source_of_check_links(raw: str, docs: Path) -> str:
    """``../docs/adr/x.md`` (as the gate prints it from ``site/``) -> ``adr/x.md``."""
    parts = Path(raw).parts
    while parts and parts[0] in ("..", "."):
        parts = parts[1:]
    if parts[:1] == (docs.name,):
        parts = parts[1:]
    return "/".join(parts) if parts else raw


def _source_of_built_page(page: str, docs: Path) -> str:
    slug = page[: -len(_INDEX_HTML)].rstrip("/") if page.endswith(_INDEX_HTML) else page
    found = page_for_slug(docs, slug)
    return found.relative_to(docs).as_posix() if found else page


def _parse_line(gate: str, line: str, docs: Path) -> Problem:
    if gate == "check-links":
        match = _CHECK_LINKS.match(line)
        if match:
            return Problem(gate, _source_of_check_links(match["source"], docs), match["target"].strip())
    else:
        match = _BUILT_LINKS.match(line)
        if match:
            return Problem(gate, _source_of_built_page(match["page"], docs), match["target"].strip())
    return Problem(gate, _UNPARSED, line)


def parse(gate: str, output: str, docs: Path) -> set[Problem]:
    """Every problem in a gate's *output*; a ``✖`` line of an unknown shape is kept, unparsed."""
    lines = (line.strip() for line in output.splitlines())
    return {_parse_line(gate, line, docs) for line in lines if line.startswith(_MARK)}


def load_debt(path: Path) -> list[Problem]:
    """The debt entries of the file at *path*."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Problem(entry["gate"], entry["source"], entry["target"]) for entry in data["entries"]]


def evaluate(problems: Iterable[Problem], debt: Iterable[Problem], docs: Path) -> Verdict:
    """The verdict on a gate's *problems* against the *debt* entries; sources are pages under *docs*."""
    found = set(problems)
    gate_names = {problem.gate for problem in found}
    entries = set(debt)
    verdict = Verdict()
    verdict.failures.extend(f"not in the link debt: {problem}" for problem in sorted(found - entries, key=str))
    for entry in sorted(entries, key=str):
        if not is_immutable(entry.source):
            verdict.failures.append(f"debt entry source is not immutable, fix the link instead: {entry}")
        elif not (docs / entry.source).is_file():
            verdict.failures.append(f"debt entry source page does not exist: {entry}")
        elif entry not in found and (not gate_names or entry.gate in gate_names):
            verdict.stale.append(f"no longer occurs (remove the entry): {entry}")
    return verdict


def _run(command: list[str]) -> tuple[int, str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603  (the gate command comes from the workflow/Makefile)
    output = result.stdout + result.stderr
    sys.stdout.write(output)
    return result.returncode, output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("gate", choices=GATES)
    parser.add_argument("--docs", type=Path, default=DOCS_PATH, help="the docs tree (default: docs/)")
    parser.add_argument("--debt", type=Path, default=DEBT_PATH, help="the link debt (default: site/link-debt.json)")
    raw = list(sys.argv[1:] if argv is None else argv)
    split = raw.index("--") if "--" in raw else len(raw)
    args = parser.parse_args(raw[:split])
    command = raw[split + 1 :]
    if not command:
        parser.error("give the gate command after --")
    code, output = _run(command)
    problems = parse(args.gate, output, args.docs)
    debt = [entry for entry in load_debt(args.debt) if entry.gate == args.gate]
    verdict = evaluate(problems, debt, args.docs)
    if code != 0 and not problems:
        verdict.failures.append(f"{args.gate} exited {code} with no problem the wrapper can parse")
    for line in verdict.stale:
        print(f"link debt: {line}")
    for line in verdict.failures:
        print(f"link debt: FAIL {line}", file=sys.stderr)
    listed = len(problems) - len([f for f in verdict.failures if f.startswith("not in the link debt")])
    print(f"link debt: {args.gate}: {len(problems)} problem(s), {listed} listed as priced debt (#7489), {len(verdict.failures)} failure(s)")
    return 1 if verdict.failures else 0


if __name__ == "__main__":
    sys.exit(main())
