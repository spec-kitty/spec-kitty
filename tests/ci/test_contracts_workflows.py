"""Guard tests for the two contract workflows (mission mission-status-contract-v1, FR-017, FR-018, FR-021, FR-022).

``.github/workflows/contracts.yml`` and ``.github/workflows/contracts-release.yml`` are pinned from their
parsed text. Every rule is a function over a workflow *text*, so each one is proved twice: the real file
passes it, and a planted violating text (the real text with one mutation) fails it for that rule only.
A rule that parsed nothing fails (class B evidence: no vacuous pass).

The single authority for the job graph is ``contracts/tools-and-workflows.md`` of the mission; the job table
below mirrors it. The tag-namespace guard implements GitHub's filter-pattern semantics (``*`` does not cross
``/``, ``**`` does), not ``fnmatch``.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.architectural import _gate_coverage as gc

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
CONTRACTS_PATH = WORKFLOWS_DIR / "contracts.yml"
RELEASE_PATH = WORKFLOWS_DIR / "contracts-release.yml"
CLI_RELEASE_PATH = WORKFLOWS_DIR / "release.yml"
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"

CANONICAL_GUARD = "(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'pull_request' || github.event_name == 'workflow_dispatch')"
RELEASE_GUARD = "(github.repository == 'spec-kitty/spec-kitty' || github.event_name == 'workflow_dispatch')"
PUBLISH_CONDITION = "github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')"
CONTRACT_TAG_FILTER = "contract-*-v*.*.*"
# The corpus the Contracts tests read plus everything they run on: the release workflow, the locked environment, the pytest
# configuration and conftest, and the lifecycle source event_mapping_check parses.
EXPECTED_PATHS = [
    "contracts/**",
    "tests/contract/**",
    ".github/CODEOWNERS",
    ".github/workflows/contracts.yml",
    ".github/workflows/contracts-release.yml",
    "uv.lock",
    "pyproject.toml",
    "pytest.ini",
    "tests/conftest.py",
    "src/specify_cli/status/lifecycle_events.py",
]
# The contract tool unit tests run in a router job (a required check through router-gate), not in contracts.yml, which runs no
# pytest at all. The router's corpus job runs only the modules that read committed Missions, to stay within its time budget.
ROUTER_PATH = WORKFLOWS_DIR / "ci-router.yml"
ROUTER_TEXT = ROUTER_PATH.read_text(encoding="utf-8")
TOOL_TEST_JOB = "tests-contract-tools"

# The job table of contracts/tools-and-workflows.md: job -> its exact needs.
EXPECTED_NEEDS: dict[str, frozenset[str]] = {
    "verify-pins": frozenset(),
    "python-checks": frozenset(),
    "validate-bundle": frozenset({"verify-pins"}),
    "lint": frozenset({"validate-bundle"}),
    "breaking-change": frozenset({"validate-bundle"}),
    "resolver-parity": frozenset({"validate-bundle"}),
    "release-dry-run": frozenset({"validate-bundle"}),
    "negative-tests": frozenset({"verify-pins"}),
    "contracts-gate": frozenset(
        {"verify-pins", "python-checks", "validate-bundle", "lint", "breaking-change", "resolver-parity", "release-dry-run", "negative-tests"}
    ),
}
# Jobs with needs that still carry the guard: validate-bundle was a root job in the skeleton and keeps it; the gate is self-starting.
MUST_GUARD = ("validate-bundle", "contracts-gate")
PYTHON_CHECK_SCRIPTS = (
    "layout_check.py",
    "citation_check.py",
    "provisional_check.py",
    "example_check.py",
    "event_mapping_check.py",
    "enum_pin_check.py",
    "leak_scan.py",
    "structure_check.py",
    "codeowners_check.py",
    "no_pytest_scan.py",
)
NODE_TOKENS = ("node", "npm", "npx", "yarn", "pnpm", "setup-node", "node-version")

CONTRACTS_TEXT = CONTRACTS_PATH.read_text(encoding="utf-8")
RELEASE_TEXT = RELEASE_PATH.read_text(encoding="utf-8")


# -- parsing helpers --------------------------------------------------------------------------------------------


def load(text: str) -> dict[Any, Any]:
    data: dict[Any, Any] = yaml.safe_load(text)
    assert isinstance(data, dict)
    return data


def triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    on = workflow.get("on", workflow.get(True))  # PyYAML reads the bare ``on`` key as boolean True
    assert isinstance(on, dict), "the workflow has no trigger mapping"
    return {str(name): (body or {}) for name, body in on.items()}


def jobs(workflow: dict[Any, Any]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = workflow.get("jobs") or {}
    assert found, "the workflow parsed no job"
    return found


def needs_of(job: dict[str, Any]) -> frozenset[str]:
    value = job.get("needs", [])
    return frozenset([value] if isinstance(value, str) else value)


def steps_of(job: dict[str, Any]) -> list[dict[str, Any]]:
    return list(job.get("steps") or [])


def run_text(job: dict[str, Any]) -> str:
    return "\n".join(str(step.get("run", "")) for step in steps_of(job))


def all_steps(workflow: dict[Any, Any]) -> list[dict[str, Any]]:
    return [step for job in jobs(workflow).values() for step in steps_of(job)]


def normalise(condition: str) -> str:
    text = " ".join(str(condition).split())
    wrapped = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", text)
    return wrapped.group(1) if wrapped else text


def code_lines(text: str) -> list[str]:
    """The workflow text without comment lines and trailing comments (a comment may name a banned word)."""
    lines = []
    for line in text.splitlines():
        stripped = re.sub(r"\s+#.*$", "", line) if not line.lstrip().startswith("#") else ""
        if stripped.strip():
            lines.append(stripped)
    return lines


def mutate(text: str, old: str, new: str) -> str:
    assert old in text, f"the planted mutation target is absent: {old!r}"
    return text.replace(old, new, 1)


# -- the rules: each takes a workflow text and returns its violations ---------------------------------------------


def verify_pins_violations(text: str) -> list[str]:
    """Every verify_pins invocation must hash something: ``--artifacts DIR`` or ``--fetch``, never ``--pins-only``.

    verify_pins refuses a run that hashed nothing (CHECKSUMS_UNVERIFIED, exit 2), so a bare call fails in CI and
    ``--pins-only`` would only dodge the refusal. A text with no invocation at all is itself a violation.
    """
    found = 0
    problems: list[str] = []
    for name, job in jobs(load(text)).items():
        for line in run_text(job).splitlines():
            if "verify_pins.py" not in line:
                continue
            found += 1
            if "--pins-only" in line:
                problems.append(f"{name}: verify_pins uses --pins-only, which verifies no checksum")
            if "--fetch" not in line and "--artifacts" not in line:
                problems.append(f"{name}: verify_pins neither passes --artifacts nor --fetch, so it hashes nothing")
    return problems or ([] if found else ["no verify_pins invocation found"])


def trigger_violations(text: str) -> list[str]:
    found = triggers(load(text))
    problems = []
    for name in ("pull_request", "push"):
        if name not in found:
            problems.append(f"no {name} trigger")
            continue
        if found[name].get("paths") != EXPECTED_PATHS:
            problems.append(f"{name} paths are {found[name].get('paths')!r}")
    if "push" in found and found["push"].get("branches") != ["main"]:
        problems.append("the push trigger does not carry branches: [main]")
    if "pull_request" in found and "branches" in found["pull_request"]:
        problems.append("the pull_request trigger carries a branches key (stacked PRs target seam branches)")
    return problems


def node_violations(text: str) -> list[str]:
    lines = code_lines(text)
    assert lines, "no workflow line was scanned"
    pattern = re.compile(r"(?<![\w-])(" + "|".join(re.escape(token) for token in NODE_TOKENS) + r")(?![\w])", re.IGNORECASE)
    return [line.strip() for line in lines if pattern.search(line)]


# A script reaches the runner by importing it, by ``-m``, or by naming it in a string; a docstring that says "never imports pytest" is not one.
_RUNNER_REFERENCE = re.compile(r"(?m)^\s*(?:import|from)\s+_?pytest\b|-m\s+pytest\b|[\"']pytest[\"']")


def pytest_violations(text: str, read: Callable[[str], str] | None = None, allowed_jobs: frozenset[str] = frozenset()) -> list[str]:
    """Pytest reachable from a step: named directly, through ``make``, or inside a script the step runs.

    A job in ``allowed_jobs`` may name pytest in its own steps; make and the scripts it runs are still refused.
    """
    read_script = read or (lambda name: (REPO_ROOT / name).read_text(encoding="utf-8"))
    problems = []
    scanned = 0
    for job_name, job in jobs(load(text)).items():
        for step in steps_of(job):
            scanned += 1
            command = f"{step.get('run', '')} {step.get('uses', '')}"
            if job_name not in allowed_jobs and re.search(r"(?<![\w-])pytest(?![\w-])", command, re.IGNORECASE):
                problems.append(f"pytest named in a step: {command.strip()[:80]}")
            if re.search(r"(?:^|[\s;&|(])make\b", str(step.get("run", ""))):
                problems.append("a step runs make, which may reach pytest")
            for script in re.findall(r"contracts/tools/[\w/]+\.py", str(step.get("run", ""))):
                if _RUNNER_REFERENCE.search(read_script(script)):
                    problems.append(f"{script} mentions pytest")
    assert scanned, "no step was scanned"
    return problems


def unpinned_uses(text: str) -> list[str]:
    uses = [str(step["uses"]) for step in all_steps(load(text)) if "uses" in step]
    assert uses, "no uses: line was parsed"
    return [value for value in uses if not re.fullmatch(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}", value)]


def fork_guard_violations(text: str, guard: str, *, gate_names: tuple[str, ...] = ()) -> list[str]:
    """Every root job and every ``always()`` job opens its ``if:`` with ``guard`` as the first top-level conjunct."""
    problems = []
    for name, job in jobs(load(text)).items():
        condition = normalise(job.get("if", ""))
        self_starting = not needs_of(job) or "always()" in condition
        if not (self_starting or name in gate_names):
            continue
        if not condition.startswith(guard):
            problems.append(f"{name}: if: {condition!r} does not open with the fork guard")
            continue
        remainder = condition[len(guard) :].strip()
        if remainder and not remainder.startswith("&&"):
            problems.append(f"{name}: the fork guard is not a top-level conjunct")
    return problems


def needs_violations(text: str, expected: dict[str, frozenset[str]]) -> list[str]:
    found = jobs(load(text))
    problems = [f"unexpected job {name}" for name in found if name not in expected]
    problems += [f"missing job {name}" for name in expected if name not in found]
    problems += [
        f"{name}: needs {sorted(needs_of(job))} != {sorted(expected[name])}" for name, job in found.items() if name in expected and needs_of(job) != expected[name]
    ]
    return problems


def timeout_violations(text: str) -> list[str]:
    return [name for name, job in jobs(load(text)).items() if not isinstance(job.get("timeout-minutes"), int)]


def prelude_violations(text: str) -> list[str]:
    """Every job that runs a contracts/tools script has the one Python install form, and runs it frozen."""
    problems = []
    checked = 0
    for name, job in jobs(load(text)).items():
        commands = run_text(job)
        if "contracts/tools/" not in commands:
            continue
        checked += 1
        uses = [str(step.get("uses", "")) for step in steps_of(job)]
        setup = [step for step in steps_of(job) if str(step.get("uses", "")).startswith("astral-sh/setup-uv@")]
        if not any(value.startswith("actions/checkout@") for value in uses):
            problems.append(f"{name}: no checkout")
        if not setup or setup[0].get("with", {}).get("python-version") != "3.12":
            problems.append(f"{name}: no setup-uv with python-version '3.12'")
        if "uv sync --frozen --no-install-project" not in commands:
            problems.append(f"{name}: no frozen sync")
        for line in commands.splitlines():
            if "contracts/tools/" in line and re.search(r"\bpython\b", line) and "uv run --frozen --no-sync python" not in line:
                problems.append(f"{name}: a script runs outside the synced environment: {line.strip()[:70]}")
    assert checked, "no job ran a contracts/tools script"
    return problems


def evaluate_condition(condition: str, event: str, ref: str) -> bool:
    """Evaluate the subset of ``if:`` the publish steps use: event_name comparisons, startsWith(github.ref, ...), && and ||."""
    text = normalise(condition)
    text = re.sub(r"github\.event_name\s*==\s*'([^']+)'", lambda match: str(match[1] == event), text)
    text = re.sub(r"startsWith\(\s*github\.ref\s*,\s*'([^']+)'\s*\)", lambda match: str(ref.startswith(match[1])), text)
    text = text.replace("&&", " and ").replace("||", " or ")

    def walk(node: ast.AST) -> bool:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.BoolOp):
            values = [walk(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Name) and node.id in ("True", "False"):
            return node.id == "True"
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return node.value
        raise AssertionError(f"unsupported if: element {ast.dump(node)} in {condition!r}")

    return walk(ast.parse(text, mode="eval"))


def publish_steps(text: str) -> list[dict[str, Any]]:
    return [step for step in all_steps(load(text)) if "gh release create" in str(step.get("run", ""))]


RELEASE_ARGS_FILE = "gh-release-args.txt"
# Flags and parsing the publish step must not carry: release_check's argument list holds them (the tool tests pin its content).
REDERIVATION_TOKENS = ("--latest", "--prerelease", "--title", "--notes", "--verify-tag", "##*-v", "%-v")


def publish_violations(text: str) -> list[str]:
    steps = publish_steps(text)
    if not steps:
        return ["no publish step"]
    problems = []
    for step in steps:
        condition = str(step.get("if", ""))
        reached = [(event, ref) for event, ref in PUBLISH_EVENTS if evaluate_condition(condition, event, ref)] if condition else list(PUBLISH_EVENTS)
        if reached != [PUBLISH_EVENTS[3]]:
            problems.append(f"{step.get('name')}: publishes for {reached}")
        run = str(step["run"])
        # The publish step consumes release_check's approved argument list and derives nothing of its own.
        if RELEASE_ARGS_FILE not in run or "mapfile" not in run:
            problems.append(f"{step.get('name')}: it does not run the arguments release_check wrote to {RELEASE_ARGS_FILE}")
        for own in REDERIVATION_TOKENS:
            if own in run:
                problems.append(f"{step.get('name')}: it derives {own!r} itself instead of consuming release_check's arguments")
    checks = [step for step in all_steps(load(text)) if "release_check.py" in str(step.get("run", "")) and "--tag" in str(step.get("run", ""))]
    if not any("--args-file" in str(step["run"]) and RELEASE_ARGS_FILE in str(step["run"]) for step in checks):
        problems.append(f"no release_check tag step writes {RELEASE_ARGS_FILE} with --args-file")
    return problems


# The release workflow's own derivation of the Contracts trigger paths (it prints one path per line).
DERIVE_PATHS_CALL = (
    'uv run --frozen --no-sync python -c \'import yaml; d = yaml.safe_load(open(".github/workflows/contracts.yml")); '
    'on = d.get("on", d.get(True)); print("\\n".join(on["push"]["paths"]))\''
)


def contracts_lookup_violations(gate: str) -> list[str]:
    """The Contracts-success lookup: a push run on main of the last commit that touched the paths read from contracts.yml."""
    rules = (
        ("event=push" in gate, "the Contracts-success check does not restrict the run to event=push"),
        ("branch=main" in gate, "the Contracts-success check does not restrict the run to branch=main"),
        (
            "head_sha=${GITHUB_SHA}" not in gate and "head_sha=$GITHUB_SHA" not in gate,
            "the Contracts-success check queries the tagged SHA, not the last commit that touched the Contracts trigger paths",
        ),
        (
            "git log -1" in gate and '-- "${paths[@]}"' in gate,
            "the Contracts-success check does not resolve the last commit that touched the Contracts trigger paths",
        ),
        (
            ".github/workflows/contracts.yml" in gate and '["paths"]' in gate,
            "the Contracts-success check does not read its path list from contracts.yml on.push.paths",
        ),
        (
            not any(literal in gate for literal in ("contracts/**", "tests/contract", "CODEOWNERS")),
            "the Contracts-success check hand-copies the Contracts trigger paths instead of reading them from contracts.yml",
        ),
    )
    return [message for holds, message in rules if not holds]


def release_steps(text: str) -> list[dict[str, Any]]:
    """The steps of the build job followed by those of the publish job, in the order the jobs run."""
    found = jobs(load(text))
    return [step for name in ("build", "publish") if name in found for step in steps_of(found[name])]


def release_gate_violations(text: str) -> list[str]:
    """A tag push publishes only a commit on main that Contracts passed on, after breaking_check against the previous release."""
    found = jobs(load(text))
    job = found.get("build")
    if job is None:
        return ["no build job"]
    steps = release_steps(text)
    problems: list[str] = []

    def index_of(*tokens: str) -> int | None:
        return next((i for i, step in enumerate(steps) if all(token in str(step.get("run", "")) for token in tokens)), None)

    ancestor = index_of("merge-base --is-ancestor", "origin/main", "exit 1")
    contracts = index_of("gh api", "workflows/contracts.yml/runs", "head_sha", "success", "exit 1")
    breaking = index_of("breaking_check.py", "--release-tag")
    publish = index_of("gh release create")
    for name, position in (
        ("an is-ancestor-of-origin/main check that fails the job", ancestor),
        ("a Contracts-success check by gh api that fails the job", contracts),
    ):
        if position is None:
            problems.append(f"no step has {name}")
        elif [bool(steps[position].get("if")) and evaluate_condition(str(steps[position]["if"]), event, ref) for event, ref in PUBLISH_EVENTS] != [
            False,
            False,
            False,
            True,
        ]:
            problems.append(f"{steps[position].get('name')}: it does not run on exactly a contract tag push")
    if contracts is not None:
        problems += contracts_lookup_violations(str(steps[contracts].get("run", "")))
    if breaking is None:
        problems.append("no step runs breaking_check.py --release-tag against the previous release")
    elif not any("--only oasdiff" in str(step.get("run", "")) for step in steps[:breaking]):
        problems.append("oasdiff is not installed before breaking_check runs")
    if publish is None:
        problems.append("no publish step")
    else:
        publish_job = found.get("publish") or {}
        if "build" not in needs_of(publish_job):
            problems.append("the publish job does not need the build job, so it could run before the checks passed")
        for name, position in (("the ancestor check", ancestor), ("the Contracts-success check", contracts), ("breaking_check", breaking)):
            if position is not None and position > publish:
                problems.append(f"{name} runs after the publish step")
    if not any((s.get("with") or {}).get("fetch-depth") == 0 for s in steps if "actions/checkout" in str(s.get("uses", ""))):
        problems.append("the checkout does not fetch full history (main and the release tags)")
    if (job.get("permissions") or {}).get("actions") != "read":
        problems.append("the job cannot read workflow runs (permissions: actions: read)")
    return problems


def gate_script_violations(text: str) -> list[str]:
    """The terminal gate fails unless EVERY needed job succeeded: no tolerant comparison, no swallowed exit."""
    gate = jobs(load(text)).get("contracts-gate")
    if gate is None:
        return ["no contracts-gate job"]
    scripts = [str(step.get("run", "")) for step in steps_of(gate) if step.get("run")]
    if len(scripts) != 1:
        return [f"the gate has {len(scripts)} script steps, not one"]
    script = scripts[0]
    problems = []
    if not any("join(needs.*.result" in str(value) for step in steps_of(gate) for value in (step.get("env") or {}).values()):
        problems.append("the gate does not read every needed job result (join(needs.*.result, ' '))")
    if not re.search(r'\[\s+"\$result"\s+!=\s+"success"\s+\]', script):
        problems.append('the gate does not compare each result with != "success"')
    if not re.search(r"\bexit 1\b", script):
        problems.append("the gate has no exit 1 on a non-success result")
    for tolerant in ("|| true", "= failure", '= "failure"', "continue-on-error", "set +e", "cancelled", "skipped"):
        if tolerant in script or tolerant in str(gate):
            problems.append(f"the gate is tolerant: it contains {tolerant!r}")
    return problems


PUBLISH_EVENTS = (
    ("pull_request", "refs/pull/1/merge"),
    ("workflow_dispatch", "refs/heads/main"),
    ("push", "refs/heads/main"),
    ("push", "refs/tags/contract-mission-status-v1.0.0"),
)


def release_trigger_violations(text: str) -> list[str]:
    found = triggers(load(text))
    problems = []
    if set(found) != {"push", "workflow_dispatch"}:
        problems.append(f"triggers are {sorted(found)}, not push and workflow_dispatch")
    push = found.get("push", {})
    if push.get("tags") != [CONTRACT_TAG_FILTER] or "branches" in push or "paths" in push:
        problems.append(f"the push trigger is {push!r}, not exactly the tag filter {CONTRACT_TAG_FILTER}")
    dry_run = (found.get("workflow_dispatch", {}).get("inputs") or {}).get("dry_run")
    if not isinstance(dry_run, dict) or dry_run.get("default") is not True:
        problems.append("workflow_dispatch has no dry_run input defaulting to true")
    return problems


def release_permission_violations(text: str) -> list[str]:
    workflow = load(text)
    problems = []
    if workflow.get("permissions") != {"contents": "read"}:
        problems.append(f"top-level permissions are {workflow.get('permissions')!r}")
    found = jobs(workflow)
    writers = [name for name, job in found.items() if (job.get("permissions") or {}).get("contents") == "write"]
    if set(found) != {"build", "publish"} or writers != ["publish"]:
        problems.append(f"expected a build job and exactly one writer, the publish job, found {writers} of {sorted(found)}")
    if (found.get("build", {}).get("permissions") or {}).get("contents") != "read":
        problems.append("the build job does not hold exactly contents: read")
    if (found.get("publish", {}).get("permissions") or {}) != {"contents": "write"}:
        problems.append("the publish job holds more than contents: write")
    return problems


# -- GitHub filter-pattern semantics (the namespace guard) ---------------------------------------------------------


def filter_regex(pattern: str) -> re.Pattern[str]:
    """GitHub's tag filter: ``*`` matches any run of characters except ``/``, ``**`` any run including ``/``, ``?`` zero or one of the previous character."""
    out = ""
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**", index):
            out += ".*"
            index += 2
            continue
        if char == "*":
            out += "[^/]*"
        elif char == "?":
            out += "?"
        else:
            out += re.escape(char)
        index += 1
    return re.compile(out)


def filter_matches(pattern: str, name: str) -> bool:
    return filter_regex(pattern).fullmatch(name) is not None


def cli_tag_filters(text: str) -> list[str]:
    tags = triggers(load(text)).get("push", {}).get("tags") or []
    return [str(tag) for tag in tags]


def namespace_violations(release_text: str, cli_text: str) -> list[str]:
    contract = [str(tag) for tag in triggers(load(release_text)).get("push", {}).get("tags") or []]
    cli = cli_tag_filters(cli_text)
    if not contract or not cli:
        return ["an empty tag filter list: the namespace guard compared nothing"]
    problems = []
    contract_tags = ("contract-mission-status-v1.0.0", "contract-mission-status-v1.0.0-rc.1")
    cli_tags = ("v3.2.7", "v3.2.0rc37")
    preview_tags = ("preview/mission-status/p1", "preview/mission-status/p1-r2", "preview/mission-status/p12-r10")
    slash_tags = ("contract-mission/status-v1.0.0", "contract-mission-status-v1.0.0/extra")
    for name in contract_tags:
        if not any(filter_matches(pattern, name) for pattern in contract):
            problems.append(f"the contract release filter misses {name}")
        if any(filter_matches(pattern, name) for pattern in cli):
            problems.append(f"the CLI filter matches the contract tag {name}")
    for name in cli_tags:
        if any(filter_matches(pattern, name) for pattern in contract):
            problems.append(f"the contract release filter matches the CLI tag {name}")
    for name in (*preview_tags, *slash_tags):
        if any(filter_matches(pattern, name) for pattern in contract):
            problems.append(f"the contract release filter matches {name}")
    for name in preview_tags:
        if any(filter_matches(pattern, name) for pattern in cli):
            problems.append(f"the CLI filter matches the preview tag {name}")
    return problems


# -- contracts.yml: the job graph ------------------------------------------------------------------------------------


def test_the_real_workflows_parse_and_hold_the_expected_jobs() -> None:
    assert len(jobs(load(CONTRACTS_TEXT))) == len(EXPECTED_NEEDS)
    assert set(jobs(load(RELEASE_TEXT))) == {"build", "publish"}


def test_contracts_workflow_triggers_are_exactly_the_three_paths_on_both_triggers() -> None:
    assert trigger_violations(CONTRACTS_TEXT) == []


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("  pull_request:\n    paths:", "  pull_request:\n    branches: [main]\n    paths:", "carries a branches key"),
        ("    branches: [main]\n", "", "does not carry branches: [main]"),
        ("      - '.github/CODEOWNERS'\n      - '.github/workflows/contracts.yml'\n", "      - '.github/workflows/contracts.yml'\n", "paths are"),
        ("      - 'uv.lock'\n", "", "paths are"),
        ("      - 'src/specify_cli/status/lifecycle_events.py'\n", "", "paths are"),
    ],
)
def test_planted_trigger_violations_are_refused(old: str, new: str, reason: str) -> None:
    problems = trigger_violations(mutate(CONTRACTS_TEXT, old, new))

    assert any(reason in problem for problem in problems), problems


def test_the_job_graph_has_exactly_the_needs_of_the_job_table() -> None:
    assert needs_violations(CONTRACTS_TEXT, EXPECTED_NEEDS) == []


def test_a_planted_wrong_needs_set_and_a_missing_job_are_refused() -> None:
    dropped = mutate(CONTRACTS_TEXT, "  validate-bundle:", "  validate-bundle-renamed:")
    assert any("missing job validate-bundle" in problem for problem in needs_violations(dropped, EXPECTED_NEEDS))
    swapped = load(CONTRACTS_TEXT)
    swapped["jobs"]["lint"]["needs"] = ["verify-pins"]
    assert any("lint: needs" in problem for problem in needs_violations(yaml.safe_dump(swapped), EXPECTED_NEEDS))


def test_validate_bundle_waits_for_verify_pins_and_the_gate_lists_every_other_job() -> None:
    found = jobs(load(CONTRACTS_TEXT))

    assert needs_of(found["validate-bundle"]) == {"verify-pins"}
    assert needs_of(found["contracts-gate"]) == set(EXPECTED_NEEDS) - {"contracts-gate"}


def test_the_fork_guard_opens_every_self_starting_job_and_the_gate() -> None:
    assert fork_guard_violations(CONTRACTS_TEXT, CANONICAL_GUARD, gate_names=MUST_GUARD) == []
    gate = normalise(jobs(load(CONTRACTS_TEXT))["contracts-gate"]["if"])
    assert gate == f"{CANONICAL_GUARD} && always()"


@pytest.mark.parametrize("job", ["verify-pins", "python-checks", "validate-bundle", "contracts-gate"])
def test_a_planted_missing_fork_guard_is_refused(job: str) -> None:
    workflow = load(CONTRACTS_TEXT)
    workflow["jobs"][job]["if"] = "always()" if job == "contracts-gate" else "true"

    problems = fork_guard_violations(yaml.safe_dump(workflow), CANONICAL_GUARD, gate_names=MUST_GUARD)

    assert any(problem.startswith(f"{job}:") for problem in problems), problems


def test_the_fork_guard_must_be_a_top_level_conjunct_not_a_disjunct() -> None:
    workflow = load(CONTRACTS_TEXT)
    workflow["jobs"]["contracts-gate"]["if"] = f"{CANONICAL_GUARD} || always()"

    problems = fork_guard_violations(yaml.safe_dump(workflow), CANONICAL_GUARD, gate_names=MUST_GUARD)

    assert any("contracts-gate" in problem and "top-level conjunct" in problem for problem in problems), problems


def test_every_job_has_a_timeout_and_the_workflow_has_a_concurrency_group_per_ref() -> None:
    assert timeout_violations(CONTRACTS_TEXT) == []
    assert timeout_violations(RELEASE_TEXT) == []
    concurrency = load(CONTRACTS_TEXT)["concurrency"]
    assert "github.ref" in str(concurrency["group"])
    # push to main: one group per SHA, nothing to cancel (a merge burst must not cancel the run the release gate looks up); PRs coalesce per ref
    assert "github.event_name == 'push' && github.sha" in str(concurrency["group"])
    assert "github.event_name != 'push'" in str(concurrency["cancel-in-progress"])
    planted = load(CONTRACTS_TEXT)
    del planted["jobs"]["lint"]["timeout-minutes"]
    assert timeout_violations(yaml.safe_dump(planted)) == ["lint"]


def test_every_uses_line_is_pinned_to_a_full_commit_sha() -> None:
    assert unpinned_uses(CONTRACTS_TEXT) == []
    assert unpinned_uses(RELEASE_TEXT) == []
    assert unpinned_uses(mutate(CONTRACTS_TEXT, "actions/setup-java@de7274f081f381c8f8158605e0321c36c376e2e6", "actions/setup-java@v6")) == [
        "actions/setup-java@v6"
    ]


def test_every_script_job_carries_the_one_python_prelude() -> None:
    assert prelude_violations(CONTRACTS_TEXT) == []
    assert prelude_violations(RELEASE_TEXT) == []
    unfrozen = mutate(CONTRACTS_TEXT, "uv sync --frozen --no-install-project", "uv sync")
    assert any("no frozen sync" in problem for problem in prelude_violations(unfrozen))
    bare = mutate(CONTRACTS_TEXT, "uv run --frozen --no-sync python contracts/tools/verify_pins.py --fetch", "python contracts/tools/verify_pins.py --fetch")
    assert any("outside the synced environment" in problem for problem in prelude_violations(bare))


# -- no Node, no pytest --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("text", [CONTRACTS_TEXT, RELEASE_TEXT], ids=["contracts", "release"])
def test_neither_workflow_uses_node(text: str) -> None:
    assert node_violations(text) == []


PLANTED_NODE_STEP = "      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0\n        with:\n          node-version: 20\n"
PLANTED_BARE_NODE = "      - name: build\n        run: node build.js\n"


@pytest.mark.parametrize(
    "planted", [PLANTED_NODE_STEP, PLANTED_BARE_NODE, "      - run: npm ci\n", "      - run: pnpm install\n"], ids=["setup-node", "bare-node", "npm", "pnpm"]
)
def test_planted_node_usage_is_refused(planted: str) -> None:
    text = mutate(CONTRACTS_TEXT, "    steps:\n", "    steps:\n" + planted)

    assert node_violations(text), "the Node scan found nothing in a planted violation"


def test_the_node_scan_ignores_a_comment_that_merely_names_node() -> None:
    assert node_violations(mutate(CONTRACTS_TEXT, "name: Contracts\n", "name: Contracts\n# Node is not used here.\n")) == []


@pytest.mark.parametrize("text", [CONTRACTS_TEXT, RELEASE_TEXT], ids=["contracts", "release"])
def test_pytest_is_unreachable_from_every_step_of_both_contract_workflows(text: str) -> None:
    assert pytest_violations(text) == []


def test_planted_pytest_reachability_is_refused() -> None:
    allowed: frozenset[str] = frozenset()
    direct = mutate(CONTRACTS_TEXT, "    steps:\n", "    steps:\n      - run: uv run pytest tests/contract\n")
    assert any("pytest named" in problem for problem in pytest_violations(direct, allowed_jobs=allowed))
    through_make = mutate(CONTRACTS_TEXT, "    steps:\n", "    steps:\n      - run: make test\n")
    assert any("runs make" in problem for problem in pytest_violations(through_make, allowed_jobs=allowed))
    through_script = pytest_violations(CONTRACTS_TEXT, read=lambda name: "import pytest\n", allowed_jobs=allowed)
    assert any("mentions pytest" in problem for problem in through_script)


def test_the_release_workflow_and_every_other_contracts_job_still_refuse_pytest() -> None:
    workflow = load(CONTRACTS_TEXT)
    workflow["jobs"]["lint"]["steps"].insert(0, {"run": "uv run --frozen pytest tests/contract"})
    assert any("pytest named" in problem for problem in pytest_violations(yaml.safe_dump(workflow)))


# -- the content of the jobs ------------------------------------------------------------------------------------------------


def test_python_checks_runs_the_ten_scripts_in_order_and_the_enum_pin_check_uses_its_default_pin() -> None:
    commands = run_text(jobs(load(CONTRACTS_TEXT))["python-checks"])
    scripts = re.findall(r"contracts/tools/(\w+\.py)", commands)

    assert tuple(scripts) == PYTHON_CHECK_SCRIPTS
    (enum_line,) = [line for line in commands.splitlines() if "enum_pin_check.py" in line]
    assert "--pins" not in enum_line, "the enum pin check must read its default pin file"
    pins = json.loads((TOOLS_DIR / "enum_pins.json").read_text(encoding="utf-8"))
    assert pins and all(values for module in pins.values() for values in module.values()), "the default pin file is empty"


def test_every_verify_pins_call_hashes_real_artefacts() -> None:
    assert verify_pins_violations(CONTRACTS_TEXT) == []
    assert verify_pins_violations(RELEASE_TEXT) == ["no verify_pins invocation found"], "the release workflow does not call verify_pins"


@pytest.mark.parametrize(
    ("replacement", "reason"),
    [
        ("python contracts/tools/verify_pins.py", "hashes nothing"),
        ("python contracts/tools/verify_pins.py --pins-only", "--pins-only"),
    ],
    ids=["bare", "pins-only"],
)
def test_a_planted_verify_pins_call_that_hashes_nothing_is_refused(replacement: str, reason: str) -> None:
    planted = mutate(CONTRACTS_TEXT, "python contracts/tools/verify_pins.py --fetch", replacement)

    assert any(reason in problem for problem in verify_pins_violations(planted))


def test_verify_pins_checks_the_manifest_and_both_workflow_files() -> None:
    commands = run_text(jobs(load(CONTRACTS_TEXT))["verify-pins"])

    assert "contracts/tools/verify_pins.py" in commands
    assert "--pins" not in commands.replace("contracts/tools/pins.json", "") or "contracts/tools/pins.json" in commands
    assert "contracts*.yml" in commands or "--workflow" not in commands, "the default workflow glob covers both contract workflows"


def test_validate_bundle_runs_over_the_real_contracts_root_and_installs_only_gradle() -> None:
    workflow = load(CONTRACTS_TEXT)
    commands = run_text(jobs(workflow)["validate-bundle"])

    assert workflow["env"]["CONTRACTS_ROOT"] == "contracts"
    assert "fixtures/spike" not in CONTRACTS_TEXT
    assert 'install_tools.py --pins contracts/tools/pins.json --dest "$RUNNER_TEMP/tools" --only gradle' in commands
    assert "--only vacuum" not in commands and "--only oasdiff" not in commands


def test_resolver_parity_runs_over_the_real_contracts_root() -> None:
    commands = run_text(jobs(load(CONTRACTS_TEXT))["resolver-parity"])

    assert '--root "$CONTRACTS_ROOT"' in commands
    assert "--module full" not in commands


def smoke_violations(text: str) -> list[str]:
    smoke = [step for step in steps_of(jobs(load(text))["validate-bundle"]) if "client_smoke.py" in str(step.get("run", ""))]
    assert smoke, "no client smoke step was parsed"
    return ["validate-bundle: the client smoke is continue-on-error" for step in smoke if step.get("continue-on-error")]


def test_the_client_smoke_is_failing_not_continue_on_error() -> None:
    smoke = [step for step in steps_of(jobs(load(CONTRACTS_TEXT))["validate-bundle"]) if "client_smoke.py" in str(step.get("run", ""))]

    assert len(smoke) == 1
    assert "--module full" not in smoke[0]["run"]

    planted = load(CONTRACTS_TEXT)
    for step in steps_of(planted["jobs"]["validate-bundle"]):
        if "client_smoke.py" in str(step.get("run", "")):
            step["continue-on-error"] = True
    assert smoke_violations(yaml.safe_dump(planted)) == ["validate-bundle: the client smoke is continue-on-error"]
    assert smoke_violations(CONTRACTS_TEXT) == []


def test_negative_tests_install_their_tools_and_run_the_driver_with_the_runtime_assembled_lint_plant() -> None:
    job = jobs(load(CONTRACTS_TEXT))["negative-tests"]
    commands = run_text(job)

    assert "install_tools.py" in commands and "run_negative_cases.py" in commands
    manifest = json.loads((TOOLS_DIR / "negative_cases.json").read_text(encoding="utf-8"))
    cases = {case["id"]: case for case in manifest["cases"]}
    assert cases["lint-forbidden-property-name"]["build"] == "lint-forbidden-property"
    assert cases["lint-forbidden-property-name"]["plant"]["code"] == "forbidden-property-name"
    assert not list((TOOLS_DIR / "fixtures" / "vacuum").glob("*forbidden*")), "the leak-shaped plant is never committed"


VACUUM_PLANTS = TOOLS_DIR / "fixtures" / "vacuum"
RULESET_PATH = REPO_ROOT / "contracts" / "lint" / "ruleset.yaml"
RULE_HEADER = re.compile(r"^# rule: ([A-Za-z0-9-]+)$")


def lint_plants(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.yaml") if path.name != "clean.yaml")


def workflow_rule_derivation() -> str:
    """The shell line of the lint step that derives the expected rule of one plant (it reads ``$plant``)."""
    lines = [line.strip() for line in run_text(jobs(load(CONTRACTS_TEXT))["lint"]).splitlines() if line.strip().startswith("rule=$(")]
    assert len(lines) == 1, f"the lint step derives the expected rule in {len(lines)} places"
    return lines[0]


def rule_the_workflow_derives(plant: Path) -> str:
    import subprocess

    completed = subprocess.run(  # noqa: S603, S607 -- bash runs only the workflow's own derivation line over a fixture path
        ["bash", "-c", f'plant="$1"; {workflow_rule_derivation()}; printf "%s" "$rule"', "bash", str(plant)],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def plant_violations(directory: Path, rule_ids: set[str], derive: Callable[[Path], str]) -> list[str]:
    """Each plant must declare a rule of the ruleset, the workflow must derive exactly that rule, and the name must start with it."""
    problems = []
    plants = lint_plants(directory)
    assert plants, "no lint plant was found"
    for plant in plants:
        header = RULE_HEADER.match(plant.read_text(encoding="utf-8").splitlines()[0])
        declared = header.group(1) if header else ""
        if declared not in rule_ids:
            problems.append(f"{plant.name}: declares {declared!r}, which is not a rule of the ruleset")
        elif derive(plant) != declared:
            problems.append(f"{plant.name}: the workflow derives {derive(plant)!r}, not {declared!r}")
        elif plant.stem != declared and not plant.stem.startswith(declared + "-"):
            problems.append(f"{plant.name}: the file name does not start with its rule {declared}")
    return problems


def test_every_lint_plant_declares_its_rule_and_the_workflow_derives_exactly_that_rule() -> None:
    rule_ids = set(yaml.safe_load(RULESET_PATH.read_text(encoding="utf-8"))["rules"])

    assert plant_violations(VACUUM_PLANTS, rule_ids, rule_the_workflow_derives) == []
    variants = [path for path in lint_plants(VACUUM_PLANTS) if path.stem not in rule_ids]
    assert variants, "the variant plant naming scheme (<rule>-<variant>.yaml) is the case this guard exists for"
    assert 'basename "$plant" .yaml' not in run_text(jobs(load(CONTRACTS_TEXT))["lint"]), "the rule must not be derived from the file name"


def test_a_planted_variant_without_a_header_or_with_a_wrong_header_is_refused(tmp_path: Path) -> None:
    rule_ids = set(yaml.safe_load(RULESET_PATH.read_text(encoding="utf-8"))["rules"])
    body = (VACUUM_PLANTS / "property-described.yaml").read_text(encoding="utf-8").split("\n", 1)[1]
    (tmp_path / "property-described-variant.yaml").write_text("# rule: property-described\n" + body, encoding="utf-8")
    assert plant_violations(tmp_path, rule_ids, rule_the_workflow_derives) == []

    (tmp_path / "enum-case-bare.yaml").write_text(body, encoding="utf-8")
    (tmp_path / "operation-tags-wrong.yaml").write_text("# rule: no-such-rule\n" + body, encoding="utf-8")
    (tmp_path / "enum-case-misnamed.yaml").write_text("# rule: operation-tags\n" + body, encoding="utf-8")
    problems = plant_violations(tmp_path, rule_ids, rule_the_workflow_derives)

    assert len(problems) == 3
    assert any("enum-case-bare.yaml" in line and "''" in line for line in problems)
    assert any("operation-tags-wrong.yaml" in line and "no-such-rule" in line for line in problems)
    assert any("enum-case-misnamed.yaml" in line and "does not start with its rule" in line for line in problems)


def test_the_lint_cases_of_the_negative_manifest_expect_the_rule_their_plant_declares() -> None:
    cases = {case["id"]: case for case in json.loads((TOOLS_DIR / "negative_cases.json").read_text(encoding="utf-8"))["cases"]}
    by_plant = {}
    for case in cases.values():
        args = case["plant"].get("args", [])
        if case["tool"] == "lint_check.py" and "--file" in args:
            by_plant[Path(args[args.index("--file") + 1]).name] = case["plant"]["code"]
    for plant in lint_plants(VACUUM_PLANTS):
        declared = RULE_HEADER.match(plant.read_text(encoding="utf-8").splitlines()[0])
        assert declared is not None, plant.name
        assert by_plant.get(plant.name) == f": {declared.group(1)}: ", f"{plant.name} has no negative case expecting its own rule"


# -- the release workflow ----------------------------------------------------------------------------------------------------------


def test_release_trigger_rules() -> None:
    assert release_trigger_violations(RELEASE_TEXT) == []
    assert triggers(load(RELEASE_TEXT)).keys() == {"push", "workflow_dispatch"}


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("  workflow_dispatch:", "  pull_request:\n  workflow_dispatch:", "triggers are"),
        ("    tags:\n      - 'contract-*-v*.*.*'", "    branches: [main]\n    tags:\n      - 'contract-*-v*.*.*'", "push trigger"),
        ("        default: true", "        default: false", "dry_run"),
        ("'contract-*-v*.*.*'", "'contract-**'", "push trigger"),
    ],
)
def test_planted_release_trigger_violations_are_refused(old: str, new: str, reason: str) -> None:
    assert any(reason in problem for problem in release_trigger_violations(mutate(RELEASE_TEXT, old, new)))


def test_release_permissions_are_read_at_the_top_and_write_only_on_the_publish_job() -> None:
    assert release_permission_violations(RELEASE_TEXT) == []
    widened = mutate(RELEASE_TEXT, "permissions:\n  contents: read", "permissions:\n  contents: write")
    assert release_permission_violations(widened)
    no_write = load(RELEASE_TEXT)
    del jobs(no_write)["publish"]["permissions"]
    assert release_permission_violations(yaml.safe_dump(no_write))
    build_writes = load(RELEASE_TEXT)
    jobs(build_writes)["build"]["permissions"]["contents"] = "write"
    assert any("build job" in problem or "exactly one writer" in problem for problem in release_permission_violations(yaml.safe_dump(build_writes)))
    publish_more = load(RELEASE_TEXT)
    jobs(publish_more)["publish"]["permissions"]["actions"] = "write"
    assert any("more than contents: write" in problem for problem in release_permission_violations(yaml.safe_dump(publish_more)))


def test_the_release_job_carries_its_fork_guard_and_the_gate_carries_the_canonical_one() -> None:
    assert fork_guard_violations(RELEASE_TEXT, RELEASE_GUARD) == []
    assert normalise(jobs(load(RELEASE_TEXT))["build"]["if"]) == RELEASE_GUARD
    planted = mutate(RELEASE_TEXT, RELEASE_GUARD, "true")
    assert fork_guard_violations(planted, RELEASE_GUARD)


def test_publication_is_reachable_only_from_a_contract_tag_push() -> None:
    assert publish_violations(RELEASE_TEXT) == []
    (step,) = publish_steps(RELEASE_TEXT)
    assert normalise(step["if"]) == PUBLISH_CONDITION
    assert [evaluate_condition(step["if"], event, ref) for event, ref in PUBLISH_EVENTS] == [False, False, False, True]


def test_zero_publish_steps_fail_and_an_unconditional_or_dispatch_reachable_publish_is_refused() -> None:
    assert publish_violations(mutate(RELEASE_TEXT, 'gh release create "${args[@]}"', 'gh release view "${args[@]}"')) == ["no publish step"]
    unconditional = load(RELEASE_TEXT)
    for step in steps_of(jobs(unconditional)["publish"]):
        if "gh release create" in str(step.get("run", "")):
            del step["if"]
    assert any("publishes for" in problem for problem in publish_violations(yaml.safe_dump(unconditional)))
    on_dispatch = load(RELEASE_TEXT)
    for step in steps_of(jobs(on_dispatch)["publish"]):
        if "gh release create" in str(step.get("run", "")):
            step["if"] = "github.event_name == 'push' || github.event_name == 'workflow_dispatch'"
    assert any("publishes for" in problem for problem in publish_violations(yaml.safe_dump(on_dispatch)))


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ("--latest=false", "derives '--latest'"),
        ("--prerelease", "derives '--prerelease'"),
        ('--title "$GITHUB_REF_NAME"', "derives '--title'"),
        ('version="${GITHUB_REF_NAME##*-v}"', "derives '##*-v'"),
    ],
)
def test_a_publish_step_that_derives_its_own_release_arguments_is_refused(extra: str, reason: str) -> None:
    planted = mutate(RELEASE_TEXT, 'gh release create "${args[@]}"', f'gh release create "${{args[@]}}" {extra}')

    assert any(reason in problem for problem in publish_violations(planted))


def test_a_publish_step_that_does_not_consume_the_checked_arguments_is_refused() -> None:
    planted = mutate(RELEASE_TEXT, 'mapfile -t args < "$args_file"', "args=(contract-x-v1.0.0)")

    assert any("does not run the arguments release_check wrote" in problem for problem in publish_violations(planted))


def test_a_release_check_tag_step_that_writes_no_arguments_file_is_refused() -> None:
    planted = mutate(RELEASE_TEXT, ' --args-file "$RUNNER_TEMP/release-out/gh-release-args.txt"', "")

    assert any("writes gh-release-args.txt with --args-file" in problem for problem in publish_violations(planted))


def test_the_release_workflow_publishes_through_the_runner_gh_and_runs_release_check_on_the_tag() -> None:
    commands = "\n".join(str(step.get("run", "")) for step in release_steps(RELEASE_TEXT))

    for script in ("install_tools.py", "bundle.py", "release_check.py"):
        assert script in commands
    assert "release_check.py" in commands and "--tag" in commands
    assert "gh release create" in commands and "--prerelease" not in commands, "the prerelease flag is release_check's, not the workflow's"


def publish_job_violations(text: str) -> list[str]:
    """The publish job is the only writer: it needs build, runs on a contract tag push only, builds nothing and re-checks the tag."""
    found = jobs(load(text))
    job, build = found.get("publish"), found.get("build")
    if job is None or build is None:
        return ["the workflow has no build and publish job pair"]
    problems = []
    if needs_of(job) != frozenset({"build"}):
        problems.append(f"publish needs {sorted(needs_of(job))}, not exactly build")
    reached = (
        [(event, ref) for event, ref in PUBLISH_EVENTS if evaluate_condition(str(job.get("if", "true")), event, ref)] if job.get("if") else list(PUBLISH_EVENTS)
    )
    if reached != [PUBLISH_EVENTS[3]]:
        problems.append(f"the publish job runs for {reached}, not only a contract tag push")
    steps = steps_of(job)
    if any("checkout" in str(step.get("uses", "")) or "setup-uv" in str(step.get("uses", "")) or "contracts/tools" in str(step.get("run", "")) for step in steps):
        problems.append("the publish job checks out or runs repository code under its write token")
    names = [str(step.get("uses", "")).split("@")[0] for step in steps]
    if "actions/download-artifact" not in names:
        problems.append("the publish job does not download the build artifact")
    recheck = next((i for i, step in enumerate(steps) if "ls-remote" in str(step.get("run", ""))), None)
    create = next((i for i, step in enumerate(steps) if "gh release create" in str(step.get("run", ""))), None)
    if recheck is None or create is None or recheck > create:
        problems.append("the publish job does not re-check the remote tag before gh release create")
    elif '"$GITHUB_SHA"' not in str(steps[recheck]["run"]) or "exit 1" not in str(steps[recheck]["run"]):
        problems.append("the tag re-check does not fail unless the tag resolves to GITHUB_SHA")
    if create is not None and '--target "$GITHUB_SHA"' not in str(steps[create]["run"]):
        problems.append('gh release create does not pass --target "$GITHUB_SHA"')
    for step in steps:
        if "${{" in str(step.get("run", "")):
            problems.append(f"{step.get('name')}: an expression is interpolated into the script (pass it through env:)")
    if not any((s.get("with") or {}).get("name") == "contract-release-assets" for s in steps_of(build)):
        problems.append("the build job does not upload contract-release-assets")
    if any("gh release create" in str(step.get("run", "")) for step in steps_of(build)):
        problems.append("the build job (a read-only token) contains a publish step")
    return problems


def test_the_publish_job_is_the_only_writer_and_rechecks_the_tag() -> None:
    assert publish_job_violations(RELEASE_TEXT) == []


def test_the_publish_job_never_runs_for_a_dry_run_or_a_branch_push() -> None:
    condition = str(jobs(load(RELEASE_TEXT))["publish"]["if"])
    assert [evaluate_condition(condition, event, ref) for event, ref in PUBLISH_EVENTS] == [False, False, False, True]


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("    needs: build\n    if: github.event_name == 'push'", "    if: github.event_name == 'push'", "needs"),
        (
            "    if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')\n    runs-on: ubuntu-24.04\n    timeout-minutes: 10",
            "    runs-on: ubuntu-24.04\n    timeout-minutes: 10",
            "not only a contract tag push",
        ),
        ('if [ "$resolved" != "$GITHUB_SHA" ]; then', "if false; then", "does not fail unless the tag resolves"),
        ("git ls-remote", "git ls-files", "does not re-check the remote tag"),
        (' --target "$GITHUB_SHA"', "", "--target"),
        (
            "          TAG_NAME: ${{ github.ref_name }}\n        run: |\n          set -eu\n          resolved",
            "        run: |\n          TAG_NAME=${{ github.ref_name }}\n          set -eu\n          resolved",
            "interpolated",
        ),
        ("      - uses: actions/download-artifact@", "      - uses: actions/checkout@", "download the build artifact"),
    ],
)
def test_planted_publish_job_weakenings_are_refused(old: str, new: str, reason: str) -> None:
    assert any(reason in problem for problem in publish_job_violations(mutate(RELEASE_TEXT, old, new))), reason


def test_a_publish_step_in_the_build_job_is_refused() -> None:
    planted = load(RELEASE_TEXT)
    jobs(planted)["build"]["steps"].append({"name": "x", "run": "gh release create x"})
    assert any("read-only token" in problem for problem in publish_job_violations(yaml.safe_dump(planted)))


def test_a_tag_push_publishes_only_a_commit_on_main_that_contracts_passed_on_after_breaking_check() -> None:
    assert release_gate_violations(RELEASE_TEXT) == []


def _without_steps(text: str, token: str) -> str:
    planted = load(text)
    for job in jobs(planted).values():
        job["steps"] = [step for step in steps_of(job) if token not in str(step.get("run", ""))]
    return yaml.safe_dump(planted)


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        ("merge-base --is-ancestor", "is-ancestor-of-origin/main"),
        ("workflows/contracts.yml/runs", "Contracts-success check"),
        ("--release-tag", "breaking_check.py --release-tag"),
    ],
)
def test_a_release_workflow_without_one_of_the_gates_is_refused(token: str, reason: str) -> None:
    assert any(reason in problem for problem in release_gate_violations(_without_steps(RELEASE_TEXT, token)))


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        (
            "            exit 1\n          fi\n      - uses: astral-sh/setup-uv",
            "            exit 0\n          fi\n      - uses: astral-sh/setup-uv",
            "is-ancestor-of-origin/main",
        ),
        ("          fetch-depth: 0  # every branch", "          fetch-depth: 1  # every branch", "full history"),
        ("      actions: read  # to read", "      checks: read  # to read", "workflow runs"),
        (
            "        if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')\n        run: |\n          set -eu\n          if ! git",
            "        run: |\n          set -eu\n          if ! git",
            "does not run on exactly a contract tag push",
        ),
    ],
)
def test_planted_release_gate_weakenings_are_refused(old: str, new: str, reason: str) -> None:
    assert any(reason in problem for problem in release_gate_violations(mutate(RELEASE_TEXT, old, new)))


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("&event=push", "", "event=push"),
        ("&branch=main", "", "branch=main"),
        ("head_sha=${base}", "head_sha=${GITHUB_SHA}", "queries the tagged SHA"),
        ('-- "${paths[@]}"', "", "does not resolve the last commit"),
        ("git log -1 --format=%H", "git rev-parse", "does not resolve the last commit"),
        (DERIVE_PATHS_CALL, "printf 'contracts/**\\n'", "hand-copies"),
    ],
)
def test_planted_weakenings_of_the_contracts_success_lookup_are_refused(old: str, new: str, reason: str) -> None:
    assert any(reason in problem for problem in release_gate_violations(mutate(RELEASE_TEXT, old, new)))


def derived_trigger_paths(release_text: str, contracts_text: str, workdir: Path) -> list[str]:
    """Run the release workflow's own path derivation over a given contracts.yml and return the lines it prints."""
    import subprocess
    import sys

    gate = next(step for step in steps_of(jobs(load(release_text))["build"]) if "workflows/contracts.yml/runs" in str(step.get("run", "")))
    line = next(line.strip() for line in str(gate["run"]).splitlines() if "python -c" in line)
    command = line.replace("uv run --frozen --no-sync python", f'"{sys.executable}"', 1).split(' > "', 1)[0]
    (workdir / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (workdir / ".github" / "workflows" / "contracts.yml").write_text(contracts_text, encoding="utf-8")
    completed = subprocess.run(["bash", "-c", command], cwd=workdir, capture_output=True, text=True, check=True)  # noqa: S603, S607 -- the workflow's own line over a copy
    return completed.stdout.splitlines()


def test_the_release_gate_looks_up_the_commit_by_the_path_list_of_contracts_yml(tmp_path: Path) -> None:
    pushed = triggers(load(CONTRACTS_TEXT))["push"]["paths"]

    assert pushed == EXPECTED_PATHS
    assert derived_trigger_paths(RELEASE_TEXT, CONTRACTS_TEXT, tmp_path) == pushed


def test_a_derived_gate_follows_a_drifted_path_list_and_a_copied_list_is_refused(tmp_path: Path) -> None:
    drifted = mutate(CONTRACTS_TEXT, "  push:\n    branches: [main]\n    paths:\n", "  push:\n    branches: [main]\n    paths:\n      - 'extra/**'\n")

    assert derived_trigger_paths(RELEASE_TEXT, drifted, tmp_path)[0] == "extra/**"
    literal = RELEASE_TEXT.replace(
        DERIVE_PATHS_CALL,
        "printf 'contracts/**\\ntests/contract/**\\n'",
        1,
    )
    assert literal != RELEASE_TEXT
    assert any("hand-copies" in problem for problem in release_gate_violations(literal))


def test_the_release_gate_steps_run_before_the_publish_step() -> None:
    steps = release_steps(RELEASE_TEXT)
    publish = next(i for i, step in enumerate(steps) if "gh release create" in str(step.get("run", "")))
    moved = load(RELEASE_TEXT)
    build = jobs(moved)["build"]
    gate = next(step for step in steps_of(build) if "merge-base" in str(step.get("run", "")))
    build["steps"] = [step for step in steps_of(build) if step is not gate]
    jobs(moved)["publish"]["steps"].append(gate)
    assert publish > 0 and any("runs after the publish step" in problem for problem in release_gate_violations(yaml.safe_dump(moved)))


# -- the terminal gate script ---------------------------------------------------------------------------------------------------------


def test_the_real_gate_script_fails_on_any_result_that_is_not_success() -> None:
    assert gate_script_violations(CONTRACTS_TEXT) == []


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ('[ "$result" != "success" ]', '[ "$result" = "failure" ]', 'does not compare each result with != "success"'),
        ('[ "$result" != "success" ]', '[ "$result" = "failure" ] || [ "$result" = "cancelled" ]', "is tolerant"),
        ("              exit 1\n", "              true\n", "no exit 1"),
        ("join(needs.*.result, ' ')", "needs.verify-pins.result", "does not read every needed job result"),
        ('echo "needed job results: $RESULTS"', 'echo "needed job results: $RESULTS"; set +e', "is tolerant"),
    ],
)
def test_a_tolerant_gate_script_is_refused(old: str, new: str, reason: str) -> None:
    assert any(reason in problem for problem in gate_script_violations(mutate(CONTRACTS_TEXT, old, new)))


# -- the tag namespace guard ---------------------------------------------------------------------------------------------------------


def test_the_filter_matcher_follows_github_semantics_not_fnmatch() -> None:
    assert filter_matches("v*.*.*", "v3.2.7")
    assert not filter_matches("a*", "a/b"), "a single star does not cross a slash"
    assert filter_matches("a**", "a/b"), "a double star does"
    assert filter_matches(CONTRACT_TAG_FILTER, "contract-mission-status-v1.0.0")
    assert not filter_matches(CONTRACT_TAG_FILTER, "contract-mission/status-v1.0.0")


def test_the_contract_and_cli_tag_namespaces_are_disjoint_and_preview_tags_match_neither() -> None:
    assert cli_tag_filters(CLI_RELEASE_PATH.read_text(encoding="utf-8")) == ["v*.*.*"]
    assert namespace_violations(RELEASE_TEXT, CLI_RELEASE_PATH.read_text(encoding="utf-8")) == []


def test_a_planted_overlapping_or_empty_tag_filter_is_refused() -> None:
    cli = CLI_RELEASE_PATH.read_text(encoding="utf-8")
    assert any("contract release filter matches" in problem for problem in namespace_violations(mutate(RELEASE_TEXT, "'contract-*-v*.*.*'", "'**'"), cli))
    assert any("preview tag" in problem for problem in namespace_violations(RELEASE_TEXT, mutate(cli, "'v*.*.*'", "'**'")))
    assert any("empty tag filter" in problem for problem in namespace_violations(RELEASE_TEXT, mutate(cli, "    tags:\n      - 'v*.*.*'\n", "")))
    slash_filter = mutate(RELEASE_TEXT, "'contract-*-v*.*.*'", "'contract-**-v*.*.*'")
    assert any("matches contract-mission/status" in problem for problem in namespace_violations(slash_filter, cli))


def test_the_tool_test_job_is_a_router_job_that_runs_the_corpus_marker_over_tests_contract_with_the_prelude() -> None:
    job = jobs(load(ROUTER_TEXT))[TOOL_TEST_JOB]
    commands = [line for line in run_text(job).replace("\\\n", " ").splitlines() if re.search(r"(?<![\w-])pytest(?![\w-])", line)]

    assert job["name"] == "tests (contract tools)"
    assert len(commands) == 1, f"expected exactly one pytest command, found {commands}"
    assert "uv run --frozen --no-sync pytest" in commands[0]
    assert '-m "corpus and not windows_ci"' in commands[0]
    assert re.search(r"\stests/contract/?(?=\s)", commands[0]), "the job must select the whole tests/contract directory"
    assert "--ignore=tests/contract/test_example_round_trip.py" in commands[0], "the example round trip belongs to the corpus-blocking job"
    assert needs_of(job) == frozenset({"changes"})
    assert "uv sync --frozen --no-install-project" in run_text(job)
    assert all(re.fullmatch(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}", str(step["uses"])) for step in steps_of(job) if "uses" in step)


def test_the_tool_test_job_is_a_required_router_dependency_gated_on_the_contract_path_groups() -> None:
    workflow = load(ROUTER_TEXT)
    assert TOOL_TEST_JOB in needs_of(jobs(workflow)["router-gate"]), "router-gate must wait for the contract tool tests"
    condition = normalise(jobs(workflow)[TOOL_TEST_JOB]["if"])
    assert condition == "needs.changes.outputs.corpus == 'true' || needs.changes.outputs.contract_tools == 'true'"
    outputs = jobs(workflow)["changes"]["outputs"]
    assert "contract_tools" in outputs and "inputs.mode == 'full'" in str(outputs["contract_tools"]), "mode=full runs it"


def test_the_contract_tools_filter_group_names_the_paths_the_contracts_workflow_triggers_on_beyond_contracts() -> None:
    filters = yaml.safe_load(next(step for step in steps_of(jobs(load(ROUTER_TEXT))["changes"]) if step.get("id") == "filter")["with"]["filters"])
    group = filters["contract_tools"]
    beyond_contracts = [path for path in EXPECTED_PATHS if path not in ("contracts/**", ".github/CODEOWNERS")]
    # The lifecycle source is spelled without its src/ prefix so the group stays non-src (a src glob would make it a code-shard gate).
    spelled = ["**/status/lifecycle_events.py" if path == "src/specify_cli/status/lifecycle_events.py" else path for path in beyond_contracts]
    spelled += [glob for glob in group if glob.startswith("**/") and glob != "**/status/lifecycle_events.py"]  # the reader's src imports: their own test pins them
    assert sorted(group) == sorted(spelled), "the router group and the Contracts workflow trigger list must not drift"
    assert not any(glob.startswith("src/") for glob in group), "a src glob would make the group a code-shard gate"
    assert "contracts/**" in filters["corpus"], "contracts/** stays owned by the corpus group"


_SRC_ROOT = REPO_ROOT / "src"
_SRC_PACKAGES = frozenset(entry.name for entry in _SRC_ROOT.iterdir() if entry.is_dir() and not entry.name.startswith((".", "_")))


def _src_files_imported_by_the_mission_status_contract_tests() -> set[str]:
    """The ``src/`` files that the mission-status reference reader and its tests import (``tests/contract/*mission_status*.py``)."""
    imported: set[str] = set()
    for module_file in sorted((REPO_ROOT / "tests" / "contract").glob("*mission_status*.py")):
        for node in ast.walk(ast.parse(module_file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module, *(f"{node.module}.{alias.name}" for alias in node.names)]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            for name in names:
                if name.split(".")[0] not in _SRC_PACKAGES:
                    continue
                base = Path("src", *name.split("."))
                for candidate in (base.with_suffix(".py"), base / "__init__.py"):
                    if (REPO_ROOT / candidate).is_file():
                        imported.add(candidate.as_posix())
    return imported


def _src_files_cited_by_the_contract_x_derived_blocks() -> set[str]:
    """The ``src/`` files the mission-status contract cites as ``x-derived`` inputs (``path: src/...``)."""
    cited: set[str] = set()
    for contract_file in (REPO_ROOT / "contracts" / "mission-status").rglob("*.yaml"):
        cited.update(re.findall(r"path: (src/[A-Za-z0-9_/]+\.py)", contract_file.read_text(encoding="utf-8")))
    return cited


def _group_selects(group: list[str], path: str) -> bool:
    """True when a ``**/<tail>`` glob of the group names ``path`` (the group spells src files without their ``src/`` prefix)."""
    return any(glob.startswith("**/") and path.endswith("/" + glob[3:]) for glob in group)


def test_the_contract_tools_filter_group_names_every_src_file_the_mission_status_reader_its_tests_import_and_the_contract_cites() -> None:
    filters = yaml.safe_load(next(step for step in steps_of(jobs(load(ROUTER_TEXT))["changes"]) if step.get("id") == "filter")["with"]["filters"])
    group = filters["contract_tools"]
    imported = _src_files_imported_by_the_mission_status_contract_tests()
    assert len(imported) > 20, f"the import scan found too little: {sorted(imported)}"
    cited = _src_files_cited_by_the_contract_x_derived_blocks()
    assert "src/specify_cli/cli/commands/invocations_cmd.py" in cited, "the x-derived scan found nothing it should"
    imported |= cited  # a file the contract cites is as much an input of the contract check as one the reader imports
    missing = sorted(path for path in imported if not _group_selects(group, path))
    assert missing == [], f"a change to these imported src files selects no `tests (contract tools)` run: {missing}"


def test_contracts_yml_no_longer_hosts_the_tool_tests() -> None:
    workflow = load(CONTRACTS_TEXT)
    assert TOOL_TEST_JOB not in jobs(workflow) and "contract-tool-tests" not in jobs(workflow)
    assert "contract-tool-tests" not in needs_of(jobs(workflow)["contracts-gate"])
    assert "pytest" not in run_text({"steps": all_steps(workflow)}).replace("no_pytest_scan", "")


# -- the tool-test job and the one home of every tests/contract module -----------------------------


ROUTER_CORPUS_JOB = "tests-corpus-blocking"
CONTRACT_TESTS_DIR = REPO_ROOT / "tests" / "contract"
TOOL_TEST_MARKER = "corpus and not windows_ci"
# The modules the router's corpus job owns: the two that read the committed corpus, plus the example round trip,
# which was a router corpus module before the contracts mission and is not a contract tool test.
ROUTER_CONTRACT_MODULES = frozenset(
    {
        "tests/contract/test_example_round_trip.py",
        "tests/contract/test_mission_status_payloads.py",
        "tests/contract/test_mission_status_reality.py",
    }
)


def pytest_command_of(job: dict[str, Any]) -> str:
    """The one logical ``pytest`` command of a job, continuation lines joined."""
    logical = run_text(job).replace("\\\n", " ")
    commands = [line for line in logical.splitlines() if re.search(r"(?<![\w-])pytest(?![\w-])", line)]
    assert len(commands) == 1, f"expected exactly one pytest command, found {commands}"
    return commands[0]


def router_contract_modules(router_text: str) -> frozenset[str]:
    """The ``tests/contract`` modules the router's corpus job names."""
    command = pytest_command_of(jobs(load(router_text))[ROUTER_CORPUS_JOB])
    return frozenset(re.findall(r"tests/contract/test_\w+\.py", command))


def tool_job_ignores(router_text: str) -> frozenset[str]:
    """The modules the router's tool-test job ignores; it selects the rest of ``tests/contract``."""
    command = pytest_command_of(jobs(load(router_text))[TOOL_TEST_JOB])
    assert re.search(r"\stests/contract/?(?=\s)", command), "the tool-test job must select the whole tests/contract directory"
    return frozenset(re.findall(r"--ignore=(\S+)", command))


def homes_of(module: str, corpus_modules: frozenset[str], router_modules: frozenset[str], ignored: frozenset[str]) -> list[str]:
    """Which of the router's corpus job and its tool-test job run *module* (both select ``-m corpus``).

    *corpus_modules* is the REAL collected set, so an indirectly applied mark (a shared ``pytestmark`` list, a helper, a
    ``conftest`` hook) counts like a literal ``@pytest.mark.corpus``. An unmarked module is deselected by both and is the
    module matrix's, so it has neither home here.
    """
    if module not in corpus_modules:
        return []
    homes = []
    if module in router_modules:
        homes.append("router corpus job")
    if module not in ignored:
        homes.append("router tool-test job")
    return homes


def home_problems(modules: frozenset[str], corpus_modules: frozenset[str], router_modules: frozenset[str], ignored: frozenset[str]) -> list[str]:
    problems = []
    for module in sorted(modules):
        homes = homes_of(module, corpus_modules, router_modules, ignored)
        if module in corpus_modules and len(homes) != 1:
            problems.append(f"{module} is run by {homes or 'nothing'}")
    for name in sorted(ignored | router_modules):
        if name not in modules:
            problems.append(f"{name} is named by a job but is not a tests/contract module")
    return problems


def live_contract_modules() -> frozenset[str]:
    found = frozenset(f"tests/contract/{path.name}" for path in sorted(CONTRACT_TESTS_DIR.glob("test_*.py")))
    assert found, "no tests/contract module was found"
    return found


_collected_corpus_modules: list[frozenset[str]] = []


def collected_corpus_modules() -> frozenset[str]:
    """The ``tests/contract`` modules that really collect a test under the jobs' marker: ``pytest --collect-only -q -m ... tests/contract``.

    Collected once per session through the same helper ``test_corpus_blocking_home`` uses, so a mark applied by any means is seen.
    """
    if not _collected_corpus_modules:
        probe = gc.Gate(workflow="probe", job="probe", shard=None, paths=["tests/contract"], marker_expr=TOOL_TEST_MARKER)
        nodeids = gc.collect_job_nodeids(probe)
        _collected_corpus_modules.append(frozenset(nodeid.split("::", 1)[0] for nodeid in nodeids if nodeid.startswith("tests/contract/")))
    modules = _collected_corpus_modules[0]
    assert modules, "non-vacuity: the corpus marker collected no tests/contract module"
    return modules


def test_the_tool_test_job_ignores_exactly_the_contract_modules_the_router_owns() -> None:
    assert tool_job_ignores(ROUTER_TEXT) == ROUTER_CONTRACT_MODULES


def test_the_router_corpus_job_runs_exactly_the_contract_modules_it_owns() -> None:
    assert router_contract_modules(ROUTER_PATH.read_text(encoding="utf-8")) == ROUTER_CONTRACT_MODULES


def test_every_corpus_marked_contract_module_has_exactly_one_home() -> None:
    modules = live_contract_modules()
    corpus = collected_corpus_modules()
    router = router_contract_modules(ROUTER_PATH.read_text(encoding="utf-8"))
    ignored = tool_job_ignores(ROUTER_TEXT)

    assert corpus <= modules
    assert home_problems(modules, corpus, router, ignored) == []
    # Non-vacuity: both homes really run something, and the tool-test job runs a module the router does not.
    assert any(homes_of(name, corpus, router, ignored) == ["router corpus job"] for name in modules)
    assert sum(homes_of(name, corpus, router, ignored) == ["router tool-test job"] for name in modules) >= 20


def test_a_planted_new_module_that_nothing_runs_is_refused() -> None:
    modules, corpus = live_contract_modules(), collected_corpus_modules()
    router = router_contract_modules(ROUTER_PATH.read_text(encoding="utf-8"))
    ignored = tool_job_ignores(ROUTER_TEXT)
    planted = "tests/contract/test_planted_unrun.py"

    assert home_problems(modules | {planted}, corpus | {planted}, router, ignored | {planted}) == [f"{planted} is run by nothing"]
    assert home_problems(modules | {planted}, corpus | {planted}, router, ignored) == [], "control: left alone, the tool-test job runs a new module"


def test_a_planted_module_that_two_jobs_run_is_refused() -> None:
    modules, corpus = live_contract_modules(), collected_corpus_modules()
    router = router_contract_modules(ROUTER_PATH.read_text(encoding="utf-8"))
    ignored = tool_job_ignores(ROUTER_TEXT)
    planted = "tests/contract/test_planted_twice.py"

    problems = home_problems(modules | {planted}, corpus | {planted}, router | {planted}, ignored)

    assert problems == [f"{planted} is run by ['router corpus job', 'router tool-test job']"]


def test_a_module_with_an_unmarked_source_and_a_real_corpus_collection_is_still_judged(tmp_path: Path) -> None:
    """The mark can arrive without the literal text ``pytest.mark.corpus`` in the module: only the real collection sees it."""
    plugin = tmp_path / "indirect_mark.py"
    plugin.write_text('import pytest\nMARKS = [getattr(pytest.mark, "cor" + "pus")]\n', encoding="utf-8")
    planted = tmp_path / "test_indirect.py"
    planted.write_text("import indirect_mark\nimport pytest\n\npytestmark = indirect_mark.MARKS\n\n\ndef test_x() -> None:\n    pass\n", encoding="utf-8")
    assert "pytest.mark.corpus" not in planted.read_text(encoding="utf-8")
    probe = gc.Gate(workflow="probe", job="probe", shard=None, paths=[str(planted)], marker_expr=TOOL_TEST_MARKER)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PYTHONPATH", str(tmp_path))
        collected = gc.collect_job_nodeids(probe)
    assert collected, "the indirectly applied corpus mark must be collected under the jobs' marker"
    name = "tests/contract/test_indirect.py"
    modules, corpus = live_contract_modules() | {name}, collected_corpus_modules() | {name}
    router = router_contract_modules(ROUTER_PATH.read_text(encoding="utf-8"))
    assert home_problems(modules, corpus, router, tool_job_ignores(ROUTER_TEXT) | {name}) == [f"{name} is run by nothing"]


def test_a_job_naming_a_module_that_does_not_exist_is_refused() -> None:
    modules, corpus = live_contract_modules(), collected_corpus_modules()
    router = router_contract_modules(ROUTER_PATH.read_text(encoding="utf-8"))
    ignored = tool_job_ignores(ROUTER_TEXT)

    problems = home_problems(modules, corpus, router, ignored | {"tests/contract/test_renamed_away.py"})

    assert problems == ["tests/contract/test_renamed_away.py is named by a job but is not a tests/contract module"]


# -- the planted breaking changes ---------------------------------------------------------------------------------------------------------

BREAKING_CANDIDATES = TOOLS_DIR / "fixtures" / "breaking_check" / "candidates"
NOT_PLANTS_IN_THE_LOOP = frozenset({"clean_same", "clean_minor", "provisional_only", "changed_same_version"})  # controls and the same-version plant


def breaking_plant_loop_violations(text: str, candidates: set[str]) -> list[str]:
    """The plant loop of the breaking-change job must name exactly the candidate directories that are not controls."""
    script = run_text(jobs(load(text))["breaking-change"])
    loops = re.findall(r"^\s*for name in ([^;]+); do\s*\n\s*echo \"== plant \$name\"", script, flags=re.MULTILINE)
    if len(loops) != 1:
        return [f"the breaking-change job has {len(loops)} plant loops, not one"]
    named = loops[0].split()
    problems = [f"the plant loop names {name}, which is not a candidate fixture directory" for name in sorted(set(named) - candidates)]
    problems += [f"the plant loop does not run the candidate fixture {name}" for name in sorted(candidates - NOT_PLANTS_IN_THE_LOOP - set(named))]
    problems += [f"the plant loop names {name} twice" for name in sorted({n for n in named if named.count(n) > 1})]
    return problems


def breaking_candidates() -> set[str]:
    return {path.name for path in BREAKING_CANDIDATES.iterdir() if path.is_dir()}


def test_the_breaking_plant_loop_covers_exactly_the_candidate_fixture_directories() -> None:
    assert len(breaking_candidates() - NOT_PLANTS_IN_THE_LOOP) >= 12, "the planted candidates were not found"
    assert breaking_plant_loop_violations(CONTRACTS_TEXT, breaking_candidates()) == []


def test_a_candidate_fixture_missing_from_or_extra_to_the_plant_loop_is_refused() -> None:
    dropped = mutate(CONTRACTS_TEXT, " added_response_header; do", "; do")
    assert breaking_plant_loop_violations(dropped, breaking_candidates()) == ["the plant loop does not run the candidate fixture added_response_header"]
    extra = mutate(CONTRACTS_TEXT, " added_response_header; do", " added_response_header no_such_dir; do")
    assert breaking_plant_loop_violations(extra, breaking_candidates()) == ["the plant loop names no_such_dir, which is not a candidate fixture directory"]
    assert breaking_plant_loop_violations(CONTRACTS_TEXT, breaking_candidates() | {"unlisted_plant"}) == [
        "the plant loop does not run the candidate fixture unlisted_plant"
    ]


def test_every_planted_breaking_candidate_has_a_negative_case() -> None:
    manifest = json.loads((TOOLS_DIR / "negative_cases.json").read_text(encoding="utf-8"))
    by_root = {}
    for case in manifest["cases"]:
        args = case["plant"].get("args", [])
        if case["tool"] == "breaking_check.py" and "--root" in args:
            by_root[Path(args[args.index("--root") + 1]).name] = case
    for name in sorted(breaking_candidates() - NOT_PLANTS_IN_THE_LOOP):
        case = by_root.get(name)
        assert case is not None, f"{name} has no negative case in negative_cases.json"
        assert case["plant"]["code"] == "BREAKING_WITHOUT_MAJOR", name
        assert "oasdiff" in case.get("tags", []), name
