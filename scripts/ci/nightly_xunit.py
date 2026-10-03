#!/usr/bin/env python3
"""Name the failing tests in a nightly xunit report (#5583).

A red nightly job's terminal step only printed ``suite exited 1``, and the
escalation issue only said the suite failed again. The pytest log that names
the tests sits in an earlier step that stays green (``set +e``, #4212). This
module reads the xunit file that step already writes and renders it for the
three places an operator looks: the job summary, ``::error`` annotations on
the failing step, and the escalation issue.

A missing or unreadable report degrades to that exit-code message plus a
warning. It never decides whether the job is red.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

DISPLAY_CAP = 20
RECORD_CAP = 200

_COULD_NOT_READ = "Could not read the xunit report"
_NO_FAILURES = "No failing tests."
_NONE_LISTED = "The xunit report listed no failing tests."
_MARKER_RE = re.compile(r"<!-- nightly-failure-ids:(.*?)-->", re.DOTALL)
_ESCALATION_MARKER_START = "<!-- nightly-escalation-key:"
_SUMMARY_ENV = "GITHUB_STEP_SUMMARY"
_WARNING_TITLE = "Nightly xunit summary"
_HELPER_FAILED = "nightly xunit summary helper failed"


class XunitReportError(ValueError):
    """The report exists but is not xunit this renderer can read."""


@dataclass(frozen=True)
class FailedTest:
    """One failing or errored testcase."""

    test_id: str
    reason: str
    file: str
    line: str


@dataclass(frozen=True)
class XunitRead:
    """A parsed report, or a problem string when the file cannot be used.

    ``problem`` set means ``failures`` is empty and must not be recorded as a
    real empty failure set.
    """

    failures: tuple[FailedTest, ...]
    problem: str | None


def parse_xunit(text: str) -> tuple[FailedTest, ...]:
    """Return failing and errored testcases. Raises :class:`XunitReportError` on bad XML."""
    try:
        # The suite's own pytest junit file, written in this job. Not third-party XML.
        root = ET.fromstring(text)  # noqa: S314
    except ET.ParseError as exc:
        raise XunitReportError(f"xunit report is not valid XML: {exc}") from exc
    return tuple(_failed_test(case) for case in root.iter("testcase") if _is_failed(case))


def read_xunit(path: Path) -> XunitRead:
    """Read ``path``. A missing or unreadable file is a problem, not an exception."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        detail = exc.strerror or str(exc)
        return XunitRead((), f"{path} ({detail})")
    try:
        return XunitRead(parse_xunit(text), None)
    except XunitReportError as exc:
        return XunitRead((), str(exc))


def recorded_ids(text: str) -> tuple[str, ...] | None:
    """Return the failure ids stored in ``text``, or ``None`` when none were stored."""
    matches = _MARKER_RE.findall(text)
    if not matches:
        return None
    return tuple(unquote(token) for token in matches[-1].split())


def with_recorded_ids(body: str, test_ids: Sequence[str]) -> str:
    """Return ``body`` with one failure-id marker holding the first :data:`RECORD_CAP` ids."""
    marker = _format_marker(test_ids[:RECORD_CAP])
    stripped = _MARKER_RE.sub("", body)
    if _ESCALATION_MARKER_START in stripped:
        return stripped.replace(_ESCALATION_MARKER_START, f"{marker}\n{_ESCALATION_MARKER_START}", 1)
    return stripped.rstrip() + f"\n\n{marker}\n"


def summary_markdown(suite_key: str, read: XunitRead, log_step: str) -> str:
    """Job-summary markdown for one suite."""
    heading = f"### Nightly `{suite_key}`\n\n"
    if read.problem:
        return f"{heading}{_COULD_NOT_READ}: {read.problem}. The suite result is unchanged.\n"
    if not read.failures:
        return f"{heading}{_NO_FAILURES}\n"
    shown, extra = _capped(read.failures, DISPLAY_CAP)
    rows = ["| Test | First error |", "| --- | --- |"]
    rows.extend(f"| `{_cell(item.test_id)}` | {_cell(item.reason)} |" for item in shown)
    tail = f"\n\nand {extra} more not shown." if extra else ""
    return f"{heading}" + "\n".join(rows) + tail + f"\n\n{_log_pointer(log_step)}\n"


def plain_report(suite_key: str, read: XunitRead, log_step: str) -> str:
    """Text for the failing step's log, including the warning when the report is unusable."""
    if read.problem:
        return f"::warning title={_WARNING_TITLE}::{suite_key}: {_COULD_NOT_READ}: {read.problem}. The suite result is unchanged.\n"
    if not read.failures:
        return f"{suite_key}: no failing tests.\n"
    shown, extra = _capped(read.failures, DISPLAY_CAP)
    lines = [f"{suite_key}: {len(read.failures)} failing test(s). First {len(shown)}:"]
    lines.extend(f"- {item.test_id} — {item.reason}" for item in shown)
    if extra:
        lines.append(f"and {extra} more.")
    lines.append(_log_pointer(log_step))
    return "\n".join(lines) + "\n"


def annotation_lines(read: XunitRead) -> tuple[str, ...]:
    """``::error`` annotations, capped at :data:`DISPLAY_CAP`, then one ``N more`` line."""
    if read.problem or not read.failures:
        return ()
    shown, extra = _capped(read.failures, DISPLAY_CAP)
    lines = [_annotation(item) for item in shown]
    if extra:
        lines.append(f"::error::{extra} more failing tests; see the job summary")
    return tuple(lines)


def issue_evidence(read: XunitRead) -> str:
    """The failure section inserted into a new escalation issue. No id marker."""
    if read.problem:
        return f"{_COULD_NOT_READ}: {read.problem}. Failing tests are not listed.\n\n"
    return _visible_failures(read.failures) + _truncation_note(read.failures) + "\n\n"


def recurrence_evidence(previous_body: str, read: XunitRead) -> str:
    """The failure section appended to a recurrence comment, including the delta."""
    if read.problem:
        return f"\n\n{_COULD_NOT_READ}: {read.problem}. Failing tests are not listed.\n"
    current = tuple(item.test_id for item in read.failures)
    delta = delta_text(recorded_ids(previous_body), current)
    return "\n\n" + _visible_failures(read.failures) + "\n\n" + delta + _truncation_note(read.failures)


def delta_text(previous: tuple[str, ...] | None, current: Sequence[str]) -> str:
    """Say whether this failure set matches the previous recorded set."""
    if previous is None:
        return "The previous failure did not record test ids."
    previous_set = set(previous)
    current_set = set(current)
    if previous_set == current_set:
        return "Same failing tests as the previous recorded failure."
    parts: list[str] = []
    newly = [item for item in current if item not in previous_set]
    passed = [item for item in previous if item not in current_set]
    if newly:
        parts.append(_id_block("Newly failing", newly))
    if passed:
        parts.append(_id_block("Now passing", passed))
    return "\n\n".join(parts)


def _is_failed(case: ET.Element) -> bool:
    return case.find("failure") is not None or case.find("error") is not None


def _failed_test(case: ET.Element) -> FailedTest:
    test_id = _test_id(case)
    line = case.get("line") or ""
    return FailedTest(test_id=test_id, reason=_reason(case), file=_location(case, test_id), line=line if line.isdigit() else "")


def _test_id(case: ET.Element) -> str:
    name = (case.get("name") or "").strip()
    file = (case.get("file") or "").strip()
    classname = (case.get("classname") or "").strip()
    if "::" in name or "/" in name or name.endswith(".py"):
        return name
    if file and name:
        return f"{file}::{name}"
    if file:
        return file
    if classname and name:
        return f"{classname}::{name}"
    return name or classname or "(unnamed test)"


def _reason(case: ET.Element) -> str:
    for tag in ("failure", "error"):
        child = case.find(tag)
        if child is None:
            continue
        raw = child.get("message") or child.text or ""
        line = next((part.strip() for part in raw.splitlines() if part.strip()), "")
        return line or tag
    return "failed"


def _location(case: ET.Element, test_id: str) -> str:
    file = (case.get("file") or "").strip()
    if file:
        return file
    head = test_id.split("::", 1)[0]
    return head if head.endswith(".py") else ""


def _capped(items: Sequence[FailedTest], cap: int) -> tuple[tuple[FailedTest, ...], int]:
    shown = tuple(items[:cap])
    return shown, len(items) - len(shown)


def _visible_failures(failures: Sequence[FailedTest]) -> str:
    if not failures:
        return _NONE_LISTED
    shown, extra = _capped(failures, DISPLAY_CAP)
    lines = [f"Failed tests ({len(failures)}):", ""]
    lines.extend(f"- `{item.test_id}` — {item.reason}" for item in shown)
    if extra:
        lines.append(f"- and {extra} more")
    return "\n".join(lines)


def _id_block(heading: str, test_ids: Sequence[str]) -> str:
    shown = list(test_ids[:DISPLAY_CAP])
    extra = len(test_ids) - len(shown)
    lines = [f"{heading}:", ""]
    lines.extend(f"- `{item}`" for item in shown)
    if extra:
        lines.append(f"- and {extra} more")
    return "\n".join(lines)


def _truncation_note(failures: Sequence[FailedTest]) -> str:
    if len(failures) <= RECORD_CAP:
        return ""
    return f"\n\nThe recorded set keeps the first {RECORD_CAP} of {len(failures)} ids."


def _format_marker(test_ids: Sequence[str]) -> str:
    encoded = " ".join(quote(item, safe="").replace("-", "%2D") for item in test_ids)
    return f"<!-- nightly-failure-ids: {encoded} -->"


def _log_pointer(log_step: str) -> str:
    return f'Full pytest log: step "{log_step}".'


def _cell(value: str) -> str:
    return " ".join(value.replace("|", "/").replace("`", "'").split())


def _property(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(",", "%2C")


def _message(value: str) -> str:
    collapsed = " ".join(value.split()).replace("::", ": ")
    if len(collapsed) <= 180:
        return collapsed
    return collapsed[:179] + "…"


def _annotation(item: FailedTest) -> str:
    props: list[str] = []
    if item.file:
        props.append(f"file={_property(item.file)}")
    if item.line:
        props.append(f"line={item.line}")
    props.append(f"title={_property(item.test_id)}")
    return "::error " + ",".join(props) + "::" + _message(item.reason)


def _append_summary(text: str) -> None:
    path = os.environ.get(_SUMMARY_ENV)
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")


def _summarize(suite_key: str, xunit: str, log_step: str) -> None:
    read = read_xunit(Path(xunit))
    sys.stdout.write(plain_report(suite_key, read, log_step))
    for line in annotation_lines(read):
        print(line)
    _append_summary(summary_markdown(suite_key, read, log_step))


def main(argv: Sequence[str] | None = None) -> int:
    """Render one report. Always exits 0 so the suite exit stays the job result."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("command", choices=("summarize",))
    parser.add_argument("--suite-key", required=True)
    parser.add_argument("--xunit", required=True)
    parser.add_argument("--log-step", required=True, help="name of the step that holds the pytest log")
    args = parser.parse_args(argv)
    try:
        _summarize(args.suite_key, args.xunit, args.log_step)
    except OSError as exc:
        print(f"::warning title={_WARNING_TITLE}::{_HELPER_FAILED}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
