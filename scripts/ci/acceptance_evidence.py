#!/usr/bin/env python3
"""Write one versioned ``evidence.json`` for a nightly ``acceptance-bdd`` leg (WP03).

Counts come from the JUnit XML of each pass folder under ``--root``
(``<pass>/{allure-results,cucumber.json,junit}``), never from step outcomes.
The bundle follows ``contracts/evidence.schema.json`` of the
``acceptance-scenario-contract`` Mission (schema_version 1). Stdlib only.

``evidence.json`` is always written. The exit status is 1 unless the gating pass is ``passed`` (no JUnit XML, failures, or nothing executed).

``--gating-step-outcome`` takes the CI outcome of the step that ran the gating pass
(``steps.<id>.outcome``). Anything but ``success`` turns a ``passed`` gating pass into
``failed``: a run that died after writing some green JUnit XML must not read as green. A
pass with no JUnit XML stays ``missing``.
"""

from __future__ import annotations

import argparse
import json
import os
from xml.parsers import expat
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
GATING_NAME = "gating"
PASSES = (GATING_NAME, "wip")
COUNTERS = ("tests", "failures", "errors", "skipped")
EVIDENCE_FILE = "evidence.json"
STEP_SUCCESS = "success"
STEP_OUTCOMES = (STEP_SUCCESS, "failure", "cancelled", "skipped")
ENVIRONMENT_FILE = "environment.properties"


def _parse_suites(path: Path) -> list[dict[str, int]]:
    """Counters of every outermost ``<testsuite>`` in one JUnit file (nested suites are not re-counted)."""
    suites: list[dict[str, int]] = []
    depth = 0

    def start(tag: str, attrs: dict[str, str]) -> None:
        nonlocal depth
        if tag == "testsuite":
            if depth == 0:
                suites.append({name: int(attrs.get(name) or 0) for name in COUNTERS})
            depth += 1

    def end(tag: str) -> None:
        nonlocal depth
        if tag == "testsuite":
            depth -= 1

    parser = expat.ParserCreate()
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(path.read_bytes(), True)
    return suites


def _junit_counts(junit_dir: Path) -> tuple[dict[str, int], bool]:
    """Sum counters over ``junit/*.xml``; second value is False when no XML exists.

    An unreadable file is counted as one error so it cannot read as green.
    """
    totals = dict.fromkeys(COUNTERS, 0)
    files = sorted(junit_dir.glob("*.xml")) if junit_dir.is_dir() else []
    for path in files:
        try:
            suites = _parse_suites(path)
        except (expat.ExpatError, OSError, ValueError):
            totals["errors"] += 1
            continue
        for suite in suites:
            for name, value in suite.items():
                totals[name] += value
    return totals, bool(files)


def _outcome(counts: dict[str, int], has_xml: bool, *, gating: bool = False) -> str:
    """``missing`` without XML; ``failed`` on failures or errors.

    A gating pass that executed no scenario (``tests - skipped == 0``) is ``failed``: a green
    leg must not rest on nothing having run. The wip pass keeps ``passed`` for zero executed.
    """
    if not has_xml:
        return "missing"
    if counts["failures"] + counts["errors"] > 0:
        return "failed"
    if gating and counts["tests"] - counts["skipped"] <= 0:
        return "failed"
    return "passed"


def _step_adjusted(outcome: str, step_outcome: str | None) -> str:
    """A ``passed`` outcome becomes ``failed`` when the step that produced it did not succeed."""
    if outcome == "passed" and step_outcome not in (None, STEP_SUCCESS):
        return "failed"
    return outcome


def _pass_entry(root: Path, name: str, step_outcome: str | None = None) -> dict[str, Any]:
    counts, has_xml = _junit_counts(root / name / "junit")
    return {
        "outcome": _step_adjusted(_outcome(counts, has_xml, gating=name == GATING_NAME), step_outcome),
        **counts,
        "results": {
            "allure": f"{name}/allure-results",
            "cucumber": f"{name}/cucumber.json",
            "junit": f"{name}/junit",
        },
    }


_PROPERTY_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


def _unescape_property(raw: str) -> str:
    """Undo ``Properties.store`` escaping: ``\\uXXXX``, ``\\t \\n \\r \\f``, and ``\\<char>`` for the rest."""
    out: list[str] = []
    index = 0
    while index < len(raw):
        char = raw[index]
        if char != "\\" or index + 1 >= len(raw):
            out.append(char)
            index += 1
            continue
        nxt = raw[index + 1]
        hex_digits = raw[index + 2 : index + 6]
        if nxt == "u" and len(hex_digits) == 4 and all(c in "0123456789abcdefABCDEF" for c in hex_digits):
            out.append(chr(int(hex_digits, 16)))
            index += 6
        else:
            out.append(_PROPERTY_ESCAPES.get(nxt, nxt))
            index += 2
    return "".join(out)


def _split_property(line: str) -> tuple[str, str] | None:
    """Split at the first unescaped ``=`` or ``:``; None when the line has no separator."""
    index = 0
    while index < len(line):
        if line[index] == "\\":
            index += 2
            continue
        if line[index] in "=:":
            return line[:index].rstrip(), line[index + 1 :].lstrip()
        index += 1
    return None


def _read_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    if not path.is_file():
        return props
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.lstrip()
        if not text or text.startswith(("#", "!")):
            continue
        pair = _split_property(text)
        if pair is not None:
            props[_unescape_property(pair[0])] = _unescape_property(pair[1])
    return props


def _environment_value(root: Path, key: str) -> str | None:
    for name in PASSES:
        value = _read_properties(root / name / "allure-results" / ENVIRONMENT_FILE).get(key)
        if value:
            return value
    return None


def _run_url() -> str | None:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def build_bundle(root: Path, os_name: str, gating_step_outcome: str | None = None) -> dict[str, Any]:
    """Assemble the evidence bundle for the pass folders under ``root``.

    ``gating_step_outcome`` is the CI outcome of the gating step; ``None`` trusts the JUnit XML alone.
    """
    step_outcomes = {GATING_NAME: gating_step_outcome}
    return {
        "schema_version": SCHEMA_VERSION,
        "commit_sha": _environment_value(root, "commit.sha"),
        "cli_version": _environment_value(root, "cli.version"),
        "os": os_name,
        "run_url": _run_url(),
        "passes": {name: _pass_entry(root, name, step_outcomes.get(name)) for name in PASSES},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="acceptance-jvm/build/acceptance")
    parser.add_argument("--os", dest="os_name", required=True, help="matrix OS label")
    parser.add_argument(
        "--gating-step-outcome",
        choices=STEP_OUTCOMES,
        default=None,
        help="CI outcome of the gating step (steps.<id>.outcome); anything but success fails the gating pass",
    )
    args = parser.parse_args(argv)
    bundle = build_bundle(args.root, args.os_name, args.gating_step_outcome)
    args.root.mkdir(parents=True, exist_ok=True)
    target = args.root / EVIDENCE_FILE
    target.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    outcome = bundle["passes"][GATING_NAME]["outcome"]
    if outcome != "passed":
        print(f"error: the {GATING_NAME} pass is {outcome} under {args.root}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
