#!/usr/bin/env python3
"""Write one versioned ``evidence.json`` for a nightly ``acceptance-bdd`` leg (WP03).

Counts come from the JUnit XML of each pass folder under ``--root``
(``<pass>/{allure-results,cucumber.json,junit}``), never from step outcomes.
The bundle follows ``contracts/evidence.schema.json`` of the
``acceptance-scenario-contract`` Mission (schema_version 1). Stdlib only.
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
PASSES = ("gating", "wip")
COUNTERS = ("tests", "failures", "errors", "skipped")
EVIDENCE_FILE = "evidence.json"
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


def _outcome(counts: dict[str, int], has_xml: bool) -> str:
    if not has_xml:
        return "missing"
    return "failed" if counts["failures"] + counts["errors"] > 0 else "passed"


def _pass_entry(root: Path, name: str) -> dict[str, Any]:
    counts, has_xml = _junit_counts(root / name / "junit")
    return {
        "outcome": _outcome(counts, has_xml),
        **counts,
        "results": {
            "allure": f"{name}/allure-results",
            "cucumber": f"{name}/cucumber.json",
            "junit": f"{name}/junit",
        },
    }


def _read_properties(path: Path) -> dict[str, str]:
    props: dict[str, str] = {}
    if not path.is_file():
        return props
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith(("#", "!")) or "=" not in text:
            continue
        key, _, value = text.partition("=")
        props[key.strip()] = value.strip()
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


def build_bundle(root: Path, os_name: str) -> dict[str, Any]:
    """Assemble the evidence bundle for the pass folders under ``root``."""
    return {
        "schema_version": SCHEMA_VERSION,
        "commit_sha": _environment_value(root, "commit.sha"),
        "cli_version": _environment_value(root, "cli.version"),
        "os": os_name,
        "run_url": _run_url(),
        "passes": {name: _pass_entry(root, name) for name in PASSES},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="acceptance-jvm/build/acceptance")
    parser.add_argument("--os", dest="os_name", required=True, help="matrix OS label")
    args = parser.parse_args(argv)
    bundle = build_bundle(args.root, args.os_name)
    args.root.mkdir(parents=True, exist_ok=True)
    target = args.root / EVIDENCE_FILE
    target.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
