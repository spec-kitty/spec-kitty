"""The golden generator of the artifact conformance gate (mission mission-status-artifact-reads, #957).

The Java service (``services/mission-status-api``) serves ``listArtifacts`` and ``getArtifactContent`` and must answer exactly as the
Python reference reader (``_mission_status_artifacts.py``) does. The shared cases live in
``services/mission-status-api/src/test/resources/artifact-conformance/cases.json``: each case is a project tree described as data
(text, base64, a repeated byte, parts joined at materialization time, a generated run of files, a directory or a symbolic link) and a
list of requests. This module materializes each tree into a temporary directory, runs the reference over every request and writes
what it answers to ``golden.json`` in the same directory. It is not a second oracle: every answer is the reference's own.

``modifiedAt`` depends on the host that materialized the tree, so it is replaced by :data:`MODIFIED_AT_MARKER`; the Java side checks
its format and compares the marker. A served content longer than :data:`LONG_CONTENT` characters is replaced by the SHA-256 of its
UTF-8 bytes, so the golden file stays small; the Java side computes the same digest.

Run from the repository root::

    .venv/bin/python -m tests.contract._mission_status_artifact_goldens --write
    .venv/bin/python -m tests.contract._mission_status_artifact_goldens --check
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tests.contract import _mission_status_artifacts as reference
from tests.contract._mission_status_payloads import load_contract_tools

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFORMANCE_DIR = REPO_ROOT / "services" / "mission-status-api" / "src" / "test" / "resources" / "artifact-conformance"
CASES_FILE = CONFORMANCE_DIR / "cases.json"
GOLDEN_FILE = CONFORMANCE_DIR / "golden.json"
MODIFIED_AT_MARKER = "<modifiedAt>"
LONG_CONTENT = 4096
OP_LIST = "list"
OP_CONTENT = "content"


def load_cases(path: Path = CASES_FILE) -> dict[str, Any]:
    """The case document."""
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def entry_bytes(entry: Mapping[str, Any]) -> bytes:
    """The bytes of one file entry of a tree (exactly one of ``text``, ``base64``, ``repeat`` or ``parts``)."""
    if "text" in entry:
        return str(entry["text"]).encode("utf-8")
    if "base64" in entry:
        return base64.b64decode(str(entry["base64"]))
    if "repeat" in entry:
        repeat = entry["repeat"]
        return bytes([int(repeat["byte"])]) * int(repeat["count"])
    if "parts" in entry:
        return "".join(str(part) for part in entry["parts"]).encode("utf-8")
    raise ValueError(f"a tree entry has no content: {sorted(entry)}")


def materialize(root: Path, tree: list[Mapping[str, Any]]) -> None:
    """Writes one case tree below ``root``: files, generated runs, directories and symbolic links (relative targets, as written)."""
    for entry in tree:
        target = root / str(entry["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if entry.get("dir"):
            target.mkdir(parents=True, exist_ok=True)
        elif "symlink" in entry:
            os.symlink(str(entry["symlink"]), target)
        elif "generate" in entry:
            spec = entry["generate"]
            target.mkdir(parents=True, exist_ok=True)
            for index in range(int(spec["count"])):
                (target / (str(spec["nameFormat"]) % index)).write_bytes(str(spec["text"]).encode("utf-8"))
        else:
            target.write_bytes(entry_bytes(entry))


def content_marker(content: str) -> str:
    """The stand-in of a long served content: the SHA-256 of its UTF-8 bytes."""
    # A body checksum compared byte for byte with the Java service: charter.hasher normalizes BOM and newlines, which this must not.
    return "<sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest() + ">"  # noqa: TID251


def masked(body: dict[str, Any]) -> dict[str, Any]:
    """The body with a long content replaced by its digest and every listing entry's ``modifiedAt`` by the marker."""
    if isinstance(body.get("content"), str) and len(body["content"]) > LONG_CONTENT:
        return {**body, "content": content_marker(body["content"])}
    if "entries" not in body:
        return body
    entries = [{**entry, "modifiedAt": MODIFIED_AT_MARKER} for entry in body["entries"]]
    return {**body, "entries": entries}


def answer(ctx: reference.ReaderContext, request: Mapping[str, Any], default_mission: str) -> dict[str, Any]:
    """The reference's status and body for one request."""
    mission_id = str(request.get("missionId", default_mission))
    if request["op"] == OP_LIST:
        outcome = reference.list_artifacts(ctx, mission_id)
    elif request["op"] == OP_CONTENT:
        outcome = reference.read_content(ctx, mission_id, [str(path) for path in request["paths"]])
    else:
        raise ValueError(f"unknown op {request['op']!r}")
    return {"request": dict(request), "status": outcome.status, "body": masked(outcome.body)}


@contextmanager
def case_root() -> Iterator[Path]:
    """A fresh temporary project root."""
    with tempfile.TemporaryDirectory(prefix="artifact-conformance-") as raw:
        yield Path(raw)


def build_goldens(cases: Mapping[str, Any]) -> dict[str, Any]:
    """Every case's answers, by case name, from the reference reader."""
    mp = pytest.MonkeyPatch()
    try:
        tools = load_contract_tools(mp, REPO_ROOT)
        goldens: dict[str, Any] = {}
        for case in cases["cases"]:
            with case_root() as root:
                materialize(root, case["tree"])
                ctx = reference.ReaderContext(repo_root=root, tools=tools)
                goldens[case["name"]] = [answer(ctx, request, str(cases["missionId"])) for request in case["requests"]]
        return {"description": "Written by tests/contract/_mission_status_artifact_goldens.py from the Python reference reader; do not edit.", "cases": goldens}
    finally:
        mp.undo()


def render(goldens: Mapping[str, Any]) -> str:
    """The one text form of the golden file: sorted keys, one-space indent, UTF-8, a final newline."""
    return json.dumps(goldens, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write or check the artifact conformance goldens.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write golden.json")
    mode.add_argument("--check", action="store_true", help="compare golden.json with the reference and write nothing")
    args = parser.parse_args(argv)
    text = render(build_goldens(load_cases()))
    if args.write:
        GOLDEN_FILE.write_text(text, encoding="utf-8")
        return 0
    current = GOLDEN_FILE.read_text(encoding="utf-8") if GOLDEN_FILE.exists() else ""
    if current != text:
        sys.stderr.write("golden.json is not what the reference answers; run --write\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
