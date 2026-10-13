#!/usr/bin/env python3
"""The two non-Gradle guards of ``.github/workflows/mission-status-api.yml`` (mission-status-read-api-overview).

``native-tag-floor``
    Counts the executed ``<testcase>`` entries (a skipped one is not executed) in the JUnit XML that the native test binary wrote
    and fails below the committed floor, so a native leg that selected no test cannot read as green.
``digests``
    The cross-leg comparison of the gate job: exactly four ``digest-*.json`` files, named for exactly linux-x64, linux-arm64,
    macos-arm64 and windows-x64, each ``{os, arch, requestCount, bodyCount, sha256}``, with equal ``requestCount`` of at least
    the floor, a ``bodyCount`` above zero and four equal ``sha256`` values (the digest covers the response bodies only).

Standard library only; it imports nothing from the repository, so it runs by path from any working directory.
Exit codes: 0 the check passed, 1 the check failed, 2 the check could not be done (missing directory, unusable arguments).
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_CANNOT = 2

EXPECTED_TARGETS = ("linux-x64", "linux-arm64", "macos-arm64", "windows-x64")
DIGEST_FIELDS = ("os", "arch", "requestCount", "bodyCount", "sha256")
CMD_FLOOR = "native-tag-floor"
CMD_DIGESTS = "digests"


def _say(message: str) -> None:
    print(message, flush=True)


def _count_executed(path: Path) -> int:
    """Executed (not skipped) test cases of one JUnit XML file; raises ``ET.ParseError`` for malformed XML."""
    root = ET.parse(path).getroot()  # noqa: S314 (CI-produced JUnit XML, never user input)
    return sum(1 for case in root.iter("testcase") if case.find("skipped") is None)


def native_tag_floor(junit_dir: Path, floor: int) -> int:
    if floor < 1:
        _say(f"native-tag-floor: the floor must be at least 1, got {floor}")
        return EXIT_CANNOT
    if not junit_dir.is_dir():
        _say(f"native-tag-floor: not a directory: {junit_dir}")
        return EXIT_CANNOT
    files = sorted(junit_dir.rglob("*.xml"))
    if not files:
        _say(f"native-tag-floor: no JUnit XML under {junit_dir}; the native test binary ran nothing (floor {floor})")
        return EXIT_FAIL
    total = 0
    for path in files:
        try:
            total += _count_executed(path)
        except ET.ParseError as error:
            _say(f"native-tag-floor: malformed XML {path.name}: {error}")
            return EXIT_FAIL
    _say(f"native-tag-floor: {total} executed test(s) in {len(files)} file(s); floor {floor}")
    if total < floor:
        _say(f"native-tag-floor: FAILED, {total} executed is below the floor of {floor}")
        return EXIT_FAIL
    return EXIT_PASS


def _load_digest(path: Path) -> tuple[dict[str, object] | None, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return None, f"{path.name}: unreadable or malformed JSON ({error})"
    if not isinstance(data, dict):
        return None, f"{path.name}: not a JSON object"
    missing = [name for name in DIGEST_FIELDS if name not in data]
    if missing:
        return None, f"{path.name}: missing field(s) {', '.join(missing)}"
    return data, ""


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _record_problems(name: str, record: dict[str, object], request_floor: int) -> list[str]:
    problems: list[str] = []
    if f"{record['os']}-{record['arch']}" != name:
        problems.append(f"{name}: content names {record['os']}-{record['arch']}, not {name}")
    requests, bodies = record["requestCount"], record["bodyCount"]
    if not _is_count(requests) or requests < request_floor:  # type: ignore[operator]
        problems.append(f"{name}: requestCount {requests!r} is below the floor of {request_floor}")
    if not _is_count(bodies) or bodies < 1:  # type: ignore[operator]
        problems.append(f"{name}: bodyCount {bodies!r} must be above zero")
    if not isinstance(record["sha256"], str) or not record["sha256"]:
        problems.append(f"{name}: sha256 is not a non-empty string")
    return problems


def _comparison_problems(records: dict[str, dict[str, object]]) -> list[str]:
    problems: list[str] = []
    if len({record["requestCount"] for record in records.values()}) > 1:
        problems.append("requestCount differs between legs")
    if len({record["sha256"] for record in records.values()}) > 1:
        problems.append("sha256 differs between legs")
    return problems


def digests(directory: Path, expected_count: int, request_floor: int) -> int:
    if expected_count != len(EXPECTED_TARGETS):
        _say(f"digests: --expected-count must be {len(EXPECTED_TARGETS)}, got {expected_count}")
        return EXIT_CANNOT
    if not directory.is_dir():
        _say(f"digests: not a directory: {directory}")
        return EXIT_CANNOT
    files = sorted(directory.rglob("digest-*.json"))
    names = [path.stem.removeprefix("digest-") for path in files]
    problems: list[str] = []
    if len(files) != expected_count:
        problems.append(f"expected exactly {expected_count} digest files, found {len(files)}: {', '.join(names) or 'none'}")
    if sorted(names) != sorted(EXPECTED_TARGETS):
        problems.append(f"digest names {sorted(names)} are not exactly {sorted(EXPECTED_TARGETS)}")
    records: dict[str, dict[str, object]] = {}
    for path, name in zip(files, names, strict=True):
        record, problem = _load_digest(path)
        if record is None:
            problems.append(problem)
            continue
        records[name] = record
        problems.extend(_record_problems(name, record, request_floor))
    if len(records) > 1:
        problems.extend(_comparison_problems(records))
    if not problems:
        _say(f"digests: {len(records)} legs agree ({next(iter(records.values()))['sha256']})")
        return EXIT_PASS
    for problem in problems:
        _say(f"digests: FAILED, {problem}")
    for name in sorted(records):
        _say(f"digests: {name} sha256={records[name]['sha256']} requestCount={records[name]['requestCount']} bodyCount={records[name]['bodyCount']}")
    return EXIT_FAIL


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mission Status API workflow guards.")
    sub = parser.add_subparsers(dest="command", required=True)
    floor = sub.add_parser(CMD_FLOOR, help="fail when the native test binary executed fewer tests than the floor")
    floor.add_argument("--junit-dir", type=Path, required=True)
    floor.add_argument("--floor", type=int, required=True)
    compare = sub.add_parser(CMD_DIGESTS, help="compare the four per-leg digest files")
    compare.add_argument("--dir", type=Path, required=True)
    compare.add_argument("--expected-count", type=int, required=True)
    compare.add_argument("--request-floor", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == CMD_FLOOR:
        return native_tag_floor(args.junit_dir, args.floor)
    return digests(args.dir, args.expected_count, args.request_floor)


if __name__ == "__main__":
    sys.exit(main())
