"""Assemble leak-class planted fixtures at run time (plan D-P11, spec FR-012, FR-021).

A planted leak (a host path, an e-mail address, a secret or token, a forbidden property name) must never be
committed: the text-level scan has no exempt directory. This module therefore writes each
plant into a temporary root from string fragments, next to a clean control on the same root,
and no literal leak-shaped string appears in this source (a unit test scans it).

``build(kind, out_dir)`` writes ``<out_dir>/planted/examples/Control.clean.yaml`` and
``<out_dir>/planted/examples/Planted.<kind>.yaml`` and returns a :class:`BuiltFixture` that
names the planted field and the codes ``leak_scan`` must report for it. The control holds
values of both field classes, the two real pass controls of spec D-14 included, so a scan of
the root can only fail on the plant.

Command line: ``python contracts/tools/fixture_builder.py --out DIR [--kind KIND]`` builds every
kind (or one) under ``DIR/<kind>/`` and prints ``<kind> <expected codes>`` per kind. Exit 0 built,
2 an unknown kind or an unusable output directory. Standard library plus PyYAML; imports nothing
from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

KINDS: tuple[str, ...] = (
    "host-path-strict",
    "host-path-human",
    "email",
    "email-dotless",
    "github-token",
    "aws-key",
    "private-key",
    "forbidden-property",
)
CONTROL_FILE = "Control.clean.yaml"
PLANTED_FILE = "Planted.planted.yaml"
EXAMPLES_PATH = ("planted", "examples")

# Fields whose string values are identifiers, handles and path-like values (spec D-14, strict class).
STRICT_FIELDS: tuple[str, ...] = (
    "missionId",
    "mid8",
    "slug",
    "wpId",
    "targetBranch",
    "mergeTargetBranch",
    "missionType",
    "eventType",
    "dependencies",
    "ownedFiles",
    "requirementRefs",
    "trackerRefs",
    "tool",
    "role",
    "profile",
    "model",
)

_SLASH = chr(47)
_AT = chr(64)


@dataclass(frozen=True)
class BuiltFixture:
    """One built root: where it is, which field carries the plant and which codes it must raise."""

    kind: str
    root: Path
    field: str
    expected_codes: tuple[str, ...]


def _home_path(tail: str) -> str:
    return _SLASH + "home" + _SLASH + "someone" + _SLASH + tail


def _email_address() -> str:
    return "someone" + _AT + "example.invalid"


def _dotless_email_address() -> str:
    return "someone" + _AT + "localhost"


def _github_token() -> str:
    return "gh" + "p_" + "a1B2c3D4e5F6g7H8i9J0" * 2


def _aws_access_key() -> str:
    return "AK" + "IA" + "ABCDEFGH" + "IJKLMNOP"


def _private_key_header() -> str:
    return "-" * 5 + "BEGIN " + "RSA " + "PRIVATE" + " KEY" + "-" * 5


def _forbidden_name() -> str:
    return "feedback" + "Path"


def _control() -> dict[str, str]:
    return {
        "missionId": "01JZAB3C4D5E6F7G8H9JKMNPQR",
        "slug": "example-mission-01JZAB3C",
        "targetBranch": "main",
        "friendlyName": "~/.kittify Runtime Centralization",
        "title": _SLASH + "tmp burn-down: sync",
        "reason": "Nothing sensitive in this sentence.",
    }


def _plant(kind: str) -> tuple[str, str, tuple[str, ...]]:
    """The field name, its planted value and the codes the scan must report."""
    if kind == "host-path-strict":
        return "targetBranch", "~" + _SLASH + "work" + _SLASH + "notes", ("HOST_PATH",)
    if kind == "host-path-human":
        return "title", "Fix the notes under " + _home_path("project"), ("HOST_PATH",)
    if kind == "email":
        return "friendlyName", "Contact " + _email_address() + " about this", ("EMAIL",)
    if kind == "email-dotless":
        return "friendlyName", "Contact " + _dotless_email_address() + " about this", ("EMAIL",)
    if kind == "github-token":
        return "reason", "Use the token " + _github_token() + " here", ("SECRET",)
    if kind == "aws-key":
        return "reason", "The access key is " + _aws_access_key() + " today", ("SECRET",)
    if kind == "private-key":
        return "reason", "Paste " + _private_key_header() + " into the file", ("SECRET",)
    if kind == "forbidden-property":
        return _forbidden_name(), "an ordinary relative value", ("FORBIDDEN_PROPERTY_NAME",)
    raise ValueError(f"unknown fixture kind {kind!r}; expected one of {KINDS}")


def build(kind: str, out_dir: str | Path) -> BuiltFixture:
    """Write the control and the plant of ``kind`` under ``out_dir`` and describe them."""
    field_name, value, codes = _plant(kind)
    root = Path(out_dir)
    examples = root.joinpath(*EXAMPLES_PATH)
    examples.mkdir(parents=True, exist_ok=True)
    (examples / CONTROL_FILE).write_text(yaml.safe_dump(_control(), sort_keys=True), encoding="utf-8")
    planted = _control() if kind != "forbidden-property" else {}
    planted[field_name] = value
    (examples / PLANTED_FILE).write_text(yaml.safe_dump(planted, sort_keys=True), encoding="utf-8")
    return BuiltFixture(kind=kind, root=root, field=field_name, expected_codes=codes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build leak-class planted fixtures at run time.")
    parser.add_argument("--out", required=True, help="directory to build under; each kind gets a subdirectory")
    parser.add_argument("--kind", action="append", default=[], help="build only this kind (repeatable)")
    arguments = parser.parse_args(argv)
    kinds = tuple(arguments.kind) or KINDS
    unknown = [kind for kind in kinds if kind not in KINDS]
    if unknown:
        print(f"CONTRACT-CHECK fixture_builder: UNKNOWN_KIND: {', '.join(unknown)}; expected one of {', '.join(KINDS)}")
        return 2
    for kind in kinds:
        built = build(kind, Path(arguments.out) / kind)
        print(f"{kind} {' '.join(built.expected_codes)} {built.root}")
    print(f"counts: kinds={len(kinds)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
