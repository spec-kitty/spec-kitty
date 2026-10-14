"""The golden-honesty test of the Mission Status API conformance gate (spec FR-008 (ii), AC-8a/8b/8d, AC-5d, AC-1f, AC-6e).

The committed goldens under ``services/mission-status-api/src/test/resources/conformance/`` must equal live output of the Python
reference helpers, byte for byte. Every fixture is provisioned into a temporary directory (a git repository only where the class
needs one) by ``_mission_status_conformance``; nothing reads the committed trees in place.

Each guarantee has a control that turns it red: a planted trivial golden, an edited golden value, a monkeypatched derivation, a
skipped or misplaced worktree registration, a disagreeing HEAD text, an unsorted writer, a removed leak pattern.
"""

from __future__ import annotations

import hashlib
import copy
import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import parse_iso
from specify_cli.coordination.surface_resolver import WorktreeTopology, classify_worktree_topology
from specify_cli.migration import schema_version as schema
from specify_cli.status.reducer import materialize_snapshot
from specify_cli.status.tail_reader import ResumeRefused, validate_resume_cursor
from tests.contract import _mission_status_conformance as gen
from tests.contract import _mission_status_payloads as payloads
from tests.contract import _mission_status_project as project

pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFORMANCE = REPO_ROOT / gen.CONFORMANCE_DIR
LEDGER = "status.events.jsonl"
MISSIONS = gen.MISSIONS_GOLDEN
PROJECT = gen.PROJECT_GOLDEN
STREAM = gen.STREAM_GOLDEN
ALT_DATE = "2031-07-07T12:34:56+00:00"
NON_CLASS_FILES = frozenset({gen.MANIFEST_NAME, gen.RESOLVER_CASES_NAME})
# The fixtures each class must hold at least (the floor of the discovered set; zero matches fails).
CLASS_FLOORS: Mapping[str, int] = {
    "interleaved": 4,
    "coordination": 2,
    "coord-husk": 1,
    "absent-topology": 1,
    "lifecycle-only": 1,
    "no-ledger": 1,
    "log-truncated": 1,
    "malformed-rows": 11,
    "torn-final-line": 2,
    "crlf-and-listing": 2,
    "project-header": 9,
    "projection": 3,
    "secret-canaries": 1,
    "symlink": 3,
}
REFUSAL = "refusal"
ALLOWED_REFUSALS = frozenset({"StoreError", "DiaryError", "UnicodeDecodeError", "ValueError", "JSONDecodeError", "MissionMetaReadError", "ProjectionError"})
REFUSAL_CLASS_OF_MALFORMED = {
    "invalid-json-line": {"JSONDecodeError"},
    "non-object-line": {"StoreError"},
    "missing-required-key": {"StoreError"},
    "unknown-lane": {"StoreError"},
    "unknown-kind": {"StoreError"},
    "malformed-meta": {"ValueError"},
    "empty-meta": {"ValueError"},
    "non-utf8-meta": {"ValueError"},
    "invalid-utf8-ledger": {"UnicodeDecodeError"},
}
CANARY_PREFIX = "CANARY-NOT-A-SECRET-"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tools() -> Iterator[payloads.ContractTools]:
    with pytest.MonkeyPatch.context() as patch:
        yield payloads.load_contract_tools(patch, REPO_ROOT)


@pytest.fixture(scope="module")
def fixtures() -> list[gen.Fixture]:
    return gen.discover_fixtures(CONFORMANCE)


@pytest.fixture(scope="module")
def generated(tools: payloads.ContractTools) -> dict[Path, bytes]:
    """Every generated file from live Python output, computed once for the module."""
    return gen.generate(CONFORMANCE, tools)


def golden_of(fixture: gen.Fixture, name: str) -> Any:
    return json.loads((fixture.path / gen.GOLDEN_DIR / name).read_text(encoding="utf-8"))


def goldens_in(fixtures: list[gen.Fixture], tag: str) -> dict[str, dict[str, Any]]:
    """The committed golden documents of one class: fixture name -> file name -> document."""
    found: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        if fixture.tag != tag:
            continue
        directory = fixture.path / gen.GOLDEN_DIR
        found[fixture.name] = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.json"))} if directory.is_dir() else {}
    return found


def copy_conformance(target: Path) -> Path:
    """A scratch repository root holding a copy of the conformance tree and of leak-patterns.json."""
    shutil.copytree(CONFORMANCE, target / gen.CONFORMANCE_DIR)
    (target / gen.LEAK_PATTERNS_FILE).parent.mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / gen.LEAK_PATTERNS_FILE, target / gen.LEAK_PATTERNS_FILE)
    return target


def ledger_counts(ledger: Path, scratch: Path) -> dict[str, int]:
    """The lane counts the reducer gives for one ledger file."""
    scratch.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ledger, scratch / LEDGER)
    return payloads.lane_counts_of(materialize_snapshot(scratch))


def ledger_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Machinery: canonical writer, ignore-list, deterministic provisioning
# ---------------------------------------------------------------------------


def test_the_comparison_ignore_list_is_empty() -> None:
    """Spec FR-008 "Comparison scope" and WP07 subtask 3: one named constant per language, asserted empty by a test."""
    assert gen.MissionStatusIgnoreList == ()


def test_the_canonical_writer_sorts_keys_packs_separators_and_keeps_utf8() -> None:
    planted = {"b": 1, "a": {"z": "café", "y": [3, 2, 1]}}
    assert gen.canonical_json(planted) == '{"a":{"y":[3,2,1],"z":"café"},"b":1}'
    assert gen.canonical_bytes(planted).endswith(b"}\n")


def test_an_unsorted_writer_turns_the_byte_identity_red(fixtures: list[gen.Fixture], tools: payloads.ContractTools, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = next(item for item in fixtures if item.key == "interleaved/two-missions")
    committed = (fixture.path / gen.GOLDEN_DIR / MISSIONS).read_bytes()
    assert gen.golden_bytes_of(fixture, tools)[MISSIONS] == committed, "control: the real writer is byte-identical"
    monkeypatch.setattr(gen, "canonical_json", lambda document: json.dumps(document, ensure_ascii=False, separators=(",", ":")))
    assert gen.golden_bytes_of(fixture, tools)[MISSIONS] != committed


def test_provisioning_is_deterministic_across_temp_roots_and_git_dates(fixtures: list[gen.Fixture], tools: payloads.ContractTools) -> None:
    chosen = [fixture for fixture in fixtures if gen.needs_git(fixture.path)] + [fixture for fixture in fixtures if fixture.key == "interleaved/two-missions"]
    assert len(chosen) >= 3
    for fixture in chosen:
        first = gen.golden_bytes_of(fixture, tools)
        second = gen.golden_bytes_of(fixture, tools, date=ALT_DATE)
        assert first == second, fixture.key


def test_no_golden_holds_a_temp_path_a_commit_id_or_a_git_date(fixtures: list[gen.Fixture]) -> None:
    leaks = re.compile(r"conformance-|/" + r"tmp/|\b[0-9a-f]{40}\b|" + re.escape(gen.DEFAULT_GIT_DATE[:10]) + r"T00:00:00")
    for fixture in fixtures:
        for path in sorted((fixture.path / gen.GOLDEN_DIR).glob("*.json")) if (fixture.path / gen.GOLDEN_DIR).is_dir() else []:
            assert not leaks.search(path.read_text(encoding="utf-8")), path


# ---------------------------------------------------------------------------
# Worktree registration (plan section 1)
# ---------------------------------------------------------------------------


def registration_problems(fixture: gen.Fixture, root: Path) -> list[str]:
    """Compare the git worktree registry with the coordination worktree ROOT of every Mission of ``fixture``."""
    problems: list[str] = []
    registered = {Path(line.removeprefix("worktree ")).resolve() for line in gen.worktree_porcelain(root).splitlines() if line.startswith("worktree ")}
    for identity in gen.mission_identities(root):
        worktree = gen.coordination_worktree_root(root, identity)
        mission_dir = worktree / "kitty-specs" / identity.directory
        coord_source = (fixture.path / gen.COORD_SOURCE / identity.directory).is_dir()
        husk_source = (fixture.path / gen.HUSK_SOURCE / identity.directory).is_dir()
        if coord_source:
            if worktree.resolve() not in registered:
                problems.append(f"{identity.directory}: the worktree root is not registered")
            topology = classify_worktree_topology(mission_dir, repo_root=root)
            if topology is not WorktreeTopology.COORD_WORKTREE:
                problems.append(f"{identity.directory}: classified {topology.name}, not COORD_WORKTREE")
        elif husk_source:
            topology = classify_worktree_topology(mission_dir, repo_root=root)
            if topology is not WorktreeTopology.UNREGISTERED or worktree.resolve() in registered:
                problems.append(f"{identity.directory}: the husk is registered or not UNREGISTERED ({topology.name})")
        elif worktree.resolve() in registered:
            problems.append(f"{identity.directory}: an own-class Mission has a registry entry")
    if not any(((fixture.path / gen.COORD_SOURCE).is_dir(), (fixture.path / gen.HUSK_SOURCE).is_dir())) and len(registered) != 1:
        problems.append("an own-class fixture has more than the main worktree in the registry")
    return problems


def provisioned_problems(fixture: gen.Fixture, tmp_path: Path, wrap_git: Callable[[Callable[..., None]], Callable[..., None]] | None = None) -> list[str]:
    root = tmp_path / "project"
    root.mkdir(parents=True)
    original = gen.run_git
    try:
        if wrap_git is not None:
            gen.run_git = wrap_git(original)  # type: ignore[assignment]  # a control swaps the module's own git runner for one scope
        gen.provision(fixture, root)
        with gen.git_environment(tmp_path, gen.DEFAULT_GIT_DATE):
            return registration_problems(fixture, root)
    finally:
        gen.run_git = original  # type: ignore[assignment]


def skip_registration(real: Callable[..., None]) -> Callable[..., None]:
    def wrapped(repo: Path, *arguments: str) -> None:
        if arguments[:2] == ("worktree", "add"):
            Path(arguments[-1]).mkdir(parents=True, exist_ok=True)
            return
        real(repo, *arguments)

    return wrapped


def register_the_mission_directory(real: Callable[..., None]) -> Callable[..., None]:
    def wrapped(repo: Path, *arguments: str) -> None:
        if arguments[:2] == ("worktree", "add"):
            target = Path(arguments[-1])
            real(repo, *arguments[:-1], str(target / "kitty-specs" / "registered-in-error"))
            return
        real(repo, *arguments)

    return wrapped


def test_coordination_worktrees_are_registered_at_the_root_and_husks_are_not(fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    git_fixtures = [fixture for fixture in fixtures if gen.needs_git(fixture.path)]
    assert any(gen.read_directory_class(fixture.path) == gen.COORD_CLASS for fixture in git_fixtures)
    assert any((fixture.path / gen.HUSK_SOURCE).is_dir() for fixture in git_fixtures)
    for index, fixture in enumerate(git_fixtures):
        assert provisioned_problems(fixture, tmp_path / str(index)) == [], fixture.key
    own = next(fixture for fixture in fixtures if fixture.key == "interleaved/two-missions")
    own_root = tmp_path / "own"
    own_root.mkdir(parents=True)
    gen.provision(own, own_root)
    assert not (own_root / ".git").exists(), "an own-class fixture without a coordination Mission gets no repository"


def test_a_skipped_registration_turns_the_registration_check_red(fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    fixture = next(item for item in fixtures if item.key == "coordination/coordinated-mission")
    assert provisioned_problems(fixture, tmp_path / "control") == []
    assert provisioned_problems(fixture, tmp_path / "planted", skip_registration)


def test_registering_the_mission_directory_instead_of_the_root_turns_the_check_red(fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    fixture = next(item for item in fixtures if item.key == "coordination/coordinated-mission")
    assert provisioned_problems(fixture, tmp_path / "planted", register_the_mission_directory)


# ---------------------------------------------------------------------------
# Project header (AC-1f)
# ---------------------------------------------------------------------------


def branch_of_head_text(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.startswith("ref:"):
        return None
    target = stripped.removeprefix("ref:").strip()
    return target.removeprefix("refs/heads/") if target.startswith("refs/heads/") else None


def head_problems(fixture_path: Path, root: Path) -> list[str]:
    """The branch the oracle read equals the branch parsed from the fixture's HEAD text."""
    text = gen.head_text_of(fixture_path)
    if text is None:
        return ["the fixture has no HEAD text"]
    read = project.read_head(root)
    parsed = branch_of_head_text(text)
    return [] if read == parsed else [f"read_head gave {read!r}, the HEAD text gives {parsed!r}"]


def test_the_branch_the_oracle_read_equals_the_branch_parsed_from_each_head_text(fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    headers = [fixture for fixture in fixtures if fixture.tag == "project-header"]
    assert len(headers) >= CLASS_FLOORS["project-header"]
    for index, fixture in enumerate(headers):
        root = tmp_path / str(index)
        root.mkdir()
        gen.provision(fixture, root)
        assert not (root / ".git" / "objects").exists(), "no git init ran for a project-header fixture"
        assert head_problems(fixture.path, root) == [], fixture.key


def test_a_head_text_that_disagrees_with_the_installed_head_turns_the_assertion_red(fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    healthy = next(fixture for fixture in fixtures if fixture.key == "project-header/healthy")
    root = tmp_path / "root"
    root.mkdir()
    gen.provision(healthy, root)
    scratch_fixture = tmp_path / "scratch-fixture"
    shutil.copytree(healthy.path, scratch_fixture)
    (scratch_fixture / gen.HEAD_TEXT).write_text("ref: refs/heads/some-other-branch\n", encoding="utf-8")
    assert head_problems(healthy.path, root) == [], "control"
    assert head_problems(scratch_fixture, root)


# ---------------------------------------------------------------------------
# The honesty test: committed bytes equal live Python output
# ---------------------------------------------------------------------------


def test_every_generated_file_equals_the_committed_file_byte_for_byte(generated: dict[Path, bytes]) -> None:
    assert gen.differences(REPO_ROOT, generated) == []


def test_every_non_java_only_fixture_has_exactly_its_goldens(fixtures: list[gen.Fixture]) -> None:
    for fixture in fixtures:
        names = {path.name for path in (fixture.path / gen.GOLDEN_DIR).glob("*.json")} if (fixture.path / gen.GOLDEN_DIR).is_dir() else set()
        if fixture.java_only:
            assert names == set(), f"{fixture.key} is java-only and carries no golden"
        else:
            assert set(gen.GOLDEN_FILES) <= names <= {*gen.GOLDEN_FILES, STREAM}, fixture.key


def test_the_file_set_of_the_conformance_tree_is_exactly_the_classes_and_two_data_files(fixtures: list[gen.Fixture]) -> None:
    top = {entry.name for entry in CONFORMANCE.iterdir()}
    assert top == set(gen.CLASS_TAGS) | NON_CLASS_FILES
    assert "portlevel-tests.txt" not in top
    for tag in gen.CLASS_TAGS:
        held = [fixture for fixture in fixtures if fixture.tag == tag]
        assert len(held) >= CLASS_FLOORS[tag], f"class {tag} holds {len(held)} fixtures, the floor is {CLASS_FLOORS[tag]}"


def test_the_manifest_lists_exactly_the_classes_with_their_parity_and_read_directory_classes(fixtures: list[gen.Fixture]) -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert [entry["tag"] for entry in manifest["classes"]] == list(gen.CLASS_TAGS)
    for entry in manifest["classes"]:
        listed = [item["name"] for item in entry["fixtures"]]
        assert listed == [fixture.name for fixture in fixtures if fixture.tag == entry["tag"]]
        assert len(listed) >= CLASS_FLOORS[entry["tag"]]
        assert entry["parity"] in {gen.PARITY_GOLDEN, gen.PARITY_JAVA_ONLY}
        assert all(item["readDirectoryClass"] in {gen.OWN_CLASS, gen.COORD_CLASS} for item in entry["fixtures"])
        if entry["parity"] == gen.PARITY_JAVA_ONLY:
            assert all(gen.TAG_JAVA_ONLY in item["tags"] for item in entry["fixtures"]), "a java-only class is tagged javaOnly per fixture"
    divergence = next(
        item for entry in manifest["classes"] if entry["tag"] == "torn-final-line" for item in entry["fixtures"] if item["name"] == "valid-json-final-line"
    )
    assert gen.TAG_KNOWN_DIVERGENCE in divergence["tags"]
    assert manifest["provisioning"], "the provisioning conventions are documented in the manifest"


# ---------------------------------------------------------------------------
# Distinguishing properties, read from golden CONTENT (AC-8b)
# ---------------------------------------------------------------------------


def items_of(documents: Mapping[str, Any]) -> list[dict[str, Any]]:
    document = documents.get(MISSIONS, {})
    return list(document.get("items", [])) if isinstance(document, dict) else []


def instant_max(values: list[str]) -> str:
    return max(values, key=lambda value: parse_iso(value).timestamp())


def interleaved_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    duplicated = text_differs = tie = reordered = False
    for fixture in (item for item in fixtures if item.tag == "interleaved"):
        by_name = {item["slug"]: item for item in items_of(found[fixture.name])}
        for mission in sorted((fixture.path / "kitty-specs").iterdir()):
            rows = ledger_rows(mission / LEDGER)
            overview = by_name.get(mission.name)
            if overview is None or overview["eventCount"] < 1:
                problems.append(f"{mission.name}: no non-empty overview in the golden")
                continue
            ids = [row["event_id"] for row in rows]
            keys = [(row["at"], row["event_id"]) for row in rows]
            at_values = [row["at"] for row in rows]
            if len(ids) != len(set(ids)):
                duplicated = True
                if overview["eventCount"] != len(set(ids)):
                    problems.append(f"{mission.name}: a duplicated event_id is counted twice")
            if len(set(at_values)) < len(at_values):
                tie = True
            if keys != sorted(keys):
                reordered = True
            if instant_max(at_values) != max(at_values) and overview["lastActivityAt"] == instant_max(at_values):
                text_differs = True
    for held, label in (
        (duplicated, "a duplicated event_id"),
        (tie, "equal at values"),
        (reordered, "file order differing from sort order"),
        (text_differs, "text order differing from instant order"),
    ):
        if not held:
            problems.append(f"no interleaved fixture shows {label}")
    return problems


def coordination_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    fixture = next((item for item in fixtures if item.key == "coordination/coordinated-mission"), None)
    if fixture is None:
        return ["no coordinated-mission fixture"]
    mission = next((fixture.path / "kitty-specs").iterdir())
    current = fixture.path / gen.COORD_SOURCE / mission.name / "kitty-specs" / mission.name / LEDGER
    served = items_of(found[fixture.name])
    if len(served) != 1:
        return ["the golden does not serve exactly one Mission"]
    want, stale = ledger_counts(current, scratch / "current"), ledger_counts(mission / LEDGER, scratch / "primary")
    problems = []
    if want == stale:
        problems.append("the coordination and primary ledgers give equal counts")
    if served[0]["statusLaneCounts"] != want:
        problems.append("the golden does not carry the coordination ledger's counts")
    return problems


def husk_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    seen_topologies: set[str] = set()
    for fixture in (item for item in fixtures if item.tag == "coord-husk"):
        by_name = {item["slug"]: item for item in items_of(found[fixture.name])}
        for mission in sorted((fixture.path / "kitty-specs").iterdir()):
            husk = fixture.path / gen.HUSK_SOURCE / mission.name / "kitty-specs" / mission.name / LEDGER
            overview = by_name.get(mission.name)
            if overview is None:
                problems.append(f"{mission.name}: not served")
                continue
            seen_topologies.add(overview["topology"])
            primary_counts, husk_counts = ledger_counts(mission / LEDGER, scratch / mission.name / "p"), ledger_counts(husk, scratch / mission.name / "h")
            if primary_counts == husk_counts:
                problems.append(f"{mission.name}: the husk ledger gives the same counts as the primary ledger")
            if overview["statusLaneCounts"] != primary_counts:
                problems.append(f"{mission.name}: the golden does not reflect the primary ledger")
    if not {"single_branch", "lanes"} <= seen_topologies:
        problems.append(f"the husk class needs a single_branch and a lanes Mission, found {sorted(seen_topologies)}")
    return problems


def absent_topology_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    lanes_states: set[str] = set()
    for fixture in (item for item in fixtures if item.tag == "absent-topology"):
        served = items_of(found[fixture.name])
        problems += [f"{item['slug']}: topology is {item['topology']}" for item in served if item["topology"] != payloads.UNKNOWN_TOPOLOGY]
        for mission in sorted((fixture.path / "kitty-specs").iterdir()):
            meta = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
            lanes = mission / "lanes.json"
            if "topology" in meta:
                problems.append(f"{mission.name}: the fixture stores a topology")
            if lanes.is_file():
                try:
                    json.loads(lanes.read_text(encoding="utf-8"))
                    lanes_states.add("valid")
                except ValueError:
                    lanes_states.add("corrupt")
        problems += [] if len(served) == len(list((fixture.path / "kitty-specs").iterdir())) else ["a Mission with a corrupt lanes.json was not served"]
    if lanes_states != {"valid", "corrupt"}:
        problems.append(f"the fixtures need one valid and one corrupt lanes.json, found {sorted(lanes_states)}")
    return problems


def lifecycle_only_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    for fixture in (item for item in fixtures if item.tag == "lifecycle-only"):
        for mission in sorted((fixture.path / "kitty-specs").iterdir()):
            types = {row["event_type"] for row in ledger_rows(mission / LEDGER)}
            if types != payloads.LIFECYCLE_ALLOW_LIST:
                problems.append(f"{mission.name}: the ledger holds {sorted(types)}, not the seven lifecycle types")
        served = items_of(found[fixture.name])
        if not served:
            problems.append(f"{fixture.name}: the golden serves no Mission")
        for item in served:
            if item["wpTotal"] != 0 or item["lifecycleStatus"] != "draft":
                problems.append(f"{item['slug']}: wpTotal {item['wpTotal']}, lifecycleStatus {item['lifecycleStatus']}")
    return problems or ([] if any(item.tag == "lifecycle-only" for item in fixtures) else ["no lifecycle-only fixture"])


def no_ledger_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    statuses: set[str] = set()
    for fixture in (item for item in fixtures if item.tag == "no-ledger"):
        problems += [f"{path.parent.name}: has a ledger" for path in (fixture.path / "kitty-specs").glob(f"*/{LEDGER}")]
        statuses |= {item["lifecycleStatus"] for item in items_of(found[fixture.name])}
        problems += [
            f"{item['slug']}: discardedAt without discarded"
            for item in items_of(found[fixture.name])
            if item["discardedAt"] and item["lifecycleStatus"] != "discarded"
        ]
    if statuses != {"discarded", "draft"}:
        problems.append(f"the statuses are {sorted(statuses)}, not discarded and draft")
    return problems


def log_truncated_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    reasons: set[str] = set()
    for fixture in (item for item in fixtures if item.tag == "log-truncated"):
        scenarios = found[fixture.name].get(STREAM, {}).get("scenarios", {})
        for scenario in scenarios.values():
            for event in scenario.get("events", []):
                reasons.add(str(event.get("reason")))
            if scenario.get("cursor", {}).get("offset") != 0:
                return ["a truncation scenario did not reset the cursor to offset 0"]
    return [] if len(reasons) >= 2 else [f"the stream goldens hold {sorted(reasons)}; a shrunken log and a same-length rewrite need two reasons"]


BLANK_LINE_FIXTURES = ("blank-line", "blank-line-final")


def blank_line_resume_problems(ledger: Path, cursor: Mapping[str, Any]) -> list[str]:
    """``tail_reader`` itself accepts the cursor's digest and rejects the digest of the last non-blank line (DD-92)."""
    try:
        validate_resume_cursor(ledger, cursor["offset"], cursor["invariant"])
    except ResumeRefused as error:
        return [f"blank-line: tail_reader refuses the recorded cursor ({error.reason})"]
    lines = [line + b"\n" for line in ledger.read_bytes().split(b"\n")[:-1]]
    other = hashlib.sha256(next(line for line in reversed(lines) if line.strip())).hexdigest()  # noqa: TID251 -- file-integrity digest, as tail_reader
    if other == cursor["invariant"]:
        return []  # the last terminated line is not blank: the two digests coincide
    try:
        validate_resume_cursor(ledger, cursor["offset"], other)
    except ResumeRefused:
        return []
    return ["blank-line: tail_reader accepts the digest of the last non-blank line"]


def blank_line_overview_problems(document: Mapping[str, Any], fixture: gen.Fixture) -> list[str]:
    """The blank line is stream-only (spec L10, S4): ``read_events_raw`` skips it, so the overview is served from all three events."""
    served = document.get("items", [])
    if REFUSAL in document or len(served) != 1:
        return ["blank-line: the overview is not served; only poll_once refuses a blank line, and that is the stream scenario"]
    if served[0]["eventCount"] != 3:
        return [f"blank-line: eventCount {served[0]['eventCount']}, not the 3 events around the blank line"]
    ledger = next((fixture.path / "kitty-specs").glob(f"*/{LEDGER}"))
    raw = ledger.read_bytes()
    cursor = served[0]["streamCursor"]
    last_line = raw[: raw.rfind(b"\n") + 1].split(b"\n")[-2] + b"\n"
    if cursor != {"offset": len(raw), "invariant": hashlib.sha256(last_line).hexdigest()}:  # noqa: TID251 -- file-integrity digest, as tail_reader
        return [f"blank-line: streamCursor {cursor} is not the cursor after the whole file"]
    if fixture.name == "blank-line-final" and not raw.endswith(b"\n\n"):
        return ["blank-line-final: the ledger does not end with a blank line"]
    return blank_line_resume_problems(ledger, cursor)


def malformed_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    for fixture in (item for item in fixtures if item.tag == "malformed-rows"):
        document = found[fixture.name].get(MISSIONS, {})
        if fixture.name in BLANK_LINE_FIXTURES:
            problems += blank_line_overview_problems(document, fixture)
            continue
        if fixture.name == "dir-without-meta":
            if REFUSAL in document or [item["slug"] for item in items_of(found[fixture.name])] != ["with-meta"]:
                problems.append("dir-without-meta: the directory without meta.json is listed or refused")
            continue
        refusal = document.get(REFUSAL)
        if refusal is None:
            problems.append(f"{fixture.name}: no refusal recorded")
        elif refusal["exception"] not in REFUSAL_CLASS_OF_MALFORMED.get(fixture.name, ALLOWED_REFUSALS):
            problems.append(f"{fixture.name}: unexpected exception class {refusal['exception']}")
    for name in BLANK_LINE_FIXTURES:
        blank = found.get(name, {}).get(STREAM, {}).get("scenarios", {})
        if not any(REFUSAL in scenario for scenario in blank.values()):
            problems.append(f"{name}: the stream scenario does not record poll_once refusing the blank line")
    return problems


def torn_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    unparseable, valid = found.get("unparseable-final-line", {}).get(MISSIONS, {}), found.get("valid-json-final-line", {}).get(MISSIONS, {})
    if unparseable.get(REFUSAL, {}).get("exception") != "StoreError":
        problems.append("the unparseable final line is not a StoreError refusal")
    if REFUSAL in valid or not valid.get("items"):
        problems.append("the valid-JSON final line is not served")
    for fixture in (item for item in fixtures if item.tag == "torn-final-line"):
        for ledger in (fixture.path / "kitty-specs").glob(f"*/{LEDGER}"):
            if ledger.read_bytes().endswith(b"\n"):
                problems.append(f"{fixture.name}: the final line is terminated")
    return problems


def crlf_listing_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    twin = {item["slug"]: item for item in items_of(found.get("crlf-and-lf-twin", {}))}
    crlf, lf = twin.get("crlf-mission"), twin.get("lf-twin")
    twin_fixture = next((item for item in fixtures if item.key == "crlf-and-listing/crlf-and-lf-twin"), None)
    if crlf is None or lf is None or twin_fixture is None:
        return ["the CRLF fixture or its LF twin is missing"]
    if b"\r\n" not in (twin_fixture.path / "kitty-specs" / "crlf-mission" / LEDGER).read_bytes():
        problems.append("the CRLF ledger holds no CRLF")
    if crlf["statusLaneCounts"] != lf["statusLaneCounts"] or crlf["eventCount"] != lf["eventCount"]:
        problems.append("CRLF counts differ from the LF twin's")
    if crlf["streamCursor"] == lf["streamCursor"]:
        problems.append("streamCursor equals the LF twin's")
    served = items_of(found.get("listing-order", {}))
    names = [item["slug"] for item in served]
    contract_order = [item["slug"] for item in payloads.order_overviews(served)]
    if names != contract_order or len(names) < 3:
        problems.append("the page order is not the contract order")
    if names in (sorted(names), sorted(names, key=str.casefold)):
        problems.append("the page order equals a byte or case-folded name order, so it proves nothing")
    return problems


def project_header_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    branches = {name: documents.get(PROJECT, {}).get("currentBranch") for name, documents in found.items()}
    if branches.get("healthy") != "main" or branches.get("git-pointer-file") != "main":
        problems.append("the healthy and pointer fixtures do not report main")
    for name in ("detached-head", "branch-fails-pattern", "branch-over-255-characters", "branch-host-path-shaped"):
        if name in branches and branches[name] is not None:
            problems.append(f"{name}: currentBranch is not null")
    if found.get("metadata-absent", {}).get(PROJECT, {}).get("schemaVersion") is not None:
        problems.append("metadata-absent: schemaVersion is not null")
    if found.get("unknown-schema-version", {}).get(PROJECT, {}).get("health") != "schema_drift":
        problems.append("unknown-schema-version: health is not schema_drift")
    if not found:
        problems.append("no project-header fixture")
    return problems


def projection_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    human = items_of(found.get("human-text-redaction", {}))
    if not human or not ("[path]" in human[0]["friendlyName"] and "[email]" in human[0]["friendlyName"]):
        problems.append("human-text-redaction: the friendly name holds no [path] and [email] token")
    nulled = items_of(found.get("nullable-strict-field-nulled", {}))
    if not nulled or nulled[0]["missionType"] is not None:
        problems.append("nullable-strict-field-nulled: the nullable strict field is not null")
    instants = items_of(found.get("non-rfc3339-instants-nulled", {}))
    if not instants or any(instants[0][key] is not None for key in ("acceptedAt", "mergedAt", "discardedAt", "lastEventId")):
        problems.append("non-rfc3339-instants-nulled: an off-shape instant or event id is served")
    elif instants[0]["lifecycleStatus"] != "active":
        problems.append("non-rfc3339-instants-nulled: an off-shape instant decided the lifecycle (ruling 1 of 2026-10-13)")
    named = found.get("project-name-refused", {})
    if named.get(PROJECT, {}).get(REFUSAL, {}).get("exception") != "ProjectionError" or not items_of(named):
        problems.append("project-name-refused: the project name was not refused while its Missions were served")
    refused = found.get("strict-field-refused", {}).get(MISSIONS, {})
    if refused.get(REFUSAL, {}).get("exception") != "ProjectionError":
        problems.append("strict-field-refused: the oracle did not refuse with ProjectionError")
    return problems


def java_only_problems(fixtures: list[gen.Fixture], found: Mapping[str, Mapping[str, Any]], scratch: Path) -> list[str]:
    problems: list[str] = []
    for fixture in (item for item in fixtures if item.java_only):
        if any(found.get(fixture.name, {})):
            problems.append(f"{fixture.key}: a java-only fixture carries a golden")
        if fixture.tag == "symlink" and not (fixture.path / gen.SYMLINK_PLAN).is_file():
            problems.append(f"{fixture.key}: no SYMLINK_PLAN")
        if fixture.tag == "secret-canaries":
            planted = {path.name for path in fixture.path.rglob("*") if path.is_file() and CANARY_PREFIX in path.read_text(encoding="utf-8", errors="replace")}
            if not {"config.yaml", "metadata.yaml", "meta.json", LEDGER} <= planted:
                problems.append(f"{fixture.key}: canaries are planted in {sorted(planted)}")
    return problems


PropertyCheck = Callable[[list[gen.Fixture], Mapping[str, Mapping[str, Any]], Path], list[str]]
PROPERTY_CHECKS: Mapping[str, PropertyCheck] = {
    "interleaved": interleaved_problems,
    "coordination": coordination_problems,
    "coord-husk": husk_problems,
    "absent-topology": absent_topology_problems,
    "lifecycle-only": lifecycle_only_problems,
    "no-ledger": no_ledger_problems,
    "log-truncated": log_truncated_problems,
    "malformed-rows": malformed_problems,
    "torn-final-line": torn_problems,
    "crlf-and-listing": crlf_listing_problems,
    "project-header": project_header_problems,
    "projection": projection_problems,
    "secret-canaries": java_only_problems,
    "symlink": java_only_problems,
}


def test_every_class_has_a_property_check() -> None:
    assert set(PROPERTY_CHECKS) == set(gen.CLASS_TAGS)


@pytest.mark.parametrize("tag", gen.CLASS_TAGS)
def test_each_class_shows_its_distinguishing_property_in_its_golden_content(tag: str, fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    assert PROPERTY_CHECKS[tag](fixtures, goldens_in(fixtures, tag), tmp_path) == []


@pytest.mark.parametrize("tag", [spec.tag for spec in gen.CLASS_SPECS if spec.parity == gen.PARITY_GOLDEN])
def test_a_trivial_golden_carrying_the_right_tag_fails_its_class(tag: str, fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    trivial_page = {"items": [], "pageInfo": {"hasNextPage": False, "nextPageCursor": None, "pageSize": 50}}
    planted = {fixture.name: {MISSIONS: trivial_page, PROJECT: {}} for fixture in fixtures if fixture.tag == tag}
    assert planted, f"the class {tag} has fixtures"
    assert PROPERTY_CHECKS[tag](fixtures, planted, tmp_path), f"a trivial golden passed the {tag} check"


# ---------------------------------------------------------------------------
# AC-8a: Python-side perturbations
# ---------------------------------------------------------------------------


def test_an_edited_stale_or_missing_golden_in_a_temp_copy_is_reported(generated: dict[Path, bytes], tmp_path: Path) -> None:
    scratch = copy_conformance(tmp_path / "copy")
    assert gen.differences(scratch, generated) == [], "control: the unedited copy is clean"
    golden_dir = scratch / gen.CONFORMANCE_DIR / "interleaved" / "two-missions" / gen.GOLDEN_DIR
    document = json.loads((golden_dir / MISSIONS).read_text(encoding="utf-8"))
    document["items"][0]["wpTotal"] += 1
    (golden_dir / MISSIONS).write_bytes(gen.canonical_bytes(document))
    (golden_dir / "extra.json").write_text("{}", encoding="utf-8")
    (golden_dir / PROJECT).unlink()
    problems = gen.differences(scratch, generated)
    assert any(problem.startswith("differs:") and "two-missions" in problem for problem in problems)
    assert any(problem.startswith("stale:") for problem in problems)
    assert any(problem.startswith("missing:") for problem in problems)


def test_monkeypatching_one_derivation_helper_turns_the_goldens_red(
    fixtures: list[gen.Fixture], tools: payloads.ContractTools, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = next(item for item in fixtures if item.key == "no-ledger/plain-and-discarded")
    committed = (fixture.path / gen.GOLDEN_DIR / MISSIONS).read_bytes()
    assert gen.golden_bytes_of(fixture, tools)[MISSIONS] == committed, "control"
    monkeypatch.setattr(payloads, "derive_lifecycle_status", lambda *arguments: "active")
    assert gen.golden_bytes_of(fixture, tools)[MISSIONS] != committed


# ---------------------------------------------------------------------------
# AC-5d, AC-1f, AC-6e: version, range and resolver guards
# ---------------------------------------------------------------------------


def test_the_manifest_names_the_installed_events_version_and_the_supported_range() -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    installed = version("spec-kitty-events")
    assert manifest["specKittyEventsVersion"] == installed, f"manifest records spec-kitty-events {manifest['specKittyEventsVersion']}, installed is {installed}"
    assert (manifest["supportedSchemaMin"], manifest["supportedSchemaMax"]) == (schema.MIN_SUPPORTED_SCHEMA, schema.MAX_SUPPORTED_SCHEMA)


def test_the_resolver_cases_yield_their_expected_class_and_the_executed_ids_equal_the_file_and_the_manifest() -> None:
    cases = json.loads((CONFORMANCE / gen.RESOLVER_CASES_NAME).read_text(encoding="utf-8"))
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert len(cases) >= 12, "the resolver table floor"
    executed: list[str] = []
    for case in cases:
        assert gen.resolved_class_of_case(case) == case["expectedClass"], case["id"]
        executed.append(case["id"])
    assert executed == manifest["resolverCaseIds"]
    assert len(set(executed)) == len(executed)
    assert {case["expectedClass"] for case in cases} == {gen.OWN_CLASS, gen.COORD_CLASS}
    assert {case["storedTopology"] for case in cases} == {"single_branch", "lanes", "coord", "lanes_with_coord", "absent"}
    assert {case["lanesJson"] for case in cases} == {"valid", "corrupt", "absent"}


def test_a_wrong_expected_class_is_caught_by_the_resolver_table() -> None:
    cases = json.loads((CONFORMANCE / gen.RESOLVER_CASES_NAME).read_text(encoding="utf-8"))
    husk = next(case for case in cases if case["id"] == "single-branch-husk-with-mission-dir")
    flipped = copy.deepcopy(husk)
    flipped["expectedClass"] = gen.COORD_CLASS
    assert gen.resolved_class_of_case(husk) == husk["expectedClass"]
    assert gen.resolved_class_of_case(flipped) != flipped["expectedClass"]


# ---------------------------------------------------------------------------
# leak-patterns.json (plan section 13, Projection)
# ---------------------------------------------------------------------------


def test_the_manifest_records_the_leak_patterns_file_by_sha256_and_the_python_verdict_of_each_probe(tools: payloads.ContractTools) -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    committed = (REPO_ROOT / gen.LEAK_PATTERNS_FILE).read_bytes()
    assert manifest["leakPatternsSha256"] == gen.file_digest(committed)
    assert committed == gen.leak_patterns_bytes(tools)
    assert manifest["patternProbes"] == gen.pattern_probes(tools)
    assert set(manifest["projectedFieldClasses"]) == {"missionId", "slug", "friendlyName", "targetBranch", "missionType", "nextAction", "name"}
    assert any(not probe["matches"] for probes in manifest["patternProbes"].values() for probe in probes), "a probe that matches nothing"
    assert any(probe["matches"] for probes in manifest["patternProbes"].values() for probe in probes)


def test_the_python_only_regex_divergence_is_recorded_not_rewritten(tools: payloads.ContractTools) -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    document = json.loads((REPO_ROOT / gen.LEAK_PATTERNS_FILE).read_text(encoding="utf-8"))
    recorded = {entry["id"] for entry in manifest["patternDivergences"]}
    assert recorded, "the Unicode-aware classes of the Python patterns are a recorded divergence"
    sources = {entry["id"]: entry["pattern"] for entry in document["patterns"]}
    assert sources["email"] == tools.leak.EMAIL_PATTERN.pattern, "the pattern text is the Python source, not a rewrite"


def test_the_manifest_states_the_regex_divergence_and_the_blank_line_invariant_as_the_oracle_behaves() -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert {entry["construct"] for entry in manifest["patternDivergences"]} == {gen.DIVERGENCE_CONSTRUCT}
    assert "Join_Control" in gen.DIVERGENCE_CONSTRUCT
    assert "needs UNICODE_CHARACTER_CLASS" not in gen.DIVERGENCE_CONSTRUCT
    blank = manifest["provisioning"]["blank-line"]
    assert "last terminated line, a blank line included (tail_reader)" in blank
    assert "non-blank terminated line" not in blank
    assert "is not a fixture" not in blank


def test_removing_one_pattern_from_a_scratch_copy_turns_the_sha_check_and_the_projection_class_red(generated: dict[Path, bytes], tmp_path: Path) -> None:
    scratch = copy_conformance(tmp_path / "copy")
    target = scratch / gen.LEAK_PATTERNS_FILE
    document = json.loads(target.read_text(encoding="utf-8"))
    document["patterns"] = [entry for entry in document["patterns"] if entry["id"] != "email"]
    target.write_bytes(gen.canonical_bytes(document))
    problems = gen.differences(scratch, generated)
    assert any("leak-patterns.json" in problem for problem in problems), problems
    assert any("manifest.json" in problem for problem in problems) is False, "control: the manifest still names the real file"
    manifest = json.loads((scratch / gen.CONFORMANCE_DIR / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert gen.file_digest(target.read_bytes()) != manifest["leakPatternsSha256"]


# ---------------------------------------------------------------------------
# The anchor (D-P9) and the symlink tag
# ---------------------------------------------------------------------------


def test_the_pinned_expected_fixture_agrees_with_the_derivations_the_goldens_are_made_from() -> None:
    expected = payloads.load_expected(REPO_ROOT)
    synthetic = [entry for entry in expected["sample"] if entry["kind"] == "synthetic"]
    assert len(synthetic) >= 4, "the anchor holds its synthetic floor"
    assert payloads.expected_mismatches({"sample": synthetic}, lambda label: {}) == []
    wrong = copy.deepcopy(synthetic)
    wrong[0]["expected"]["lifecycleStatus"] = "done" if wrong[0]["expected"]["lifecycleStatus"] != "done" else "active"
    assert payloads.expected_mismatches({"sample": wrong}, lambda label: {})


def test_the_java_only_classes_are_skipped_by_their_tag_and_the_tag_is_present(fixtures: list[gen.Fixture]) -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    tagged = {item["name"] for entry in manifest["classes"] for item in entry["fixtures"] if gen.TAG_JAVA_ONLY in item.get("tags", [])}
    java_only = {fixture.name for fixture in fixtures if fixture.tag in gen.JAVA_ONLY_TAGS}
    assert tagged == java_only and java_only, "every fixture of a java-only class is tagged and none is compared"
    assert not list(CONFORMANCE.glob("symlink/*/golden")) and not list(CONFORMANCE.glob("secret-canaries/*/golden"))


def test_git_is_only_provisioned_for_the_fixtures_that_need_it(fixtures: list[gen.Fixture]) -> None:
    needing = {fixture.key for fixture in fixtures if gen.needs_git(fixture.path)}
    assert needing == {
        "coordination/coordinated-mission",
        "coordination/coord-worktree-absent",
        "coord-husk/husk-beside-single-branch-and-lanes",
    }
    assert subprocess.run(["git", "--version"], check=True, capture_output=True).returncode == 0
