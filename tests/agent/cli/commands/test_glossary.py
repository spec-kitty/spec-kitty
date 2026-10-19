"""Tests for the glossary management CLI commands.

Tests all three glossary subcommands:
  - glossary list: term listing with scope/status/json filters
  - glossary conflicts: conflict history from event log
  - glossary resolve: interactive conflict resolution

Each test uses tmp_path fixtures with mock glossary seed files and
mock event logs to avoid filesystem coupling.
"""

import json

import pytest
from typer.testing import CliRunner

# We import the top-level app so the glossary subcommand is registered
from specify_cli.cli.commands.glossary import app as glossary_app

pytestmark = pytest.mark.fast

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_glossary_store(tmp_path):
    """Create mock glossary store with seed files containing test data.

    Creates team_domain and mission_local seed files.
    """
    glossaries_dir = tmp_path / ".kittify" / "glossaries"
    glossaries_dir.mkdir(parents=True)

    team_domain = glossaries_dir / "team_domain.yaml"
    team_domain.write_text(
        "terms:\n"
        "  - surface: workspace\n"
        "    definition: Git worktree directory for a work package\n"
        "    confidence: 0.9\n"
        "    status: active\n"
        "  - surface: mission\n"
        "    definition: Purpose-specific workflow machine\n"
        "    confidence: 1.0\n"
        "    status: active\n"
    )

    mission_local = glossaries_dir / "mission_local.yaml"
    mission_local.write_text(
        "terms:\n"
        "  - surface: primitive\n"
        "    definition: Atomic unit of work in a mission step\n"
        "    confidence: 0.85\n"
        "    status: draft\n"
    )

    return tmp_path


@pytest.fixture
def mock_glossary_empty(tmp_path):
    """Create empty glossary directory (no seed files)."""
    glossaries_dir = tmp_path / ".kittify" / "glossaries"
    glossaries_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_no_glossary(tmp_path):
    """Create repo without glossary directory."""
    return tmp_path


@pytest.fixture
def mock_event_log(tmp_path):
    """Create mock event log with both blocked and resolved conflict events.

    Events:
    - SemanticCheckEvaluated (blocked, 1 finding: workspace, ambiguous, high)
    - GlossaryClarificationRequested (deferred with UUID conflict_id)
    - GlossaryClarificationResolved (resolves the workspace conflict)
    """
    events_dir = tmp_path / ".kittify" / "events" / "glossary"
    events_dir.mkdir(parents=True)

    # Use a real UUID as conflict_id (as ClarificationMiddleware would)
    workspace_conflict_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

    events = [
        {
            "event_type": "SemanticCheckEvaluated",
            "step_id": "test-001",
            "mission_id": "software-dev",
            "run_id": "run-1",
            "timestamp": "2026-02-16T12:00:00Z",
            "blocked": True,
            "effective_strictness": "medium",
            "findings": [
                {
                    "term": {"surface_text": "workspace"},
                    "conflict_type": "ambiguous",
                    "severity": "high",
                    "confidence": 0.9,
                    "candidate_senses": [
                        {
                            "surface": "workspace",
                            "scope": "team_domain",
                            "definition": "Git worktree directory",
                            "confidence": 0.9,
                        },
                        {
                            "surface": "workspace",
                            "scope": "mission_local",
                            "definition": "IDE workspace folder",
                            "confidence": 0.7,
                        },
                    ],
                    "context": "description field",
                }
            ],
            "overall_severity": "high",
            "confidence": 0.9,
            "recommended_action": "block",
        },
        {
            "event_type": "GlossaryClarificationRequested",
            "conflict_id": workspace_conflict_id,
            "term": "workspace",
            "question": "What does 'workspace' mean in this context?",
            "options": ["Git worktree directory", "IDE workspace folder"],
            "urgency": "high",
            "mission_id": "software-dev",
            "run_id": "run-1",
            "step_id": "test-001",
            "timestamp": "2026-02-16T12:01:00Z",
        },
        {
            "event_type": "GlossaryClarificationResolved",
            "conflict_id": workspace_conflict_id,
            "term_surface": "workspace",
            "selected_sense": {
                "surface": "workspace",
                "scope": "team_domain",
                "definition": "Git worktree directory",
                "confidence": 0.9,
            },
            "actor": {"actor_id": "user:alice"},
            "resolution_mode": "interactive",
            "provenance": {"source": "user_clarification"},
            "timestamp": "2026-02-16T12:05:00Z",
        },
    ]

    event_file = events_dir / "software-dev.events.jsonl"
    with event_file.open("w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    return tmp_path


# Canonical conflict IDs for unresolved fixture (used in tests)
UNRESOLVED_WORKSPACE_CID = "bbbb1111-2222-3333-4444-555566667777"
UNRESOLVED_CONFIG_CID = "cccc1111-2222-3333-4444-555566667777"


@pytest.fixture
def mock_event_log_unresolved(tmp_path):
    """Create mock event log with only unresolved conflicts.

    Events:
    - SemanticCheckEvaluated (blocked, 2 findings: workspace and config)
    - GlossaryClarificationRequested for each finding (with UUID conflict_ids)
    """
    events_dir = tmp_path / ".kittify" / "events" / "glossary"
    events_dir.mkdir(parents=True)

    events = [
        {
            "event_type": "SemanticCheckEvaluated",
            "step_id": "test-002",
            "mission_id": "software-dev",
            "run_id": "run-2",
            "timestamp": "2026-02-16T13:00:00Z",
            "blocked": True,
            "effective_strictness": "max",
            "findings": [
                {
                    "term": {"surface_text": "workspace"},
                    "conflict_type": "ambiguous",
                    "severity": "high",
                    "confidence": 0.9,
                    "candidate_senses": [
                        {
                            "surface": "workspace",
                            "scope": "team_domain",
                            "definition": "Git worktree directory",
                            "confidence": 0.9,
                        },
                    ],
                    "context": "step input",
                },
                {
                    "term": {"surface_text": "config"},
                    "conflict_type": "unknown",
                    "severity": "medium",
                    "confidence": 0.6,
                    "candidate_senses": [],
                    "context": "metadata field",
                },
            ],
            "overall_severity": "high",
            "confidence": 0.9,
            "recommended_action": "block",
        },
        {
            "event_type": "GlossaryClarificationRequested",
            "conflict_id": UNRESOLVED_WORKSPACE_CID,
            "term": "workspace",
            "question": "What does 'workspace' mean in this context?",
            "options": ["Git worktree directory"],
            "urgency": "high",
            "mission_id": "software-dev",
            "run_id": "run-2",
            "step_id": "test-002",
            "timestamp": "2026-02-16T13:00:01Z",
        },
        {
            "event_type": "GlossaryClarificationRequested",
            "conflict_id": UNRESOLVED_CONFIG_CID,
            "term": "config",
            "question": "What does 'config' mean in this context?",
            "options": [],
            "urgency": "medium",
            "mission_id": "software-dev",
            "run_id": "run-2",
            "step_id": "test-002",
            "timestamp": "2026-02-16T13:00:02Z",
        },
    ]

    event_file = events_dir / "software-dev.events.jsonl"
    with event_file.open("w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")

    return tmp_path


@pytest.fixture
def mock_event_log_multi_mission(tmp_path):
    """Create event logs spanning multiple missions."""
    events_dir = tmp_path / ".kittify" / "events" / "glossary"
    events_dir.mkdir(parents=True)

    # software-dev mission
    sw_events = [
        {
            "event_type": "SemanticCheckEvaluated",
            "step_id": "sw-001",
            "mission_id": "software-dev",
            "run_id": "run-1",
            "timestamp": "2026-02-16T12:00:00Z",
            "blocked": True,
            "effective_strictness": "medium",
            "findings": [
                {
                    "term": {"surface_text": "workspace"},
                    "conflict_type": "ambiguous",
                    "severity": "high",
                    "confidence": 0.9,
                    "candidate_senses": [],
                    "context": "description",
                }
            ],
            "overall_severity": "high",
            "confidence": 0.9,
            "recommended_action": "block",
        },
        {
            "event_type": "GlossaryClarificationRequested",
            "conflict_id": "dddd1111-2222-3333-4444-555566667777",
            "term": "workspace",
            "question": "What does 'workspace' mean in this context?",
            "options": [],
            "urgency": "high",
            "mission_id": "software-dev",
            "run_id": "run-1",
            "step_id": "sw-001",
            "timestamp": "2026-02-16T12:00:01Z",
        },
    ]

    sw_file = events_dir / "software-dev.events.jsonl"
    with sw_file.open("w") as f:
        for event in sw_events:
            f.write(json.dumps(event) + "\n")

    # documentation mission
    doc_events = [
        {
            "event_type": "SemanticCheckEvaluated",
            "step_id": "doc-001",
            "mission_id": "documentation",
            "run_id": "run-2",
            "timestamp": "2026-02-16T13:00:00Z",
            "blocked": True,
            "effective_strictness": "max",
            "findings": [
                {
                    "term": {"surface_text": "tutorial"},
                    "conflict_type": "unknown",
                    "severity": "low",
                    "confidence": 0.5,
                    "candidate_senses": [],
                    "context": "content",
                }
            ],
            "overall_severity": "low",
            "confidence": 0.5,
            "recommended_action": "warn",
        },
        {
            "event_type": "GlossaryClarificationRequested",
            "conflict_id": "eeee1111-2222-3333-4444-555566667777",
            "term": "tutorial",
            "question": "What does 'tutorial' mean in this context?",
            "options": [],
            "urgency": "low",
            "mission_id": "documentation",
            "run_id": "run-2",
            "step_id": "doc-001",
            "timestamp": "2026-02-16T13:00:01Z",
        },
    ]

    doc_file = events_dir / "documentation.events.jsonl"
    with doc_file.open("w") as f:
        for event in doc_events:
            f.write(json.dumps(event) + "\n")

    return tmp_path


@pytest.fixture
def mock_empty_event_log(tmp_path):
    """Create empty events directory (no event log files)."""
    events_dir = tmp_path / ".kittify" / "events" / "glossary"
    events_dir.mkdir(parents=True)
    return tmp_path


# =============================================================================
# Tests: glossary list
# =============================================================================


class TestGlossaryList:
    """Tests for the 'glossary list' command."""

    def test_list_all_scopes(self, mock_glossary_store, monkeypatch):
        """Verify glossary list displays all terms from all scopes."""
        monkeypatch.chdir(mock_glossary_store)
        result = runner.invoke(glossary_app, ["list"])

        assert result.exit_code == 0
        assert "workspace" in result.stdout
        assert "mission" in result.stdout
        assert "primitive" in result.stdout
        assert "Total: 3 term(s)" in result.stdout

    def test_list_scope_filter(self, mock_glossary_store, monkeypatch):
        """Verify --scope filter restricts output to one scope."""
        monkeypatch.chdir(mock_glossary_store)
        result = runner.invoke(glossary_app, ["list", "--scope", "team_domain"])

        assert result.exit_code == 0
        assert "workspace" in result.stdout
        assert "mission" in result.stdout
        # primitive is in mission_local, should not appear
        assert "primitive" not in result.stdout
        assert "Total: 2 term(s)" in result.stdout

    def test_list_status_filter(self, mock_glossary_store, monkeypatch):
        """Verify --status filter restricts output by status."""
        monkeypatch.chdir(mock_glossary_store)
        result = runner.invoke(glossary_app, ["list", "--status", "draft"])

        assert result.exit_code == 0
        assert "primitive" in result.stdout
        # workspace and mission terms (active) should not appear as Term entries
        # Note: "mission" substring also appears in scope name "mission_local"
        # and in the definition, so we check the active terms specifically
        assert "workspace" not in result.stdout
        assert "Total: 1 term(s)" in result.stdout

    def test_list_json_output(self, mock_glossary_store, monkeypatch):
        """Verify --json produces valid JSON output."""
        monkeypatch.chdir(mock_glossary_store)
        result = runner.invoke(glossary_app, ["list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 3

        # Check structure
        surfaces = {d["surface"] for d in data}
        assert "workspace" in surfaces
        assert "mission" in surfaces
        assert "primitive" in surfaces

        # Check all fields present
        for item in data:
            assert "surface" in item
            assert "scope" in item
            assert "definition" in item
            assert "status" in item
            assert "confidence" in item

    def test_list_json_with_scope_filter(self, mock_glossary_store, monkeypatch):
        """Verify --json with --scope produces filtered JSON."""
        monkeypatch.chdir(mock_glossary_store)
        result = runner.invoke(glossary_app, ["list", "--json", "--scope", "mission_local"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["surface"] == "primitive"

    def test_list_empty_glossary(self, mock_glossary_empty, monkeypatch):
        """Verify graceful message when glossary has no terms."""
        monkeypatch.chdir(mock_glossary_empty)
        result = runner.invoke(glossary_app, ["list"])

        assert result.exit_code == 0
        assert "No terms found" in result.stdout

    def test_list_no_glossary_dir(self, mock_no_glossary, monkeypatch):
        """Verify error when glossary is not initialized."""
        monkeypatch.chdir(mock_no_glossary)
        result = runner.invoke(glossary_app, ["list"])

        assert result.exit_code == 1
        assert "not initialized" in result.stdout.lower()

    def test_list_invalid_scope(self, mock_glossary_store, monkeypatch):
        """Verify error on invalid --scope value."""
        monkeypatch.chdir(mock_glossary_store)
        result = runner.invoke(glossary_app, ["list", "--scope", "invalid_scope"])

        assert result.exit_code == 1
        assert "Invalid scope" in result.stdout

    def test_list_invalid_status(self, mock_glossary_store, monkeypatch):
        """Verify error on invalid --status value."""
        monkeypatch.chdir(mock_glossary_store)
        result = runner.invoke(glossary_app, ["list", "--status", "bogus"])

        assert result.exit_code == 1
        assert "Invalid status" in result.stdout

    def test_list_long_definition_truncated(self, tmp_path, monkeypatch):
        """Verify definitions longer than 60 chars are truncated in table."""
        monkeypatch.chdir(tmp_path)
        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        long_def = "A" * 100
        seed = glossaries_dir / "team_domain.yaml"
        seed.write_text(
            f"terms:\n  - surface: longterm\n    definition: {long_def}\n    confidence: 0.8\n    status: active\n"
        )

        result = runner.invoke(glossary_app, ["list"])
        assert result.exit_code == 0
        # In Rich table output, the definition should be truncated with ellipsis
        # Rich uses unicode ellipsis character U+2026
        assert "\u2026" in result.stdout or "..." in result.stdout

    def test_list_long_definition_full_in_json(self, tmp_path, monkeypatch):
        """Verify full definition is preserved in JSON output."""
        monkeypatch.chdir(tmp_path)
        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        long_def = "A" * 100
        seed = glossaries_dir / "team_domain.yaml"
        seed.write_text(
            f"terms:\n  - surface: longterm\n    definition: {long_def}\n    confidence: 0.8\n    status: active\n"
        )

        result = runner.invoke(glossary_app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["definition"] == long_def

    def test_list_empty_json_output(self, mock_glossary_empty, monkeypatch):
        """Verify --json with no terms returns empty array."""
        monkeypatch.chdir(mock_glossary_empty)
        result = runner.invoke(glossary_app, ["list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []


# =============================================================================
# Tests: glossary conflicts
# =============================================================================


class TestGlossaryConflicts:
    """Tests for the 'glossary conflicts' command."""

    def test_conflicts_all(self, mock_event_log, monkeypatch):
        """Verify conflicts command displays all conflicts from event log."""
        monkeypatch.chdir(mock_event_log)
        result = runner.invoke(glossary_app, ["conflicts"])

        assert result.exit_code == 0
        assert "workspace" in result.stdout
        assert "ambiguous" in result.stdout
        assert "high" in result.stdout
        assert "resolved" in result.stdout
        assert "Total: 1 conflict(s)" in result.stdout

    def test_conflicts_unresolved_only(self, mock_event_log, monkeypatch):
        """Verify --unresolved filter excludes resolved conflicts."""
        monkeypatch.chdir(mock_event_log)
        result = runner.invoke(glossary_app, ["conflicts", "--unresolved"])

        assert result.exit_code == 0
        # All conflicts in mock_event_log are resolved
        assert "No conflicts found" in result.stdout
        assert "Total: 0 conflict(s)" in result.stdout

    def test_conflicts_unresolved_present(self, mock_event_log_unresolved, monkeypatch):
        """Verify --unresolved shows unresolved conflicts when they exist."""
        monkeypatch.chdir(mock_event_log_unresolved)
        result = runner.invoke(glossary_app, ["conflicts", "--unresolved"])

        assert result.exit_code == 0
        assert "workspace" in result.stdout
        assert "config" in result.stdout
        assert "Total: 2 conflict(s)" in result.stdout
        assert "Unresolved: 2" in result.stdout

    def test_conflicts_mission_filter(self, mock_event_log_multi_mission, monkeypatch):
        """Verify --mission filter restricts to specific mission."""
        monkeypatch.chdir(mock_event_log_multi_mission)
        result = runner.invoke(glossary_app, ["conflicts", "--mission", "documentation"])

        assert result.exit_code == 0
        assert "tutorial" in result.stdout
        assert "workspace" not in result.stdout
        assert "Total: 1 conflict(s)" in result.stdout

    def test_conflicts_strictness_filter(self, mock_event_log_multi_mission, monkeypatch):
        """Verify --strictness filter restricts to specific strictness level."""
        monkeypatch.chdir(mock_event_log_multi_mission)
        result = runner.invoke(glossary_app, ["conflicts", "--strictness", "max"])

        assert result.exit_code == 0
        assert "tutorial" in result.stdout
        # workspace conflict has medium strictness, should be filtered out
        assert "Total: 1 conflict(s)" in result.stdout

    def test_conflicts_invalid_strictness(self, mock_event_log, monkeypatch):
        """Verify error on invalid --strictness value."""
        monkeypatch.chdir(mock_event_log)
        result = runner.invoke(glossary_app, ["conflicts", "--strictness", "invalid"])

        assert result.exit_code == 1
        assert "Invalid strictness" in result.stdout

    def test_conflicts_json_output(self, mock_event_log, monkeypatch):
        """Verify --json produces valid JSON conflict list."""
        monkeypatch.chdir(mock_event_log)
        result = runner.invoke(glossary_app, ["conflicts", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["term"] == "workspace"
        assert data[0]["status"] == "resolved"
        assert data[0]["type"] == "ambiguous"
        assert data[0]["severity"] == "high"
        assert "effective_strictness" in data[0]

    def test_conflicts_no_events(self, mock_empty_event_log, monkeypatch):
        """Verify graceful message when no events exist."""
        monkeypatch.chdir(mock_empty_event_log)
        result = runner.invoke(glossary_app, ["conflicts"])

        assert result.exit_code == 0
        assert "No events found" in result.stdout

    def test_conflicts_no_events_dir(self, tmp_path, monkeypatch):
        """Verify graceful message when events directory does not exist."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(glossary_app, ["conflicts"])

        assert result.exit_code == 0
        assert "No events found" in result.stdout

    def test_conflicts_json_empty(self, mock_empty_event_log, monkeypatch):
        """Verify --json returns empty array when no events."""
        monkeypatch.chdir(mock_empty_event_log)
        result = runner.invoke(glossary_app, ["conflicts", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_conflicts_malformed_event_skipped(self, tmp_path, monkeypatch):
        """Verify malformed JSONL lines are skipped without crashing."""
        monkeypatch.chdir(tmp_path)
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        event_file = events_dir / "test.events.jsonl"
        good_check_event = {
            "event_type": "SemanticCheckEvaluated",
            "step_id": "good-001",
            "mission_id": "test",
            "timestamp": "2026-02-16T12:00:00Z",
            "blocked": True,
            "effective_strictness": "medium",
            "findings": [
                {
                    "term": {"surface_text": "valid"},
                    "conflict_type": "unknown",
                    "severity": "low",
                    "confidence": 0.5,
                    "candidate_senses": [],
                    "context": "test",
                }
            ],
        }
        good_requested_event = {
            "event_type": "GlossaryClarificationRequested",
            "conflict_id": "malformed-test-uuid",
            "term": "valid",
            "question": "What does 'valid' mean?",
            "options": [],
            "urgency": "low",
            "mission_id": "test",
            "run_id": "r1",
            "step_id": "good-001",
            "timestamp": "2026-02-16T12:00:01Z",
        }

        with event_file.open("w") as f:
            f.write("this is not valid json\n")
            f.write(json.dumps(good_check_event) + "\n")
            f.write("{broken json\n")
            f.write(json.dumps(good_requested_event) + "\n")

        result = runner.invoke(glossary_app, ["conflicts"])
        assert result.exit_code == 0
        assert "valid" in result.stdout
        assert "Total: 1 conflict(s)" in result.stdout

    def test_conflicts_summary_shows_unresolved_count(self, mock_event_log_unresolved, monkeypatch):
        """Verify unresolved summary count is displayed."""
        monkeypatch.chdir(mock_event_log_unresolved)
        result = runner.invoke(glossary_app, ["conflicts"])

        assert result.exit_code == 0
        assert "Unresolved: 2" in result.stdout

    def test_conflicts_non_blocked_events_ignored(self, tmp_path, monkeypatch):
        """Verify events with blocked=False are not shown as conflicts."""
        monkeypatch.chdir(tmp_path)
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "pass-001",
                "mission_id": "test",
                "timestamp": "2026-02-16T12:00:00Z",
                "blocked": False,
                "effective_strictness": "off",
                "findings": [],
            },
        ]

        event_file = events_dir / "test.events.jsonl"
        with event_file.open("w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        result = runner.invoke(glossary_app, ["conflicts"])
        assert result.exit_code == 0
        assert "No events found" not in result.stdout or "No conflicts found" in result.stdout


# =============================================================================
# Tests: glossary resolve
# =============================================================================


class TestGlossaryResolve:
    """Tests for the 'glossary resolve' command."""

    def test_resolve_not_found(self, mock_event_log, monkeypatch):
        """Verify error when conflict ID does not exist."""
        monkeypatch.chdir(mock_event_log)
        result = runner.invoke(glossary_app, ["resolve", "nonexistent-id"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_resolve_select_candidate(self, mock_event_log_unresolved, monkeypatch):
        """Verify resolving by selecting a candidate sense."""
        monkeypatch.chdir(mock_event_log_unresolved)

        # Input: select candidate #1
        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="1\n",
        )

        assert result.exit_code == 0
        assert "resolved successfully" in result.stdout.lower()

        # Verify event was written
        event_file = mock_event_log_unresolved / ".kittify" / "events" / "glossary" / "software-dev.events.jsonl"
        lines = event_file.read_text().strip().split("\n")
        last_event = json.loads(lines[-1])
        assert last_event["event_type"] == "GlossaryClarificationResolved"
        assert last_event["conflict_id"] == UNRESOLVED_WORKSPACE_CID
        assert last_event["resolution_mode"] == "async"

    def test_resolve_custom_definition(self, mock_event_log_unresolved, monkeypatch):
        """Verify resolving with a custom definition emits both events."""
        monkeypatch.chdir(mock_event_log_unresolved)

        # Input: 'C' for custom, then the definition
        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="C\nMy custom definition for workspace\n",
        )

        assert result.exit_code == 0
        assert "resolved successfully" in result.stdout.lower()

        # Verify BOTH events were written
        event_file = mock_event_log_unresolved / ".kittify" / "events" / "glossary" / "software-dev.events.jsonl"
        lines = event_file.read_text().strip().split("\n")

        # Second-to-last: GlossaryClarificationResolved
        resolved_event = json.loads(lines[-2])
        assert resolved_event["event_type"] == "GlossaryClarificationResolved"
        assert resolved_event["selected_sense"]["definition"] == "My custom definition for workspace"
        assert resolved_event["selected_sense"]["scope"] == "team_domain"

        # Last: GlossarySenseUpdated
        sense_event = json.loads(lines[-1])
        assert sense_event["event_type"] == "GlossarySenseUpdated"
        assert sense_event["new_sense"]["definition"] == "My custom definition for workspace"
        assert sense_event["term_surface"] == "workspace"

    def test_resolve_defer(self, mock_event_log_unresolved, monkeypatch):
        """Verify deferring resolution exits cleanly."""
        monkeypatch.chdir(mock_event_log_unresolved)

        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="D\n",
        )

        assert result.exit_code == 0
        assert "deferred" in result.stdout.lower()

    def test_resolve_already_resolved_confirm_no(self, mock_event_log, monkeypatch):
        """Verify already-resolved conflict shows warning, exits on 'no'."""
        monkeypatch.chdir(mock_event_log)

        # Use the UUID from mock_event_log fixture
        resolved_cid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = runner.invoke(
            glossary_app,
            ["resolve", resolved_cid],
            input="n\n",
        )

        assert result.exit_code == 0
        assert "already resolved" in result.stdout.lower()

    def test_resolve_already_resolved_confirm_yes(self, mock_event_log, monkeypatch):
        """Verify re-resolving an already-resolved conflict when confirmed."""
        monkeypatch.chdir(mock_event_log)

        # Use the UUID from mock_event_log fixture
        resolved_cid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        # Confirm yes, then select candidate 1
        result = runner.invoke(
            glossary_app,
            ["resolve", resolved_cid],
            input="y\n1\n",
        )

        assert result.exit_code == 0
        assert "resolved successfully" in result.stdout.lower()

    def test_resolve_invalid_selection(self, mock_event_log_unresolved, monkeypatch):
        """Verify error on invalid numeric selection."""
        monkeypatch.chdir(mock_event_log_unresolved)

        # Candidate index out of range (only 1 candidate)
        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="99\n",
        )

        assert result.exit_code == 1
        assert "invalid" in result.stdout.lower()

    def test_resolve_no_events_dir(self, tmp_path, monkeypatch):
        """Verify error when events directory does not exist."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(glossary_app, ["resolve", "any-id"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_resolve_with_mission_flag(self, mock_event_log_unresolved, monkeypatch):
        """Verify --mission flag overrides auto-detected mission."""
        monkeypatch.chdir(mock_event_log_unresolved)

        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID, "--mission", "custom-mission"],
            input="1\n",
        )

        assert result.exit_code == 0
        assert "resolved successfully" in result.stdout.lower()

        # Verify event was written to custom mission log
        custom_file = mock_event_log_unresolved / ".kittify" / "events" / "glossary" / "custom-mission.events.jsonl"
        assert custom_file.exists()
        lines = custom_file.read_text().strip().split("\n")
        last_event = json.loads(lines[-1])
        assert last_event["event_type"] == "GlossaryClarificationResolved"

    def test_resolve_shows_conflict_details(self, mock_event_log_unresolved, monkeypatch):
        """Verify conflict details are displayed before prompting."""
        monkeypatch.chdir(mock_event_log_unresolved)

        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="D\n",
        )

        assert result.exit_code == 0
        assert "workspace" in result.stdout
        assert "ambiguous" in result.stdout
        assert "high" in result.stdout
        assert "Git worktree directory" in result.stdout


# =============================================================================
# Tests: _extract_conflicts_from_events (internal helper)
# =============================================================================


class TestExtractConflicts:
    """Tests for the internal _extract_conflicts_from_events helper."""

    def test_extracts_from_clarification_requested(self):
        """Verify conflicts are extracted from GlossaryClarificationRequested events."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s1",
                "mission_id": "m1",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "medium",
                "findings": [
                    {
                        "term": {"surface_text": "test"},
                        "conflict_type": "unknown",
                        "severity": "low",
                    }
                ],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": "uuid-1234-5678",
                "term": "test",
                "question": "What does 'test' mean?",
                "options": [],
                "urgency": "low",
                "mission_id": "m1",
                "run_id": "r1",
                "step_id": "s1",
                "timestamp": "2026-01-01T00:00:01Z",
            },
        ]

        result = _extract_conflicts_from_events(events)
        assert len(result) == 1
        assert result[0]["term"] == "test"
        assert result[0]["conflict_id"] == "uuid-1234-5678"
        assert result[0]["status"] == "unresolved"

    def test_uses_real_uuid_not_synthesized(self):
        """Regression: conflict_id must be UUID from event, not step_id-term."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        real_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s1",
                "mission_id": "m1",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "medium",
                "findings": [{"term": {"surface_text": "test"}, "conflict_type": "unknown", "severity": "low"}],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": real_uuid,
                "term": "test",
                "options": [],
                "urgency": "low",
                "mission_id": "m1",
                "run_id": "r1",
                "step_id": "s1",
                "timestamp": "2026-01-01T00:00:01Z",
            },
        ]

        result = _extract_conflicts_from_events(events)
        assert len(result) == 1
        # Must be the real UUID, not "s1-test"
        assert result[0]["conflict_id"] == real_uuid
        assert result[0]["conflict_id"] != "s1-test"

    def test_marks_resolved_with_uuid(self):
        """Verify resolved events mark conflicts as resolved using UUID match."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        cid = "resolve-uuid-1234"
        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s1",
                "mission_id": "m1",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "medium",
                "findings": [{"term": {"surface_text": "test"}, "conflict_type": "ambiguous", "severity": "high"}],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": cid,
                "term": "test",
                "options": [],
                "urgency": "high",
                "mission_id": "m1",
                "run_id": "r1",
                "step_id": "s1",
                "timestamp": "2026-01-01T00:00:01Z",
            },
            {
                "event_type": "GlossaryClarificationResolved",
                "conflict_id": cid,
                "term_surface": "test",
                "timestamp": "2026-01-01T00:01:00Z",
            },
        ]

        result = _extract_conflicts_from_events(events)
        assert len(result) == 1
        assert result[0]["status"] == "resolved"
        assert result[0]["conflict_id"] == cid

    def test_immediately_resolved_without_requested(self):
        """Verify immediately resolved conflicts (no Requested event) appear."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        cid = "immediate-resolve-uuid"
        events = [
            {
                "event_type": "GlossaryClarificationResolved",
                "conflict_id": cid,
                "term_surface": "test",
                "timestamp": "2026-01-01T00:01:00Z",
            },
        ]

        result = _extract_conflicts_from_events(events)
        assert len(result) == 1
        assert result[0]["conflict_id"] == cid
        assert result[0]["status"] == "resolved"
        assert result[0]["term"] == "test"

    def test_skips_non_blocked(self):
        """Verify non-blocked SemanticCheckEvaluated without clarification events are ignored."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s1",
                "blocked": False,
                "findings": [],
            }
        ]

        result = _extract_conflicts_from_events(events)
        assert len(result) == 0

    def test_mission_filter(self):
        """Verify mission filter works."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s1",
                "mission_id": "m1",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "medium",
                "findings": [{"term": {"surface_text": "a"}, "conflict_type": "unknown", "severity": "low"}],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": "uuid-a",
                "term": "a",
                "options": [],
                "urgency": "low",
                "mission_id": "m1",
                "run_id": "r1",
                "step_id": "s1",
                "timestamp": "2026-01-01T00:00:01Z",
            },
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s2",
                "mission_id": "m2",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "max",
                "findings": [{"term": {"surface_text": "b"}, "conflict_type": "unknown", "severity": "low"}],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": "uuid-b",
                "term": "b",
                "options": [],
                "urgency": "low",
                "mission_id": "m2",
                "run_id": "r2",
                "step_id": "s2",
                "timestamp": "2026-01-01T00:00:01Z",
            },
        ]

        result = _extract_conflicts_from_events(events, mission_filter="m1")
        assert len(result) == 1
        assert result[0]["term"] == "a"

    def test_strictness_filter(self):
        """Verify strictness filter works."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s1",
                "mission_id": "m1",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "medium",
                "findings": [{"term": {"surface_text": "a"}, "conflict_type": "unknown", "severity": "low"}],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": "uuid-a",
                "term": "a",
                "options": [],
                "urgency": "low",
                "mission_id": "m1",
                "run_id": "r1",
                "step_id": "s1",
                "timestamp": "2026-01-01T00:00:01Z",
            },
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s2",
                "mission_id": "m2",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "max",
                "findings": [{"term": {"surface_text": "b"}, "conflict_type": "unknown", "severity": "low"}],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": "uuid-b",
                "term": "b",
                "options": [],
                "urgency": "low",
                "mission_id": "m2",
                "run_id": "r2",
                "step_id": "s2",
                "timestamp": "2026-01-01T00:00:01Z",
            },
        ]

        result = _extract_conflicts_from_events(events, strictness_filter="max")
        assert len(result) == 1
        assert result[0]["term"] == "b"

    def test_enriches_from_semantic_check(self):
        """Verify conflict data is enriched from SemanticCheckEvaluated findings."""
        from specify_cli.cli.commands.glossary import _extract_conflicts_from_events

        events = [
            {
                "event_type": "SemanticCheckEvaluated",
                "step_id": "s1",
                "mission_id": "m1",
                "timestamp": "2026-01-01T00:00:00Z",
                "blocked": True,
                "effective_strictness": "medium",
                "findings": [
                    {
                        "term": {"surface_text": "test"},
                        "conflict_type": "ambiguous",
                        "severity": "high",
                    }
                ],
            },
            {
                "event_type": "GlossaryClarificationRequested",
                "conflict_id": "enrich-uuid",
                "term": "test",
                "options": [],
                "urgency": "high",
                "mission_id": "m1",
                "run_id": "r1",
                "step_id": "s1",
                "timestamp": "2026-01-01T00:00:01Z",
            },
        ]

        result = _extract_conflicts_from_events(events)
        assert len(result) == 1
        # Type comes from SemanticCheckEvaluated finding
        assert result[0]["type"] == "ambiguous"
        # Effective strictness comes from SemanticCheckEvaluated event
        assert result[0]["effective_strictness"] == "medium"


# =============================================================================
# Tests: _load_store_from_seeds and _get_all_terms_from_store
# =============================================================================


class TestStoreHelpers:
    """Tests for the internal store helper functions."""

    def test_load_store_from_seeds(self, mock_glossary_store):
        """Verify store is populated from seed files."""
        from specify_cli.cli.commands.glossary import _load_store_from_seeds

        store = _load_store_from_seeds(mock_glossary_store)
        assert "team_domain" in store._cache
        assert "workspace" in store._cache["team_domain"]
        assert "mission" in store._cache["team_domain"]
        assert "mission_local" in store._cache
        assert "primitive" in store._cache["mission_local"]

    def test_get_all_terms_no_filter(self, mock_glossary_store):
        """Verify all terms returned without filters."""
        from specify_cli.cli.commands.glossary import (
            _get_all_terms_from_store,
            _load_store_from_seeds,
        )

        store = _load_store_from_seeds(mock_glossary_store)
        terms = _get_all_terms_from_store(store)
        assert len(terms) == 3

    def test_replayed_sense_missing_timestamp_gets_aware_utc_fallback(self, mock_glossary_store, tmp_path):
        """kernel-clock-single-door FR-011: a replayed ``GlossarySenseUpdated``
        event missing its ``timestamp`` field falls back to an aware-UTC
        instant, not naive local time.

        Regression guard for the naive ``datetime.now().isoformat()``
        fallback formerly in ``cli.commands.glossary._load_store_from_seeds``
        (research/migration-notes.md): a naive fallback, once round-tripped
        through ``fromisoformat``, produces a ``Provenance.timestamp`` with
        no tz — silently mislabeling local time as an instant once any
        caller serializes it. Non-vacuity: reverting the door's
        ``now_utc_iso()`` fallback back to a bare ``datetime.now().isoformat()``
        makes ``tzinfo`` come back ``None`` and this assertion fails.
        """
        from specify_cli.cli.commands.glossary import _load_store_from_seeds

        events_dir = mock_glossary_store / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)
        event_file = events_dir / "test.events.jsonl"
        event_file.write_text(
            json.dumps(
                {
                    "event_type": "GlossarySenseUpdated",
                    "actor": {"actor_id": "system:test"},
                    "new_sense": {
                        "surface": "no-timestamp-term",
                        "scope": "team_domain",
                        "definition": "A sense whose event carries no timestamp field",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        store = _load_store_from_seeds(mock_glossary_store)

        senses = store._cache["team_domain"]["no-timestamp-term"]
        assert len(senses) == 1
        assert senses[0].provenance.timestamp.tzinfo is not None

    def test_get_all_terms_scope_filter(self, mock_glossary_store):
        """Verify scope filter works."""
        from specify_cli.cli.commands.glossary import (
            _get_all_terms_from_store,
            _load_store_from_seeds,
        )
        from glossary.scope import GlossaryScope

        store = _load_store_from_seeds(mock_glossary_store)
        terms = _get_all_terms_from_store(store, scope_filter=GlossaryScope.TEAM_DOMAIN)
        assert len(terms) == 2
        assert all(t.scope == "team_domain" for t in terms)

    def test_get_all_terms_status_filter(self, mock_glossary_store):
        """Verify status filter works."""
        from specify_cli.cli.commands.glossary import (
            _get_all_terms_from_store,
            _load_store_from_seeds,
        )

        store = _load_store_from_seeds(mock_glossary_store)
        terms = _get_all_terms_from_store(store, status_filter="active")
        assert len(terms) == 2
        assert all(t.status.value == "active" for t in terms)

    def test_get_all_terms_sorted(self, mock_glossary_store):
        """Verify terms are sorted by scope then surface."""
        from specify_cli.cli.commands.glossary import (
            _get_all_terms_from_store,
            _load_store_from_seeds,
        )

        store = _load_store_from_seeds(mock_glossary_store)
        terms = _get_all_terms_from_store(store)
        surfaces = [t.surface.surface_text for t in terms]
        # mission_local comes before team_domain alphabetically
        assert surfaces[0] == "primitive"  # mission_local
        assert "mission" in surfaces
        assert "workspace" in surfaces

    def test_empty_store(self, tmp_path):
        """Verify empty store returns no terms."""
        from specify_cli.cli.commands.glossary import (

            _get_all_terms_from_store,
            _load_store_from_seeds,
        )

        (tmp_path / ".kittify" / "glossaries").mkdir(parents=True)
        store = _load_store_from_seeds(tmp_path)
        terms = _get_all_terms_from_store(store)
        assert len(terms) == 0


# =============================================================================
# Regression tests for review feedback fixes (cycle 2/3)
# =============================================================================


class TestRegressionEventLogReplay:
    """Regression tests for Fix 1: glossary list must replay event log.

    The list command was only reading seed YAML files but never replaying
    GlossarySenseUpdated and GlossaryClarificationResolved events from the
    event log. Custom senses and resolved clarifications were invisible.
    """

    def test_list_includes_sense_updated_from_events(self, tmp_path, monkeypatch):
        """Verify glossary list shows terms added via GlossarySenseUpdated events."""
        monkeypatch.chdir(tmp_path)

        # Create empty glossary directory (no seed files)
        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        # Create event log with a GlossarySenseUpdated event
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        event = {
            "event_type": "GlossarySenseUpdated",
            "term_surface": "deployment",
            "scope": "team_domain",
            "new_sense": {
                "surface": "deployment",
                "scope": "team_domain",
                "definition": "Process of releasing code to production",
                "confidence": 1.0,
                "status": "active",
            },
            "actor": {"actor_id": "user:cli"},
            "update_type": "create",
            "provenance": {"source": "cli_resolve"},
            "timestamp": "2026-02-16T14:00:00+00:00",
        }

        event_file = events_dir / "software-dev.events.jsonl"
        event_file.write_text(json.dumps(event) + "\n")

        result = runner.invoke(glossary_app, ["list"])
        assert result.exit_code == 0
        assert "deployment" in result.stdout
        assert "Total: 1 term(s)" in result.stdout

    def test_list_includes_clarification_resolved_senses(self, tmp_path, monkeypatch):
        """Verify glossary list shows senses from GlossaryClarificationResolved events."""
        monkeypatch.chdir(tmp_path)

        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        event = {
            "event_type": "GlossaryClarificationResolved",
            "conflict_id": "resolved-uuid-1234",
            "term_surface": "pipeline",
            "selected_sense": {
                "surface": "pipeline",
                "scope": "team_domain",
                "definition": "Series of data processing steps",
                "confidence": 0.95,
            },
            "actor": {"actor_id": "user:bob"},
            "resolution_mode": "async",
            "provenance": {"source": "user_clarification"},
            "timestamp": "2026-02-16T14:00:00+00:00",
        }

        event_file = events_dir / "test.events.jsonl"
        event_file.write_text(json.dumps(event) + "\n")

        result = runner.invoke(glossary_app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["surface"] == "pipeline"
        assert data[0]["definition"] == "Series of data processing steps"

    def test_list_merges_seeds_and_events(self, tmp_path, monkeypatch):
        """Verify glossary list combines seed file terms with event log terms."""
        monkeypatch.chdir(tmp_path)

        # Seed file with one term
        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)
        seed = glossaries_dir / "team_domain.yaml"
        seed.write_text(
            "terms:\n"
            "  - surface: workspace\n"
            "    definition: Git worktree directory\n"
            "    confidence: 0.9\n"
            "    status: active\n"
        )

        # Event log with a different term
        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)
        event = {
            "event_type": "GlossarySenseUpdated",
            "term_surface": "deployment",
            "scope": "team_domain",
            "new_sense": {
                "surface": "deployment",
                "scope": "team_domain",
                "definition": "Release to production",
                "confidence": 1.0,
                "status": "active",
            },
            "actor": {"actor_id": "user:cli"},
            "update_type": "create",
            "provenance": {"source": "cli_resolve"},
            "timestamp": "2026-02-16T14:00:00+00:00",
        }
        event_file = events_dir / "test.events.jsonl"
        event_file.write_text(json.dumps(event) + "\n")

        result = runner.invoke(glossary_app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        surfaces = {d["surface"] for d in data}
        assert "workspace" in surfaces  # from seed
        assert "deployment" in surfaces  # from event log


class TestRegressionRealConflictIds:
    """Regression tests for Fix 2: use real UUID conflict_ids from events.

    The code was synthesizing conflict_ids as step_id-term instead of using
    the canonical UUID conflict_ids from GlossaryClarificationRequested and
    GlossaryClarificationResolved events. This caused resolve to never find
    real conflicts.
    """

    def test_conflicts_display_real_uuids(self, mock_event_log, monkeypatch):
        """Verify conflict list shows real UUID conflict_ids, not synthesized ones."""
        monkeypatch.chdir(mock_event_log)

        result = runner.invoke(glossary_app, ["conflicts", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) >= 1

        # The conflict_id must be a real UUID, not step_id-term format
        for conflict in data:
            assert "-" in conflict["conflict_id"]
            # Must NOT be the old synthesized format "test-001-workspace"
            assert not conflict["conflict_id"].startswith("test-001-")

    def test_resolve_finds_conflict_by_uuid(self, mock_event_log_unresolved, monkeypatch):
        """Verify resolve command can find a conflict by its UUID conflict_id."""
        monkeypatch.chdir(mock_event_log_unresolved)

        # Use real UUID from fixture
        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="D\n",
        )

        assert result.exit_code == 0
        assert "workspace" in result.stdout

    def test_resolve_rejects_synthesized_id(self, mock_event_log_unresolved, monkeypatch):
        """Verify resolve command does NOT find conflicts by old synthesized IDs."""
        monkeypatch.chdir(mock_event_log_unresolved)

        # Old synthesized format should not be found
        result = runner.invoke(
            glossary_app,
            ["resolve", "test-002-workspace"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestRegressionSenseUpdatedOnCustomResolve:
    """Regression tests for Fix 3: emit GlossarySenseUpdated for custom definitions.

    When the user provides a custom definition via 'glossary resolve' (choice "C"),
    only GlossaryClarificationResolved was being emitted. The fix adds
    GlossarySenseUpdated emission to match ClarificationMiddleware behavior.
    """

    def test_custom_resolve_emits_both_events(self, mock_event_log_unresolved, monkeypatch):
        """Verify custom resolution emits both Resolved and SenseUpdated events."""
        monkeypatch.chdir(mock_event_log_unresolved)

        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="C\nCustom workspace definition\n",
        )
        assert result.exit_code == 0

        # Read all events
        event_file = mock_event_log_unresolved / ".kittify" / "events" / "glossary" / "software-dev.events.jsonl"
        lines = event_file.read_text().strip().split("\n")
        new_events = [json.loads(line) for line in lines]

        # Find the two new events (last two lines)
        event_types = [e["event_type"] for e in new_events]
        assert "GlossaryClarificationResolved" in event_types
        assert "GlossarySenseUpdated" in event_types

        # Verify SenseUpdated has the custom definition
        sense_events = [e for e in new_events if e["event_type"] == "GlossarySenseUpdated"]
        assert len(sense_events) >= 1
        assert sense_events[-1]["new_sense"]["definition"] == "Custom workspace definition"
        assert sense_events[-1]["term_surface"] == "workspace"

    def test_candidate_resolve_does_not_emit_sense_updated(self, mock_event_log_unresolved, monkeypatch):
        """Verify selecting a candidate (not custom) does NOT emit SenseUpdated."""
        monkeypatch.chdir(mock_event_log_unresolved)

        result = runner.invoke(
            glossary_app,
            ["resolve", UNRESOLVED_WORKSPACE_CID],
            input="1\n",
        )
        assert result.exit_code == 0

        # Read all events
        event_file = mock_event_log_unresolved / ".kittify" / "events" / "glossary" / "software-dev.events.jsonl"
        lines = event_file.read_text().strip().split("\n")
        new_events = [json.loads(line) for line in lines]

        # Only GlossaryClarificationResolved should be added, not SenseUpdated
        sense_events = [e for e in new_events if e["event_type"] == "GlossarySenseUpdated"]
        assert len(sense_events) == 0


# =============================================================================
# Regression tests for deprecated status mapping (cycle 3/3)
# =============================================================================


class TestRegressionDeprecatedStatus:
    """Regression tests for deprecated status coercion bug.

    The old code mapped any status other than "active" to SenseStatus.DRAFT,
    which silently dropped the "deprecated" state.  Terms marked
    status: deprecated in seed files or GlossarySenseUpdated events were
    rendered as "draft", and --status deprecated always returned empty.
    """

    def test_deprecated_seed_term_surfaces_with_status_filter(self, tmp_path, monkeypatch):
        """Verify glossary list --status deprecated shows deprecated seed terms."""
        monkeypatch.chdir(tmp_path)

        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        seed = glossaries_dir / "team_domain.yaml"
        seed.write_text(
            "terms:\n"
            "  - surface: workspace\n"
            "    definition: Git worktree directory\n"
            "    confidence: 0.9\n"
            "    status: active\n"
            "  - surface: legacy-api\n"
            "    definition: Old REST API (superseded by v2)\n"
            "    confidence: 1.0\n"
            "    status: deprecated\n"
        )

        # --status deprecated must return the deprecated term
        result = runner.invoke(glossary_app, ["list", "--status", "deprecated"])
        assert result.exit_code == 0
        assert "legacy-api" in result.stdout
        assert "Total: 1 term(s)" in result.stdout

    def test_deprecated_seed_term_shown_with_correct_status_in_json(self, tmp_path, monkeypatch):
        """Verify JSON output contains status: deprecated, not draft."""
        monkeypatch.chdir(tmp_path)

        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        seed = glossaries_dir / "team_domain.yaml"
        seed.write_text(
            "terms:\n"
            "  - surface: old-tool\n"
            "    definition: Superseded by new-tool\n"
            "    confidence: 0.8\n"
            "    status: deprecated\n"
        )

        result = runner.invoke(glossary_app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["surface"] == "old-tool"
        assert data[0]["status"] == "deprecated"

    def test_deprecated_event_log_term_surfaces(self, tmp_path, monkeypatch):
        """Verify deprecated status from GlossarySenseUpdated events is preserved."""
        monkeypatch.chdir(tmp_path)

        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        events_dir = tmp_path / ".kittify" / "events" / "glossary"
        events_dir.mkdir(parents=True)

        event = {
            "event_type": "GlossarySenseUpdated",
            "term_surface": "retired-term",
            "scope": "team_domain",
            "new_sense": {
                "surface": "retired-term",
                "scope": "team_domain",
                "definition": "No longer in use",
                "confidence": 1.0,
                "status": "deprecated",
            },
            "actor": {"actor_id": "user:admin"},
            "update_type": "deprecate",
            "provenance": {"source": "manual"},
            "timestamp": "2026-02-16T15:00:00+00:00",
        }

        event_file = events_dir / "test.events.jsonl"
        event_file.write_text(json.dumps(event) + "\n")

        result = runner.invoke(glossary_app, ["list", "--status", "deprecated", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["surface"] == "retired-term"
        assert data[0]["status"] == "deprecated"

    def test_deprecated_not_mixed_with_draft(self, tmp_path, monkeypatch):
        """Verify --status draft does NOT return deprecated terms and vice versa."""
        monkeypatch.chdir(tmp_path)

        glossaries_dir = tmp_path / ".kittify" / "glossaries"
        glossaries_dir.mkdir(parents=True)

        seed = glossaries_dir / "team_domain.yaml"
        seed.write_text(
            "terms:\n"
            "  - surface: draft-term\n"
            "    definition: A term still in draft\n"
            "    confidence: 0.5\n"
            "    status: draft\n"
            "  - surface: deprecated-term\n"
            "    definition: A deprecated term\n"
            "    confidence: 1.0\n"
            "    status: deprecated\n"
            "  - surface: active-term\n"
            "    definition: An active term\n"
            "    confidence: 1.0\n"
            "    status: active\n"
        )

        # --status draft returns only draft
        result = runner.invoke(glossary_app, ["list", "--status", "draft", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["surface"] == "draft-term"
        assert data[0]["status"] == "draft"

        # --status deprecated returns only deprecated
        result = runner.invoke(glossary_app, ["list", "--status", "deprecated", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["surface"] == "deprecated-term"
        assert data[0]["status"] == "deprecated"

        # --status active returns only active
        result = runner.invoke(glossary_app, ["list", "--status", "active", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 1
        assert data[0]["surface"] == "active-term"
        assert data[0]["status"] == "active"


def test_resolve_exits_1_when_the_repair_lock_times_out(tmp_path, monkeypatch):
    """A torn-tail repair that cannot take its lock exits 1 with a message, never a raw traceback."""
    import typer

    from kernel.locks import LockAcquireTimeout
    from specify_cli.cli.commands import glossary as glossary_cmd

    def _timeout(event, path):
        raise LockAcquireTimeout(path=str(path) + ".lock")

    monkeypatch.setattr(glossary_cmd, "build_record", lambda event: event)
    monkeypatch.setattr(glossary_cmd, "append_event", _timeout)

    with pytest.raises(typer.Exit) as excinfo:
        glossary_cmd._append_resolution_events([{"event_type": "GlossarySenseUpdated"}], tmp_path / "x.events.jsonl")

    assert excinfo.value.exit_code == 1
