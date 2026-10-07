"""Pure proofs of the additive slice of the ``mission-status`` contract (FR-017 to FR-020, FR-022, FR-023, FR-024, FR-027, FR-029).

The module reads no release tag, no history and starts no subprocess: every proof is a pure function over a
directory tree or a list, and every function has planted negatives on scratch data. The contract is unreleased
(``1.0.0-SNAPSHOT``, never tagged) and this slice ships in that same release: there is no new version.

Which proofs are tests and which are wrap-up commands. Tests (this module, pure): the extended scratch pair (the
candidate without the ``/drift`` and ``/ops/invocations`` path keys and the ``Drift`` and ``Ops`` tags, with the
three frozen pre-slice ``Project`` files swapped in, is the baseline; byte identity for everything outside
``CHANGED_ALLOWED``; the bundle comparison under the masking rule of ``_bundle_problems``), the section-scoped
CHANGELOG checks (headings, deferred gaps, statements, the four qualified provisional names, every reported
provisional token), the scope function over the slice data, the dependency check and the citation pins. Wrap-up
commands (they need ``oasdiff``, full history and scratch copies this pure module lacks, and are recorded by the
orchestrator): the ``git diff --exit-code <baseline sha> -- contracts/mission-status`` outside the slice file set,
the ``--baseline-root`` runs of ``breaking_check.py`` over a scratch copy of the main tree (a lowered-major run that
reports exactly the four breaking additions of ``Project`` and a same-major run that refuses them, because
``breaking_check.py`` refuses any bundle change against a baseline of the same version), the ancestor check of the
baseline commit, the scope check over the real ``git diff --name-status`` and the replay of the contract workflow
jobs. The frozen copies under ``tests/contract/fixtures/mission_status_pre_slice/`` are ``git show`` of the baseline
commit, never typed; ``cmp`` against it is a wrap-up command.

Lifetime: the assertion that ``info.version`` equals the version on ``main`` (``1.0.0-SNAPSHOT``) belongs to this
slice. The release process or the next Mission that changes the contract replaces it.
"""

from __future__ import annotations

import copy
import functools
import re
import shutil
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

import pytest
import yaml

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

OPENAPI_FILE = "openapi.yaml"
LEAK_PATTERNS_TOOL = "leak_patterns"
LEAK_SCAN_PATH = "contracts/tools/leak_scan.py"
PACKS_WORKFLOW_PATH = ".github/workflows/packs.yml"
ROUTER_WORKFLOW_PATH = ".github/workflows/ci-router.yml"
FIXTURE_BUILDER_PATH = "contracts/tools/fixture_builder.py"
PROJECT_SCHEMA_PATH = "contracts/mission-status/schemas/Project.yaml"

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
MODULE = CONTRACTS / "mission-status"
TOOLS = CONTRACTS / "tools"
CHANGELOG = MODULE / "CHANGELOG.md"
OPENAPI = MODULE / OPENAPI_FILE

MAIN_VERSION = "1.0.0-SNAPSHOT"  # the version of the contract tree on main: this slice does not change it
ENTRY_PREFIX = MAIN_VERSION
ENTRY_HEADINGS = ("Added", "Changed", "Removed", "Provisional", "Deferred to the next major version")
DEFERRED_HEADING = "Deferred to the next major version"
PROVISIONAL_HEADING = "Provisional"
ADDED_HEADING = "Added"
# the three gaps still deferred, each a tuple of strings the Deferred section must hold
DEFERRED_GAPS: dict[str, tuple[str, ...]] = {
    "per-Mission staleness": ("per-Mission staleness", "MissionOverview"),
    "actor on WorkPackageSummary": ("actor on `WorkPackageSummary`",),
    "lane weights": ("lane weights", "weightedPercentage"),
}
# the two behaviours of the artifact reads that a reader of the replaced dashboard routes should know
READ_BEHAVIOURS: dict[str, tuple[str, ...]] = {
    "invalid UTF-8 is a 415": ("invalid UTF-8", "415"),
    "root status records are not artifacts": ("status.events.jsonl", "status.json", "not artifacts"),
}
# statements of the Drift and Ops reads that the Added section must make (D-P11): each a tuple of strings that the
# section's own text must hold; the checks read the Added section only, so the same words elsewhere do not satisfy them
ADDED_STATEMENTS: dict[str, tuple[str, ...]] = {
    "info is not carried": ("The `info` value", "is not carried"),
    "missionId and artifactPath are non-null": ("`missionId` and `artifactPath` of `DriftFinding` are non-null",),
    "the cap of 1000 findings": ("at most 1000 findings", "`truncated`"),
    "derived_view_stale is not shipped, with its reason": ("`derived_view_stale`", "is not shipped", "no example exists"),
    "a manifest without mission_slug is not evaluated": ("`mission_slug`", "is not evaluated for", "`lane_branch_missing`"),
}
# the qualified names of the provisional elements that a bare word of the previous slice also satisfies (friction F-4):
# ``kind``, ``code`` and ``truncated`` are named by the artifact elements, so only the qualified text proves these four
QUALIFIED_PROVISIONAL = ("DriftFinding.kind", "DriftReport.truncated", "DriftRefusal.code", "OpsRefusal.code")
PROVISIONAL_ELEMENTS_COUNT = 34  # the elements the provisional check reports for the resolved tree (counts: provisional_elements=34)
ISSUE_REFERENCE = "#5533"
ROUTE_FAMILIES = ("/api/artifact/*", "/api/research/*", "/api/contracts/*", "/api/checklists/*", "/api/dossier/*")
ROUTE_EXCLUSIONS = ("dossier overview", "snapshot export", "not covered")
# the provisional elements of AD-14, named as whole words inside the entry's own Provisional section
AD14_ELEMENTS = (
    "reviewCycles",
    "workspace",
    "ReviewCycle",
    "Workspace",
    "ArtifactKind",
    "truncated",
    "redacted",
    "code",
    "ArtifactRefusalCode",
    "WorkPackageDetailRefusalCode",
    "ArtifactRefusal",
    "WorkPackageDetailRefusal",
    "kind",
)

_ENTRY_HEADING = re.compile(r"^##\s+(\S.*?)\s*$")
_SUBHEADING = re.compile(r"^###\s+(\S.*?)\s*$")


def changelog_entry(text: str, prefix: str = ENTRY_PREFIX) -> str | None:
    """The text of the ``## <prefix>`` entry, from its heading to the next entry heading, or None."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if (m := _ENTRY_HEADING.match(line)) and m.group(1) == prefix), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if _ENTRY_HEADING.match(lines[i])), len(lines))
    return "\n".join(lines[start:end])


def entry_sections(entry: str) -> dict[str, str]:
    """The ``###`` sections of an entry by heading text (a repeated heading keeps its last text)."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in entry.splitlines():
        heading = _SUBHEADING.match(line)
        if heading:
            current = sections.setdefault(heading.group(1), [])
            current.clear()
        elif current is not None:
            current.append(line)
    return {name: "\n".join(body) for name, body in sections.items()}


def names_whole_word(text: str, token: str) -> bool:
    """True when ``token`` appears as a whole word: no word character or hyphen borders it."""
    return re.search(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])", text) is not None


def route_coverage_problems(entry: str) -> list[str]:
    """The route coverage statement of FR-024: #5533, the five route families, the two exclusions, no mapping table."""
    sections = entry_sections(entry)
    added = sections.get(ADDED_HEADING, "")
    problems = [f"route_family_missing: {family}" for family in ROUTE_FAMILIES if family not in added]
    problems += [f"route_exclusion_missing: {phrase}" for phrase in ROUTE_EXCLUSIONS if phrase not in added]
    if ISSUE_REFERENCE not in added:
        problems.append(f"issue_reference_missing: {ISSUE_REFERENCE}")
    if any(line.lstrip().startswith("|") for line in entry.splitlines()):
        problems.append("route_table_present: the entry holds a table row")
    return problems


def changelog_entry_problems(entry: str, provisional_tokens: Sequence[str]) -> list[str]:
    """Every way the changelog entry misses the shape of FR-018, FR-024 and D-P11; empty when it holds."""
    sections = entry_sections(entry)
    problems = [f"heading_missing: {name}" for name in ENTRY_HEADINGS if name not in sections]
    problems += [f"heading_unexpected: {name}" for name in sections if name not in ENTRY_HEADINGS]
    deferred = sections.get(DEFERRED_HEADING, "")
    for gap, needles in DEFERRED_GAPS.items():
        if not all(needle in deferred for needle in needles):
            problems.append(f"gap_missing: {gap}")
    added = sections.get(ADDED_HEADING, "")
    for behaviour, needles in READ_BEHAVIOURS.items():
        if not all(needle in added for needle in needles):
            problems.append(f"behaviour_missing: {behaviour}")
    problems += route_coverage_problems(entry)
    problems += [f"statement_missing: {name}" for name, needles in ADDED_STATEMENTS.items() if not all(needle in added for needle in needles)]
    provisional = sections.get(PROVISIONAL_HEADING, "")
    problems += [f"qualified_name_missing: {name}" for name in QUALIFIED_PROVISIONAL if not names_whole_word(provisional, name)]
    problems += [f"provisional_unnamed: {token}" for token in dict.fromkeys((*AD14_ELEMENTS, *provisional_tokens)) if not names_whole_word(provisional, token)]
    return problems


def _problems_of(prefix: str, problems: Sequence[str]) -> list[str]:
    return [problem for problem in problems if problem.startswith(prefix)]


_MP = pytest.MonkeyPatch()


@pytest.fixture(scope="module", autouse=True)
def _undo_tool_registration() -> Iterator[None]:
    yield
    _MP.undo()


def _tool(name: str, *, syspath: bool = False) -> ModuleType:
    return load_tool(_MP, TOOLS / f"{name}.py", f"{name}_for_the_1_1_proof", syspath=TOOLS if syspath else None)


def _read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _real_entry() -> str:
    entry = changelog_entry(CHANGELOG.read_text(encoding="utf-8"))
    assert entry is not None, f"the CHANGELOG has no '## {ENTRY_PREFIX}' entry"
    return entry


@functools.cache
def _reported_provisional_tokens() -> tuple[str, ...]:
    """The tokens the provisional check reports for the resolved tree: the one entry must name every one."""
    resolver = _tool("contract_resolver", syspath=True)
    provisional = _tool("provisional_check", syspath=True)
    reported = [element.token for element in provisional._Walk(resolver.resolve(MODULE).tree).elements.values()]
    assert reported, "the provisional check reports no element: the proof would be vacuous"
    return tuple(dict.fromkeys(reported))


def test_the_tree_version_equals_the_version_on_main() -> None:
    """Slice-scoped: no new contract version ships (operator ruling); replaced by the release process (module docstring)."""
    version = _read_yaml(OPENAPI)["info"]["version"]
    assert version == MAIN_VERSION, f"info.version is {version!r}, not the unreleased {MAIN_VERSION!r} of main"


def test_the_changelog_entry_of_the_tree_version_is_the_merged_entry() -> None:
    heading = _real_entry().splitlines()[0]
    assert heading == f"## {_read_yaml(OPENAPI)['info']['version']}", heading


def test_the_entry_has_exactly_its_five_headings() -> None:
    problems = changelog_entry_problems(_real_entry(), [])
    assert not _problems_of("heading_", problems), problems


def test_exactly_three_gaps_remain_deferred_and_the_project_branch_is_not_one() -> None:
    assert set(DEFERRED_GAPS) == {"per-Mission staleness", "actor on WorkPackageSummary", "lane weights"}
    assert len(DEFERRED_GAPS) == 3
    assert "project branch" not in _real_entry_deferred()


def _real_entry_deferred() -> str:
    return entry_sections(_real_entry()).get(DEFERRED_HEADING, "")


def test_the_entry_names_the_three_deferred_gaps_in_its_deferred_section() -> None:
    assert not _problems_of("gap_missing", changelog_entry_problems(_real_entry(), []))


def test_the_entry_states_the_two_read_behaviours_under_added() -> None:
    assert not _problems_of("behaviour_missing", changelog_entry_problems(_real_entry(), []))


def test_the_entry_refers_to_5533_names_the_five_route_families_and_holds_no_route_table() -> None:
    assert route_coverage_problems(_real_entry()) == []


def test_the_entry_names_every_provisional_element_inside_its_own_provisional_section() -> None:
    tokens = _reported_provisional_tokens()
    assert not _problems_of("provisional_unnamed", changelog_entry_problems(_real_entry(), tokens))


# --------------------------------------------------------------------------------------
# Planted negatives of the entry checks: every rule fails on an entry that breaks only that rule
# --------------------------------------------------------------------------------------

NOT_KILLED = "the mutation was not killed"


def _expect_problem(name: str, problems: Sequence[str], code: str) -> None:
    """Fail loudly, naming the mutation, unless ``problems`` holds ``code``."""
    assert code in problems, f"{NOT_KILLED}: {name} (expected {code!r}, got {list(problems)!r})"


def _edit_section(entry: str, heading: str, edit: Any) -> str:
    """``entry`` with the text of one ``###`` section replaced by ``edit(text)``; the section must exist."""
    lines = entry.splitlines()
    start = next((i for i, line in enumerate(lines) if line == f"### {heading}"), None)
    assert start is not None, f"the entry has no section {heading!r}"
    end = next((i for i in range(start + 1, len(lines)) if _SUBHEADING.match(lines[i])), len(lines))
    body = edit("\n".join(lines[start + 1 : end]))
    return "\n".join([*lines[: start + 1], *body.splitlines(), *lines[end:]])


def test_the_real_entry_is_clean_for_every_rule_so_the_planted_entries_differ_in_one_rule_only() -> None:
    assert changelog_entry_problems(_real_entry(), _reported_provisional_tokens()) == []


def test_an_entry_without_its_deferred_section_is_refused() -> None:
    entry = _real_entry()
    cut = entry[: entry.index(f"### {DEFERRED_HEADING}")]
    _expect_problem("no Deferred section", changelog_entry_problems(cut, []), f"heading_missing: {DEFERRED_HEADING}")


def test_an_entry_with_an_unknown_extra_heading_is_refused() -> None:
    entry = _real_entry() + "\n### Notes\n\nSomething.\n"
    _expect_problem("a sixth heading", changelog_entry_problems(entry, []), "heading_unexpected: Notes")


@pytest.mark.parametrize("gap", list(DEFERRED_GAPS))
def test_an_entry_missing_one_deferred_gap_is_refused(gap: str) -> None:
    needles = DEFERRED_GAPS[gap]
    broken = _edit_section(
        _real_entry(),
        DEFERRED_HEADING,
        lambda text: "\n".join(line for line in text.splitlines() if not any(needle in line for needle in needles)),
    )
    _expect_problem(f"gap {gap} removed", changelog_entry_problems(broken, []), f"gap_missing: {gap}")


def test_a_gap_named_only_outside_the_deferred_section_is_refused() -> None:
    moved = _edit_section(_real_entry(), DEFERRED_HEADING, lambda text: "") + "\n".join(DEFERRED_GAPS["lane weights"])
    _expect_problem("the gaps named outside the Deferred section", changelog_entry_problems(moved, []), "gap_missing: lane weights")


@pytest.mark.parametrize("behaviour", list(READ_BEHAVIOURS))
def test_an_entry_missing_one_read_behaviour_under_added_is_refused(behaviour: str) -> None:
    needles = READ_BEHAVIOURS[behaviour]
    broken = _edit_section(_real_entry(), ADDED_HEADING, lambda text: _scrub(text, needles))
    _expect_problem(f"behaviour {behaviour} removed", changelog_entry_problems(broken, []), f"behaviour_missing: {behaviour}")


def _scrub(text: str, needles: Sequence[str]) -> str:
    for needle in needles:
        text = text.replace(needle, "REDACTED-NEEDLE")
    return text


@pytest.mark.parametrize("family", ROUTE_FAMILIES)
def test_an_entry_missing_one_route_family_is_refused(family: str) -> None:
    broken = _edit_section(_real_entry(), ADDED_HEADING, lambda text: text.replace(family, "x"))
    _expect_problem(f"route family {family} removed", route_coverage_problems(broken), f"route_family_missing: {family}")


@pytest.mark.parametrize("phrase", ROUTE_EXCLUSIONS)
def test_an_entry_that_does_not_state_an_exclusion_is_refused(phrase: str) -> None:
    broken = _edit_section(_real_entry(), ADDED_HEADING, lambda text: text.replace(phrase, "x"))
    _expect_problem(f"exclusion {phrase} removed", route_coverage_problems(broken), f"route_exclusion_missing: {phrase}")


def test_an_entry_without_the_issue_reference_is_refused() -> None:
    broken = _edit_section(_real_entry(), ADDED_HEADING, lambda text: text.replace(ISSUE_REFERENCE, "#1"))
    _expect_problem("no #5533", route_coverage_problems(broken), f"issue_reference_missing: {ISSUE_REFERENCE}")


def test_an_entry_with_a_route_by_route_table_is_refused() -> None:
    entry = _real_entry() + "\n| old route | new route |\n|---|---|\n| /api/artifact/x | /artifacts |\n"
    assert any(problem.startswith("route_table_present") for problem in route_coverage_problems(entry))


@pytest.mark.parametrize("token", AD14_ELEMENTS)
def test_a_provisional_element_not_named_in_the_entrys_own_provisional_section_is_refused(token: str) -> None:
    pattern = re.compile(r"(?<![\w-])" + re.escape(token) + r"(?![\w-])")
    broken = _edit_section(_real_entry(), PROVISIONAL_HEADING, lambda text: pattern.sub("REDACTED-NEEDLE", text))
    _expect_problem(f"{token} unnamed in Provisional", changelog_entry_problems(broken, []), f"provisional_unnamed: {token}")


def test_a_provisional_element_named_only_in_another_section_is_refused() -> None:
    entry = _real_entry()
    provisional = entry_sections(entry)[PROVISIONAL_HEADING]
    emptied = _edit_section(entry, PROVISIONAL_HEADING, lambda text: "Nothing.")
    moved = emptied + "\n" + provisional
    assert "provisional_unnamed: reviewCycles" in changelog_entry_problems(moved, [])


def test_a_reported_provisional_token_missing_from_the_section_is_refused() -> None:
    _expect_problem("a reported token absent", changelog_entry_problems(_real_entry(), ["notInTheEntryAtAll"]), "provisional_unnamed: notInTheEntryAtAll")


def test_the_entry_makes_every_statement_of_the_drift_and_ops_reads_under_added() -> None:
    assert set(ADDED_STATEMENTS) == {
        "info is not carried",
        "missionId and artifactPath are non-null",
        "the cap of 1000 findings",
        "derived_view_stale is not shipped, with its reason",
        "a manifest without mission_slug is not evaluated",
    }
    assert not _problems_of("statement_missing", changelog_entry_problems(_real_entry(), []))


@pytest.mark.parametrize("statement", list(ADDED_STATEMENTS))
def test_an_entry_missing_one_statement_under_added_is_refused(statement: str) -> None:
    broken = _edit_section(_real_entry(), ADDED_HEADING, lambda text: _scrub(text, ADDED_STATEMENTS[statement]))
    _expect_problem(f"statement {statement} removed", changelog_entry_problems(broken, []), f"statement_missing: {statement}")


@pytest.mark.parametrize("statement", list(ADDED_STATEMENTS))
def test_a_statement_made_only_outside_the_added_section_is_refused(statement: str) -> None:
    """The check is scoped to its heading: the words in Deferred or Provisional do not satisfy it."""
    needles = ADDED_STATEMENTS[statement]
    stripped = _edit_section(_real_entry(), ADDED_HEADING, lambda text: _scrub(text, needles))
    moved = _edit_section(stripped, DEFERRED_HEADING, lambda text: text + "\n" + "\n".join(needles))
    _expect_problem(f"statement {statement} moved to Deferred", changelog_entry_problems(moved, []), f"statement_missing: {statement}")


def test_the_cap_statement_is_the_findings_cap_and_not_the_artifact_listing_cap() -> None:
    """The artifact listing also says 1000: only the findings sentence satisfies the Drift statement."""
    broken = _edit_section(_real_entry(), ADDED_HEADING, lambda text: text.replace("at most 1000 findings", "at most 1000 entries"))
    _expect_problem("the findings cap reworded", changelog_entry_problems(broken, []), "statement_missing: the cap of 1000 findings")


def test_the_four_qualified_provisional_names_are_exactly_these() -> None:
    assert QUALIFIED_PROVISIONAL == ("DriftFinding.kind", "DriftReport.truncated", "DriftRefusal.code", "OpsRefusal.code")


def test_the_real_entry_names_the_four_qualified_names_inside_its_provisional_section() -> None:
    provisional = entry_sections(_real_entry())[PROVISIONAL_HEADING]
    assert [name for name in QUALIFIED_PROVISIONAL if not names_whole_word(provisional, name)] == []
    assert not _problems_of("qualified_name_missing", changelog_entry_problems(_real_entry(), []))


@pytest.mark.parametrize("name", QUALIFIED_PROVISIONAL)
def test_an_entry_missing_one_qualified_name_is_refused_although_the_bare_word_is_still_named(name: str) -> None:
    """The bare ``kind``, ``code`` and ``truncated`` are named by the artifact elements, so the word check cannot see this loss."""
    broken = _edit_section(_real_entry(), PROVISIONAL_HEADING, lambda text: text.replace(name, "REDACTED-NEEDLE"))
    problems = changelog_entry_problems(broken, [])
    _expect_problem(f"{name} removed", problems, f"qualified_name_missing: {name}")
    bare = name.split(".")[1]
    assert f"provisional_unnamed: {bare}" not in problems, f"the plant must be invisible to the word check of {bare!r}"


@pytest.mark.parametrize("name", QUALIFIED_PROVISIONAL)
def test_a_qualified_name_named_only_outside_the_provisional_section_is_refused(name: str) -> None:
    emptied = _edit_section(_real_entry(), PROVISIONAL_HEADING, lambda text: text.replace(name, "REDACTED-NEEDLE"))
    moved = _edit_section(emptied, ADDED_HEADING, lambda text: text + "\n" + name)
    _expect_problem(f"{name} moved to Added", changelog_entry_problems(moved, []), f"qualified_name_missing: {name}")


def _schema_has_property(schema: str, member: str) -> bool:
    document = _read_yaml(MODULE / "schemas" / f"{schema}.yaml")
    parts = [document, *(part for part in document.get("allOf", []) if isinstance(part, dict))]
    return any(member in part.get("properties", {}) for part in parts)


@pytest.mark.parametrize("name", QUALIFIED_PROVISIONAL)
def test_each_qualified_name_is_a_real_property_of_its_schema(name: str) -> None:
    schema, member = name.split(".")
    assert _schema_has_property(schema, member), f"{name} names a property its schema does not have"


def test_a_property_that_is_not_in_the_schema_is_not_found() -> None:
    assert not _schema_has_property("OpsRefusal", "notAProperty")


def test_the_reported_provisional_elements_are_counted() -> None:
    """The count of ``provisional_check.py`` for the tree; a changed list of elements changes it and this proof together."""
    resolver = _tool("contract_resolver", syspath=True)
    provisional = _tool("provisional_check", syspath=True)
    elements = provisional._Walk(resolver.resolve(MODULE).tree).elements
    assert len(elements) == PROVISIONAL_ELEMENTS_COUNT
    reported = set(_reported_provisional_tokens())
    assert {"kind", "code", "truncated"} <= reported, "the tool reports the bare words, which is why the qualified names are asserted literally"
    assert not reported & set(QUALIFIED_PROVISIONAL), "the tool reports no qualified token: the four names are the contract's own addition"


def test_the_scan_of_an_entry_that_does_not_exist_is_a_failure_not_a_pass() -> None:
    assert changelog_entry("# Changelog\n\n## 0.9.0\n\nOnly one.\n") is None


# --------------------------------------------------------------------------------------
# The additive proof: byte identity, bundle comparison, same version (FR-017, D-P10)
# --------------------------------------------------------------------------------------

MODULE_NAME = "mission-status"
SHARED_NAME = "_shared"
# the files of the module that may differ between the baseline and the candidate: the version, path map and tags,
# the four index files (new entries), the CHANGELOG (the entry) and the three Project files this slice extends;
# nothing else of the module or of _shared
PROJECT_FILES = (
    f"{MODULE_NAME}/schemas/Project.yaml",
    f"{MODULE_NAME}/examples/Project.example.yaml",
    f"{MODULE_NAME}/paths/project.yaml",
)
CHANGED_ALLOWED = frozenset(
    {
        f"{MODULE_NAME}/openapi.yaml",
        f"{MODULE_NAME}/CHANGELOG.md",
        f"{MODULE_NAME}/examples/_index.yaml",
        f"{MODULE_NAME}/parameters/_index.yaml",
        f"{MODULE_NAME}/responses/_index.yaml",
        f"{MODULE_NAME}/schemas/_index.yaml",
        *PROJECT_FILES,
    }
)
# the paths and the tags the two new operations add; a scratch baseline is the candidate without them (it stands for main)
NEW_PATH_KEYS = (
    "/drift",
    "/ops/invocations",
)
NEW_TAGS = ("Drift", "Ops")
# the pre-slice Project files: ``git show`` of the baseline commit into the source layout, never typed
FROZEN_ROOT = Path(__file__).resolve().parent / "fixtures" / "mission_status_pre_slice"
PROJECT_PATH_KEY = "/project"
PROJECT_SCHEMA_NAME = "Project"
EXISTING_PATH_FILE = f"{MODULE_NAME}/paths/missions_missionId.yaml"
EXISTING_SCHEMA_FILE = f"{MODULE_NAME}/schemas/WorkPackage.yaml"
SHARED_SCHEMA_FILE = f"{SHARED_NAME}/schemas/Problem.yaml"


@functools.cache
def _resolver() -> ModuleType:
    return _tool("contract_resolver", syspath=True)


def _files_below(root: Path) -> dict[str, bytes]:
    """Every file of the module and of ``_shared`` under ``root``: relative POSIX path to bytes."""
    found: dict[str, bytes] = {}
    for name in (MODULE_NAME, SHARED_NAME):
        base = root / name
        if base.is_dir():
            found.update({path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(base.rglob("*")) if path.is_file()})
    return found


def _version_of(root: Path) -> str | None:
    document = _read_yaml(root / MODULE_NAME / OPENAPI_FILE)
    version = document.get("info", {}).get("version") if isinstance(document, dict) else None
    return version if isinstance(version, str) else None


def _byte_identity_problems(baseline: dict[str, bytes], candidate: dict[str, bytes]) -> list[str]:
    problems = []
    for relative, content in baseline.items():
        if relative in CHANGED_ALLOWED:
            continue
        if relative not in candidate:
            problems.append(f"byte_identity: {relative} is missing from the candidate")
        elif candidate[relative] != content:
            problems.append(f"byte_identity: {relative} differs from the baseline")
    return problems


MASKED_SCHEMA = {"masked": PROJECT_SCHEMA_NAME}


def _project_200(tree: dict[str, Any]) -> dict[str, Any]:
    """The media type object of the 200 response of ``getProject`` in a resolved tree (the resolver inlines every reference)."""
    return tree["paths"][PROJECT_PATH_KEY]["get"]["responses"]["200"]["content"]["application/json"]


def _masked_tree(tree: dict[str, Any]) -> dict[str, Any]:
    """The resolved tree with the only two permitted masks: the ``Project`` schema and the description of ``getProject``.

    The resolver inlines every reference, so the ``Project`` schema stands where ``getProject`` answers 200 and nowhere
    else; it is masked only when its title is ``Project``, so a 200 that points to any other schema stays visible.
    The rest of the ``/project`` path item stays: the ``operationId``, ``summary``, tags, parameters and every
    response code are compared. A mask over the whole path item would hide a change to that operation.
    """
    masked = copy.deepcopy(tree)
    operation = masked["paths"][PROJECT_PATH_KEY]["get"]
    operation.pop("description", None)
    media = _project_200(masked)
    if media["schema"].get("title") == PROJECT_SCHEMA_NAME:
        media["schema"] = dict(MASKED_SCHEMA)
    return masked


def _bundle_problems(baseline_root: Path, candidate_root: Path) -> list[str]:
    """The resolved candidate minus the new operations and tags, at the baseline version, equals the resolved baseline except the two masks."""
    resolver = _resolver()
    try:
        baseline_tree = resolver.resolve(baseline_root / MODULE_NAME).tree
        candidate_tree = copy.deepcopy(resolver.resolve(candidate_root / MODULE_NAME).tree)
    except resolver.ResolveError as error:
        return [f"resolve_failed: {error}"]
    for key in set(candidate_tree["paths"]) - set(baseline_tree["paths"]):
        del candidate_tree["paths"][key]
    baseline_tags = {tag["name"] for tag in baseline_tree.get("tags", [])}
    candidate_tree["tags"] = [tag for tag in candidate_tree.get("tags", []) if tag["name"] in baseline_tags]
    candidate_tree["info"]["version"] = baseline_tree["info"]["version"]
    try:
        baseline_masked, candidate_masked = _masked_tree(baseline_tree), _masked_tree(candidate_tree)
    except (KeyError, TypeError) as error:
        return [f"bundle_changed: the masked part {error} is missing from a tree"]
    if candidate_masked == baseline_masked:
        return []
    base_paths, candidate_paths = baseline_masked["paths"], candidate_masked["paths"]
    changed = sorted(key for key in set(base_paths) | set(candidate_paths) if base_paths.get(key) != candidate_paths.get(key))
    if baseline_masked.get("tags") != candidate_masked.get("tags"):
        changed.append("tags")
    return [f"bundle_changed: the existing operations differ: {changed}"]


def additive_proof_problems(baseline_root: Path, candidate_root: Path) -> list[str]:
    """Every way ``candidate_root`` fails to be an additive change of ``baseline_root``; empty when it is one.

    (a) every baseline file of the module and ``_shared`` is byte-identical in the candidate except the allowed set;
    (b) the candidate bundle tree minus the new path keys, at the baseline version, equals the baseline tree;
    (c) the candidate version equals the baseline version: the slice ships in the same unreleased release.
    """
    baseline = _files_below(baseline_root)
    if not baseline:
        return [f"no_baseline_files: nothing of {MODULE_NAME} or {SHARED_NAME} was found under {baseline_root.name}"]
    problems = _byte_identity_problems(baseline, _files_below(candidate_root))
    problems += _bundle_problems(baseline_root, candidate_root)
    baseline_version, candidate_version = _version_of(baseline_root), _version_of(candidate_root)
    if candidate_version is None or candidate_version != baseline_version:
        problems.append(f"version: {candidate_version!r} is not the baseline version {baseline_version!r}")
    return problems


def _make_pair(tmp_path: Path) -> tuple[Path, Path]:
    """A scratch (baseline, candidate): the candidate is this tree; the baseline stands for main.

    The baseline is the candidate without the two new path keys and the two new tags, and with the three frozen
    pre-slice ``Project`` files swapped in.
    """
    pair = []
    for name in ("baseline", "candidate"):
        root = tmp_path / name
        shutil.copytree(MODULE, root / MODULE_NAME)
        shutil.copytree(CONTRACTS / SHARED_NAME, root / SHARED_NAME)
        pair.append(root)
    baseline, candidate = pair
    document = _read_yaml(baseline / MODULE_NAME / OPENAPI_FILE)
    for key in NEW_PATH_KEYS:
        reference = document["paths"].pop(key)["$ref"]
        (baseline / MODULE_NAME / reference).unlink()
    document["tags"] = [tag for tag in document["tags"] if tag["name"] not in NEW_TAGS]
    document["info"]["version"] = MAIN_VERSION
    _write_yaml(baseline / MODULE_NAME / OPENAPI_FILE, document)
    for relative in PROJECT_FILES:
        shutil.copyfile(FROZEN_ROOT / relative.removeprefix(f"{MODULE_NAME}/"), baseline / relative)
    return baseline, candidate


def _write_yaml(path: Path, document: Any) -> None:
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def _set_version(root: Path, version: str) -> None:
    path = root / MODULE_NAME / OPENAPI_FILE
    document = _read_yaml(path)
    document["info"]["version"] = version
    _write_yaml(path, document)


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    return _make_pair(tmp_path)


def test_the_scratch_baseline_is_this_tree_without_exactly_the_two_new_operations_and_tags(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    resolver = _resolver()
    base_tree, candidate_tree = resolver.resolve(baseline / MODULE_NAME).tree, resolver.resolve(candidate / MODULE_NAME).tree
    base_paths, candidate_paths = set(base_tree["paths"]), set(candidate_tree["paths"])
    assert NEW_PATH_KEYS == ("/drift", "/ops/invocations")
    assert candidate_paths - base_paths == set(NEW_PATH_KEYS)
    assert base_paths < candidate_paths and len(base_paths) >= 5, "the baseline must keep the existing operations"
    assert NEW_TAGS == ("Drift", "Ops")
    assert {tag["name"] for tag in candidate_tree["tags"]} - {tag["name"] for tag in base_tree["tags"]} == set(NEW_TAGS)
    assert {tag["name"] for tag in base_tree["tags"]} == {"Project", "Missions", "Events"}


def test_the_scratch_baseline_holds_the_three_frozen_project_files_and_no_other_project_change(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    assert len(PROJECT_FILES) == 3
    for relative in PROJECT_FILES:
        assert (baseline / relative).read_bytes() == (FROZEN_ROOT / relative.removeprefix(f"{MODULE_NAME}/")).read_bytes()
        assert (baseline / relative).read_bytes() != (candidate / relative).read_bytes(), f"{relative} was not extended by the slice"
    assert set(PROJECT_FILES) <= CHANGED_ALLOWED


def test_the_frozen_project_schema_is_the_pre_slice_shape() -> None:
    """Before the slice a Project held its name and Mission count only: the five added properties are absent from the copy."""
    frozen = _read_yaml(FROZEN_ROOT / "schemas" / "Project.yaml")
    current = _read_yaml(MODULE / "schemas" / "Project.yaml")
    assert set(frozen["properties"]) == {"name", "missionCount"}
    assert set(current["properties"]) - set(frozen["properties"]) == {"specKittyVersion", "schemaVersion", "health", "currentBranch", "lastActivityAt"}
    assert set(_read_yaml(FROZEN_ROOT / "examples" / "Project.example.yaml")) == {"name", "missionCount"}


def test_no_two_frozen_names_in_one_directory_differ_only_by_case() -> None:
    names = [path.relative_to(FROZEN_ROOT).as_posix() for path in sorted(FROZEN_ROOT.rglob("*")) if path.is_file()]
    assert names == ["examples/Project.example.yaml", "paths/project.yaml", "schemas/Project.yaml"]
    assert len({name.lower() for name in names}) == len(names)


def test_this_tree_is_an_additive_change_over_its_scratch_baseline(pair: tuple[Path, Path]) -> None:
    assert additive_proof_problems(*pair) == []


def test_a_byte_change_to_an_existing_schema_fails_the_byte_identity_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    target = candidate / EXISTING_SCHEMA_FILE
    target.write_bytes(target.read_bytes() + b"# planted\n")
    _expect_problem("a byte added to WorkPackage", additive_proof_problems(baseline, candidate), f"byte_identity: {EXISTING_SCHEMA_FILE} differs from the baseline")


def test_a_byte_change_to_a_shared_file_fails_the_byte_identity_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    target = candidate / SHARED_SCHEMA_FILE
    target.write_bytes(target.read_bytes() + b"# planted\n")
    _expect_problem(
        "a byte added to a shared schema", additive_proof_problems(baseline, candidate), f"byte_identity: {SHARED_SCHEMA_FILE} differs from the baseline"
    )


def test_a_deleted_existing_file_fails_the_byte_identity_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    (candidate / EXISTING_SCHEMA_FILE).unlink()
    _expect_problem(
        "an existing schema deleted", additive_proof_problems(baseline, candidate), f"byte_identity: {EXISTING_SCHEMA_FILE} is missing from the candidate"
    )


@pytest.mark.parametrize("name", sorted(CHANGED_ALLOWED - {f"{MODULE_NAME}/openapi.yaml"}))
def test_a_change_to_an_allowed_file_does_not_fail_the_byte_identity_rule(pair: tuple[Path, Path], name: str) -> None:
    """The index files and the CHANGELOG may differ; the version and path map change is exercised by the other rules."""
    baseline, candidate = pair
    target = candidate / name
    target.write_bytes(target.read_bytes() + b"\n# allowed to differ\n")
    assert not [problem for problem in additive_proof_problems(baseline, candidate) if problem.startswith("byte_identity")]


def test_a_409_added_to_an_existing_operation_fails_the_bundle_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    path = candidate / EXISTING_PATH_FILE
    operation = _read_yaml(path)
    operation["get"]["responses"]["409"] = {"$ref": "../../_shared/responses/Problem.yaml"}
    _write_yaml(path, operation)
    problems = additive_proof_problems(baseline, candidate)
    assert any(problem.startswith("bundle_changed") for problem in problems), f"{NOT_KILLED}: a 409 added: {problems}"


PROJECT_PATH_FILE = f"{MODULE_NAME}/paths/project.yaml"
PROJECT_SCHEMA_FILE = f"{MODULE_NAME}/schemas/Project.yaml"


def _bundle_changed(problems: Sequence[str]) -> bool:
    return any(problem.startswith("bundle_changed") for problem in problems)


def test_the_unmutated_candidate_passes_with_only_the_two_permitted_masks(pair: tuple[Path, Path]) -> None:
    """Control: the candidate differs from the baseline in the Project schema and in the getProject description, and nowhere else."""
    baseline, candidate = pair
    resolver = _resolver()
    base_tree, candidate_tree = resolver.resolve(baseline / MODULE_NAME).tree, resolver.resolve(candidate / MODULE_NAME).tree
    assert _project_200(base_tree)["schema"]["title"] == _project_200(candidate_tree)["schema"]["title"] == PROJECT_SCHEMA_NAME
    assert _project_200(base_tree) != _project_200(candidate_tree)
    assert base_tree["paths"][PROJECT_PATH_KEY]["get"]["description"] != candidate_tree["paths"][PROJECT_PATH_KEY]["get"]["description"]
    assert _bundle_problems(baseline, candidate) == []


def _mutate_project_operation(candidate: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    path = candidate / PROJECT_PATH_FILE
    document = _read_yaml(path)
    mutate(document["get"])
    _write_yaml(path, document)


def test_an_extra_response_code_on_get_project_fails_the_bundle_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    _mutate_project_operation(candidate, lambda operation: operation["responses"].update({"404": {"$ref": "../../_shared/responses/Problem.yaml"}}))
    problems = _bundle_problems(baseline, candidate)
    assert _bundle_changed(problems), f"{NOT_KILLED}: an extra response code on getProject: {problems}"


def test_a_changed_200_schema_reference_on_get_project_fails_the_bundle_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    _mutate_project_operation(
        candidate, lambda operation: operation["responses"]["200"]["content"]["application/json"].update({"schema": {"$ref": "../schemas/WorkPackage.yaml"}})
    )
    problems = _bundle_problems(baseline, candidate)
    assert _bundle_changed(problems), f"{NOT_KILLED}: a changed 200 schema reference on getProject: {problems}"


def test_a_changed_operation_id_or_summary_of_get_project_fails_the_bundle_rule(pair: tuple[Path, Path]) -> None:
    """Only the description is masked: the summary changed by the final edit would have to be unmasked on purpose."""
    for member in ("operationId", "summary"):
        baseline, candidate = _make_pair(pair[0].parent / f"mask-{member}")
        _mutate_project_operation(candidate, lambda operation, member=member: operation.update({member: operation[member] + "X"}))
        problems = _bundle_problems(baseline, candidate)
        assert _bundle_changed(problems), f"{NOT_KILLED}: {member} of getProject changed: {problems}"


def test_a_change_to_another_existing_schema_fails_the_bundle_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    path = candidate / EXISTING_SCHEMA_FILE
    document = _read_yaml(path)
    document["description"] = str(document.get("description", "")) + " planted"
    _write_yaml(path, document)
    problems = additive_proof_problems(baseline, candidate)
    assert _bundle_changed(problems), f"{NOT_KILLED}: another existing schema changed: {problems}"
    assert any(f"byte_identity: {EXISTING_SCHEMA_FILE}" in problem for problem in problems)


def test_a_changed_existing_tag_fails_the_bundle_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    path = candidate / MODULE_NAME / OPENAPI_FILE
    document = _read_yaml(path)
    document["tags"][0]["description"] += " planted"
    _write_yaml(path, document)
    problems = _bundle_problems(baseline, candidate)
    assert _bundle_changed(problems), f"{NOT_KILLED}: an existing tag changed: {problems}"


def test_a_change_to_the_project_schema_or_the_get_project_description_alone_is_masked(pair: tuple[Path, Path]) -> None:
    """The two masks do their job: a further edit of either is invisible to the bundle rule, and visible to nothing else."""
    baseline, candidate = pair
    project = _read_yaml(candidate / PROJECT_SCHEMA_FILE)
    project["description"] = str(project.get("description", "")) + " further edit"
    _write_yaml(candidate / PROJECT_SCHEMA_FILE, project)
    _mutate_project_operation(candidate, lambda operation: operation.update({"description": "A further description."}))
    assert additive_proof_problems(baseline, candidate) == []


def test_the_mask_does_not_exclude_the_whole_project_path_item(pair: tuple[Path, Path]) -> None:
    baseline, _ = pair
    tree = _resolver().resolve(baseline / MODULE_NAME).tree
    masked = _masked_tree(tree)
    assert "description" not in masked["paths"][PROJECT_PATH_KEY]["get"]
    assert set(masked["paths"][PROJECT_PATH_KEY]["get"]) == set(tree["paths"][PROJECT_PATH_KEY]["get"]) - {"description"}
    assert _project_200(masked)["schema"] == MASKED_SCHEMA and _project_200(tree)["schema"] != MASKED_SCHEMA
    assert set(masked["paths"]) == set(tree["paths"]), "no other path item is masked"
    assert masked["paths"][PROJECT_PATH_KEY]["get"]["operationId"] == "getProject"


def test_an_existing_operation_dropped_from_the_path_map_fails_the_bundle_rule_alone(pair: tuple[Path, Path]) -> None:
    """The path map is an allowed file, so only the bundle rule can see this change (it is independent of the byte rule)."""
    baseline, candidate = pair
    path = candidate / MODULE_NAME / OPENAPI_FILE
    document = _read_yaml(path)
    del document["paths"]["/project"]
    _write_yaml(path, document)
    problems = additive_proof_problems(baseline, candidate)
    assert any(problem.startswith("bundle_changed") for problem in problems), f"{NOT_KILLED}: an operation dropped: {problems}"
    assert not [problem for problem in problems if problem.startswith("byte_identity")], problems


def test_an_unresolvable_candidate_fails_loudly_instead_of_comparing(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    path = candidate / MODULE_NAME / OPENAPI_FILE
    document = _read_yaml(path)
    document["paths"]["/project"] = {"$ref": "paths/does_not_exist.yaml"}
    _write_yaml(path, document)
    assert any(problem.startswith("resolve_failed") for problem in additive_proof_problems(baseline, candidate))


@pytest.mark.parametrize("version", ["1.0.0", "1.1.0", "1.1.0-SNAPSHOT", "1.0.1-SNAPSHOT", "2.0.0-SNAPSHOT", "garbage"])
def test_a_candidate_version_other_than_the_baseline_version_fails_the_version_rule(pair: tuple[Path, Path], version: str) -> None:
    baseline, candidate = pair
    _set_version(candidate, version)
    _expect_problem(f"version {version}", [problem.split(":")[0] for problem in additive_proof_problems(baseline, candidate)], "version")


def test_a_baseline_with_an_unreadable_version_fails_the_version_rule(pair: tuple[Path, Path]) -> None:
    baseline, candidate = pair
    _set_version(baseline, "not-a-version")
    assert any(problem.startswith("version") for problem in additive_proof_problems(baseline, candidate))


def test_an_empty_baseline_fails_loudly_instead_of_passing(pair: tuple[Path, Path], tmp_path: Path) -> None:
    _, candidate = pair
    empty = tmp_path / "empty"
    empty.mkdir()
    assert [problem.split(":")[0] for problem in additive_proof_problems(empty, candidate)] == ["no_baseline_files"]


# --------------------------------------------------------------------------------------
# Determinism of the bundle
# --------------------------------------------------------------------------------------


def bundle_build_problems(build: Callable[[], str]) -> list[str]:
    """Two builds of the same input must give the same non-empty text."""
    first, second = build(), build()
    problems = []
    if not first or not second:
        problems.append("empty_bundle: a build produced no text")
    if first != second:
        problems.append("nondeterministic: two builds differ")
    return problems


def test_two_bundle_builds_of_this_tree_are_byte_identical() -> None:
    bundle = _tool("bundle", syspath=True)
    resolver = _resolver()
    assert bundle_build_problems(lambda: bundle.render_bundle(resolver.resolve(MODULE).tree)) == []


def test_two_bundle_files_written_from_this_tree_are_byte_identical(tmp_path: Path) -> None:
    bundle = _tool("bundle", syspath=True)
    first = bundle.write_bundle(MODULE, tmp_path / "one").read_bytes()
    second = bundle.write_bundle(MODULE, tmp_path / "two").read_bytes()
    assert first and first == second


def test_a_nondeterministic_build_fails_the_determinism_rule() -> None:
    counter = iter(range(1000))
    assert "nondeterministic: two builds differ" in bundle_build_problems(lambda: f"member: {next(counter)}")


def test_an_empty_build_fails_the_determinism_rule() -> None:
    assert "empty_bundle: a build produced no text" in bundle_build_problems(lambda: "")


# --------------------------------------------------------------------------------------
# The scope function: the allowed set is data that carries the statuses each entry admits
# --------------------------------------------------------------------------------------

PREFIX = "prefix"
EXACT = "exact"
ADDED = frozenset({"A"})
MODIFIED = frozenset({"M"})
ADDED_OR_MODIFIED = frozenset({"A", "M"})


class ScopeRule(NamedTuple):
    """One rule of the allowed set: how ``path`` matches (prefix or exact) and the statuses an entry may carry."""

    match: str
    path: str
    statuses: frozenset[str]


# the slice file set: new files under the module, the named existing files, the test tree, never a deletion
SLICE_ALLOWED: tuple[ScopeRule, ...] = (
    ScopeRule(PREFIX, "contracts/mission-status/", ADDED),
    ScopeRule(EXACT, "contracts/mission-status/openapi.yaml", MODIFIED),
    ScopeRule(EXACT, "contracts/mission-status/CHANGELOG.md", MODIFIED),
    ScopeRule(EXACT, "contracts/mission-status/schemas/_index.yaml", MODIFIED),
    ScopeRule(EXACT, "contracts/mission-status/examples/_index.yaml", MODIFIED),
    ScopeRule(EXACT, "contracts/mission-status/parameters/_index.yaml", MODIFIED),
    ScopeRule(EXACT, "contracts/mission-status/responses/_index.yaml", MODIFIED),
    ScopeRule(EXACT, PROJECT_SCHEMA_PATH, MODIFIED),
    ScopeRule(EXACT, "contracts/mission-status/examples/Project.example.yaml", MODIFIED),
    ScopeRule(EXACT, "contracts/mission-status/paths/project.yaml", MODIFIED),
    ScopeRule(EXACT, FIXTURE_BUILDER_PATH, MODIFIED),
    ScopeRule(EXACT, "contracts/tools/negative_cases.json", MODIFIED),
    ScopeRule(EXACT, "contracts/tools/enum_pins.json", MODIFIED),
    # the router path-group globs of the contract tool tests (the reader modules the tools import select the job)
    ScopeRule(EXACT, ROUTER_WORKFLOW_PATH, MODIFIED),
    ScopeRule(PREFIX, "tests/contract/", ADDED_OR_MODIFIED),
)
# the registrations of the new test modules and of the router routing of the Op data: exactly these paths, no wildcard
EXTRA_ALLOWED_REGISTRATIONS: tuple[ScopeRule, ...] = (
    ScopeRule(EXACT, PACKS_WORKFLOW_PATH, MODIFIED),
    ScopeRule(EXACT, "tests/architectural/test_ci_corpus_trigger_completeness.py", MODIFIED),
    ScopeRule(EXACT, "tests/ci/test_contracts_routing.py", MODIFIED),
    ScopeRule(EXACT, "tests/release/ci_retirement_scrub.json", MODIFIED),
)
# the slice allows no dependency change: no rule and no change may name a file of the dependency set
DEPENDENCY_FILES = ("pyproject.toml", "uv.lock")


def _rule_admits(rule: ScopeRule, status: str, path: str) -> bool:
    matches = path.startswith(rule.path) if rule.match == PREFIX else path == rule.path
    return matches and status in rule.statuses


def scope_problems(changes: Sequence[tuple[str, str]], allowed: Sequence[ScopeRule]) -> list[str]:
    """The name-status entries ``(status, path)`` of a ``git diff --name-status --no-renames`` that no rule admits.

    A rename is a deletion plus an addition. No entry at all is itself a problem: a scope check that examined
    nothing proves nothing.
    """
    if not changes:
        return ["no_changes: no entry was examined"]
    return [f"out_of_scope: {status} {path}" for status, path in changes if not any(_rule_admits(rule, status, path) for rule in allowed)]


# entries a branch of this Mission holds (the shape of the real diff, written as data)
IN_SCOPE_CHANGES: tuple[tuple[str, str], ...] = (
    ("A", "contracts/mission-status/schemas/DriftReport.yaml"),
    ("A", "contracts/mission-status/examples/OpsInvocation.open.yaml"),
    ("A", "contracts/mission-status/paths/drift.yaml"),
    ("M", "contracts/mission-status/openapi.yaml"),
    ("M", "contracts/mission-status/CHANGELOG.md"),
    ("M", "contracts/mission-status/schemas/_index.yaml"),
    ("M", "contracts/mission-status/examples/_index.yaml"),
    ("M", "contracts/mission-status/parameters/_index.yaml"),
    ("M", "contracts/mission-status/responses/_index.yaml"),
    ("M", PROJECT_SCHEMA_PATH),
    ("M", "contracts/mission-status/examples/Project.example.yaml"),
    ("M", "contracts/mission-status/paths/project.yaml"),
    ("M", FIXTURE_BUILDER_PATH),
    ("M", "contracts/tools/negative_cases.json"),
    ("M", "contracts/tools/enum_pins.json"),
    ("A", "tests/contract/test_mission_status_project.py"),
    ("A", "tests/contract/fixtures/mission_status_pre_slice/schemas/Project.yaml"),
    ("M", "tests/contract/test_leak_scan.py"),
    ("M", ROUTER_WORKFLOW_PATH),
)
REGISTRATION_CHANGES: tuple[tuple[str, str], ...] = (
    ("M", PACKS_WORKFLOW_PATH),
    ("M", "tests/architectural/test_ci_corpus_trigger_completeness.py"),
    ("M", "tests/ci/test_contracts_routing.py"),
    ("M", "tests/release/ci_retirement_scrub.json"),
)


def test_the_entries_of_a_branch_inside_the_slice_pass() -> None:
    assert scope_problems(IN_SCOPE_CHANGES, SLICE_ALLOWED) == []
    assert scope_problems([*IN_SCOPE_CHANGES, *REGISTRATION_CHANGES], [*SLICE_ALLOWED, *EXTRA_ALLOWED_REGISTRATIONS]) == []


@pytest.mark.parametrize(
    "entry",
    [("A", "src/specify_cli/new_module.py"), ("M", "src/specify_cli/status/store.py"), ("A", "docs/how-to/new.md"), ("M", "docs/index.md"), ("A", "README.md")],
)
def test_a_path_in_neither_set_is_reported(entry: tuple[str, str]) -> None:
    _expect_problem(f"path in neither set {entry}", scope_problems([entry], SLICE_ALLOWED), f"out_of_scope: {entry[0]} {entry[1]}")


@pytest.mark.parametrize(
    "path", ["contracts/mission-status/schemas/WorkPackage.yaml", "contracts/mission-status/paths/missions.yaml", "contracts/_shared/schemas/Problem.yaml"]
)
def test_a_modification_of_an_existing_contract_file_outside_the_named_ones_is_reported(path: str) -> None:
    _expect_problem(f"M under the new-files prefix {path}", scope_problems([("M", path)], SLICE_ALLOWED), f"out_of_scope: M {path}")


@pytest.mark.parametrize(
    "path",
    ["contracts/tools/breaking_check.py", LEAK_SCAN_PATH, "contracts/tools/leak_patterns.py", "contracts/tools/leak_scan.py.orig", "contracts/tools/pins.json"],
)
def test_a_modification_of_a_tools_file_that_is_not_one_of_the_named_ones_is_reported(path: str) -> None:
    _expect_problem(f"unnamed tools file {path}", scope_problems([("M", path)], SLICE_ALLOWED), f"out_of_scope: M {path}")


@pytest.mark.parametrize(
    "path",
    [FIXTURE_BUILDER_PATH, "contracts/mission-status/openapi.yaml", PROJECT_SCHEMA_PATH, "tests/contract/test_leak_scan.py"],
)
def test_a_deletion_is_reported_for_every_path_even_a_named_one(path: str) -> None:
    _expect_problem(f"D entry {path}", scope_problems([("D", path)], [*SLICE_ALLOWED, *EXTRA_ALLOWED_REGISTRATIONS]), f"out_of_scope: D {path}")


def test_an_addition_of_a_named_existing_file_is_reported() -> None:
    _expect_problem("A for a named existing file", scope_problems([("A", FIXTURE_BUILDER_PATH)], SLICE_ALLOWED), f"out_of_scope: A {FIXTURE_BUILDER_PATH}")


@pytest.mark.parametrize("path", ["contracts/mission-status-extra/a.yaml", "tests/contract_extra/a.py", "contracts/mission-statusX"])
def test_a_prefix_lookalike_is_not_inside_the_prefix(path: str) -> None:
    assert scope_problems([("A", path)], SLICE_ALLOWED) == [f"out_of_scope: A {path}"]


def test_a_rename_is_a_deletion_plus_an_addition_and_the_deletion_is_reported() -> None:
    changes = [("D", "contracts/mission-status/schemas/Project.yaml"), ("A", "contracts/mission-status/schemas/ProjectRenamed.yaml")]
    assert scope_problems(changes, SLICE_ALLOWED) == ["out_of_scope: D contracts/mission-status/schemas/Project.yaml"]


def test_the_registration_paths_are_reported_unless_their_rules_are_supplied() -> None:
    problems = scope_problems(REGISTRATION_CHANGES, SLICE_ALLOWED)
    assert problems == [f"out_of_scope: {status} {path}" for status, path in REGISTRATION_CHANGES]
    assert scope_problems(REGISTRATION_CHANGES, [*SLICE_ALLOWED, *EXTRA_ALLOWED_REGISTRATIONS]) == []


def test_a_registration_path_with_another_status_or_a_third_workflow_file_is_reported() -> None:
    allowed = [*SLICE_ALLOWED, *EXTRA_ALLOWED_REGISTRATIONS]
    assert scope_problems([("A", PACKS_WORKFLOW_PATH)], allowed) == ["out_of_scope: A .github/workflows/packs.yml"]
    assert scope_problems([("M", ".github/workflows/ci-nightly.yml")], allowed) == ["out_of_scope: M .github/workflows/ci-nightly.yml"]
    assert scope_problems([("A", ".github/workflows/ci-router.yml")], allowed) == ["out_of_scope: A .github/workflows/ci-router.yml"]


@pytest.mark.parametrize(
    "path",
    ["docs/development/reference/ci-gate-mechanics.md", "tests/ci/test_contracts_workflows.py", "src/specify_cli/status/drift.py", "pyproject.toml", "uv.lock"],
)
def test_a_file_this_slice_does_not_touch_is_reported_for_every_status(path: str) -> None:
    """The previous slice's router companions are not in this slice's set, and neither is any ``src/`` file or dependency file."""
    for status in ("A", "M", "D"):
        _expect_problem(f"{status} for {path}", scope_problems([(status, path)], SLICE_ALLOWED), f"out_of_scope: {status} {path}")


def test_a_planted_extra_file_and_a_planted_src_path_fail_the_scope_over_a_branch_inside_the_slice() -> None:
    allowed = [*SLICE_ALLOWED, *EXTRA_ALLOWED_REGISTRATIONS]
    inside = [*IN_SCOPE_CHANGES, *REGISTRATION_CHANGES]
    assert scope_problems(inside, allowed) == []
    extra, source = ("A", "notes/extra-file.md"), ("M", "src/specify_cli/status/store.py")
    _expect_problem("a planted extra file", scope_problems([*inside, extra], allowed), f"out_of_scope: {extra[0]} {extra[1]}")
    _expect_problem("a planted src path", scope_problems([*inside, source], allowed), f"out_of_scope: {source[0]} {source[1]}")
    assert scope_problems([*inside, extra, source], allowed) == [f"out_of_scope: {extra[0]} {extra[1]}", f"out_of_scope: {source[0]} {source[1]}"]


def test_the_slice_data_names_exactly_these_rules() -> None:
    """A changed list of rules changes this pin and the data together: the Mission's file set is written once."""
    assert len(SLICE_ALLOWED) == 15
    assert [rule.path for rule in SLICE_ALLOWED if rule.match == PREFIX] == ["contracts/mission-status/", "tests/contract/"]
    assert sorted(rule.path for rule in SLICE_ALLOWED if rule.match == EXACT) == sorted(
        [
            "contracts/mission-status/openapi.yaml",
            "contracts/mission-status/CHANGELOG.md",
            "contracts/mission-status/schemas/_index.yaml",
            "contracts/mission-status/examples/_index.yaml",
            "contracts/mission-status/parameters/_index.yaml",
            "contracts/mission-status/responses/_index.yaml",
            PROJECT_SCHEMA_PATH,
            "contracts/mission-status/examples/Project.example.yaml",
            "contracts/mission-status/paths/project.yaml",
            FIXTURE_BUILDER_PATH,
            "contracts/tools/negative_cases.json",
            "contracts/tools/enum_pins.json",
            ROUTER_WORKFLOW_PATH,
        ]
    )
    assert len(EXTRA_ALLOWED_REGISTRATIONS) == 4
    assert len(IN_SCOPE_CHANGES) == 19 and len(REGISTRATION_CHANGES) == 4


def dependency_problems(rules: Sequence[ScopeRule], changes: Sequence[tuple[str, str]]) -> list[str]:
    """Every rule or change that names a dependency file (at any depth); this slice adds no dependency."""
    named = [f"dependency_rule: {rule.path}" for rule in rules if Path(rule.path).name in DEPENDENCY_FILES]
    return named + [f"dependency_change: {status} {path}" for status, path in changes if Path(path).name in DEPENDENCY_FILES]


def test_no_rule_and_no_change_of_the_slice_names_a_dependency_file() -> None:
    assert DEPENDENCY_FILES == ("pyproject.toml", "uv.lock")
    assert dependency_problems([*SLICE_ALLOWED, *EXTRA_ALLOWED_REGISTRATIONS], [*IN_SCOPE_CHANGES, *REGISTRATION_CHANGES]) == []


@pytest.mark.parametrize("name", DEPENDENCY_FILES)
def test_a_planted_added_dependency_fails_the_dependency_check(name: str) -> None:
    rule = ScopeRule(EXACT, name, MODIFIED)
    assert dependency_problems([*SLICE_ALLOWED, rule], []) == [f"dependency_rule: {name}"], f"{NOT_KILLED}: a rule for {name}"
    assert dependency_problems([], [("M", name)]) == [f"dependency_change: M {name}"], f"{NOT_KILLED}: a change of {name}"
    nested = f"packages/extra/{name}"
    assert dependency_problems([], [("A", nested)]) == [f"dependency_change: A {nested}"], f"{NOT_KILLED}: a nested {name}"


def test_an_empty_change_list_is_a_failure_not_a_pass() -> None:
    assert scope_problems([], SLICE_ALLOWED) == ["no_changes: no entry was examined"]


def test_the_allowed_data_has_the_shape_the_proof_needs() -> None:
    every_rule = [*SLICE_ALLOWED, *EXTRA_ALLOWED_REGISTRATIONS]
    assert all("D" not in rule.statuses and rule.statuses for rule in every_rule), "no rule admits a deletion"
    assert all("*" not in rule.path and "?" not in rule.path for rule in every_rule), "no wildcard"
    assert all(rule.path.endswith("/") for rule in every_rule if rule.match == PREFIX), "a prefix rule ends with a slash"
    assert all(rule.statuses == MODIFIED for rule in every_rule if rule.match == EXACT), "an existing named file admits M only"
    assert [rule.path for rule in EXTRA_ALLOWED_REGISTRATIONS] == [
        PACKS_WORKFLOW_PATH,
        "tests/architectural/test_ci_corpus_trigger_completeness.py",
        "tests/ci/test_contracts_routing.py",
        "tests/release/ci_retirement_scrub.json",
    ]
    assert not any("required_examples" in rule.path for rule in every_rule), "the example-required guard lives in a test (OD-2)"


# --------------------------------------------------------------------------------------
# Terminology: no "feature" in the module or in the changelog entry; cited symbol names are exempt (AC-VERSION)
# --------------------------------------------------------------------------------------

FORBIDDEN_TERM = "feature"
CITATION_KEYS = frozenset({"x-source", "x-derived"})
# inside a citation only these members name a symbol, a path or an input; prose such as ``rule`` is scanned,
# and so is any whitespace-bearing text inside these members (a name or a path holds no whitespace)
SYMBOL_KEYS = frozenset({"path", "symbol", "inputs"})


def _term_hits(node: Any, where: str, *, in_citation: bool = False) -> list[str]:
    """Every string key or value below ``node`` that holds the forbidden term; symbol names inside citations are skipped."""
    if isinstance(node, str):
        return [f"terminology: {where}: {node[:60]!r}"] if FORBIDDEN_TERM in node.lower() else []
    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            hits += _term_hits(str(key), f"{where} (key)")
            if in_citation and key in SYMBOL_KEYS:
                hits += _prose_hits(value, f"{where}/{key}")
                continue
            hits += _term_hits(value, f"{where}/{key}", in_citation=in_citation or key in CITATION_KEYS)
    elif isinstance(node, list):
        for position, item in enumerate(node):
            hits += _term_hits(item, f"{where}[{position}]", in_citation=in_citation)
    return hits


def _prose_hits(node: Any, where: str) -> list[str]:
    """Scan only the prose inside a symbol, path or inputs value: a name or a path holds no whitespace."""
    if isinstance(node, str):
        return _term_hits(node, where) if any(character.isspace() for character in node) else []
    if isinstance(node, list):
        return [hit for position, item in enumerate(node) for hit in _prose_hits(item, f"{where}[{position}]")]
    return []


def terminology_problems(module_dir: Path, entry: str) -> list[str]:
    """The term hits over every YAML file of the module (citation values skipped) and over the CHANGELOG entry text."""
    files = sorted(module_dir.rglob("*.yaml"))
    if not files:
        return [f"no_files: no YAML file was found under {module_dir.name}"]
    hits: list[str] = []
    for path in files:
        hits += _term_hits(_read_yaml(path), path.relative_to(module_dir).as_posix())
    hits += [f"terminology: CHANGELOG entry: {line[:60]!r}" for line in entry.splitlines() if FORBIDDEN_TERM in line.lower()]
    return hits


def test_the_module_and_the_1_1_entry_hold_no_feature_term() -> None:
    assert terminology_problems(MODULE, _real_entry()) == []


def test_a_planted_feature_in_a_description_is_found(tmp_path: Path) -> None:
    (tmp_path / "A.yaml").write_text("title: A\ndescription: A Feature flag of the work package.\n", encoding="utf-8")
    hits = terminology_problems(tmp_path, "")
    assert hits and hits[0].startswith("terminology: A.yaml/description"), f"{NOT_KILLED}: a planted feature: {hits}"


def test_a_planted_feature_in_a_property_name_an_example_value_and_the_entry_is_found(tmp_path: Path) -> None:
    (tmp_path / "B.yaml").write_text("properties:\n  featureDir:\n    type: string\nexamples:\n  - [features]\n", encoding="utf-8")
    hits = terminology_problems(tmp_path, "line one\nA feature here\n")
    assert len(hits) == 3, f"{NOT_KILLED}: key, list value and entry text: {hits}"


def test_a_cited_symbol_name_with_feature_inside_a_citation_is_allowed(tmp_path: Path) -> None:
    text = "title: C\nproperties:\n  dir:\n    x-source:\n      path: src/specify_cli/core/paths.py\n      symbol: feature_dir\n"
    (tmp_path / "C.yaml").write_text(text + "    x-derived:\n      rule: reads the value\n      inputs:\n        - feature_dir\n", encoding="utf-8")
    assert terminology_problems(tmp_path, "") == []


def test_a_planted_feature_in_the_prose_of_a_citation_is_found(tmp_path: Path) -> None:
    text = "title: D\nproperties:\n  dir:\n    x-derived:\n      rule: reads the feature value\n      inputs:\n        - feature_dir\n"
    (tmp_path / "D.yaml").write_text(text, encoding="utf-8")
    hits = terminology_problems(tmp_path, "")
    assert len(hits) == 1 and "rule" in hits[0], f"{NOT_KILLED}: a feature in a citation rule: {hits}"


def test_a_planted_feature_in_prose_inside_a_symbol_path_or_inputs_value_is_found(tmp_path: Path) -> None:
    text = (
        "title: E\nproperties:\n  dir:\n    x-source:\n      path: src/a.py, the feature directory\n      symbol: reads the feature value\n"
        "    x-derived:\n      rule: reads the value\n      inputs:\n        - the feature input\n"
    )
    (tmp_path / "E.yaml").write_text(text, encoding="utf-8")
    hits = terminology_problems(tmp_path, "")
    assert len(hits) == 3, f"{NOT_KILLED}: prose inside a symbol, path and inputs value: {hits}"


def test_a_scan_that_finds_no_file_fails_loudly(tmp_path: Path) -> None:
    assert terminology_problems(tmp_path, "") == [f"no_files: no YAML file was found under {tmp_path.name}"]


# --------------------------------------------------------------------------------------
# Credential kinds: the descriptions name what SECRET_PATTERNS refuses (FR-019)
# --------------------------------------------------------------------------------------

_TOKEN_PREFIX_LETTERS = re.compile(r"gh\[([a-z]+)\]_")
_AWS_PREFIXES = re.compile(r"\(\?:([A-Z]+(?:\|[A-Z]+)*)\)")
GITHUB_FINE_GRAINED_PREFIX = "github_pat"
PEM_WORDS = ("PEM", "private key")


def credential_words(patterns: Sequence[re.Pattern[str]]) -> list[str]:
    """The words a description must use to name the kinds ``patterns`` refuse, read from the pattern sources."""
    words: list[str] = []
    for position, pattern in enumerate(patterns):
        source = pattern.pattern
        classic, aws = _TOKEN_PREFIX_LETTERS.search(source), _AWS_PREFIXES.search(source)
        if classic:
            words += [f"gh{letter}" for letter in classic.group(1)]
        elif GITHUB_FINE_GRAINED_PREFIX in source:
            words.append(GITHUB_FINE_GRAINED_PREFIX)
        elif aws:
            words += aws.group(1).split("|")
        elif "PRIVATE KEY" in source:
            words += PEM_WORDS
        else:
            raise AssertionError(f"credential pattern {position} is of a kind this proof does not know: {source!r}")
    return words


def credential_description_problems(patterns: Sequence[re.Pattern[str]], descriptions: dict[str, str]) -> list[str]:
    words = credential_words(patterns)
    return [f"credential_word_missing: {word!r} in {where}" for where, text in descriptions.items() for word in words if word not in text]


def _credential_descriptions() -> dict[str, str]:
    readable = _read_yaml(MODULE / "schemas" / "ArtifactEntry.yaml")["properties"]["readable"]["description"]
    refused = _read_yaml(MODULE / "responses" / "ArtifactSecretRefused.yaml")["description"]
    return {"ArtifactEntry.readable": readable, "ArtifactSecretRefused": refused}


def test_the_descriptions_name_every_credential_kind_of_the_secret_patterns() -> None:
    patterns = _tool(LEAK_PATTERNS_TOOL).SECRET_PATTERNS
    assert len(patterns) == 4, "a credential kind was added or removed: update the descriptions and this proof together"
    assert credential_description_problems(patterns, _credential_descriptions()) == []


def test_the_pattern_sources_give_the_documented_words() -> None:
    words = credential_words(_tool(LEAK_PATTERNS_TOOL).SECRET_PATTERNS)
    assert words == ["ghp", "gho", "ghu", "ghs", "ghr", "github_pat", "AKIA", "ASIA", "PEM", "private key"]


def test_a_credential_kind_added_to_the_patterns_but_not_to_the_descriptions_is_reported() -> None:
    extra = re.compile(r"(?<![A-Za-z0-9_])gh[pousrx]_[A-Za-z0-9]{36,}")
    patterns = (extra, *_tool(LEAK_PATTERNS_TOOL).SECRET_PATTERNS[1:])
    problems = credential_description_problems(patterns, _credential_descriptions())
    assert "credential_word_missing: 'ghx' in ArtifactSecretRefused" in problems, f"{NOT_KILLED}: a new token prefix: {problems}"


def test_a_description_that_drops_a_credential_kind_is_reported() -> None:
    descriptions = {name: text.replace("AKIA", "XXXX") for name, text in _credential_descriptions().items()}
    problems = credential_description_problems(_tool(LEAK_PATTERNS_TOOL).SECRET_PATTERNS, descriptions)
    assert "credential_word_missing: 'AKIA' in ArtifactEntry.readable" in problems


def test_a_pattern_of_an_unknown_kind_fails_loudly() -> None:
    with pytest.raises(AssertionError, match="does not know"):
        credential_words([re.compile("something-new")])


def test_the_representative_credentials_match_exactly_the_patterns_that_name_them() -> None:
    """The description is only as true as the patterns: each documented kind has one sample that its pattern matches."""
    patterns = _tool(LEAK_PATTERNS_TOOL).SECRET_PATTERNS
    samples = [
        "gh" + "p" + "_" + "A" * 36,
        GITHUB_FINE_GRAINED_PREFIX + "_" + "A" * 40,
        "AK" + "IA" + "A" * 16,
        "-" * 5 + "BEGIN PRIVATE KEY" + "-" * 5,
    ]
    assert [[pattern.search(sample) is not None for pattern in patterns].index(True) for sample in samples] == [0, 1, 2, 3]


# --------------------------------------------------------------------------------------
# Refusal examples pair each code with its status; the required examples exist (FR-019, OD-2)
# --------------------------------------------------------------------------------------

ARTIFACT_REFUSAL_STATUS = {
    "invalid_artifact_path": 400,
    "not_found": 404,
    "artifact_too_large": 413,
    "artifact_not_text": 415,
    "artifact_secret": 422,
    "artifact_unreadable": 500,
    "artifact_listing_unreadable": 500,
}
DETAIL_REFUSAL_STATUS = {"not_found": 404, "source_unreadable": 500}
REFUSAL_GROUPS = (
    ("ArtifactRefusal", "ArtifactRefusalCode", ARTIFACT_REFUSAL_STATUS),
    ("WorkPackageDetailRefusal", "WorkPackageDetailRefusalCode", DETAIL_REFUSAL_STATUS),
)
REQUIRED_EXAMPLES: tuple[str, ...] = (
    "ArtifactListing.populated.yaml",
    "ArtifactListing.truncated.yaml",
    "ArtifactContent.empty.yaml",
    "ArtifactContent.json.yaml",
    "ArtifactContent.markdown.yaml",
    "ArtifactContent.redacted.yaml",
    "ArtifactRefusal.invalid-artifact-path.yaml",
    "ArtifactRefusal.not-found.yaml",
    "ArtifactRefusal.artifact-too-large.yaml",
    "ArtifactRefusal.artifact-not-text.yaml",
    "ArtifactRefusal.artifact-secret.yaml",
    "ArtifactRefusal.artifact-unreadable.yaml",
    "ArtifactRefusal.artifact-listing-unreadable.yaml",
    "WorkPackageDetail.populated.yaml",
    "WorkPackageDetail.no-cycles.yaml",
    "WorkPackageDetail.null-workspace.yaml",
    "WorkPackageDetail.planning-lane.yaml",
    "WorkPackageDetail.unknown-change-state.yaml",
    "WorkPackageDetail.unparseable-cycle.yaml",
    "WorkPackageDetail.cycle-without-path.yaml",
    "WorkPackageDetailRefusal.not-found.yaml",
    "WorkPackageDetailRefusal.source-unreadable.yaml",
)


def refusal_example_problems(examples: dict[str, Any], statuses: dict[str, int]) -> list[str]:
    """Each example carries a known code with the status pinned to it; every code has at least one example."""
    problems = []
    for name, document in examples.items():
        code, status = (document.get("code"), document.get("status")) if isinstance(document, dict) else (None, None)
        if code not in statuses:
            problems.append(f"unknown_code: {name}: {code!r}")
        elif status != statuses[code]:
            problems.append(f"wrong_status: {name}: {code} carries {status!r}, pinned to {statuses[code]}")
    seen = {document.get("code") for document in examples.values() if isinstance(document, dict)}
    problems += [f"code_without_example: {code}" for code in statuses if code not in seen]
    return problems


def required_example_problems(examples_dir: Path, required: Sequence[str]) -> list[str]:
    """Each required example file exists and holds a non-empty mapping; an empty requirement is itself a problem."""
    if not required:
        return ["no_requirement: the list of required examples is empty"]
    problems = []
    for name in required:
        path = examples_dir / name
        if not path.is_file():
            problems.append(f"example_missing: {name}")
        elif not isinstance(_read_yaml(path), dict) or not _read_yaml(path):
            problems.append(f"example_empty: {name}")
    return problems


def _refusal_examples(schema: str) -> dict[str, Any]:
    return {path.name: _read_yaml(path) for path in sorted((MODULE / "examples").glob(f"{schema}.*.yaml"))}


@pytest.mark.parametrize(("schema", "code_schema", "statuses"), REFUSAL_GROUPS)
def test_the_refusal_examples_pair_each_code_with_its_pinned_status(schema: str, code_schema: str, statuses: dict[str, int]) -> None:
    assert refusal_example_problems(_refusal_examples(schema), statuses) == []
    assert set(_read_yaml(MODULE / "schemas" / f"{code_schema}.yaml")["enum"]) == set(statuses), "the code enumeration and the pinned statuses differ"


@pytest.mark.parametrize(("schema", "code_schema", "statuses"), REFUSAL_GROUPS)
def test_a_refusal_example_with_another_status_or_an_unknown_code_is_reported(schema: str, code_schema: str, statuses: dict[str, int]) -> None:
    del code_schema
    examples = copy.deepcopy(_refusal_examples(schema))
    first, second = sorted(examples)[:2]
    examples[first]["status"] = 418
    examples[second]["code"] = "invented_code"
    problems = refusal_example_problems(examples, statuses)
    assert any(problem.startswith("wrong_status") for problem in problems), f"{NOT_KILLED}: a wrong status: {problems}"
    assert any(problem.startswith("unknown_code") for problem in problems), f"{NOT_KILLED}: an unknown code: {problems}"


def test_a_code_without_any_example_is_reported() -> None:
    examples = {name: document for name, document in _refusal_examples("ArtifactRefusal").items() if "not-found" not in name}
    assert "code_without_example: not_found" in refusal_example_problems(examples, ARTIFACT_REFUSAL_STATUS)


def test_every_required_example_exists_and_holds_a_mapping() -> None:
    assert required_example_problems(MODULE / "examples", REQUIRED_EXAMPLES) == []


def test_the_unparseable_cycle_example_nulls_only_what_a_parse_failure_nulls() -> None:
    """An unparseable cycle file is still an eligible artifact: its pointer and path are set, and only reviewedAt, reviewer and verdict are null."""
    cycle = _read_yaml(MODULE / "examples" / "WorkPackageDetail.unparseable-cycle.yaml")["reviewCycles"][0]
    assert (cycle["reviewedAt"], cycle["reviewer"], cycle["verdict"]) == (None, None, None)
    assert cycle["feedbackReference"] and cycle["artifactPath"]
    assert cycle["artifactPath"].endswith(f"review-cycle-{cycle['cycleNumber']}.md")


def test_a_required_example_that_is_deleted_or_emptied_is_reported(tmp_path: Path) -> None:
    shutil.copytree(MODULE / "examples", tmp_path / "examples")
    examples = tmp_path / "examples"
    (examples / REQUIRED_EXAMPLES[0]).unlink()
    (examples / REQUIRED_EXAMPLES[1]).write_text("", encoding="utf-8")
    problems = required_example_problems(examples, REQUIRED_EXAMPLES)
    assert problems == [f"example_missing: {REQUIRED_EXAMPLES[0]}", f"example_empty: {REQUIRED_EXAMPLES[1]}"], f"{NOT_KILLED}: {problems}"


def test_an_empty_requirement_fails_loudly(tmp_path: Path) -> None:
    assert required_example_problems(tmp_path, []) == ["no_requirement: the list of required examples is empty"]


def test_the_required_examples_are_the_new_examples_of_the_module() -> None:
    """No new example file goes unrequired: a deleted example cannot hide behind a list that was never extended."""
    old_schemas = (
        "Project",
        "MissionOverview",
        "MissionDetail",
        "WorkPackage",
        "StatusTransitionEvent",
        "MissionLifecycleEvent",
        "LogTruncatedEvent",
        "StreamRefusal",
        "PageCursorRefusal",
        "MissionOverviewPage",
        "DriftReport",
        "DriftRefusal",
        "OpsInvocationPage",
        "OpsInvocation",
        "OpsRefusal",
    )
    present = {path.name for path in (MODULE / "examples").glob("*.yaml") if not path.name.startswith(("_index", *[f"{old}." for old in old_schemas]))}
    assert present == set(REQUIRED_EXAMPLES)


# --------------------------------------------------------------------------------------
# Citation pins of the Ops read (FR-017, FR-020): the evidence members cite the field they derive from
# --------------------------------------------------------------------------------------

RECORD_SOURCE = "src/specify_cli/invocation/record.py"
EVIDENCE_REFERENCE_SYMBOL = "OpCompletedEvent.evidence_ref"
OPS_EVIDENCE_MEMBERS = ("kind", "value", "redacted")
OPS_INVOCATION_MEMBER_COUNT = 13  # FR-017: thirteen members, all required, seven of them nullable ("twelve" elsewhere is a miscount)


def record_symbol_problems(schema: dict[str, Any], members: Sequence[str], expected: str) -> list[str]:
    """Every member of ``schema`` whose citation of the record module names a symbol other than ``expected``, or none at all."""
    problems = []
    for member in members:
        inputs = schema["properties"][member]["x-derived"]["inputs"]
        symbols = [entry["symbol"] for entry in inputs if isinstance(entry, dict) and entry.get("path") == RECORD_SOURCE]
        if symbols != [expected]:
            problems.append(f"citation: {member} cites {symbols!r} of {RECORD_SOURCE}, not [{expected!r}]")
    return problems


def test_the_evidence_members_cite_the_evidence_reference_of_the_completed_event() -> None:
    schema = _read_yaml(MODULE / "schemas" / "OpsEvidence.yaml")
    assert record_symbol_problems(schema, OPS_EVIDENCE_MEMBERS, EVIDENCE_REFERENCE_SYMBOL) == []
    assert list(schema["properties"]) == list(OPS_EVIDENCE_MEMBERS)


@pytest.mark.parametrize("member", OPS_EVIDENCE_MEMBERS)
def test_a_bare_event_citation_on_an_evidence_member_is_refused(member: str) -> None:
    schema = copy.deepcopy(_read_yaml(MODULE / "schemas" / "OpsEvidence.yaml"))
    for entry in schema["properties"][member]["x-derived"]["inputs"]:
        if isinstance(entry, dict) and entry.get("path") == RECORD_SOURCE:
            entry["symbol"] = "OpCompletedEvent"
    problems = record_symbol_problems(schema, OPS_EVIDENCE_MEMBERS, EVIDENCE_REFERENCE_SYMBOL)
    assert len(problems) == 1 and problems[0].startswith(f"citation: {member} "), f"{NOT_KILLED}: a bare citation on {member}: {problems}"


def test_an_evidence_member_without_a_citation_of_the_record_module_is_refused() -> None:
    schema = copy.deepcopy(_read_yaml(MODULE / "schemas" / "OpsEvidence.yaml"))
    schema["properties"]["value"]["x-derived"]["inputs"] = ["kind"]
    assert len(record_symbol_problems(schema, OPS_EVIDENCE_MEMBERS, EVIDENCE_REFERENCE_SYMBOL)) == 1


def test_an_ops_invocation_has_thirteen_members_all_required() -> None:
    schema = _read_yaml(MODULE / "schemas" / "OpsInvocation.yaml")
    assert len(schema["properties"]) == OPS_INVOCATION_MEMBER_COUNT == 13
    assert sorted(schema["required"]) == sorted(schema["properties"])
