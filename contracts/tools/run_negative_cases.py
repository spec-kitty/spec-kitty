"""Run every planted negative case of the contract tooling and require each check to fail for the expected reason (FR-021).

``contracts/tools/negative_cases.json`` lists the cases. Each case names a ``tool`` (a script under ``contracts/tools/``), a
``plant`` run that must exit with the expected status and print the expected stable code, and a ``control`` run on the same
root that must pass. A check that passes on its plant, fails for another reason, or fails its own clean control fails the case.

Manifest shape::

    {"cases": [{
        "id": "layout-path-file-name", "tool": "layout_check.py", "root": "contracts/tools/fixtures/layout_check",
        "tags": ["jvm"],                                   # optional: tools the case needs on PATH (jvm, vacuum, oasdiff)
        "build": "leak:email",                             # optional: a plant assembled at run time (never committed)
        "plant": {"args": ["--root", "{root}"], "keep": ["clean", "v_x"], "code": "PATH_FILE_NAME", "exit": 1},
        "control": {"args": ["--root", "{root}"], "keep": ["clean"], "exit": 0}}]}

Placeholders in ``args``: ``{root}`` (the run's root: the case ``root``, or a copy holding only the ``keep`` entries, or the
root a ``build`` assembled), ``{work}`` (the case's scratch directory), ``{out}`` (a fresh empty directory outside the
repository) and ``{repo}``. A run may override ``tool``. ``exit`` defaults to 1 for a plant and 0 for a control.

Failure codes (exit 1), printed as ``CONTRACT-CHECK run_negative_cases: CASE_FAILED: <id>: <CODE>: <detail>``:
``PLANT_PASSED`` (the plant exited 0), ``WRONG_EXIT``, ``WRONG_REASON`` (the code is not in the output), ``CONTROL_MISSING``,
``CONTROL_FAILED`` (the clean control did not pass), ``CONTROL_SHOWS_PLANT_CODE`` and, once at the end, ``CASE_COUNT_MISMATCH``
(the cases that ran plus the cases skipped are not the length of the manifest).

Cannot do its job (exit 2): ``MANIFEST_UNREADABLE``, ``ZERO_CASES``, ``MANIFEST_INVALID``, ``TOOL_MISSING`` (a script or a
binary a case needs is absent) and ``BUILD_UNKNOWN``. ``--exclude-tag TAG`` skips (and counts) the cases carrying that tag, so
a machine without the JVM can run the rest; CI never passes it. The last line is always
``counts: cases=N ran=N skipped=N passed=N failed=N``.

Run as a bare script. Standard library plus PyYAML (a runtime-assembled plant) and the sibling ``fixture_builder``; it never
imports pytest.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CHECK_NAME = "run_negative_cases"
TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parents[1]
DEFAULT_MANIFEST = TOOLS_DIR / "negative_cases.json"
CASE_TIMEOUT_SECONDS = 3600
TAG_BINARIES: dict[str, tuple[str, ...]] = {"jvm": ("java", "gradle"), "vacuum": ("vacuum",), "oasdiff": ("oasdiff",)}
LINT_CLEAN_CONTROL = Path("contracts") / "tools" / "fixtures" / "vacuum" / "clean.yaml"
DETAIL_LIMIT = 240

Which = Callable[[str], str | None]
Execute = Callable[[Sequence[str], Path], tuple[int, str]]


class CannotRun(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Report:
    cases: int = 0
    ran: int = 0
    skipped: int = 0
    passed: int = 0
    failed: list[str] = field(default_factory=list)

    def counts_line(self) -> str:
        return f"counts: cases={self.cases} ran={self.ran} skipped={self.skipped} passed={self.passed} failed={len(self.failed)}"


@dataclass(frozen=True)
class Outcome:
    case_id: str
    problem: tuple[str, str] | None  # (code, detail) or None when the case holds


def subprocess_execute(command: Sequence[str], cwd: Path) -> tuple[int, str]:
    """Run ``command`` (an argument list, never a shell string) and return ``(status, stdout + stderr)``."""
    completed = subprocess.run(  # noqa: S603 -- argument list built here, interpreter is sys.executable, no shell
        list(command), capture_output=True, text=True, timeout=CASE_TIMEOUT_SECONDS, check=False, cwd=cwd
    )
    return completed.returncode, completed.stdout + completed.stderr


def load_manifest(path: Path) -> list[dict[str, Any]]:
    try:
        document: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CannotRun("MANIFEST_UNREADABLE", f"{path}: {type(error).__name__}") from error
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list) or not cases:
        raise CannotRun("ZERO_CASES", f"{path} lists no case")
    ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not isinstance(case.get("tool"), str):
            raise CannotRun("MANIFEST_INVALID", f"a case lacks a string id or tool: {str(case)[:80]}")
        if case["id"] in ids:
            raise CannotRun("MANIFEST_INVALID", f"duplicate case id {case['id']}")
        ids.add(case["id"])
        if not isinstance(case.get("plant"), dict) or not isinstance(case["plant"].get("code"), str):
            raise CannotRun("MANIFEST_INVALID", f"{case['id']}: the plant names no expected code")
    return cases


def copy_kept(source: Path, keep: Sequence[str], destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    for name in keep:
        entry = source / name
        if not entry.exists():
            raise CannotRun("MANIFEST_INVALID", f"{entry} does not exist")
        shutil.copytree(entry, destination / name) if entry.is_dir() else shutil.copy2(entry, destination / name)
    return destination


def build_leak(kind: str, work: Path) -> tuple[Path, Path]:
    """A leak-class plant assembled from fragments at run time, and the same root without the planted file."""
    import fixture_builder  # noqa: PLC0415 -- sibling script, importable only once the tools directory is on sys.path

    built = fixture_builder.build(kind, work / "leak")
    control = work / "leak-control"
    shutil.copytree(built.root, control)
    (control / Path(*fixture_builder.EXAMPLES_PATH) / fixture_builder.PLANTED_FILE).unlink()
    return built.root, control


def build_lint_forbidden_property(work: Path) -> tuple[Path, Path]:
    """The lint plant the rule ``forbidden-property-name`` must refuse: a property named like a local path.

    It is leak-shaped, so it is assembled from fragments here and never committed. The control is the committed clean bundle.
    """
    document = yaml.safe_load((REPO_ROOT / LINT_CLEAN_CONTROL).read_text(encoding="utf-8"))
    schema = document["paths"]["/things"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    name = "work" + "tree" + "Path"
    schema["properties"][name] = {"type": "string", "description": "A local path.", "x-source": {"path": "src/example/things.py", "symbol": "Thing.id"}}
    plant = work / "forbidden-property.yaml"
    plant.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return plant, REPO_ROOT / LINT_CLEAN_CONTROL


def build_no_pytest(work: Path) -> tuple[Path, Path]:
    """A contracts root whose one script imports the test runner, and the committed clean root.

    The plant is written here, never committed: a committed planted import would reach the repository's own lint and scan.
    """
    runner = "pyt" + "est"
    plant = work / "no-pytest-plant"
    shutil.copytree(TOOLS_DIR / "fixtures" / "no_pytest_scan" / "clean", plant)
    (plant / "tools" / "plant_import.py").write_text(f"import {runner}\n\nNAME = {runner}.__name__\n", encoding="utf-8")
    return plant, TOOLS_DIR / "fixtures" / "no_pytest_scan" / "clean"


def build_parity(view: str, work: Path) -> tuple[Path, Path]:
    """Two staged directories for ``resolver_parity.py``: the written bundle of the clean module with the planted Java view, and with the clean one."""
    import bundle  # noqa: PLC0415 -- sibling script, importable only once the tools directory is on sys.path

    fixtures = TOOLS_DIR / "fixtures" / "resolver_parity"
    staged = []
    for label, name in (("plant", view), ("control", "ok")):
        directory = work / f"parity-{label}"
        bundle.write_bundle(fixtures / "clean" / "alpha", directory)
        target = directory / "javaview" / "alpha" / "openapi.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixtures / "java_views" / f"{name}.yaml", target)
        staged.append(directory)
    return staged[0], staged[1]


def assemble(case: dict[str, Any], work: Path) -> tuple[Path | None, Path | None]:
    """The plant root and the control root of ``case`` (``None`` when it has none)."""
    build = case.get("build")
    if build is not None:
        if isinstance(build, str) and build.startswith("leak:"):
            return build_leak(build.removeprefix("leak:"), work)
        if isinstance(build, str) and build.startswith("parity:"):
            return build_parity(build.removeprefix("parity:"), work)
        if build == "no-pytest":
            return build_no_pytest(work)
        if build == "lint-forbidden-property":
            return build_lint_forbidden_property(work)
        raise CannotRun("BUILD_UNKNOWN", f"{case['id']}: unknown build {build!r}")
    root = REPO_ROOT / case["root"] if case.get("root") else None
    roots: list[Path | None] = []
    for which in ("plant", "control"):
        keep = (case.get(which) or {}).get("keep")
        roots.append(copy_kept(root, keep, work / which) if root is not None and keep else root)
    return roots[0], roots[1]


def expand(argument: str, variables: dict[str, str]) -> str:
    for name, value in variables.items():
        argument = argument.replace("{" + name + "}", value)
    return argument


def run_spec(case: dict[str, Any], spec: dict[str, Any], root: Path | None, work: Path, tools_dir: Path, execute: Execute, label: str) -> tuple[int, str]:
    out_dir = work / f"{label}-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    variables = {"root": str(root) if root is not None else "", "work": str(work), "out": str(out_dir), "repo": str(REPO_ROOT)}
    script = tools_dir / str(spec.get("tool", case["tool"]))
    if not script.is_file():
        raise CannotRun("TOOL_MISSING", f"{case['id']}: {script} does not exist")
    return execute([sys.executable, str(script), *(expand(str(argument), variables) for argument in spec.get("args", []))], REPO_ROOT)


def code_in(code: str, output: str) -> bool:
    """A stable code (upper case and underscores) must stand alone; any other expected text is a plain substring."""
    if re.fullmatch(r"[A-Z][A-Z_]+", code):
        return re.search(rf"(?<![\w-]){code}(?![\w-])", output) is not None
    return code in output


def judge(case: dict[str, Any], work: Path, tools_dir: Path, execute: Execute) -> tuple[str, str] | None:
    """``(code, detail)`` of the first way ``case`` fails, or ``None`` when its plant fails as expected and its control passes."""
    plant, control = assemble(case, work)
    spec = case["plant"]
    status, output = run_spec(case, spec, plant, work, tools_dir, execute, "plant")
    expected_exit = int(spec.get("exit", 1))
    if status == 0 and expected_exit != 0:
        return "PLANT_PASSED", f"the plant passed: {tail(output)}"
    if status != expected_exit:
        return "WRONG_EXIT", f"exit {status}, expected {expected_exit}: {tail(output)}"
    code = spec["code"]
    if not code_in(code, output):
        return "WRONG_REASON", f"{code} is not in the output: {tail(output)}"
    control_spec = case.get("control")
    if not isinstance(control_spec, dict):
        return "CONTROL_MISSING", "the case has no clean control"
    control_status, control_output = run_spec(case, control_spec, control, work, tools_dir, execute, "control")
    if control_status != int(control_spec.get("exit", 0)):
        return "CONTROL_FAILED", f"the clean control exited {control_status}: {tail(control_output)}"
    if code_in(code, control_output):
        return "CONTROL_SHOWS_PLANT_CODE", f"the clean control printed {code}"
    return None


def tail(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return " | ".join(lines[-3:])[:DETAIL_LIMIT]


def missing_binaries(case: dict[str, Any], which: Which) -> list[str]:
    needed = [binary for tag in case.get("tags", []) for binary in TAG_BINARIES.get(tag, ())]
    return [binary for binary in needed if which(binary) is None]


def run_each(cases: Iterable[dict[str, Any]], work: Path, tools_dir: Path, execute: Execute) -> Iterable[Outcome]:
    """Run each case in its own scratch directory. A truncated implementation of this function is what the count check catches."""
    for case in cases:
        scratch = work / str(case["id"])
        scratch.mkdir(parents=True, exist_ok=True)
        yield Outcome(str(case["id"]), judge(case, scratch, tools_dir, execute))


def run(
    argv: Sequence[str] | None = None,
    *,
    out: Callable[[str], None] = print,
    execute: Execute = subprocess_execute,
    which: Which = shutil.which,
    iterate: Callable[[Iterable[dict[str, Any]], Path, Path, Execute], Iterable[Outcome]] = run_each,
) -> int:
    parser = argparse.ArgumentParser(description="Run every planted negative case and its clean control.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, type=Path)
    parser.add_argument("--tools-dir", default=TOOLS_DIR, type=Path, help="where the case scripts live (default: contracts/tools)")
    parser.add_argument("--work", default=None, type=Path, help="scratch directory outside the repository (default: a temporary one)")
    parser.add_argument("--exclude-tag", action="append", default=[], help="skip, and count, the cases carrying this tag (repeatable)")
    args = parser.parse_args(argv)

    report = Report()
    try:
        cases = load_manifest(args.manifest)
        report.cases = len(cases)
        selected = [case for case in cases if not set(case.get("tags", [])) & set(args.exclude_tag)]
        report.skipped = len(cases) - len(selected)
        for case in selected:
            absent = missing_binaries(case, which)
            if absent:
                raise CannotRun("TOOL_MISSING", f"{case['id']} needs {', '.join(absent)} on PATH (install_tools.py installs them)")
        work = args.work if args.work is not None else Path(tempfile.mkdtemp(prefix="negative-cases-"))
        work.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(args.tools_dir))
        try:
            outcomes = list(iterate(selected, work, args.tools_dir, execute))
        finally:
            sys.path.remove(str(args.tools_dir))
    except CannotRun as error:
        out(f"CONTRACT-CHECK {CHECK_NAME}: {error.code}: {error.detail}")
        out(report.counts_line())
        return 2

    report.ran = len(outcomes)
    for outcome in outcomes:
        if outcome.problem is None:
            report.passed += 1
            out(f"PASS {outcome.case_id}")
        else:
            report.failed.append(outcome.case_id)
            out(f"CONTRACT-CHECK {CHECK_NAME}: CASE_FAILED: {outcome.case_id}: {outcome.problem[0]}: {outcome.problem[1]}")
    mismatch = report.ran + report.skipped != report.cases
    if mismatch:
        out(f"CONTRACT-CHECK {CHECK_NAME}: CASE_COUNT_MISMATCH: ran {report.ran} and skipped {report.skipped} of {report.cases} cases in the manifest")
    out(report.counts_line())
    return 1 if report.failed or mismatch else 0


if __name__ == "__main__":
    sys.exit(run())
