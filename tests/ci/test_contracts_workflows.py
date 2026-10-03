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
EXPECTED_PATHS = ["contracts/**", ".github/CODEOWNERS", ".github/workflows/contracts.yml"]

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


def pytest_violations(text: str, read: Callable[[str], str] | None = None) -> list[str]:
    """Pytest reachable from a step: named directly, through ``make``, or inside a script the step runs."""
    read_script = read or (lambda name: (REPO_ROOT / name).read_text(encoding="utf-8"))
    problems = []
    steps = all_steps(load(text))
    assert steps, "no step was scanned"
    for step in steps:
        command = f"{step.get('run', '')} {step.get('uses', '')}"
        if re.search(r"(?<![\w-])pytest(?![\w-])", command, re.IGNORECASE):
            problems.append(f"pytest named in a step: {command.strip()[:80]}")
        if re.search(r"(?:^|[\s;&|(])make\b", str(step.get("run", ""))):
            problems.append("a step runs make, which may reach pytest")
        for script in re.findall(r"contracts/tools/[\w/]+\.py", str(step.get("run", ""))):
            if _RUNNER_REFERENCE.search(read_script(script)):
                problems.append(f"{script} mentions pytest")
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
        if "--latest=false" not in str(step["run"]):
            problems.append(f"{step.get('name')}: no --latest=false")
        run = str(step["run"])
        if "--prerelease" in run and not re.search(r'case "\$version" in \*-\*\)[^;]*--prerelease', run):
            problems.append(f"{step.get('name')}: --prerelease is not conditional on a prerelease semver")
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
    writers = [name for name, job in jobs(workflow).items() if (job.get("permissions") or {}).get("contents") == "write"]
    if len(jobs(workflow)) != 1 or len(writers) != 1:
        problems.append(f"expected exactly one job holding contents: write, found {writers} of {len(jobs(workflow))}")
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
    assert len(jobs(load(RELEASE_TEXT))) == 1


def test_contracts_workflow_triggers_are_exactly_the_three_paths_on_both_triggers() -> None:
    assert trigger_violations(CONTRACTS_TEXT) == []


@pytest.mark.parametrize(
    ("old", "new", "reason"),
    [
        ("  pull_request:\n    paths:", "  pull_request:\n    branches: [main]\n    paths:", "carries a branches key"),
        ("    branches: [main]\n", "", "does not carry branches: [main]"),
        ("      - '.github/CODEOWNERS'\n      - '.github/workflows/contracts.yml'\n  push:", "      - '.github/workflows/contracts.yml'\n  push:", "paths are"),
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
    assert "github.ref" in str(load(CONTRACTS_TEXT)["concurrency"]["group"])
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
    bare = mutate(CONTRACTS_TEXT, "uv run --frozen --no-sync python contracts/tools/verify_pins.py", "python contracts/tools/verify_pins.py")
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
def test_pytest_is_unreachable_from_every_step(text: str) -> None:
    assert pytest_violations(text) == []


def test_planted_pytest_reachability_is_refused() -> None:
    direct = mutate(CONTRACTS_TEXT, "    steps:\n", "    steps:\n      - run: uv run pytest tests/contract\n")
    assert any("pytest named" in problem for problem in pytest_violations(direct))
    through_make = mutate(CONTRACTS_TEXT, "    steps:\n", "    steps:\n      - run: make test\n")
    assert any("runs make" in problem for problem in pytest_violations(through_make))
    through_script = pytest_violations(CONTRACTS_TEXT, read=lambda name: "import pytest\n")
    assert any("mentions pytest" in problem for problem in through_script)


# -- the content of the jobs ------------------------------------------------------------------------------------------------


def test_python_checks_runs_the_ten_scripts_in_order_and_the_enum_pin_check_uses_its_default_pin() -> None:
    commands = run_text(jobs(load(CONTRACTS_TEXT))["python-checks"])
    scripts = re.findall(r"contracts/tools/(\w+\.py)", commands)

    assert tuple(scripts) == PYTHON_CHECK_SCRIPTS
    (enum_line,) = [line for line in commands.splitlines() if "enum_pin_check.py" in line]
    assert "--pins" not in enum_line, "the enum pin check must read its default pin file"
    pins = json.loads((TOOLS_DIR / "enum_pins.json").read_text(encoding="utf-8"))
    assert pins and all(values for module in pins.values() for values in module.values()), "the default pin file is empty"


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


def test_release_permissions_are_read_at_the_top_and_write_on_the_one_job() -> None:
    assert release_permission_violations(RELEASE_TEXT) == []
    widened = mutate(RELEASE_TEXT, "permissions:\n  contents: read", "permissions:\n  contents: write")
    assert release_permission_violations(widened)
    no_write = load(RELEASE_TEXT)
    del jobs(no_write)["release"]["permissions"]
    assert release_permission_violations(yaml.safe_dump(no_write))


def test_the_release_job_carries_its_fork_guard_and_the_gate_carries_the_canonical_one() -> None:
    assert fork_guard_violations(RELEASE_TEXT, RELEASE_GUARD) == []
    assert normalise(jobs(load(RELEASE_TEXT))["release"]["if"]) == RELEASE_GUARD
    planted = mutate(RELEASE_TEXT, RELEASE_GUARD, "true")
    assert fork_guard_violations(planted, RELEASE_GUARD)


def test_publication_is_reachable_only_from_a_contract_tag_push() -> None:
    assert publish_violations(RELEASE_TEXT) == []
    (step,) = publish_steps(RELEASE_TEXT)
    assert normalise(step["if"]) == PUBLISH_CONDITION
    assert [evaluate_condition(step["if"], event, ref) for event, ref in PUBLISH_EVENTS] == [False, False, False, True]


def test_zero_publish_steps_fail_and_a_missing_latest_false_or_condition_is_refused() -> None:
    assert publish_violations(mutate(RELEASE_TEXT, "gh release create", "gh release view")) == ["no publish step"]
    assert any("--latest=false" in problem for problem in publish_violations(mutate(RELEASE_TEXT, "--latest=false", "--latest")))
    unconditional = load(RELEASE_TEXT)
    for step in steps_of(jobs(unconditional)["release"]):
        if "gh release create" in str(step.get("run", "")):
            del step["if"]
    assert any("publishes for" in problem for problem in publish_violations(yaml.safe_dump(unconditional)))
    on_dispatch = mutate(RELEASE_TEXT, PUBLISH_CONDITION, "github.event_name == 'push' || github.event_name == 'workflow_dispatch'")
    assert any("publishes for" in problem for problem in publish_violations(on_dispatch))


def test_the_release_workflow_publishes_through_the_runner_gh_and_runs_release_check_on_the_tag() -> None:
    commands = run_text(jobs(load(RELEASE_TEXT))["release"])

    for script in ("install_tools.py", "bundle.py", "release_check.py"):
        assert script in commands
    assert "release_check.py" in commands and "--tag" in commands
    assert "--prerelease" in commands


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
