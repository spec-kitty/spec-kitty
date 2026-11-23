"""Reject missing statement evidence before scoring an immutable critical diff."""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import tokenize
from pathlib import Path
from typing import cast

from coverage import Coverage
from coverage.parser import PythonParser
from defusedxml.ElementTree import parse  # type: ignore[import-untyped]
from diff_cover.diff_reporter import GitDiffReporter  # type: ignore[import-untyped]
from diff_cover.git_diff import GitDiffFileTool  # type: ignore[import-untyped]
from diff_cover.git_path import GitPathTool  # type: ignore[import-untyped]
from diff_cover.violationsreporters.violations_reporter import XmlCoverageReporter  # type: ignore[import-untyped]

# #7789: an empty scored diff applies no gate. Say so instead of claiming evidence.
GATE_NOT_APPLIED = "diff-cover gate not applied: no changed executable critical-path statements"
EVIDENCE_PRESENT = "ci-aggregate: changed executable critical statements have coverage evidence"


def report_scored(output: Path, normalized: list[str]) -> None:
    """Write the scoring patch and report whether the gate has anything to score.

    diff-cover passes an empty patch with "No lines with coverage information",
    so an empty ``normalized`` is reported as a notice and a step-summary line,
    never as coverage evidence.
    """
    output.write_text("".join(normalized), encoding="utf-8")
    if normalized:
        print(EVIDENCE_PRESENT)
        return
    print(f"::notice::{GATE_NOT_APPLIED}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(f"{GATE_NOT_APPLIED}\n")


def statement_lines(text: str, changed: set[int], exclusions: list[str]) -> set[int]:
    """Map changed code tokens to coverage's unique statement origins."""
    parser = PythonParser(text=text, exclude="|".join(exclusions))
    parser.parse_source()
    ignored = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER, tokenize.ENCODING}
    code_lines = {
        line for token in tokenize.generate_tokens(io.StringIO(text).readline) if token.type not in ignored for line in range(token.start[0], token.end[0] + 1)
    }
    return parser.first_lines(changed & code_lines) & parser.statements


def validate(diff_file: Path, sources_file: Path, reports: list[Path], exclude: list[str], output: Path) -> None:
    """Use the scorer's path/line readers and coverage's Python statement parser.

    Source bytes come from the already validated immutable Git tree, never from
    a PR checkout. Parsing does not import or execute them. A genuine empty
    executable comparison remains valid; a missing report cannot create one.
    """
    GitPathTool.set_cwd(str(Path.cwd()))
    diff = GitDiffReporter(git_diff=GitDiffFileTool(str(diff_file)), exclude=exclude)
    coverage = XmlCoverageReporter([parse(report) for report in reports])
    sources = json.loads(sources_file.read_text(encoding="utf-8"))
    # The canonical producer has no report exclusion overrides; use coverage's
    # defaults (including pragmas), never an ambient checkout rc file.
    exclusions = cast(list[str], Coverage(config_file=False).get_option("report:exclude_lines"))
    missing: dict[str, list[int]] = {}
    normalized: list[str] = []
    for path in diff.src_paths_changed():
        changed = set(diff.lines_changed(path))
        if not changed or not path.endswith(".py"):
            continue
        raw = base64.b64decode(sources[path], validate=True)
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        text = raw.decode(encoding)
        statements = statement_lines(text, changed, exclusions)
        absent = statements - set(coverage.measured_lines(path) or ())
        if absent:
            missing[path] = sorted(absent)
        if statements:
            # This is a scoring representation, not an applyable tree patch.
            # Keep raw full/critical diffs intact. One hunk per unique origin
            # lets the unchanged diff-cover engine score multiline statements
            # using the producer's original XML line numbers and hit union.
            before, after = (json.dumps(prefix + path, ensure_ascii=False) for prefix in ("a/", "b/"))
            normalized.extend([f"diff --git {before} {after}\n", f"--- {before}\n", f"+++ {after}\n"])
            source_lines = text.splitlines()
            for line in sorted(statements):
                normalized.extend([f"@@ -0,0 +{line},1 @@\n", f"+{source_lines[line - 1]}\n"])
    if missing:
        raise ValueError(f"missing coverage evidence for changed executable lines: {missing}")
    report_scored(output, normalized)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diff-file", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--exclude", nargs="*", default=[])
    args = parser.parse_args()
    validate(args.diff_file, args.sources, args.reports, args.exclude, args.output)


if __name__ == "__main__":
    main()
