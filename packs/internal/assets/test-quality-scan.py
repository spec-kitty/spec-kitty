#!/usr/bin/env python3
"""Static test-quality triage for a pytest corpus: rank files for squad review.

Maintainer tooling for the ``test-suite-quality-assessment`` procedure. It runs no
tests. It parses every test module with ``ast``, flags weak-oracle and
test-smell patterns per test function, optionally attaches git provenance
(when the file was added, when it was last touched, which commit added it), and
writes a ranked worklist per domain so review squads read the worst files first.

The flags are heuristics, not verdicts. A flagged test is a candidate for a
human or agent read against the Test Desiderata; an unflagged test is not
proven good. Codes map to the review rubric in the procedure:

    no-assertion         R1 vacuous: no assert, no raises, no assert-like call
    weak-only-assert     R1 vacuous: the only assert is ``True`` or ``x is not None``
    type-only-assert     R1 vacuous: the only assert is isinstance/callable/hasattr
    broad-raises         R1 vacuous: ``pytest.raises(Exception)``
    over-mocking         R2 over-mock: four or more patches/mocks in one test
    interaction-assert   R3 implementation-coupled: asserts on mock calls
    private-attr         R3 implementation-coupled: three or more private attributes
    literal-source-scan  R4 literal scan: reads source text and asserts substrings
    line-number-pin      R6 line pin: asserts a ``file.py:NN`` location
    fake-short-ulid      R7 fabricated data: a mission_id that is not a ULID
    long-test            R8 multi-behaviour: more than 80 lines
    many-asserts         R8 multi-behaviour: fifteen or more asserts
    sleep / wallclock    R9 non-deterministic: real sleeps or unfrozen clocks
    skip-or-xfail        a skip or xfail that is not a platform/tool guard
    vague-name           the name does not say what behaviour is promised
    provenance-tokens    development-assist hint: WP/FR/T-ids or issue numbers
                         in the test name or docstring

Usage (from the repository root; the asset resolves through the doctrine layer)::

    python "$(spec-kitty doctrine asset path test-quality-scan)" \
        --out work/test-quality/$(date +%F)

    # one domain only, or only tests new/changed since a revision:
    python "$(spec-kitty doctrine asset path test-quality-scan)" --paths tests/status
    python "$(spec-kitty doctrine asset path test-quality-scan)" --since origin/main~50

Outputs, all under ``--out``:

    tests.json          one row per flagged test (file, line, name, flags, score)
    files.json          one row per file (domain, score, flag counts, git provenance)
    summary.md          per-domain totals and the top-ranked files
    ledger/<domain>.md  a review checklist per domain; never overwritten, so a
                        squad run can be resumed where it stopped

Standard library only. Python 3.11+.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

#: Weight of each flag code in a file's triage score. Vacuous oracles weigh the
#: most: they pass on a broken product. Style-level smells weigh the least.
WEIGHTS: dict[str, int] = {
    "no-assertion": 5,
    "weak-only-assert": 4,
    "type-only-assert": 3,
    "broad-raises": 3,
    "literal-source-scan": 3,
    "line-number-pin": 3,
    "over-mocking": 2,
    "private-attr": 2,
    "fake-short-ulid": 2,
    "sleep": 2,
    "wallclock": 2,
    "interaction-assert": 1,
    "skip-or-xfail": 1,
    "long-test": 1,
    "many-asserts": 1,
    "vague-name": 1,
    "provenance-tokens": 1,
}

#: Domains this large are split one level deeper so a squad gets a readable slice.
DEEP_DOMAINS = frozenset({"specify_cli"})

_ASSERT_LIKE_CALL = re.compile(r"assert_|\.assert|expect|check_|_assert|verify")
_MOCK_CALL = re.compile(r"(^|\.)(patch|patch\.object|MagicMock|Mock|AsyncMock|create_autospec)$")
_INTERNAL_TARGET = re.compile(r"(specify_cli|charter|runtime|mission_runtime|kernel|glossary)\.")
_INTERACTION = re.compile(
    r"\.(assert_called|assert_called_once|assert_called_with|assert_called_once_with"
    r"|assert_not_called|assert_any_call|assert_has_calls)\b|\.call_count\b|\.call_args"
)
_SOURCE_READ = re.compile(r"(read_text|open)\(.*\)")
_SOURCE_PATH = re.compile(r"src/|Path\(.*(specify_cli|charter|runtime)")
_SUBSTRING_ASSERT = re.compile(r"\bassert\b.*(\bin\b|\bnot in\b)")
_PLATFORM_GUARD = re.compile(r"skipif\(.*(platform|sys\.|win|shutil\.which|os\.name|environ)")
_WALLCLOCK = re.compile(r"(datetime\.now|datetime\.utcnow|time\.time)\(\)")
_FROZEN_CLOCK = re.compile(r"freeze|monkeypatch|clock")
_LINE_PIN = re.compile(r"\.py:\d+")
_BROAD_RAISES = re.compile(r"pytest\.raises\((Exception|BaseException)\)")
_PRIVATE_ATTR = re.compile(r"\b[a-z_]+\._[a-z][a-z0-9_]*\b(?!\()")
_PRIVATE_ATTR_NOISE = ("self.", "monkeypatch", "mock", "os.", "sys.", "pytest", "tmp_path", "capsys", "re.", "json.")
_VAGUE_NAME = re.compile(r"test_?\d*|test_(it_works|basic|smoke|misc|foo|bar|simple|ok|works)")
_ULID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
#: A folded ``"0" * n`` longer than this cannot be a 26-character ULID anyway.
_MAX_FOLD_REPEAT = 64
_PROVENANCE = re.compile(r"\b(WP\d{2}|FR-\d{3}|NFR-\d{3}|T\d{3}|#\d{3,5})\b|_(wp|fr|t)\d{2,3}(_|$)|_issue_?\d{3,5}")


@dataclass
class TestRow:
    """One flagged test function."""

    file: str
    line: int
    test: str
    flags: list[str]
    score: int


@dataclass
class FileRow:
    """Aggregated triage for one test module."""

    file: str
    domain: str
    tests: int = 0
    flagged_tests: int = 0
    score: int = 0
    flags: dict[str, int] = field(default_factory=dict)
    added: str | None = None
    added_by: str | None = None
    last_touched: str | None = None


def domain_of(path: str) -> str:
    """Return the review domain of a test path (``tests/<a>`` or ``tests/<a>/<b>``)."""
    parts = Path(path).parts
    if len(parts) < 3:
        return "(root)"
    if parts[1] in DEEP_DOMAINS and len(parts) >= 4:
        return f"{parts[1]}/{parts[2]}"
    return parts[1]


def iter_tests(tree: ast.Module) -> list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Return ``(qualified_name, node)`` for every test function, classes included."""
    found: list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def walk(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                walk(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test"):
                found.append((f"{prefix}{node.name}", node))

    walk(tree.body, "")
    return found


def _oracle_flags(fn: ast.FunctionDef | ast.AsyncFunctionDef, call_names: list[str]) -> list[str]:
    """Flags about whether the test can fail at all (R1)."""
    asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
    raises = [n for n in ast.walk(fn) if isinstance(n, ast.With | ast.AsyncWith) and any("raises" in ast.unparse(i.context_expr) for i in n.items)]
    if not asserts and not raises and not any(_ASSERT_LIKE_CALL.search(c) for c in call_names):
        return ["no-assertion"]
    if len(asserts) != 1 or raises:
        return []
    only = ast.unparse(asserts[0].test)
    if only in ("True", "1") or re.fullmatch(r"\w+ is not None", only):
        return ["weak-only-assert"]
    if re.fullmatch(r"(isinstance|callable|hasattr)\(.*\)", only):
        return ["type-only-assert"]
    return []


def _coupling_flags(fn: ast.FunctionDef | ast.AsyncFunctionDef, calls: list[ast.Call], seg: str) -> list[str]:
    """Flags about coupling to implementation rather than behaviour (R2, R3)."""
    flags: list[str] = []
    mocks = sum(1 for c in calls if _MOCK_CALL.search(ast.unparse(c.func)))
    internal_setattrs = sum(1 for c in calls if ast.unparse(c.func).endswith("monkeypatch.setattr") and c.args and _INTERNAL_TARGET.search(ast.unparse(c.args[0])))
    patch_decorators = sum(1 for d in fn.decorator_list if "patch" in ast.unparse(d))
    if mocks + internal_setattrs + patch_decorators >= 4:
        flags.append("over-mocking")
    if _INTERACTION.search(seg):
        flags.append("interaction-assert")
    private = {p for p in _PRIVATE_ATTR.findall(seg) if not p.startswith(_PRIVATE_ATTR_NOISE)}
    if len(private) >= 3:
        flags.append("private-attr")
    return flags


def _text_flags(fn: ast.FunctionDef | ast.AsyncFunctionDef, seg: str) -> list[str]:
    """Flags read off the test's source text (R4, R6, R7, R9, skips)."""
    checks = (
        (
            "literal-source-scan",
            _SOURCE_READ.search(seg) and _SOURCE_PATH.search(seg) and _SUBSTRING_ASSERT.search(seg) and "ast.parse" not in seg,
        ),
        ("line-number-pin", _LINE_PIN.search(seg)),
        ("broad-raises", _BROAD_RAISES.search(seg)),
        ("fake-short-ulid", _has_fake_ulid(fn)),
        ("sleep", "time.sleep(" in seg),
        ("wallclock", _WALLCLOCK.search(seg) and not _FROZEN_CLOCK.search(seg)),
        ("skip-or-xfail", re.search(r"pytest\.(skip|xfail)\(", seg) or _unguarded_skip(fn)),
    )
    return [code for code, hit in checks if hit]


def _fold_str(node: ast.expr) -> str | None:
    """Constant-fold a string expression built from literals, ``+`` and ``* int``.

    Returns ``None`` for anything else, so an unfoldable value is never judged.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if not isinstance(node, ast.BinOp):
        return None
    if isinstance(node.op, ast.Add):
        left, right = _fold_str(node.left), _fold_str(node.right)
        return None if left is None or right is None else left + right
    if isinstance(node.op, ast.Mult):
        folded = _fold_repeat(node.left, node.right)
        return folded if folded is not None else _fold_repeat(node.right, node.left)
    return None


def _fold_repeat(text_node: ast.expr, count_node: ast.expr) -> str | None:
    text = _fold_str(text_node)
    count = count_node.value if isinstance(count_node, ast.Constant) else None
    if text is None or not isinstance(count, int) or isinstance(count, bool) or not 0 <= count <= _MAX_FOLD_REPEAT:
        return None
    return text * count


def _mission_id_values(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.expr]:
    """Every expression the test binds to a ``mission_id`` (kwarg, dict key, assignment)."""
    values: list[ast.expr] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.keyword) and node.arg == "mission_id":
            values.append(node.value)
        elif isinstance(node, ast.Dict):
            values.extend(v for k, v in zip(node.keys, node.values, strict=True) if isinstance(k, ast.Constant) and k.value == "mission_id")
        elif isinstance(node, ast.Assign):
            values.extend(node.value for target in node.targets if _names_mission_id(target))
        elif isinstance(node, ast.AnnAssign) and node.value is not None and _names_mission_id(node.target):
            values.append(node.value)
    return values


def _names_mission_id(target: ast.expr) -> bool:
    return (isinstance(target, ast.Name) and target.id == "mission_id") or (isinstance(target, ast.Attribute) and target.attr == "mission_id")


def _has_fake_ulid(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when a ``mission_id`` folds to a string that is not a 26-character ULID (R7)."""
    folded = (_fold_str(value) for value in _mission_id_values(fn))
    return any(text is not None and not _ULID.fullmatch(text) for text in folded)


def _unguarded_skip(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in fn.decorator_list:
        text = ast.unparse(decorator)
        if re.search(r"xfail|skip", text) and not _PLATFORM_GUARD.search(text):
            return True
    return False


def _shape_flags(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Flags about the test's shape and naming (R8, dev-assist hints)."""
    flags: list[str] = []
    end = fn.end_lineno or fn.lineno
    if end - fn.lineno + 1 > 80:
        flags.append("long-test")
    if sum(1 for n in ast.walk(fn) if isinstance(n, ast.Assert)) >= 15:
        flags.append("many-asserts")
    if _VAGUE_NAME.fullmatch(fn.name):
        flags.append("vague-name")
    if _PROVENANCE.search(f"{fn.name}\n{ast.get_docstring(fn) or ''}"):
        flags.append("provenance-tokens")
    return flags


def flags_for(fn: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]) -> list[str]:
    """Return every flag code the test function trips, in rubric order."""
    seg = "\n".join(lines[fn.lineno - 1 : fn.end_lineno])
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
    call_names = [ast.unparse(c.func) for c in calls]
    return [
        *_oracle_flags(fn, call_names),
        *_coupling_flags(fn, calls, seg),
        *_text_flags(fn, seg),
        *_shape_flags(fn),
    ]


def score(flags: list[str]) -> int:
    return sum(WEIGHTS.get(flag, 1) for flag in flags)


def scan_file(repo: Path, rel: str, only: set[str] | None) -> tuple[FileRow, list[TestRow]]:
    """Scan one module; ``only`` restricts scoring to those qualified test names."""
    row = FileRow(file=rel, domain=domain_of(rel))
    source = (repo / rel).read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        row.flags = {"unparseable": 1}
        return row, []
    lines = source.splitlines()
    counts: Counter[str] = Counter()
    rows: list[TestRow] = []
    for name, fn in iter_tests(tree):
        if only is not None and name not in only:
            continue
        row.tests += 1
        flags = flags_for(fn, lines)
        if flags:
            rows.append(TestRow(file=rel, line=fn.lineno, test=name, flags=flags, score=score(flags)))
            counts.update(flags)
    row.flagged_tests = len(rows)
    row.score = sum(r.score for r in rows)
    row.flags = dict(counts.most_common())
    return row, rows


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    return result.stdout if result.returncode == 0 else ""


def collect_paths(repo: Path, roots: list[str]) -> list[str]:
    """Every ``test_*.py`` / ``*_test.py`` under the given roots, repo-relative."""
    found: set[str] = set()
    for root in roots:
        base = repo / root
        candidates = [base] if base.is_file() else [*base.rglob("test_*.py"), *base.rglob("*_test.py")]
        for path in candidates:
            if "__pycache__" not in path.parts:
                found.add(path.relative_to(repo).as_posix())
    return sorted(found)


def changed_tests_since(repo: Path, since: str, roots: list[str]) -> dict[str, set[str] | None]:
    """Map each test file added or changed since ``since`` to the tests to score.

    A new file scores every test (``None``). A changed file scores only the test
    functions whose source text differs from the ``since`` revision.
    """
    out: dict[str, set[str] | None] = {}
    listing = git(repo, "diff", "--name-status", "--diff-filter=AMR", f"{since}...HEAD", "--", *roots)
    for line in listing.splitlines():
        parts = line.split("\t")
        status, path = parts[0], parts[-1]
        if not re.search(r"(^|/)(test_[^/]*|[^/]*_test)\.py$", path):
            continue
        old_path = parts[1] if status.startswith("R") else path
        old_source = git(repo, "show", f"{since}:{old_path}") if not status.startswith("A") else ""
        out[path] = None if not old_source else _changed_names(old_source, (repo / path).read_text(encoding="utf-8"))
    return out


def _changed_names(old_source: str, new_source: str) -> set[str]:
    def bodies(source: str) -> dict[str, str]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}
        lines = source.splitlines()
        return {name: "\n".join(lines[fn.lineno - 1 : fn.end_lineno]) for name, fn in iter_tests(tree)}

    old, new = bodies(old_source), bodies(new_source)
    return {name for name, body in new.items() if old.get(name) != body}


def attach_provenance(repo: Path, files: dict[str, FileRow], roots: list[str]) -> None:
    """Fill ``added``/``added_by``/``last_touched`` from one ``git log`` pass.

    On a shallow clone the oldest reachable commit stands in for "added".
    """
    log = git(repo, "log", "--format=@@%h\t%as\t%s", "--name-only", "--no-renames", "--", *roots)
    commit: tuple[str, str, str] | None = None
    for line in log.splitlines():
        if line.startswith("@@"):
            sha, date, subject = (line[2:].split("\t", 2) + ["", ""])[:3]
            commit = (sha, date, subject)
            continue
        row = files.get(line.strip())
        if row is None or commit is None:
            continue
        if row.last_touched is None:
            row.last_touched = commit[1]
        row.added, row.added_by = commit[1], f"{commit[0]} {commit[2][:90]}"


def render_summary(files: list[FileRow], top: int) -> str:
    by_domain: dict[str, list[FileRow]] = defaultdict(list)
    for row in files:
        by_domain[row.domain].append(row)
    lines = [
        "# Test-quality triage",
        "",
        "Static heuristics only; every flag is a candidate for review, not a verdict.",
        "",
        "| Domain | Files | Tests | Flagged tests | Score | Top flags |",
        "|---|---:|---:|---:|---:|---|",
    ]
    ranked = sorted(by_domain.items(), key=lambda kv: -sum(r.score for r in kv[1]))
    for domain, rows in ranked:
        flags: Counter[str] = Counter()
        for r in rows:
            flags.update(r.flags)
        top_flags = ", ".join(f"{k} {v}" for k, v in flags.most_common(3))
        tests = sum(r.tests for r in rows)
        flagged = sum(r.flagged_tests for r in rows)
        lines.append(f"| {domain} | {len(rows)} | {tests} | {flagged} | {sum(r.score for r in rows)} | {top_flags} |")
    lines += ["", f"## Top {top} files overall", ""]
    for row in sorted(files, key=lambda r: -r.score)[:top]:
        if row.score:
            lines.append(f"- `{row.file}` score {row.score}: {_flag_text(row)}")
    return "\n".join(lines) + "\n"


def _flag_text(row: FileRow) -> str:
    return ", ".join(f"{k} {v}" for k, v in row.flags.items())


def write_ledgers(out: Path, files: list[FileRow], tests: list[TestRow], top: int) -> list[Path]:
    """Seed one review checklist per domain; an existing ledger is left untouched."""
    ledger_dir = out / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    tests_by_file: dict[str, list[TestRow]] = defaultdict(list)
    for t in tests:
        tests_by_file[t.file].append(t)
    written: list[Path] = []
    for domain in sorted({f.domain for f in files}):
        path = ledger_dir / f"{domain.replace('/', '__')}.md"
        ranked = [f for f in sorted(files, key=lambda r: -r.score) if f.domain == domain and f.score][:top]
        if path.exists() or not ranked:
            continue
        body = [f"# Review ledger: {domain}", "", "Verdicts: KEEP, FIX, RETIRE (name the covering guard), SPLIT-BY-KIND.", ""]
        for f in ranked:
            provenance = f" (added {f.added} by {f.added_by})" if f.added else ""
            body.append(f"- [ ] `{f.file}` score {f.score}{provenance}")
            for t in sorted(tests_by_file[f.file], key=lambda r: -r.score)[:5]:
                body.append(f"  - `{t.test}` line {t.line}: {', '.join(t.flags)}")
            body.append("  - Verdict:")
        path.write_text("\n".join(body) + "\n", encoding="utf-8")
        written.append(path)
    return written


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root (default: cwd)")
    parser.add_argument("--paths", nargs="+", default=["tests"], help="test roots or files to scan (default: tests)")
    parser.add_argument("--since", help="only score tests added or changed since this git revision")
    parser.add_argument("--out", type=Path, default=Path("work/test-quality"), help="output directory")
    parser.add_argument("--top", type=int, default=25, help="files per domain ledger and in the summary")
    parser.add_argument("--no-git", action="store_true", help="skip git provenance (faster, works outside git)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = args.repo.resolve()
    targets: dict[str, set[str] | None] = changed_tests_since(repo, args.since, args.paths) if args.since else dict.fromkeys(collect_paths(repo, args.paths))
    file_rows: dict[str, FileRow] = {}
    test_rows: list[TestRow] = []
    for rel, only in sorted(targets.items()):
        row, rows = scan_file(repo, rel, only)
        file_rows[rel] = row
        test_rows.extend(rows)
    if not args.no_git:
        attach_provenance(repo, file_rows, args.paths)
    out = args.out if args.out.is_absolute() else repo / args.out
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(file_rows.values(), key=lambda r: (-r.score, r.file))
    (out / "tests.json").write_text(json.dumps([asdict(t) for t in test_rows], indent=1), encoding="utf-8")
    (out / "files.json").write_text(json.dumps([asdict(f) for f in files], indent=1), encoding="utf-8")
    (out / "summary.md").write_text(render_summary(files, args.top), encoding="utf-8")
    ledgers = write_ledgers(out, files, test_rows, args.top)
    total_tests = sum(f.tests for f in files)
    print(
        f"scanned {len(files)} files, {total_tests} tests; {len(test_rows)} flagged; "
        f"{len(ledgers)} new ledgers; wrote {out.relative_to(repo) if out.is_relative_to(repo) else out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
