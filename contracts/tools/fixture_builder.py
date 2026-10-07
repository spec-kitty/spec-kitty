"""Assemble leak-class planted fixtures at run time (plan D-P11, spec FR-012, FR-015, FR-021).

A planted leak (a host path, an e-mail address, a secret or token, a forbidden property name, a
malformed artifact path) must never be committed: the text-level scan has no exempt directory. This
module therefore writes each plant into a temporary root from string fragments, next to a clean control
on the same root, and no literal leak-shaped string appears in this source (a unit test scans it).

There are 34 kinds in four groups: the eight original kinds; ten ``strict-<name>`` kinds, a leading-tilde
host path planted under one of the strict-class names added for the Mission status contract 1.1; twelve
``artifact-path-*`` kinds, each one malformed ``path`` entry of the artifact-path rule, and the thirteenth, ``artifact-path-reference``,
its ``artifactPath`` key; and three regression controls (``content-host-path-and-email``, ``credential-in-content``,
``credential-in-title``) that pass on a scanner without the artifact-path class and guard it against a
mask that is too wide.

``build(kind, out_dir)`` writes ``<out_dir>/planted/examples/Control.clean.yaml`` and
``<out_dir>/planted/examples/Planted.planted.yaml`` and returns a :class:`BuiltFixture` that names the
planted field (a dotted key path, ``entries[0].path`` for a nested one) and the codes ``leak_scan`` must
report for it. A kind is a :class:`Plant`: a document fragment deep-merged into the planted document and
a clean fragment deep-merged into the control (mappings merge recursively, lists are replaced). The control
holds values of both field classes, the two real pass controls of spec D-14 included; the control of an
artifact-path kind also holds the legitimate odd names (a ``home/<x>/`` segment, a space, an accented
letter, an at sign), so a scan of the root can only fail on the plant.

Command line: ``python contracts/tools/fixture_builder.py --out DIR [--kind KIND]`` builds every
kind (or one) under ``DIR/<kind>/`` and prints ``<kind> <expected codes>`` per kind. Exit 0 built,
2 an unknown kind or an unusable output directory. Standard library plus PyYAML; imports nothing
from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

import yaml

_OLD_KINDS: tuple[str, ...] = (
    "host-path-strict",
    "host-path-human",
    "email",
    "email-dotless",
    "github-token",
    "aws-key",
    "private-key",
    "forbidden-property",
)
# The strict-class names added for the Mission status contract 1.1 and the health, drift and ops slice (title stays human text).
_NEW_STRICT_NAMES: tuple[str, ...] = (
    "id",
    "laneId",
    "laneBranch",
    "planningBranch",
    "pattern",
    "feedbackReference",
    "reviewer",
    "kind",
    "mediaType",
    "changeState",
    "specKittyVersion",
    "currentBranch",
    "profileId",
    "action",
    "invocationId",
    "sourceCode",
)
_STRICT_KIND_PREFIX = "strict-"
_ARTIFACT_PATH_KIND_PREFIX = "artifact-path-"
_ARTIFACT_PATH_FORMS: tuple[str, ...] = (
    "empty",
    "too-long",
    "absolute",
    "tilde",
    "drive-letter",
    "backslash",
    "nul",
    "line-break",
    "empty-segment",
    "trailing-slash",
    "dot-segment",
    "dotdot-segment",
)
_REFERENCE_KIND = "artifact-path-reference"
_REGRESSION_KINDS: tuple[str, ...] = ("content-host-path-and-email", "credential-in-content", "credential-in-title")
CODE_ARTIFACT_PATH = "ARTIFACT_PATH_MALFORMED"
KINDS: tuple[str, ...] = (
    *_OLD_KINDS,
    *(_STRICT_KIND_PREFIX + name for name in _NEW_STRICT_NAMES),
    *(_ARTIFACT_PATH_KIND_PREFIX + form for form in _ARTIFACT_PATH_FORMS),
    _REFERENCE_KIND,
    *_REGRESSION_KINDS,
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
    *_NEW_STRICT_NAMES,
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


@dataclass(frozen=True)
class Plant:
    """One kind: the fragment merged into the planted document, the clean one merged into the control, the field and the codes."""

    fragment: dict[str, Any]
    field: str
    codes: tuple[str, ...]
    control_fragment: dict[str, Any] = dataclass_field(default_factory=dict)


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


def _artifact_path_value(form: str) -> str:
    """One malformed artifact path of ``form``, built from fragments."""
    values = {
        "empty": "",
        "too-long": "a" * 513,
        "absolute": _SLASH + "srv" + _SLASH + "notes.md",
        "tilde": "~" + _SLASH + "notes.md",
        "drive-letter": "C:" + _SLASH + "notes.md",
        "backslash": "dir" + chr(92) + "notes.md",
        "nul": "dir" + chr(0) + "notes.md",
        "line-break": "dir" + chr(10) + "notes.md",
        "empty-segment": "dir" + _SLASH * 2 + "notes.md",
        "trailing-slash": "dir" + _SLASH + "notes" + _SLASH,
        "dot-segment": "dir" + _SLASH + "." + _SLASH + "notes.md",
        "dotdot-segment": "dir" + _SLASH + ".." + _SLASH + "notes.md",
    }
    return values[form]


def _legitimate_odd_names() -> list[str]:
    """Names the artifact-path rule admits and the scan must not flag: a home segment, a space, an accented letter, an at sign."""
    return ["home" + _SLASH + "someone" + _SLASH + "notes.md", "with space.md", "caf" + chr(233) + ".md", "icon" + _AT + "2x.png"]


def _entries(key: str, values: list[str]) -> dict[str, Any]:
    return {"entries": [{key: value} for value in values]}


def _artifact_path_plant(kind: str) -> Plant:
    key = "artifactPath" if kind == _REFERENCE_KIND else "path"
    form = "dotdot-segment" if kind == _REFERENCE_KIND else kind.removeprefix(_ARTIFACT_PATH_KIND_PREFIX)
    return Plant(_entries(key, [_artifact_path_value(form)]), f"entries[0].{key}", (CODE_ARTIFACT_PATH,), _entries(key, _legitimate_odd_names()))


def _strict_plant(kind: str) -> Plant:
    name = kind.removeprefix(_STRICT_KIND_PREFIX)
    return Plant({name: "~" + _SLASH + "work" + _SLASH + "notes"}, name, ("HOST_PATH",), {name: "clean-value"})


def _single(name: str, value: str, codes: tuple[str, ...]) -> Plant:
    return Plant({name: value}, name, codes)


def _plant(kind: str) -> Plant:
    """The fragment, control fragment, field name and codes the scan must report for ``kind``."""
    plants = {
        "host-path-strict": lambda: _single("targetBranch", "~" + _SLASH + "work" + _SLASH + "notes", ("HOST_PATH",)),
        "host-path-human": lambda: _single("title", "Fix the notes under " + _home_path("project"), ("HOST_PATH",)),
        "email": lambda: _single("friendlyName", "Contact " + _email_address() + " about this", ("EMAIL",)),
        "email-dotless": lambda: _single("friendlyName", "Contact " + _dotless_email_address() + " about this", ("EMAIL",)),
        "github-token": lambda: _single("reason", "Use the token " + _github_token() + " here", ("SECRET",)),
        "aws-key": lambda: _single("reason", "The access key is " + _aws_access_key() + " today", ("SECRET",)),
        "private-key": lambda: _single("reason", "Paste " + _private_key_header() + " into the file", ("SECRET",)),
        "forbidden-property": lambda: _single(_forbidden_name(), "an ordinary relative value", ("FORBIDDEN_PROPERTY_NAME",)),
        "content-host-path-and-email": lambda: _single("content", "See " + _home_path("notes") + " or write " + _email_address(), ("HOST_PATH", "EMAIL")),
        "credential-in-content": lambda: _single("content", "Use the token " + _github_token() + " here", ("SECRET",)),
        "credential-in-title": lambda: _single("title", "Use the token " + _github_token() + " here", ("SECRET",)),
    }
    if kind in plants:
        return plants[kind]()
    if kind.startswith(_STRICT_KIND_PREFIX) and kind in KINDS:
        return _strict_plant(kind)
    if kind.startswith(_ARTIFACT_PATH_KIND_PREFIX) and kind in KINDS:
        return _artifact_path_plant(kind)
    raise ValueError(f"unknown fixture kind {kind!r}; expected one of {KINDS}")


def _merge(base: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """``fragment`` over ``base``: mappings merge recursively, every other value (a list included) replaces."""
    merged = copy.deepcopy(base)
    for key, value in fragment.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _dump(document: dict[str, Any]) -> str:
    return yaml.safe_dump(document, sort_keys=True)


def build(kind: str, out_dir: str | Path) -> BuiltFixture:
    """Write the control and the plant of ``kind`` under ``out_dir`` and describe them."""
    plant = _plant(kind)
    root = Path(out_dir)
    examples = root.joinpath(*EXAMPLES_PATH)
    examples.mkdir(parents=True, exist_ok=True)
    (examples / CONTROL_FILE).write_text(_dump(_merge(_control(), plant.control_fragment)), encoding="utf-8")
    base = _control() if kind != "forbidden-property" else {}
    (examples / PLANTED_FILE).write_text(_dump(_merge(base, plant.fragment)), encoding="utf-8")
    return BuiltFixture(kind=kind, root=root, field=plant.field, expected_codes=plant.codes)


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
