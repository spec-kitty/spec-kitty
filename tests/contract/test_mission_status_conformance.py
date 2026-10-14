"""The golden-honesty test of the Mission Status API conformance gate (spec FR-008 (ii), AC-8a/8b/8d, AC-5d, AC-1f, AC-6e).

The committed goldens under ``services/mission-status-api/src/test/resources/conformance/`` must equal live output of the Python
reference helpers, byte for byte. Every fixture is provisioned into a temporary directory (a git repository only where the class
needs one) by ``_mission_status_conformance``; nothing reads the committed trees in place.

Each guarantee has a control that turns it red: a planted trivial golden, an edited golden value, a monkeypatched derivation, a
skipped or misplaced worktree registration, a disagreeing HEAD text, an unsorted writer, a removed leak pattern.
"""

from __future__ import annotations

import ast
import hashlib
import copy
import json
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pytest
import yaml

from kernel.clock import datetime, parse_iso
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
    # The detail and artifact classes (FR-014, plan section 14): the Count column at the commit that adds them, never lowered.
    "detail-populated": 8,
    "detail-early": 1,
    "detail-planning-only": 1,
    "phases-matrix": 19,
    "wp-malformed-frontmatter": 28,
    "wp-duplicate-id": 3,
    "wp-two-selectors": 1,
    "wp-prompt-bytes": 13,
    "cycles": 4,
    "legacy-lanes-json": 1,
    "tasks-md": 12,
    "worktree-states": 7,
    "artifacts-populated": 1,
    "artifacts-sort": 1,
    "artifacts-refusals": 1,
    "artifacts-links": 3,
    "artifacts-redaction": 1,
    "lookup-faults": 3,
    "projection-nulls": 6,
    "projection-refusals": 4,
    "resolved-state": 21,
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
        elif fixture.detail:
            assert names == set(gen.GOLDEN_FILES_OF[fixture.tag]), f"{fixture.key} holds exactly the golden files of its class"
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


# ---------------------------------------------------------------------------
# Distinguishing properties of the detail and artifact classes (AC-8b, T048 step 5), read from golden CONTENT
# ---------------------------------------------------------------------------

GET_MISSION = gen.GET_MISSION_GOLDEN
GET_WP = gen.GET_WORK_PACKAGE_GOLDEN
GET_PROMPT = gen.GET_PROMPT_GOLDEN
GET_WP_DETAIL = gen.GET_WP_DETAIL_GOLDEN
LIST_ARTIFACTS = gen.LIST_ARTIFACTS_GOLDEN
GET_ARTIFACT = gen.GET_ARTIFACT_GOLDEN
KEY = gen.MISSION_KEY
Found = Mapping[str, Mapping[str, Any]]


def entry_of(found: Found, fixture: str, golden: str, key: str) -> dict[str, Any]:
    """One keyed document of one golden file of one fixture; ``{}`` when anything on the way is missing."""
    value = found.get(fixture, {}).get(golden, {})
    value = value.get(key, {}) if isinstance(value, dict) else {}
    return value if isinstance(value, dict) else {}


def body_of(found: Found, fixture: str, golden: str, key: str) -> dict[str, Any]:
    body = entry_of(found, fixture, golden, key).get("body", {})
    return body if isinstance(body, dict) else {}


def wp_ids_of(found: Found, fixture: str) -> list[str]:
    return [item.get("wpId") for item in entry_of(found, fixture, GET_MISSION, KEY).get("workPackages", [])]


def expect(problems: list[str], condition: bool, text: str) -> None:
    if not condition:
        problems.append(text)


def detail_populated_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    lanes = {item.get("wpId"): item.get("statusLane") for item in entry_of(found, "populated", GET_MISSION, KEY).get("workPackages", [])}
    expect(problems, lanes == {"WP01": "done", "WP02": "in_progress", "WP03": "planned"}, f"populated: the lanes are {lanes}")
    cycles = body_of(found, "populated", GET_WP_DETAIL, "WP01").get("reviewCycles", [])
    expect(problems, [cycle.get("verdict") for cycle in cycles] == ["approved"], "populated: no approved review cycle")
    third = body_of(found, "populated", GET_WP_DETAIL, "WP03").get("dependencies", [])
    expect(problems, [item.get("statusLane") for item in third] == ["done", "in_progress"], "populated: the dependencies carry no lane")
    expect(problems, body_of(found, "null-workspace", GET_WP_DETAIL, "WP01").get("workspace", {}).get("laneId", "x") is None, "null-workspace: a lane is named")
    planning = body_of(found, "planning-lane", GET_WP_DETAIL, "WP01").get("workspace", {})
    expect(problems, (planning.get("laneId"), planning.get("laneBranch", "x")) == ("lane-planning", None), "planning-lane: not a planning lane without a branch")
    states = [item.get("changeState") for item in body_of(found, "unknown-change-state", GET_WP_DETAIL, "WP01").get("ownedFiles", [])]
    expect(problems, states == ["unknown", "unknown"], f"unknown-change-state: {states}")
    ghost = body_of(found, "dependency-unknown", GET_WP_DETAIL, "WP01").get("dependencies")
    expect(
        problems, ghost == [{"wpId": "WP99", "title": "WP99", "statusLane": None}], "dependency-unknown: the unknown dependency is not shown by id with a null lane"
    )
    for sibling in ("bad-sibling-before", "bad-sibling-after"):
        expect(problems, wp_ids_of(found, sibling) == ["WP01"], f"{sibling}: the unreadable sibling is listed")
        expect(problems, entry_of(found, sibling, GET_WP_DETAIL, "WP01").get("status") == 200, f"{sibling}: the good Work Package is not served")
    keys = list(entry_of(found, "unicode-subtask-ids", GET_WP, "WP01").get("subtasks", {}))
    expect(problems, keys == sorted(keys) and len(keys) == 3, "unicode-subtask-ids: the subtask keys are not in code point order")
    expect(
        problems,
        any(key.startswith(chr(0xFF5E)) for key in keys) and any(key.startswith(chr(0x1F600)) for key in keys),
        "unicode-subtask-ids: the two ids are missing",
    )
    return problems


def detail_early_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    mission = entry_of(found, "early", GET_MISSION, KEY)
    served = [item.get("status") for item in mission.get("phases", [])]
    return (
        []
        if mission.get("eventCount") == 0 and mission.get("workPackages") == [] and served == ["pending"] * 5
        else ["early: not an empty Mission with five pending phases"]
    )


def planning_only_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    mission = entry_of(found, "planning-only", GET_MISSION, KEY)
    lanes = [item.get("statusLane", "x") for item in mission.get("workPackages", [])]
    return [] if mission.get("eventCount") == 0 and lanes == [None, None] else ["planning-only: not two Work Packages with no recorded lane"]


# Per fixture: the (status, basis) of the five phases in the contract order, derived from the truth table of AC-1.3 (not from the golden).
PENDING_TAIL = [("pending", "derived_from_status_lanes")] * 2
FILE, DONE_EVENT, STARTED_EVENT, NEITHER = ("complete", "artifact"), ("complete", "lifecycle_event"), ("in_progress", "lifecycle_event"), ("pending", "artifact")
LANES_PENDING = ("pending", "derived_from_status_lanes")
LANES_COMPLETE = ("complete", "derived_from_status_lanes")
LANES_STARTED = ("in_progress", "derived_from_status_lanes")
PHASE_TABLE: Mapping[str, list[tuple[str, str]]] = {
    "ps-file": [FILE] * 3 + PENDING_TAIL,
    "ps-completed": [DONE_EVENT] * 3 + PENDING_TAIL,
    "ps-started": [STARTED_EVENT] * 3 + PENDING_TAIL,
    "ps-neither": [NEITHER] * 3 + PENDING_TAIL,
    "ps-file-completed": [FILE] * 3 + PENDING_TAIL,  # the file is tested before the Completed event
    "ps-completed-started": [DONE_EVENT] * 3 + PENDING_TAIL,  # the Completed event is tested before the Started event
    "ps-link-file": [FILE] * 3 + PENDING_TAIL,  # V1: the oracle follows the link
    "ps-link-completed": [FILE] * 3 + PENDING_TAIL,
    "ps-link-started": [FILE] * 3 + PENDING_TAIL,
    "ps-link-neither": [FILE] * 3 + PENDING_TAIL,
    "ps-rotated": [FILE, DONE_EVENT, STARTED_EVENT, *PENDING_TAIL],
    "lc-empty": [NEITHER] * 3 + [LANES_PENDING, LANES_PENDING],
    "lc-planned": [NEITHER] * 3 + [LANES_PENDING, LANES_PENDING],
    "lc-mix": [NEITHER] * 3 + [LANES_STARTED, LANES_STARTED],
    "lc-for-review": [NEITHER] * 3 + [LANES_COMPLETE, LANES_STARTED],
    "lc-done": [NEITHER] * 3 + [LANES_COMPLETE, LANES_COMPLETE],
    "lc-canceled": [NEITHER] * 3 + [LANES_COMPLETE, LANES_COMPLETE],
    "lc-blocked": [NEITHER] * 3 + [LANES_PENDING, LANES_PENDING],
    "marker-row-without-event-id": [DONE_EVENT, NEITHER, NEITHER, *PENDING_TAIL],  # the oracle counts a marker row that has no event_id or timestamp
}
PHASE_ORDER = ["specify", "plan", "tasks", "implement", "review"]


def phases_matrix_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    expect(problems, set(found) == set(PHASE_TABLE) and len(PHASE_TABLE) == 19, "phases-matrix: the fixtures are not the 19 of the cross product")
    for name, want in PHASE_TABLE.items():
        phases = entry_of(found, name, GET_MISSION, KEY).get("phases", [])
        expect(problems, [item.get("name") for item in phases] == PHASE_ORDER, f"{name}: the phases are not in the contract order")
        expect(
            problems,
            [(item.get("status"), item.get("basis")) for item in phases] == want,
            f"{name}: the phases are {[(i.get('status'), i.get('basis')) for i in phases]}",
        )
    return problems


MALFORMED_SERVED = frozenset({1, 2, 3, 11, 12, 13, 14, 15, 21, 27, 28})
MALFORMED_NEVER_SERVED = frozenset({4, 5, 6, 7, 8, 9, 10, 18, 19, 20, 22, 23, 24, 25, 26})


def malformed_frontmatter_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    for number in range(1, 29):
        name = f"wpm-{number:02d}"
        served = wp_ids_of(found, name)
        if number in MALFORMED_SERVED:
            expect(problems, served == ["WP01"], f"{name}: expected to be served, listed {served}")
            expect(problems, entry_of(found, name, GET_WP_DETAIL, "WP01").get("status") == 200, f"{name}: the detail is not served")
        elif number in MALFORMED_NEVER_SERVED:
            expect(problems, served == [] and "WP01" not in found.get(name, {}).get(GET_WP, {}), f"{name}: expected to be skipped, listed {served}")
        expect(problems, entry_of(found, name, GET_WP_DETAIL, gen.UNKNOWN_WP_ID).get("status") == 404, f"{name}: the unknown id is not a 404")
    expect(problems, len(MALFORMED_SERVED | MALFORMED_NEVER_SERVED) == 26, "the served and skipped sets do not cover the corpus but for two cases")
    upper = entry_of(found, "wpm-27", GET_WP, "WP01").get("title")
    expect(problems, upper == "Upper B", f"wpm-27: byte order must pick WP01-B.md, not the case-folded first; got {upper!r}")
    stringified = entry_of(found, "wpm-28", GET_WP, "WP01").get("authored", {}).get("subtasks", [])
    expect(
        problems,
        bool(stringified) and all(isinstance(item, str) and item.startswith("{") for item in stringified),
        "wpm-28: the oracle does not serve a stringified mapping (V20)",
    )
    return problems


def duplicate_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    want = {"duplicate-wp-id": "First holder", "duplicate-mission-id": "First Mission holder", "duplicate-then-broken": "First Mission holder"}
    expect(problems, set(found) == set(want), "wp-duplicate-id: the fixtures are not the three of the specification")
    for name, title in want.items():
        expect(problems, wp_ids_of(found, name) == ["WP01"], f"{name}: the id is not listed once")
        expect(problems, entry_of(found, name, GET_WP, "WP01").get("title") == title, f"{name}: the first holder must win")
    return problems


def two_selectors_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    references = body_of(found, "two-selectors", GET_WP_DETAIL, "WP08").get("artifactReferences", {})
    title = entry_of(found, "two-selectors", GET_WP, "WP08").get("title")
    problems = []
    expect(problems, title == "From file x", f"two-selectors: the frontmatter comes from WP07-x.md, not {title!r}")
    expect(problems, references.get("prompt", {}).get("path") == "tasks/WP08-y.md", "two-selectors: the prompt reference is not tasks/WP08-y.md")
    return problems


PROMPT_PROPERTIES: Mapping[str, Callable[[str], bool]] = {
    "host-path": lambda text: "Users" in text and "[path]" not in text,
    "email": lambda text: "@" in text and "[email]" not in text,
    "near-miss-token": lambda text: "ghp_" in text and len(text.split("ghp_")[1].split()[0]) == 35,
    "crlf": lambda text: text == "\nline one\nline two\n",  # the oracle's text-mode read translates CRLF (R-4)
    "lone-cr": lambda text: text == "\nline one\nline two\n",  # and a lone CR
    "trailing-newline": lambda text: text.endswith("text\n"),
    "no-trailing-newline": lambda text: text.endswith("text") and not text.endswith("\n"),
    "u2028": lambda text: chr(0x2028) in text,
    "u0085": lambda text: chr(0x85) in text,
    "supplementary-character": lambda text: any(ord(char) > 0xFFFF for char in text),
    "quote-and-backslash": lambda text: '"' in text and "\\" in text,
    "zero-bytes": lambda text: text == "",
    "bytes-200000": lambda text: len(text.encode("utf-8")) >= 200_000,
}


def prompt_bytes_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    expect(problems, set(found) == set(PROMPT_PROPERTIES) and len(PROMPT_PROPERTIES) == 13, "wp-prompt-bytes: the fixtures are not the 13 bodies of AC-9.1")
    for name, holds in PROMPT_PROPERTIES.items():
        with_prompt, without = entry_of(found, name, GET_PROMPT, "WP01"), entry_of(found, name, GET_WP, "WP01")
        text = with_prompt.get("promptMarkdown")
        expect(problems, isinstance(text, str) and holds(text), f"{name}: the golden promptMarkdown does not show the body")
        expect(problems, bool(without) and "promptMarkdown" not in without, f"{name}: the request without the prompt carries promptMarkdown")
    return problems


def cycles_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []

    def cycles(name: str) -> list[dict[str, Any]]:
        return body_of(found, name, GET_WP_DETAIL, "WP01").get("reviewCycles", [])

    expect(
        problems,
        set(found) == {"no-cycles", "cycle-without-path", "unparseable-cycle", "numeric-order"},
        "cycles: the fixtures are not the four of the specification",
    )
    expect(
        problems, cycles("no-cycles") == [] and "WP01" in found.get("no-cycles", {}).get(GET_WP_DETAIL, {}), "no-cycles: not a served Work Package with no cycle"
    )
    expect(problems, [cycle.get("cycleNumber") for cycle in cycles("numeric-order")] == [1, 2, 9, 10], "numeric-order: not 1, 2, 9, 10")
    only = cycles("cycle-without-path")
    expect(
        problems,
        len(only) == 1 and only[0].get("feedbackReference") is None and only[0].get("artifactPath"),
        "cycle-without-path: the entry is dropped or fabricated",
    )
    broken = cycles("unparseable-cycle")
    expect(
        problems,
        len(broken) == 1 and broken[0].get("reviewedAt") is None and broken[0].get("reviewer") is None and broken[0].get("cycleNumber") == 1,
        "unparseable-cycle: members are not null",
    )
    return problems


def legacy_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    served = entry_of(found, "legacy-lanes-json", GET_WP_DETAIL, "WP01")
    if (served.get("status"), served.get("body", {}).get("code")) != (500, "source_unreadable"):
        return ["legacy-lanes-json: the oracle does not refuse the read"]
    held = next((item for item in fixtures if item.tag == "legacy-lanes-json"), None)
    lanes = next((held.path / "kitty-specs").glob("*/lanes.json"), None) if held else None
    text = lanes.read_text(encoding="utf-8") if lanes else ""
    return [] if "feature_slug" in text and "mission_slug" not in text else ["legacy-lanes-json: the fixture is not a feature_slug manifest"]


def tasks_md_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []

    def titles(name: str) -> dict[str, Any]:
        return {item.get("id"): item.get("title") for item in body_of(found, name, GET_WP_DETAIL, "WP01").get("subtasks", [])}

    expect(problems, len(found) == 12, "tasks-md: not 12 fixtures")
    expect(
        problems,
        titles("tasks-md-table-and-checkbox") == {"T001": "Checkbox form", "T002": "Bold parallel", "T003": "Table form"},
        "tasks-md-table-and-checkbox: wrong titles",
    )
    expect(
        problems,
        titles("table-row-other-wp").get("T002") is None and titles("table-row-other-wp").get("T001") == "Mine",
        "table-row-other-wp: a row naming another Work Package is taken",
    )
    expect(problems, titles("fenced-fake-row").get("T002") is None, "fenced-fake-row: a fenced row is taken")
    expect(problems, titles("duplicate-subtask-id").get("T001") == "First wins", "duplicate-subtask-id: the first row must win")
    expect(problems, titles("reopened-heading").get("T002") is None, "reopened-heading: a re-appearing heading reopened the section")
    expect(problems, entry_of(found, "invalid-utf8", GET_WP_DETAIL, "WP01").get("status") == 500, "invalid-utf8: not a 500")
    expect(problems, titles("crlf").get("T001") == "Windows line ends", "crlf: the title keeps a carriage return or is lost")
    expect(problems, titles("bom").get("T001") == "After a byte order mark", "bom: the leading byte order mark loses the row")
    expect(problems, titles("nbsp-and-u0085").get("T001") == "Title with nbsp", "nbsp-and-u0085: no-break space or U+0085 not stripped")
    expect(problems, titles("arabic-indic-subtask-id").get("T001") is None, "arabic-indic-subtask-id: an Arabic-Indic digit counts as a digit")
    expect(problems, titles("arabic-indic-wp-token").get("T001") is None, "arabic-indic-wp-token: an Arabic-Indic digit counts in a Work Package token")
    expect(problems, "\r" in str(titles("lone-cr-title").get("T001")), "lone-cr-title: the lone carriage return was split")
    return problems


def worktree_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    want = {
        "dir-and-git-present": True,
        "dir-without-git": False,
        "dir-absent": False,
        "directory-symlink": True,  # V7: the oracle follows the link
        "git-entry-symlink": True,  # V7
        "planning-lane": False,
        "no-lane": False,
    }
    expect(problems, set(found) == set(want), "worktree-states: the fixtures are not the seven of AC-10.3")
    for name, present in want.items():
        workspace = body_of(found, name, GET_WP_DETAIL, "WP01").get("workspace", {})
        expect(problems, workspace.get("worktreePresent") is present, f"{name}: worktreePresent is {workspace.get('worktreePresent')!r}")
    expect(problems, body_of(found, "no-lane", GET_WP_DETAIL, "WP01").get("workspace", {}).get("laneId", "x") is None, "no-lane: a lane is named")
    return problems


def artifacts_populated_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    entries = body_of(found, "artifacts-populated", LIST_ARTIFACTS, KEY).get("entries", [])
    kinds = {entry.get("kind") for entry in entries}
    expect(
        problems,
        {
            "spec",
            "plan",
            "tasks",
            "data_model",
            "quickstart",
            "analysis_report",
            "research",
            "contract",
            "checklist",
            "work_package_prompt",
            "review_cycle",
            "other",
        }
        <= kinds,
        f"kinds {sorted(kinds)}",
    )
    expect(
        problems,
        bool(entries) and {entry.get("modifiedAt") for entry in entries} == {"2026-09-21T14:13:20Z"},
        "the modification times are not the provisioned ones",
    )
    contents = found.get("artifacts-populated", {}).get(GET_ARTIFACT, {})
    expect(problems, {entry.get("path") for entry in entries if entry.get("readable")} <= set(contents), "a readable entry has no content document")
    expect(problems, all(document.get("status") == 200 for document in contents.values()) and bool(contents), "a listed file is not served")
    return problems


def artifacts_sort_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    paths = [entry.get("path") for entry in body_of(found, "artifacts-sort", LIST_ARTIFACTS, KEY).get("entries", [])]
    problems = []
    expect(problems, len(paths) >= 10 and paths == sorted(paths, key=lambda value: value.encode("utf-8")), "artifacts-sort: not in byte order of the UTF-8 path")
    expect(
        problems,
        paths != sorted(paths, key=str.casefold) and paths != sorted(paths, key=lambda value: value.encode("utf-16-be")),
        "artifacts-sort: equals a case-folded or UTF-16 order, so it proves nothing",
    )
    return problems


def artifacts_refusals_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    documents = found.get("artifacts-refusals", {}).get(GET_ARTIFACT, {})
    statuses = {document.get("status") for document in documents.values()}
    expect(problems, {200, 400, 404, 413, 415, 422} <= statuses, f"artifacts-refusals: the statuses are {sorted(statuses)}")
    for path, document in documents.items():
        if document.get("status") != 200:
            expect(problems, set(document.get("body", {})) == {"type", "title", "status", "code", "detail"}, f"{path}: a refusal body carries more than a problem")
            expect(problems, "content" not in document.get("body", {}) and path not in json.dumps(document), f"{path}: a refusal body holds content or the path")
    return problems


def artifacts_redaction_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    documents = found.get("artifacts-redaction", {}).get(GET_ARTIFACT, {})
    both = documents.get("paths-and-mail.md", {}).get("body", {})
    expect(
        problems,
        both.get("redacted") is True and "[path]" in both.get("content", "") and "[email]" in both.get("content", ""),
        "paths-and-mail.md: no [path] and [email]",
    )
    expect(
        problems,
        "Trailing: [path]\n" in both.get("content", ""),
        "paths-and-mail.md: only the matched prefix of the path was replaced (the non-space characters that follow must go too)",
    )
    clean = documents.get("clean.md", {}).get("body", {})
    expect(problems, clean.get("redacted") is False and clean.get("content") == "Nothing to redact here.\n", "clean.md: a file with neither is changed")
    return problems


def projection_nulls_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    problems: list[str] = []
    head = entry_of(found, "head-dates-nulled", GET_MISSION, KEY)
    expect(
        problems,
        head.get("acceptedAt", "x") is None
        and head.get("mergedAt", "x") is None
        and head.get("discardedAt", "x") is None
        and head.get("lifecycleStatus") == "planned",
        "head-dates-nulled: the oracle nulls an off-shape head date and derives the lifecycle without it (V19 is retired: oracle and service agree)",
    )
    expect(
        problems,
        entry_of(found, "merge-target-branch-path", GET_WP, "WP01").get("mergeTargetBranch", "x") is None,
        "merge-target-branch-path: a path-shaped branch is served",
    )
    long = body_of(found, "planning-branch-too-long", GET_WP_DETAIL, "WP01").get("workspace", {})
    expect(problems, long.get("planningBranch", "x") is None and long.get("laneId") == "lane-a", "planning-branch-too-long: the over-long branch is served")
    override = entry_of(found, "override-partial-junk-at", GET_WP, "WP01").get("review", {}).get("override") or {}
    expect(
        problems,
        override.get("complete") is False and override.get("at", "x") is None,
        "override-partial-junk-at: the partial override is not shown with a null time",
    )
    junk_lane = body_of(found, "lane-id-fails-pattern", GET_WP_DETAIL, "WP01").get("workspace", {})
    expect(problems, junk_lane.get("laneId", "x") is None and junk_lane.get("laneBranch", "x") is None, "lane-id-fails-pattern: the lane id is served")
    junk_cycle = body_of(found, "reviewed-at-junk", GET_WP_DETAIL, "WP01").get("reviewCycles", [])
    expect(problems, len(junk_cycle) == 1 and junk_cycle[0].get("reviewedAt", "x") is None, "reviewed-at-junk: the junk time is served")
    return problems


RESOLVED_STATE_FIXTURES = frozenset(
    {
        "set-each-member",
        "overwrite-each-member",
        "clear-each-member",
        "model-absent-sentinel",
        "review-result-approved",
        "review-result-changes-requested",
        "review-result-sticky",
        "override-partial",
        "override-release-marker",
        "history-mixed-offsets",
        "annotation-order",
        "losing-seed-payload",
        "actor-forms",
        "no-members",
        "float-agent-and-actor",
        "annotation-at-float",
        "annotation-at-list",
        "override-member-float",
        "verdict-not-text",
        "subtask-status-genesis",
        "history-event-id-not-text",
    }
)
ASSIGNMENT_HANDLES = ("agent", "assignee", "role", "agentProfile", "agentProfileVersion", "model", "provider")
SENTINEL_TEXT = "__resolved_"


def _wp(found: Found, fixture: str, wp_id: str) -> dict[str, Any]:
    return entry_of(found, fixture, GET_WP, wp_id)


def _assignment(found: Found, fixture: str, wp_id: str) -> dict[str, Any]:
    return _wp(found, fixture, wp_id).get("assignment", {})


def _review(found: Found, fixture: str, wp_id: str) -> dict[str, Any]:
    return _wp(found, fixture, wp_id).get("review", {})


def _instant(text: str) -> float:
    return datetime.fromisoformat(text).timestamp()


def _ledger_rows_of(fixture: gen.Fixture) -> list[dict[str, Any]]:
    return ledger_rows(next((fixture.path / "kitty-specs").iterdir()) / LEDGER)


def resolved_state_history_problems(fixtures: list[gen.Fixture], found: Found) -> list[str]:
    """AC-20.3, derived from the committed ledger rather than the golden: transitions only, instant then event id, force only for the literal true."""
    problems: list[str] = []
    fixture = next((item for item in fixtures if item.key == "resolved-state/history-mixed-offsets"), None)
    history = _wp(found, "history-mixed-offsets", "WP01").get("history", [])
    if fixture is None or not history:
        return ["history-mixed-offsets: no history is served"]
    rows = _ledger_rows_of(fixture)
    ledger = [row for row in rows if "to_lane" in row and row.get("wp_id") == "WP01"]
    ordered = sorted(ledger, key=lambda row: (_instant(row["at"]), row["event_id"]))
    expect(
        problems, [item.get("eventId") for item in history] == [row["event_id"] for row in ordered], "history-mixed-offsets: not ordered by instant then event id"
    )
    expect(problems, {item.get("kind") for item in history} == {"transition"}, "history-mixed-offsets: a row that is not a transition is listed")
    literal = {row["event_id"] for row in ledger if row.get("force") is True}
    expect(
        problems,
        {item.get("eventId") for item in history if item.get("force") is True} == literal,
        "history-mixed-offsets: force is not true only for the literal true",
    )
    expect(problems, any(row.get("force") not in (True, False) for row in ledger), "history-mixed-offsets: the ledger holds no non-boolean force")
    instants = [_instant(item["at"]) for item in history]
    expect(problems, len(set(instants)) < len(instants), "history-mixed-offsets: no two stamps share an instant")
    stamps = [item["at"] for item in history]
    mixed = any(stamp.endswith("Z") for stamp in stamps) and any("." in stamp for stamp in stamps) and any(stamp.endswith("+02:00") for stamp in stamps)
    expect(problems, mixed, "history-mixed-offsets: the stamps do not mix Z, fractions and offsets")
    expect(problems, stamps != sorted(stamps), "history-mixed-offsets: text order equals instant order, so the fixture proves nothing")
    between = {key for row in rows for key in ("kind", "event_type", "event_name") if key in row}
    expect(
        problems,
        between == {"kind", "event_type", "event_name"},
        "history-mixed-offsets: no annotation, lifecycle and retrospective row sits among the transitions",
    )
    expect(problems, history[0].get("fromStatusLane", "x") is None, "history-mixed-offsets: the genesis bootstrap shows a lane")
    # V28: spec-kitty-events 10.5.1 sorts the done departure after the clock-ahead approval it followed, so the oracle ends done.
    subject = _wp(found, "history-mixed-offsets", "WP01")
    expect(
        problems,
        (subject.get("statusLane"), subject.get("lastEventId")) == ("done", "0000000000000000000000R104"),
        "history-mixed-offsets: the oracle no longer ends done on R104, so V28 is stale",
    )
    return problems


def resolved_state_problems(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
    """FR-020 / AC-20.1: every member of the mapping is non-empty in some golden, the control is empty, and the sentinel is never text."""
    problems: list[str] = []
    held = {fixture.name for fixture in fixtures if fixture.tag == "resolved-state"}
    expect(problems, held == RESOLVED_STATE_FIXTURES, f"resolved-state: the fixtures differ from the expected set by {sorted(held ^ RESOLVED_STATE_FIXTURES)}")
    seen = _wp(found, "set-each-member", "WP01")
    expect(
        problems, all(_assignment(found, "set-each-member", "WP01").get(handle) for handle in ASSIGNMENT_HANDLES), "set-each-member: an assignment handle is empty"
    )
    expect(problems, seen.get("subtaskProgress") == {"done": 2, "total": 4}, "set-each-member: the subtask progress is not 2 of 4")
    expect(problems, (_review(found, "set-each-member", "WP01").get("latestResult") or {}).get("verdict") == "approved", "set-each-member: no approved result")
    expect(problems, (_review(found, "set-each-member", "WP01").get("override") or {}).get("complete") is True, "set-each-member: no complete override")
    expect(problems, seen.get("actor", {}).get("tool") == "reviewer-renata", "set-each-member: the actor is not the latest applied transition's")
    for wp_id in ("WP01", "WP02"):
        member = _wp(found, "no-members", wp_id)
        empty = (
            member.get("subtasks") == {}
            and member.get("subtaskProgress") == {"done": 0, "total": 0}
            and all(value is None for value in member.get("assignment", {"x": 1}).values())
            and _review(found, "no-members", wp_id) == {"latestResult": None, "override": None}
        )
        expect(problems, empty, f"no-members {wp_id}: a resolved member is not empty (the control)")
    first = _assignment(found, "overwrite-each-member", "WP01")
    second = {"agent": "agent-second", "assignee": "owner-second", "role": "role-second", "agentProfile": "profile-second", "agentProfileVersion": "2.0.0"}
    expect(problems, first == {**second, "model": "model-second", "provider": "provider-second"}, "overwrite-each-member: a handle kept its first value")
    expect(
        problems,
        _wp(found, "overwrite-each-member", "WP01").get("subtasks") == {"T001": "done", "T002": "planned"},
        "overwrite-each-member: subtask T001 not replaced",
    )
    review = _review(found, "overwrite-each-member", "WP01")
    expect(problems, (review.get("latestResult") or {}).get("reference", "").endswith("review-cycle-2.md"), "overwrite-each-member: the result was not replaced")
    expect(problems, (review.get("override") or {}).get("actor") == "operator-second", "overwrite-each-member: the override was not replaced")
    other = _assignment(found, "overwrite-each-member", "WP02")
    expect(
        problems,
        set(other.values()) == {"agent-other", "owner-other", "role-other", "profile-other", "9.9.9", "model-other", "provider-other"},
        "overwrite-each-member: WP01's overwrite leaked into WP02",
    )
    cleared = _wp(found, "clear-each-member", "WP01")
    expect(problems, cleared.get("assignment", {}).get("agent", "x") is None, "clear-each-member: the release did not clear the agent")
    expect(problems, cleared.get("assignment", {}).get("assignee") == "owner-olga", "clear-each-member: the release cleared the assignee")
    expect(problems, cleared.get("review") == {"latestResult": None, "override": None}, "clear-each-member: the result or the override survived")
    expect(problems, cleared.get("subtasks", {}).get("T001") == "done", "clear-each-member: the subtasks were cleared")
    sentinel_wp = _assignment(found, "model-absent-sentinel", "WP01")
    sentinel_handles = ("agentProfile", "agentProfileVersion", "model", "provider")
    expect(
        problems,
        all(sentinel_wp.get(handle, "x") is None for handle in sentinel_handles) and sentinel_wp.get("role") == "implementer",
        "model-absent-sentinel WP01: a sentinel is served",
    )
    replaced = _assignment(found, "model-absent-sentinel", "WP02")
    expect(
        problems, (replaced.get("model", "x"), replaced.get("agentProfile", "x")) == (None, None), "model-absent-sentinel: a sentinel did not replace a real model"
    )
    expect(
        problems,
        (replaced.get("provider"), replaced.get("agentProfileVersion")) == ("provider-real", "3.1.4"),
        "model-absent-sentinel: an untouched handle changed",
    )
    expect(problems, SENTINEL_TEXT not in json.dumps(found.get("model-absent-sentinel", {})), "model-absent-sentinel: sentinel text in the golden")
    expect(
        problems,
        (_review(found, "review-result-approved", "WP01").get("latestResult") or {}).get("verdict") == "approved",
        "review-result-approved: no approved verdict",
    )
    expect(
        problems,
        (_review(found, "review-result-approved", "WP02").get("latestResult") or {}).get("reference") == "",
        "review-result-approved: a null reference is not empty text",
    )
    rejected = _review(found, "review-result-changes-requested", "WP01").get("latestResult") or {}
    expect(
        problems,
        rejected.get("verdict") == "changes_requested" and "feedback_path" not in rejected,
        "review-result-changes-requested: verdict or feedback_path wrong",
    )
    for wp_id, verdict in (("WP01", "approved"), ("WP02", "approved"), ("WP03", None)):
        latest = _review(found, "review-result-sticky", wp_id).get("latestResult")
        expect(problems, (latest or {}).get("verdict") == verdict, f"review-result-sticky {wp_id}: the result is not sticky")
    partial = {wp_id: _review(found, "override-partial", wp_id).get("override") or {} for wp_id in ("WP01", "WP02", "WP03")}
    expect(
        problems,
        all(item.get("complete") is False for item in partial.values()) and all(partial.values()),
        "override-partial: a partial record is complete or absent",
    )
    expect(problems, bool(partial["WP01"].get("at")) and partial["WP01"].get("reason", "x") is None, "override-partial WP01: the time or the blank reason")
    expect(problems, partial["WP02"].get("at", "x") is None and partial["WP02"].get("reason") == "needs rework", "override-partial WP02: the reason-only record")
    expect(problems, partial["WP03"].get("at", "x") is None, "override-partial WP03: an offset-less time is shown")
    released = [_review(found, "override-release-marker", wp_id) for wp_id in ("WP01", "WP02")]
    expect(problems, all(item.get("override", "x") is None for item in released), "override-release-marker: the release marker left an override")
    ordered = _assignment(found, "annotation-order", "WP01")
    expect(
        problems,
        (ordered.get("assignee"), ordered.get("model"), ordered.get("role")) == ("owner-late", "model-late", "role-early"),
        "annotation-order: not (at, event_id) order",
    )
    seed = _wp(found, "losing-seed-payload", "WP01")
    expect(
        problems,
        seed.get("statusLane") == "blocked" and seed.get("assignment", {}).get("agent") == "seed-agent",
        "losing-seed-payload: the seed payload is not folded",
    )
    expect(
        problems,
        (_review(found, "losing-seed-payload", "WP01").get("latestResult") or {}).get("reviewer") == "seed-reviewer",
        "losing-seed-payload: no seed verdict",
    )
    expect(problems, seed.get("actor", {}).get("tool") == "claude", "losing-seed-payload: a losing seed changed the actor")
    tools_of = {wp_id: _wp(found, "actor-forms", wp_id).get("actor", {}).get("tool", "x") for wp_id in ("WP01", "WP02", "WP03", "WP04")}
    expect(problems, tools_of == {"WP01": "claude-code", "WP02": None, "WP03": "annotator-ann", "WP04": "claude"}, f"actor-forms: {tools_of}")
    problems.extend(resolved_state_history_problems(fixtures, found))
    expect(problems, _assignment(found, "float-agent-and-actor", "WP01").get("agent") == "1.5", "float-agent-and-actor: the float agent is not its repr (V21)")
    expect(
        problems, _wp(found, "float-agent-and-actor", "WP02").get("actor", {}).get("tool") == "2.5", "float-agent-and-actor: the float actor is not its repr (V21)"
    )
    for name in ("annotation-at-float", "annotation-at-list"):
        expect(problems, str(_assignment(found, name, "WP01").get("assignee")).startswith("owner-"), f"{name}: the oracle did not read the annotation (V22)")
    expect(
        problems,
        (_review(found, "override-member-float", "WP01").get("override") or {}).get("reason") == "2.5",
        "override-member-float: the member is not its repr (V22)",
    )
    expect(
        problems,
        (_review(found, "verdict-not-text", "WP01").get("latestResult") or {}).get("verdict") == 7,
        "verdict-not-text: the oracle did not serve the raw value (V23)",
    )
    genesis = _wp(found, "subtask-status-genesis", "WP01").get("subtasks")
    expect(problems, genesis == {"T001": "genesis", "T002": "uninitialized", "T003": "done"}, "subtask-status-genesis: the oracle refused a lane status (V24)")
    texts = [item.get("eventId") for item in _wp(found, "history-event-id-not-text", "WP01").get("history", [])]
    expect(problems, texts[1:] == [424242], "history-event-id-not-text: the numeric event id is not carried as stored (V25)")
    return problems


def java_only_detail_problems(tag: str, names: frozenset[str]) -> Callable[[list[gen.Fixture], Found, Path], list[str]]:
    """A java-only detail class: the fixtures are exactly ``names``, none carries a golden, and each holds what its Java assertion needs."""

    def check(fixtures: list[gen.Fixture], found: Found, scratch: Path) -> list[str]:
        held = [fixture for fixture in fixtures if fixture.tag == tag]
        problems = [] if {fixture.name for fixture in held} == names else [f"{tag}: the fixtures are not {sorted(names)}"]
        for fixture in held:
            if (fixture.path / gen.GOLDEN_DIR).exists():
                problems.append(f"{fixture.key}: a java-only fixture carries a golden")
            if tag == "artifacts-links" and not (fixture.path / gen.PROVISION_PLAN).is_file():
                problems.append(f"{fixture.key}: no PROVISION_PLAN")
            if tag == "lookup-faults":
                committed = len(list((fixture.path / "kitty-specs").iterdir()))
                linked = (fixture.path / gen.PROVISION_PLAN).is_file() and "link" in (fixture.path / gen.PROVISION_PLAN).read_text(encoding="utf-8")
                if committed < (1 if fixture.name == "bad-sibling-unknown-link" else 2) or linked != (fixture.name != "bad-sibling-unknown-meta"):
                    problems.append(f"{fixture.key}: the faulted sibling Mission is not what its name says")
        return problems

    return check


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
    "detail-populated": detail_populated_problems,
    "detail-early": detail_early_problems,
    "detail-planning-only": planning_only_problems,
    "phases-matrix": phases_matrix_problems,
    "wp-malformed-frontmatter": malformed_frontmatter_problems,
    "wp-duplicate-id": duplicate_problems,
    "wp-two-selectors": two_selectors_problems,
    "wp-prompt-bytes": prompt_bytes_problems,
    "cycles": cycles_problems,
    "legacy-lanes-json": legacy_problems,
    "tasks-md": tasks_md_problems,
    "worktree-states": worktree_problems,
    "artifacts-populated": artifacts_populated_problems,
    "artifacts-sort": artifacts_sort_problems,
    "artifacts-refusals": artifacts_refusals_problems,
    "artifacts-links": java_only_detail_problems("artifacts-links", frozenset({"symlinked-file", "symlinked-directory", "junction"})),
    "artifacts-redaction": artifacts_redaction_problems,
    "lookup-faults": java_only_detail_problems(
        "lookup-faults", frozenset({"bad-sibling-unknown-meta", "bad-sibling-unknown-link", "bad-sibling-unknown-two-faults"})
    ),
    "projection-nulls": projection_nulls_problems,
    "projection-refusals": java_only_detail_problems(
        "projection-refusals", frozenset({"history-at-not-instant", "history-event-id-leak", "owned-file-pattern-leak", "dependency-id-leak"})
    ),
    "resolved-state": resolved_state_problems,
}


def test_every_class_has_a_property_check() -> None:
    assert set(PROPERTY_CHECKS) == set(gen.CLASS_TAGS)


@pytest.mark.parametrize("tag", gen.CLASS_TAGS)
def test_each_class_shows_its_distinguishing_property_in_its_golden_content(tag: str, fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    assert PROPERTY_CHECKS[tag](fixtures, goldens_in(fixtures, tag), tmp_path) == []


def trivial_goldens(fixtures: list[gen.Fixture], tag: str) -> dict[str, dict[str, Any]]:
    """A trivial document under every golden name of the class: overview-shaped for the overview classes, an empty keyed object per detail golden."""
    if tag in gen.GOLDEN_FILES_OF:
        return {fixture.name: dict.fromkeys(gen.GOLDEN_FILES_OF[tag], {}) for fixture in fixtures if fixture.tag == tag}
    trivial_page = {"items": [], "pageInfo": {"hasNextPage": False, "nextPageCursor": None, "pageSize": 50}}
    return {fixture.name: {MISSIONS: trivial_page, PROJECT: {}} for fixture in fixtures if fixture.tag == tag}


@pytest.mark.parametrize("tag", [spec.tag for spec in gen.ALL_CLASS_SPECS if spec.parity == gen.PARITY_GOLDEN])
def test_a_trivial_golden_carrying_the_right_tag_fails_its_class(tag: str, fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    planted = trivial_goldens(fixtures, tag)
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


# ---------------------------------------------------------------------------
# FR-014: the detail and artifact surface (T046, T047, T048)
# ---------------------------------------------------------------------------

JAVA_TEST_ROOT = REPO_ROOT / "services" / "mission-status-api" / "src" / "test" / "java" / "org" / "speckitty" / "missionstatus" / "conformance" / "golden"
GOLDEN_SUITE_TEST = JAVA_TEST_ROOT / "GoldenSuiteTest.java"
DETAIL_CENSUS_TEST = JAVA_TEST_ROOT / "DetailManifestCensusTest.java"
ROUTER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci-router.yml"
FORBIDDEN_NAME_CHARACTERS = frozenset(':"?*|{}$')
# AC-14.4: each row of the FR-012 table whose Java status the oracle does not produce maps to its divergence entry.
ROW_TO_ENTRY: Mapping[str, str] = {
    "C3": "V9",
    "C4": "V9",
    "C5": "V9",
    "M4a over 1 MiB": "V5",
    "M7": "V18",
    "M8": "V2",
    "M9": "V16",
    "M10": "V14",
    "M13": "V15",
    "W2": "V12",
    "W3 over 1 MiB": "V17",
    "M11": "V17",
    "A1 walk bound": "V10",
    "A5": "V13",
    "A8": "V15",
}
# V19 is RETIRED, not reused and not renumbered: main's oracle fix (29d49cd77) nulls an off-shape head date before it derives the lifecycle, so row M14 no longer
# diverges and `projection-nulls/head-dates-nulled` is an ordinary conformance case. V20 to V26 keep their numbers.
# V28 (the 10.5.1 approved-departure lift, spec-kitty#6268) is recorded by the base slice.
RETIRED_ENTRY_IDS = frozenset({"V19"})
RETIRED_ROWS = frozenset({"M14"})
EXPECTED_ENTRY_IDS = [f"V{number}" for number in range(1, 27) if f"V{number}" not in RETIRED_ENTRY_IDS] + ["V28"]
DETAIL_FIXTURE_TOTAL = 8 + 1 + 1 + 19 + 28 + 3 + 1 + 13 + 4 + 1 + 12 + 7 + 1 + 1 + 1 + 3 + 1 + 3 + 6 + 4


def manifest_of(root: Path) -> dict[str, Any]:
    return json.loads((root / gen.CONFORMANCE_DIR / gen.MANIFEST_NAME).read_text(encoding="utf-8"))


def divergence_problems(manifest: Mapping[str, Any]) -> list[str]:
    """AC-14.4 over a manifest document: every row has its entry, no entry is stale, every named fixture exists and is tagged where it must be."""
    problems: list[str] = []
    entries = {entry["id"]: entry for entry in manifest.get(gen.KNOWN_DIVERGENCES_KEY, [])}
    if list(entries) != EXPECTED_ENTRY_IDS:
        problems.append(f"the entry ids are {list(entries)}, not V1 to V26 and V28 without the retired {sorted(RETIRED_ENTRY_IDS)}")
    for retired in RETIRED_ENTRY_IDS & set(entries):
        problems.append(f"{retired} is retired and must stay absent")
    for row in RETIRED_ROWS & set(ROW_TO_ENTRY):
        problems.append(f"row {row} no longer diverges and must have no entry")
    for row, entry_id in ROW_TO_ENTRY.items():
        if entry_id not in entries:
            problems.append(f"row {row} has no entry {entry_id}")
    keys = {f"{entry['tag']}/{item['name']}": item for entry in manifest["classes"] for item in entry["fixtures"]}
    covered: set[str] = set()
    class_tags = {entry["tag"] for entry in manifest["classes"]}
    for entry in entries.values():
        if not all(isinstance(entry.get(field), str) and entry[field].strip() for field in ("id", "cause", "fixture", "oracleOutcome", "javaAssertion")):
            problems.append(f"{entry['id']}: a field is missing or empty")
        if entry.get("oracleOutcome") == entry.get("javaAssertion"):
            problems.append(f"{entry['id']}: the two outcomes are equal (a stale entry)")
        for key in entry.get("fixtures", []):
            covered.add(key)
            if key not in keys:
                problems.append(f"{entry['id']}: names the fixture {key}, which the manifest does not hold")
        if entry.get("fixture") == gen.RESOLVED_STATE_PENDING and gen.RESOLVED_STATE_TAG in class_tags:
            problems.append(f"{entry['id']}: still pending although the manifest holds the {gen.RESOLVED_STATE_TAG} class (fill its fixtures)")
        if not entry.get("fixtures") and entry.get("fixture") not in {gen.INJECTED, gen.GENERATED, gen.RESOLVED_STATE_PENDING}:
            problems.append(f"{entry['id']}: names no committed fixture and is neither injected nor generated at test time")
    tagged = {key for key, item in keys.items() if gen.TAG_KNOWN_DIVERGENCE in item.get("tags", []) and key.split("/")[0] in gen.DETAIL_TAGS}
    if tagged - covered:
        problems.append(f"knownDivergence fixtures with no entry: {sorted(tagged - covered)}")
    return problems


def test_every_detail_class_carries_the_detail_surface_and_the_overview_entries_carry_none(fixtures: list[gen.Fixture]) -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    for entry in manifest["classes"]:
        if entry["tag"] in gen.DETAIL_TAGS:
            assert entry["surface"] == gen.SURFACE_DETAIL, entry["tag"]
        else:
            assert "surface" not in entry, f"{entry['tag']}: an existing entry must stay byte-identical"
    assert [entry["tag"] for entry in manifest["classes"][: len(gen.OVERVIEW_TAGS)]] == list(gen.OVERVIEW_TAGS)
    assert sum(1 for fixture in fixtures if fixture.detail) >= DETAIL_FIXTURE_TOTAL


def test_the_known_divergences_are_complete_distinct_and_pinned() -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert divergence_problems(manifest) == []
    mutated_missing = copy.deepcopy(manifest)
    mutated_missing[gen.KNOWN_DIVERGENCES_KEY] = [entry for entry in mutated_missing[gen.KNOWN_DIVERGENCES_KEY] if entry["id"] != "V9"]
    assert divergence_problems(mutated_missing), "deleting one entry turns the divergence test red"
    mutated_v26 = copy.deepcopy(manifest)
    mutated_v26[gen.KNOWN_DIVERGENCES_KEY] = [entry for entry in mutated_v26[gen.KNOWN_DIVERGENCES_KEY] if entry["id"] != "V26"]
    assert divergence_problems(mutated_v26), "deleting the V26 entry turns the divergence test red"
    mutated_v28 = copy.deepcopy(manifest)
    mutated_v28[gen.KNOWN_DIVERGENCES_KEY] = [entry for entry in mutated_v28[gen.KNOWN_DIVERGENCES_KEY] if entry["id"] != "V28"]
    assert divergence_problems(mutated_v28), "deleting the V28 entry turns the divergence test red"
    mutated_equal = copy.deepcopy(manifest)
    next(entry for entry in mutated_equal[gen.KNOWN_DIVERGENCES_KEY] if entry["id"] == "V1")["javaAssertion"] = manifest[gen.KNOWN_DIVERGENCES_KEY][0][
        "oracleOutcome"
    ]
    assert divergence_problems(mutated_equal), "equal outcomes turn it red"
    mutated_fixture = copy.deepcopy(manifest)
    next(entry for entry in mutated_fixture[gen.KNOWN_DIVERGENCES_KEY] if entry["id"] == "V20")["fixtures"] = ["projection-nulls/no-such-fixture"]
    assert divergence_problems(mutated_fixture), "an entry naming a fixture the manifest lacks turns it red"
    revived = copy.deepcopy(manifest)
    revived[gen.KNOWN_DIVERGENCES_KEY].append(
        {"id": "V19", "cause": "revived", "fixture": "projection-nulls", "fixtures": [], "oracleOutcome": "a", "javaAssertion": "b"}
    )
    assert any("V19 is retired" in problem for problem in divergence_problems(revived)), "a revived V19 turns it red"
    untagged_fixture = copy.deepcopy(manifest)
    next(item for entry in untagged_fixture["classes"] if entry["tag"] == "projection-nulls" for item in entry["fixtures"] if item["name"] == "head-dates-nulled")[
        "tags"
    ] = [gen.TAG_KNOWN_DIVERGENCE]
    assert any("no entry" in problem for problem in divergence_problems(untagged_fixture)), "re-tagging head-dates-nulled turns it red"
    assert "V19" in RETIRED_ENTRY_IDS and "M14" not in ROW_TO_ENTRY


D159_ENTRY_IDS = ["V21", "V22", "V23", "V24", "V25"]


def test_a_pending_resolved_state_marker_is_refused_once_the_manifest_holds_a_resolved_state_class() -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in manifest[gen.KNOWN_DIVERGENCES_KEY]}
    assert [entry_id for entry_id, entry in entries.items() if entry.get("fixture") == gen.RESOLVED_STATE_PENDING] == [], "after WP08 no entry is pending"
    assert any(entry["tag"] == gen.RESOLVED_STATE_TAG for entry in manifest["classes"]), "the resolved-state class exists at this tip"
    assert all(entries[entry_id]["fixtures"] for entry_id in D159_ENTRY_IDS), "the five D-159 candidates name their resolved-state fixtures"
    assert divergence_problems(manifest) == [], "the real manifest holds"
    # The planted-class leg (kept from WP07): reset the five entries to the pending marker. With the class present each is refused as pending ...
    pending = copy.deepcopy(manifest)
    for entry in pending[gen.KNOWN_DIVERGENCES_KEY]:
        if entry["id"] in D159_ENTRY_IDS:
            entry["fixture"] = gen.RESOLVED_STATE_PENDING
            entry["fixtures"] = []
    problems = divergence_problems(pending)
    assert len([problem for problem in problems if "pending" in problem]) == len(D159_ENTRY_IDS), problems
    assert all(any(entry_id in problem for problem in problems) for entry_id in D159_ENTRY_IDS), problems
    # ... and with the class planted out of a manifest that lacks one, the marker stands (it only becomes a defect once the class exists).
    without = copy.deepcopy(pending)
    without["classes"] = [entry for entry in without["classes"] if entry["tag"] != gen.RESOLVED_STATE_TAG]
    assert not any("pending" in problem for problem in divergence_problems(without)), "no class, so the marker stands"
    planted = copy.deepcopy(without)
    planted["classes"].append({"tag": gen.RESOLVED_STATE_TAG, "fixtures": []})
    assert len([problem for problem in divergence_problems(planted) if "pending" in problem]) == len(D159_ENTRY_IDS)
    filled = copy.deepcopy(planted)
    for entry in filled[gen.KNOWN_DIVERGENCES_KEY]:
        if entry["id"] in D159_ENTRY_IDS:
            entry["fixture"] = "resolved-state/some-fixture"
            entry["fixtures"] = [f"{gen.RESOLVED_STATE_TAG}/some-fixture"]
    filled["classes"][-1]["fixtures"] = [{"name": "some-fixture", "tags": [gen.TAG_KNOWN_DIVERGENCE]}]
    assert not any("pending" in problem for problem in divergence_problems(filled)), "filled entries are no longer pending"


def test_the_tagged_divergence_fixtures_are_exactly_the_ones_whose_golden_differs_from_java() -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    tagged = {
        f"{entry['tag']}/{item['name']}"
        for entry in manifest["classes"]
        if entry["tag"] in gen.DETAIL_TAGS
        for item in entry["fixtures"]
        if gen.TAG_KNOWN_DIVERGENCE in item.get("tags", [])
    }
    assert tagged == {
        "phases-matrix/ps-link-file",
        "phases-matrix/ps-link-completed",
        "phases-matrix/ps-link-started",
        "phases-matrix/ps-link-neither",
        "worktree-states/directory-symlink",
        "worktree-states/git-entry-symlink",
        "wp-malformed-frontmatter/wpm-28",
        "resolved-state/float-agent-and-actor",
        "resolved-state/annotation-at-float",
        "resolved-state/annotation-at-list",
        "resolved-state/override-member-float",
        "resolved-state/verdict-not-text",
        "resolved-state/subtask-status-genesis",
        "resolved-state/history-event-id-not-text",
        "resolved-state/history-mixed-offsets",
    }


def test_the_default_path_outcome_stored_for_v3_and_v4_is_what_the_live_default_path_gives(fixtures: list[gen.Fixture], tools: payloads.ContractTools) -> None:
    manifest = json.loads((CONFORMANCE / gen.MANIFEST_NAME).read_text(encoding="utf-8"))
    by_key = {fixture.key: fixture for fixture in fixtures}
    checked = 0
    for entry in manifest[gen.KNOWN_DIVERGENCES_KEY]:
        for key, stored in entry.get("defaultPathOutcomes", {}).items():
            assert gen.default_path_outcome(by_key[key], tools) == stored, f"{entry['id']} {key}: the live default path no longer reproduces the stored outcome"
            checked += 1
    assert checked == 3
    stored = {key: outcome for entry in manifest[gen.KNOWN_DIVERGENCES_KEY] for key, outcome in entry.get("defaultPathOutcomes", {}).items()}
    assert stored["wp-duplicate-id/duplicate-wp-id"] == {"workPackageIds": ["WP01", "WP01"]}, "the default path lists a duplicate id twice"
    assert stored["wp-malformed-frontmatter/wpm-04"]["refusal"]["exception"] == "FrontmatterError", "the default path raises on a malformed file"
    assert stored["wp-malformed-frontmatter/wpm-23"] == {"workPackageIds": ["WP06"]}, "the default path follows a symlinked file"
    index_fed = golden_of(by_key["wp-malformed-frontmatter/wpm-23"], gen.GET_MISSION_GOLDEN)[gen.MISSION_KEY]["workPackages"]
    assert index_fed == [], "the index-fed golden skips the link, so the default path is the divergence and not the golden"
    mutated = copy.deepcopy(stored)
    mutated["wp-malformed-frontmatter/wpm-23"] = {"workPackageIds": []}
    assert gen.default_path_outcome(by_key["wp-malformed-frontmatter/wpm-23"], tools) != mutated["wp-malformed-frontmatter/wpm-23"]


def test_the_default_path_divergence_entries_name_fixtures_that_exist_and_each_differs_from_its_golden(fixtures: list[gen.Fixture]) -> None:
    by_key = {fixture.key: fixture for fixture in fixtures}
    for entry in gen.KNOWN_DIVERGENCES:
        for key in entry.get("defaultPathFixtures", []):
            assert key in by_key and not by_key[key].java_only, key


# -- the paired Java census (D-109) -------------------------------------------------------------------------------------------------------


def java_floors(text: str, constant: str) -> dict[str, int]:
    """The ``Map.entry("tag", n)`` pairs of the map assigned to ``constant`` in a Java source; an empty parse is the caller's failure."""
    start = text.find(f"{constant} =")
    if start < 0:
        return {}
    block = text[start : text.find(");", start)]
    return {tag: int(count) for tag, count in re.findall(r'Map\.entry\("([a-z0-9-]+)",\s*(\d+)\)', block)}


def test_the_java_class_floors_mirror_the_python_ones() -> None:
    overview = java_floors(GOLDEN_SUITE_TEST.read_text(encoding="utf-8"), "CLASS_FLOORS")
    detail = java_floors(DETAIL_CENSUS_TEST.read_text(encoding="utf-8"), "DETAIL_CLASS_FLOORS")
    assert overview and detail, "a named floor with an empty parse is a failure, not a pass"
    assert not set(overview) & set(detail), "a class has its floor in one Java map only"
    assert {**overview, **detail} == dict(CLASS_FLOORS)
    assert set(overview) == set(gen.OVERVIEW_TAGS) and set(detail) == set(gen.DETAIL_TAGS)
    assert java_floors("no map here", "CLASS_FLOORS") == {}, "the parser reports an absent map as empty, which the assertion above refuses"
    assert java_floors("CLASS_FLOORS = Map.of();", "CLASS_FLOORS") == {}


def test_the_java_class_floors_turn_red_when_one_drifts() -> None:
    detail = java_floors(DETAIL_CENSUS_TEST.read_text(encoding="utf-8"), "DETAIL_CLASS_FLOORS")
    drifted = {**detail, "phases-matrix": detail["phases-matrix"] - 1}
    assert {**java_floors(GOLDEN_SUITE_TEST.read_text(encoding="utf-8"), "CLASS_FLOORS"), **drifted} != dict(CLASS_FLOORS)


# -- determinism, honesty controls, hygiene (T048) ----------------------------------------------------------------------------------------


def test_the_detail_goldens_are_deterministic_across_differently_named_roots_and_git_dates(fixtures: list[gen.Fixture], tools: payloads.ContractTools) -> None:
    chosen = [fixture for fixture in fixtures if fixture.detail and not fixture.java_only]
    assert len(chosen) >= 100
    for fixture in chosen:
        assert gen.golden_bytes_of(fixture, tools) == gen.golden_bytes_of(fixture, tools, date=ALT_DATE), fixture.key


@pytest.mark.parametrize(
    ("fixture_key", "golden", "request_key"),
    [
        ("detail-populated/populated", gen.GET_WP_DETAIL_GOLDEN, "WP01"),
        ("artifacts-populated/artifacts-populated", gen.LIST_ARTIFACTS_GOLDEN, gen.MISSION_KEY),
        ("wp-prompt-bytes/host-path", gen.GET_PROMPT_GOLDEN, "WP01"),
    ],
)
def test_one_perturbed_byte_of_a_detail_listing_or_prompt_golden_turns_the_comparison_red(
    fixture_key: str, golden: str, request_key: str, generated: dict[Path, bytes], tmp_path: Path
) -> None:
    scratch = copy_conformance(tmp_path / "copy")
    assert gen.differences(scratch, generated) == [], "control: the unedited copy is clean"
    tag, name = fixture_key.split("/")
    target = scratch / gen.CONFORMANCE_DIR / tag / name / gen.GOLDEN_DIR / golden
    raw = bytearray(target.read_bytes())
    raw[len(raw) // 2] ^= 0x01
    target.write_bytes(bytes(raw))
    assert any(fixture_key.replace("/", "/") in problem for problem in gen.differences(scratch, generated)), request_key


def test_write_rewrites_a_stale_detail_golden_that_check_reports(generated: dict[Path, bytes], tmp_path: Path) -> None:
    scratch = copy_conformance(tmp_path / "copy")
    target = scratch / gen.CONFORMANCE_DIR / "tasks-md" / "crlf" / gen.GOLDEN_DIR / gen.GET_WP_DETAIL_GOLDEN
    target.write_bytes(gen.canonical_bytes({"stale": True}))
    assert any(problem.startswith("differs:") and "tasks-md/crlf" in problem for problem in gen.differences(scratch, generated)), "--check names the stale golden"
    gen.write_all(scratch, generated)
    assert gen.differences(scratch, generated) == [], "--write rewrites it"
    assert target.read_bytes() == generated[gen.CONFORMANCE_DIR / "tasks-md" / "crlf" / gen.GOLDEN_DIR / gen.GET_WP_DETAIL_GOLDEN]


def test_a_detail_golden_missing_from_a_scratch_copy_is_reported(generated: dict[Path, bytes], tmp_path: Path) -> None:
    scratch = copy_conformance(tmp_path / "copy")
    (scratch / gen.CONFORMANCE_DIR / "cycles" / "numeric-order" / gen.GOLDEN_DIR / gen.GET_WP_DETAIL_GOLDEN).unlink()
    assert any(problem.startswith("missing:") and "numeric-order" in problem for problem in gen.differences(scratch, generated))


def test_removing_a_fixture_a_class_or_a_manifest_entry_from_a_scratch_copy_turns_the_census_red(
    fixtures: list[gen.Fixture], generated: dict[Path, bytes], tmp_path: Path
) -> None:
    scratch = copy_conformance(tmp_path / "copy")
    shutil.rmtree(scratch / gen.CONFORMANCE_DIR / "wp-prompt-bytes" / "zero-bytes")
    after = [fixture for fixture in gen.discover_fixtures(scratch / gen.CONFORMANCE_DIR) if fixture.tag == "wp-prompt-bytes"]
    assert len(after) == CLASS_FLOORS["wp-prompt-bytes"] - 1 < CLASS_FLOORS["wp-prompt-bytes"], "one fixture removed: the class is under its floor"
    assert any("zero-bytes" in problem for problem in gen.differences(scratch, generated)), "the generator reports the removed fixture's goldens"
    manifest = manifest_of(scratch)
    manifest["classes"] = [entry for entry in manifest["classes"] if entry["tag"] != "cycles"]
    assert [entry["tag"] for entry in manifest["classes"]] != list(gen.CLASS_TAGS), "one manifest class removed"
    removed = manifest_of(REPO_ROOT)
    removed["classes"][-1]["fixtures"] = removed["classes"][-1]["fixtures"][:-1]
    assert sum(len(entry["fixtures"]) for entry in removed["classes"]) < sum(len(entry["fixtures"]) for entry in manifest_of(REPO_ROOT)["classes"])


def test_the_phases_array_and_the_cross_product_are_pinned_by_the_phases_matrix_class(fixtures: list[gen.Fixture]) -> None:
    held = {fixture.name for fixture in fixtures if fixture.tag == "phases-matrix"}
    assert held == set(PHASE_TABLE) and len(held) == 19
    seen = {(name.split("-")[1] if name.startswith("ps-") else name) for name in held}
    assert {"file", "completed", "started", "neither", "link", "rotated"} <= seen
    assert {name for name in held if name.startswith("lc-")} == {"lc-empty", "lc-planned", "lc-mix", "lc-for-review", "lc-done", "lc-canceled", "lc-blocked"}
    for fixture in (item for item in fixtures if item.tag == "phases-matrix"):
        order = [phase["name"] for phase in golden_of(fixture, gen.GET_MISSION_GOLDEN)[gen.MISSION_KEY]["phases"]]
        assert order == PHASE_ORDER, fixture.key


def test_the_committed_tree_holds_no_symlink_no_git_entry_and_no_forbidden_name_character() -> None:
    seen = 0
    for path in sorted(CONFORMANCE.rglob("*")):
        relative = path.relative_to(CONFORMANCE).as_posix()
        seen += 1
        assert not path.is_symlink(), f"{relative} is a symbolic link"
        assert ".git" not in relative.split("/"), f"{relative} is a .git entry"
        assert not FORBIDDEN_NAME_CHARACTERS & set(relative), f"{relative} holds a character the Windows filename gate rejects"
        assert relative.isascii(), f"{relative}: a committed non-ASCII name stops the native-image test build (made at test time by a write line)"
    assert seen >= 300, "the scan sees the conformance tree"


def test_no_committed_fixture_holds_a_whole_credential_a_home_path_or_a_plain_address(fixtures: list[gen.Fixture], tools: payloads.ContractTools) -> None:
    home = re.compile(r"/home/[A-Za-z0-9_.-]+/|/Users/[A-Za-z0-9_.-]+/")
    address = re.compile(r"[A-Za-z0-9._-]+@[A-Za-z0-9-]+\.[A-Za-z]+")
    for fixture in (item for item in fixtures if item.detail):
        for path in sorted(fixture.path.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 50_000:  # the two bulk bodies are runs of one letter
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            where = path.relative_to(CONFORMANCE).as_posix()
            assert not home.search(text), where
            assert not any(pattern.search(text) for pattern in tools.leak.SECRET_PATTERNS), f"{where} holds a whole credential shape"
            whole = [match for match in address.findall(text.replace("@@", "")) if not match.endswith(".invalid")] if "@" in text.replace("@@", "") else []
            assert not whole or path.name in {"config.yaml", "metadata.yaml"}, f"{where} holds a whole address"


# -- PROVISION_PLAN (D-42, OO-4) ----------------------------------------------------------------------------------------------------------


def plan_fixture(tmp_path: Path, lines: list[str]) -> tuple[Path, Path]:
    fixture_path, root = tmp_path / "fixture", tmp_path / "project"
    fixture_path.mkdir()
    root.mkdir()
    (fixture_path / gen.PROVISION_PLAN).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fixture_path, root


def test_the_provision_plan_applies_its_six_verbs_to_the_copy(tmp_path: Path) -> None:
    fixture_path, root = plan_fixture(
        tmp_path,
        [
            "# a comment",
            "",
            "dir\tkitty-specs/m/real",
            "gitentry\tkitty-specs/m/real/.git",
            "link\tkitty-specs/m/linked\tkitty-specs/m/real",
            "mtime\tkitty-specs/m/real/.git\t1790000000",
            "substitute\tkitty-specs/m/note.md\t@@X@@\tab\tcd",
            "write\tkitty-specs/m/made/" + chr(0xE9) + ".md\tcontent",
        ],
    )
    (root / "kitty-specs" / "m").mkdir(parents=True)
    (root / "kitty-specs" / "m" / "note.md").write_text("see @@X@@ here\n", encoding="utf-8")
    gen.apply_provision_plan(fixture_path, root)
    assert (root / "kitty-specs" / "m" / "linked").is_symlink() and (root / "kitty-specs" / "m" / "linked" / ".git").is_file()
    assert int((root / "kitty-specs" / "m" / "real" / ".git").stat().st_mtime) == 1790000000
    assert (root / "kitty-specs" / "m" / "note.md").read_text(encoding="utf-8") == "see abcd here\n"
    assert (root / "kitty-specs" / "m" / "made" / (chr(0xE9) + ".md")).read_text(encoding="utf-8") == "content"


@pytest.mark.parametrize(
    "line",
    [
        "unknown\tx",
        "dir\t../escape",
        "dir\t/absolute",
        "link\tonly-one-argument",
        "substitute\tnote.md\t@@MISSING@@\tx",
        "mtime\tnothing-here\t17",
        "write\t../escape\tx",
    ],
)
def test_a_provision_plan_line_that_is_unusable_or_leaves_the_root_is_refused(line: str, tmp_path: Path) -> None:
    fixture_path, root = plan_fixture(tmp_path, [line])
    (root / "note.md").write_text("no marker\n", encoding="utf-8")
    with pytest.raises((ValueError, OSError)):
        gen.apply_provision_plan(fixture_path, root)


def test_a_link_to_the_outside_tree_points_into_a_sibling_directory(tmp_path: Path) -> None:
    fixture_path, root = plan_fixture(tmp_path, ["link\tpoint\t@outside/tree"])
    (fixture_path / gen.OUTSIDE_TREE / "tree").mkdir(parents=True)
    gen.apply_provision_plan(fixture_path, root)
    assert (root / "point").resolve() == (root.parent / gen.OUTSIDE_TREE / "tree").resolve()


def test_the_provision_plan_and_the_artifact_requests_are_never_copied_into_the_project_root(fixtures: list[gen.Fixture], tmp_path: Path) -> None:
    holding = [fixture for fixture in fixtures if (fixture.path / gen.PROVISION_PLAN).is_file()]
    assert len(holding) >= 20
    for fixture in holding[:5] + [item for item in fixtures if (item.path / gen.ARTIFACT_REQUESTS).is_file()]:
        root = tmp_path / fixture.key.replace("/", "-")
        root.mkdir()
        gen.provision(fixture, root)
        assert not (root / gen.PROVISION_PLAN).exists() and not (root / gen.ARTIFACT_REQUESTS).exists(), fixture.key
    inside = [path for fixture in fixtures for path in fixture.path.joinpath("kitty-specs").rglob(gen.PROVISION_PLAN)]
    assert inside == [], "the plan sits at the fixture top level, never inside a Mission"


def test_the_symlink_class_keeps_reading_symlink_plan_as_before(fixtures: list[gen.Fixture]) -> None:
    plans = [fixture for fixture in fixtures if fixture.tag == "symlink"]
    assert len(plans) >= 3 and all((fixture.path / gen.SYMLINK_PLAN).is_file() and not (fixture.path / gen.PROVISION_PLAN).exists() for fixture in plans)
    assert gen.SYMLINK_PLAN in gen.NOT_COPIED and gen.PROVISION_PLAN in gen.NOT_COPIED


# -- AC-14.6: the router names every src file the generator imports --------------------------------------------------------------------------


def router_contract_tools_group() -> set[str]:
    lines = ROUTER_WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == "contract_tools:" and lines[index + 1].strip().startswith("- '"))
    entries: set[str] = set()
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if not stripped.startswith("- '"):
            break
        entries.add(stripped.removeprefix("- '").removesuffix("'"))
    return entries


def generator_src_imports() -> set[str]:
    tree = ast.parse((REPO_ROOT / "tests" / "contract" / "_mission_status_conformance.py").read_text(encoding="utf-8"))
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in {"specify_cli", "kernel", "mission_runtime"}
    }
    found: set[str] = set()
    for module in modules:
        base = REPO_ROOT / "src" / Path(*module.split("."))
        found.add(f"**/{module.replace('.', '/')}" + (".py" if base.with_suffix(".py").is_file() else "/__init__.py"))
    return found


def test_the_contract_tools_filter_group_names_every_src_file_the_extended_generator_imports() -> None:
    group = router_contract_tools_group()
    assert len(group) > 30, "the filter group was read"
    imported = generator_src_imports()
    assert "**/specify_cli/status/wp_metadata.py" in imported, "the new import of the generator is among the derived ones"
    assert imported - group == set(), f"the group omits {sorted(imported - group)}"
    assert generator_src_imports() | {"**/specify_cli/not_imported.py"} - group, "a src file missing from the group is detected"


# ---------------------------------------------------------------------------
# FR-021, AC-21.1 to AC-21.3: the baseline-red record (P0 precondition)
# ---------------------------------------------------------------------------
#
# ``traces/baseline-red.yaml`` holds the red set of the targeted modules on two bases, captured once before the first Work Package.
# The pure function ``base_violations`` takes an injected object resolver, so the controls do not depend on what a checkout holds:
# the real run injects ``git``, the controls inject a fake. After history compaction and the retarget the recorded base B no longer
# exists; that is the typed outcome ``unreachable_after_rewrite``, accepted only for an ``ephemeral`` base.

BASELINE_RECORD = REPO_ROOT / "kitty-specs" / "mission-status-read-api-mission-detail-01M4S6D5" / "traces" / "baseline-red.yaml"
BASELINE_SHA = re.compile(r"[0-9a-f]{40}")
REALITY_MODULE = "tests/contract/test_mission_status_reality.py"
REALITY_STATUS = "not run: known timeout"
CLOSED_ISSUE = 3284
GRADLE_MODULE = "gradle:services/mission-status-api:test"
UNREACHABLE_AFTER_REWRITE = "unreachable_after_rewrite"
# Module -> (executed floor on base A, executed floor on base B). ``None`` means the module is absent on that base (decided by
# ``git cat-file -e`` at capture) and is recorded ``absent_on_base`` with ``executed: 0``. A floor is the number captured, so a
# module emptied of tests falls below it. The reality module is listed apart: it is recorded ``not run``.
BASELINE_MODULES: dict[str, tuple[int | None, int | None]] = {
    "tests/contract/test_mission_status_artifacts.py": (138, 138),
    "tests/contract/test_mission_status_conformance.py": (None, 54),
    "tests/contract/test_mission_status_contract_1_1.py": (179, 179),
    "tests/contract/test_mission_status_detail.py": (241, 241),
    "tests/contract/test_mission_status_drift.py": (72, 72),
    "tests/contract/test_mission_status_examples.py": (318, 318),
    "tests/contract/test_mission_status_ops.py": (160, 160),
    "tests/contract/test_mission_status_payloads.py": (172, 172),
    "tests/contract/test_mission_status_project.py": (29, 29),
    "tests/ci/test_mission_status_api_build.py": (None, 160),
    "tests/ci/test_mission_status_corpus_compare.py": (None, 31),
    "tests/ci/test_mission_status_gate_checks.py": (None, 29),
    "tests/ci/test_mission_status_routing.py": (None, 11),
    GRADLE_MODULE: (None, 2315),
}
BASELINE_GLOBS = ("tests/contract/test_mission_status_*.py", "tests/ci/test_mission_status_*.py")


class ObjectResolver:
    """The injected view of git objects: does a commit exist, and what is its tree."""

    def exists(self, sha: str) -> bool:
        raise NotImplementedError

    def tree_of(self, sha: str) -> str:
        raise NotImplementedError


class GitObjects(ObjectResolver):
    def exists(self, sha: str) -> bool:
        return subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=REPO_ROOT, capture_output=True, check=False).returncode == 0

    def tree_of(self, sha: str) -> str:
        return subprocess.run(["git", "rev-parse", f"{sha}^{{tree}}"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


@dataclass
class FakeObjects(ObjectResolver):
    present: set[str] = field(default_factory=set)
    trees: dict[str, str] = field(default_factory=dict)

    def exists(self, sha: str) -> bool:
        return sha in self.present

    def tree_of(self, sha: str) -> str:
        return self.trees.get(sha, "")


def normalise_signature(exception_class: str, message: str) -> str:
    """AC-21.2: exception class plus the first message line with ULIDs, absolute paths, hexadecimal runs and digits replaced."""
    line = message.strip().splitlines()[0] if message.strip() else ""
    line = re.sub(r"\b[0-9A-HJKMNP-TV-Z]{26}\b", "<ULID>", line)
    line = re.sub(r"(?<![\w.])/[^\s'\"]+", "<PATH>", line)
    line = re.sub(r"\b[0-9a-f]{7,}\b", "<HEX>", line)
    line = re.sub(r"\d+", "<N>", line)
    return f"{exception_class}: {line}"


def b_outcome(record: Mapping[str, Any], objects: ObjectResolver) -> str:
    """``verified`` when base B resolves, else the typed ``unreachable_after_rewrite``."""
    return "verified" if objects.exists(record["bases"]["B"]["sha"]) else UNREACHABLE_AFTER_REWRITE


def base_violations(record: Mapping[str, Any], objects: ObjectResolver) -> list[str]:
    """AC-21.1 rules (1) to (4) for the two bases."""
    found: list[str] = []
    bases = record.get("bases", {})
    shas = {name: str(bases.get(name, {}).get("sha", "")) for name in ("A", "B")}
    for name, sha in shas.items():
        if not BASELINE_SHA.fullmatch(sha):
            found.append(f"base {name} sha is not 40 hex")
    tree = str(bases.get("B", {}).get("tree", ""))
    if not BASELINE_SHA.fullmatch(tree):
        found.append("base B tree hash is not 40 hex")
    if shas["A"] == shas["B"]:
        found.append("base A and base B are the same commit")
    if BASELINE_SHA.fullmatch(shas["A"]) and not objects.exists(shas["A"]):
        found.append("base A does not resolve")
    if BASELINE_SHA.fullmatch(shas["B"]):
        if objects.exists(shas["B"]):
            if objects.tree_of(shas["B"]) != tree:
                found.append("base B resolves but its tree differs from the recorded tree")
        elif bases.get("B", {}).get("ephemeral") is not True:
            found.append("base B does not resolve and is not recorded ephemeral")
    return found


def _row_violations(module: str, base: str, row: Any, record: Mapping[str, Any]) -> list[str]:
    where = f"{module} base {base} row"
    if not isinstance(row, Mapping):
        return [f"{where} is not a mapping"]
    found: list[str] = []
    for key in ("id", "signature"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            found.append(f"{where} has no {key}")
    if row.get("base") != record["bases"][base]["sha"]:
        found.append(f"{where} names a base sha that is not base {base}")
    issue = row.get("issue")
    if not isinstance(issue, int) or isinstance(issue, bool):
        found.append(f"{where} has no issue number")
    elif issue == CLOSED_ISSUE:
        found.append(f"{where} cites the closed issue {CLOSED_ISSUE}")
    elif issue not in {entry.get("number") for entry in record.get("issues", [])}:
        found.append(f"{where} cites issue {issue} that is not in the issues list")
    return found


def _base_entry_violations(module: str, base: str, entry: Any, floor: int | None, record: Mapping[str, Any]) -> list[str]:
    if not isinstance(entry, Mapping):
        return [f"{module} has no entry for base {base}"]
    found: list[str] = []
    executed, failed, rows = entry.get("executed"), entry.get("failed"), entry.get("rows")
    if not isinstance(executed, int) or not isinstance(failed, int) or not isinstance(rows, list):
        return [f"{module} base {base} lacks executed, failed or rows"]
    if floor is None:
        if entry.get("status") != "absent_on_base":
            found.append(f"{module} is absent on base {base} but is not recorded absent_on_base")
        if executed != 0 or failed != 0 or rows:
            found.append(f"{module} is absent_on_base on {base} but holds counts or rows")
        return found
    if entry.get("status") != "run":
        found.append(f"{module} exists on base {base} but is recorded {entry.get('status')!r}, not run")
    if executed < floor:
        found.append(f"{module} base {base} executed {executed} is under the floor {floor}")
    if len(rows) != failed:
        found.append(f"{module} base {base} has {len(rows)} rows for {failed} failed")
    for row in rows:
        found.extend(_row_violations(module, base, row, record))
    return found


def _not_run_violations(entry: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    if entry.get("status") != REALITY_STATUS:
        found.append("the reality module is not recorded 'not run: known timeout'")
    if entry.get("attribution") != "unclassified":
        found.append("the reality module has no attribution 'unclassified'")
    if not isinstance(entry.get("issue"), int) or isinstance(entry.get("issue"), bool):
        found.append("the reality module has no issue number")
    if not str(entry.get("reason", "")).strip():
        found.append("the reality module has no reason")
    if entry.get("rows"):
        found.append("the reality module is not run and must hold no rows")
    return found


def record_violations(record: Mapping[str, Any], objects: ObjectResolver, live_modules: set[str]) -> list[str]:
    """Every violation of AC-21.1 to AC-21.3 in a baseline record; empty when the record holds."""
    found = base_violations(record, objects)
    listed = {str(entry.get("module")): entry for entry in record.get("modules", [])}
    if set(listed) != set(BASELINE_MODULES) | {REALITY_MODULE}:
        found.append(f"the module list differs from the committed one by {sorted(set(listed) ^ (set(BASELINE_MODULES) | {REALITY_MODULE}))}")
    for module in sorted(set(listed) - {GRADLE_MODULE}):
        if module not in live_modules:
            found.append(f"{module} is listed but absent from the live glob")
    for module, (floor_a, floor_b) in BASELINE_MODULES.items():
        if module in listed:
            for base, floor in (("A", floor_a), ("B", floor_b)):
                found.extend(_base_entry_violations(module, base, listed[module].get(base), floor, record))
    if REALITY_MODULE in listed:
        found.extend(_not_run_violations(listed[REALITY_MODULE]))
    issues = record.get("issues", [])
    for entry in issues:
        number = entry.get("number")
        if not isinstance(number, int) or entry.get("issueState") != "OPEN" or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(entry.get("checked", ""))):
            found.append(f"issue entry {number!r} lacks a number, issueState OPEN or a checked date")
    if REALITY_MODULE in listed and listed[REALITY_MODULE].get("issue") not in {entry.get("number") for entry in issues}:
        found.append("the reality module cites an issue that is not in the issues list")
    for base in ("A", "B"):
        entries = [listed[m][base] for m in BASELINE_MODULES if m in listed and isinstance(listed[m].get(base), Mapping)]
        failed = sum(e["failed"] for e in entries if isinstance(e.get("failed"), int))
        rows = sum(len(e["rows"]) for e in entries if isinstance(e.get("rows"), list))
        if record.get("redCount", {}).get(base) != failed or failed != rows:
            found.append(f"redCount of base {base} is not the sum of failed and the number of rows")
    return found


def _live_modules() -> set[str]:
    return {path.relative_to(REPO_ROOT).as_posix() for pattern in BASELINE_GLOBS for path in REPO_ROOT.glob(pattern)}


def _real_record() -> dict[str, Any]:
    loaded = yaml.safe_load(BASELINE_RECORD.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _fake_objects(record: Mapping[str, Any]) -> FakeObjects:
    return FakeObjects({record["bases"]["A"]["sha"], record["bases"]["B"]["sha"]}, {record["bases"]["B"]["sha"]: record["bases"]["B"]["tree"]})


def _module(record: dict[str, Any], name: str) -> dict[str, Any]:
    return next(entry for entry in record["modules"] if entry["module"] == name)


def _with_planted_red(record: dict[str, Any]) -> dict[str, Any]:
    """A consistent copy with one red on base B: one row, ``failed`` 1, ``redCount`` 1."""
    planted = copy.deepcopy(record)
    entry = _module(planted, "tests/contract/test_mission_status_detail.py")["B"]
    entry["failed"] = 1
    signature = normalise_signature("AssertionError", "assert 1 == 2")
    entry["rows"] = [
        {"id": "tests/contract/test_mission_status_detail.py::test_planted", "base": planted["bases"]["B"]["sha"], "signature": signature, "issue": 5927}
    ]
    planted["redCount"]["B"] = 1
    return planted


def test_baseline_record_holds_against_git_and_the_live_module_glob() -> None:
    record = _real_record()
    objects = GitObjects()
    assert record_violations(record, objects, _live_modules()) == []
    assert b_outcome(record, objects) in {"verified", UNREACHABLE_AFTER_REWRITE}


def _drop_module(record: dict[str, Any]) -> None:
    record["modules"] = [entry for entry in record["modules"] if entry["module"] != "tests/contract/test_mission_status_ops.py"]


def _drop_reality(record: dict[str, Any]) -> None:
    record["modules"] = [entry for entry in record["modules"] if entry["module"] != REALITY_MODULE]


def _lower_executed(record: dict[str, Any]) -> None:
    _module(record, "tests/contract/test_mission_status_examples.py")["B"]["executed"] -= 1


def _raise_failed(record: dict[str, Any]) -> None:
    _module(record, "tests/contract/test_mission_status_examples.py")["B"]["failed"] = 1


def _flip_absent_flag_off(record: dict[str, Any]) -> None:
    _module(record, "tests/ci/test_mission_status_routing.py")["A"]["status"] = "run"


def _flip_absent_flag_on(record: dict[str, Any]) -> None:
    _module(record, "tests/contract/test_mission_status_detail.py")["A"]["status"] = "absent_on_base"


def _reality_with_row(record: dict[str, Any]) -> None:
    _module(record, REALITY_MODULE)["rows"] = [{"id": "x", "base": record["bases"]["A"]["sha"], "signature": "y", "issue": 5927}]


def _reality_without_attribution(record: dict[str, Any]) -> None:
    del _module(record, REALITY_MODULE)["attribution"]


def _reality_without_issue(record: dict[str, Any]) -> None:
    del _module(record, REALITY_MODULE)["issue"]


def _red_count_off(record: dict[str, Any]) -> None:
    record["redCount"]["A"] = 1


def _issue_not_open(record: dict[str, Any]) -> None:
    record["issues"][0]["issueState"] = "CLOSED"


def _executed_text(record: dict[str, Any]) -> None:
    _module(record, "tests/contract/test_mission_status_ops.py")["A"]["executed"] = "160"


BASELINE_CONTROLS: dict[str, Callable[[dict[str, Any]], None]] = {
    "malformed base A sha": lambda r: r["bases"]["A"].__setitem__("sha", "d0c6ca61d"),
    "malformed base B sha": lambda r: r["bases"]["B"].__setitem__("sha", "z" * 40),
    "same sha for both bases": lambda r: r["bases"]["B"].__setitem__("sha", r["bases"]["A"]["sha"]),
    "base B tree hash changed while B is present": lambda r: r["bases"]["B"].__setitem__("tree", "0" * 40),
    "base B tree hash malformed": lambda r: r["bases"]["B"].__setitem__("tree", "abc"),
    "ephemeral removed while B is absent": lambda r: (r["bases"]["B"].__delitem__("ephemeral"), r["bases"]["B"].__setitem__("sha", "1" * 40)),
    "base A absent": lambda r: r["bases"]["A"].__setitem__("sha", "2" * 40),
    "a module removed": _drop_module,
    "the reality module removed": _drop_reality,
    "executed count altered below its floor": _lower_executed,
    "failed count raised without rows": _raise_failed,
    "executed given as text": _executed_text,
    "module present on A recorded absent_on_base": _flip_absent_flag_on,
    "module absent on A recorded without absent_on_base": _flip_absent_flag_off,
    "reality module holds a row": _reality_with_row,
    "reality module without attribution": _reality_without_attribution,
    "reality module without issue": _reality_without_issue,
    "redCount disagrees with the sum of failed": _red_count_off,
    "issue no longer OPEN": _issue_not_open,
}


@pytest.mark.parametrize("name", sorted(BASELINE_CONTROLS))
def test_baseline_record_control_turns_red(name: str) -> None:
    record = _real_record()
    objects = _fake_objects(record)  # built from the real record: a control that edits a sha names a commit the fake does not hold
    live = _live_modules()
    assert record_violations(record, objects, live) == [], "the control starts from a green record"
    mutated = copy.deepcopy(record)
    BASELINE_CONTROLS[name](mutated)
    assert record_violations(mutated, objects, live) != [], name


def test_baseline_record_row_checks_are_not_vacuous_with_a_planted_red() -> None:
    record = _real_record()
    objects, live = _fake_objects(record), _live_modules()
    planted = _with_planted_red(record)
    assert record_violations(planted, objects, live) == [], "a consistent planted red is accepted"

    def violations_after(mutate: Callable[[dict[str, Any]], None]) -> list[str]:
        copy_of = copy.deepcopy(planted)
        mutate(copy_of)
        return record_violations(copy_of, objects, live)

    def row(r: dict[str, Any]) -> dict[str, Any]:
        return _module(r, "tests/contract/test_mission_status_detail.py")["B"]["rows"][0]

    assert violations_after(lambda r: _module(r, "tests/contract/test_mission_status_detail.py")["B"]["rows"].clear()), "a row removed"
    assert violations_after(lambda r: row(r).__delitem__("issue")), "a row without an issue"
    assert violations_after(lambda r: row(r).__setitem__("issue", CLOSED_ISSUE)), "a row citing the closed issue"
    assert violations_after(lambda r: row(r).__setitem__("issue", 4242)), "a row citing an issue not in the list"
    assert violations_after(lambda r: row(r).__setitem__("signature", " ")), "a row without a signature"
    assert violations_after(lambda r: row(r).__setitem__("base", record["bases"]["A"]["sha"])), "a row naming the other base"
    assert violations_after(lambda r: r["redCount"].__setitem__("B", 0)), "redCount not matching the failed count"


def test_baseline_record_unreachable_base_b_is_accepted_only_when_ephemeral() -> None:
    record = _real_record()
    live = _live_modules()
    only_a = FakeObjects({record["bases"]["A"]["sha"]})
    assert b_outcome(record, only_a) == UNREACHABLE_AFTER_REWRITE
    assert record_violations(record, only_a, live) == [], "an ephemeral base B that no longer resolves is the accepted outcome"
    not_ephemeral = copy.deepcopy(record)
    not_ephemeral["bases"]["B"]["ephemeral"] = False
    assert record_violations(not_ephemeral, only_a, live) != []


def test_baseline_record_module_list_allows_a_superset_but_not_a_missing_module() -> None:
    record = _real_record()
    objects = _fake_objects(record)
    live = _live_modules()
    assert record_violations(record, objects, live | {"tests/contract/test_mission_status_new_in_this_mission.py"}) == []
    assert record_violations(record, objects, live - {"tests/contract/test_mission_status_ops.py"}) != []


def test_baseline_record_signature_is_stable_across_numbers_paths_and_ids() -> None:
    first = normalise_signature("Failed", "Timeout >240.0s at /srv/build/repo/tests/x.py line 12 for 01KXYZABCDEFGHJKMNPQRSTVWX sha deadbeef12")
    second = normalise_signature("Failed", "Timeout >241.5s at /srv/other/place/tests/y.py line 99 for 01KABCDEFGHJKMNPQRSTVWXYZ0 sha 0123456789ab")
    assert first == second
    assert normalise_signature("KeyError", "'findings'") != normalise_signature("AssertionError", "'findings'")
    assert normalise_signature("KeyError", "'findings'") != normalise_signature("KeyError", "'summary'")
