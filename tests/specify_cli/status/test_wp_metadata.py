"""WP03 / FR-005+FR-006: Unit and CI tests for WPMetadata Pydantic model.

T012 — Unit tests for WPMetadata model and validators.
T013 — CI validation test ensuring all kitty-specs WP files pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from specify_cli.status.emit import build_claim_policy_metadata, emit_status_transition
from specify_cli.status.models import AgentAssignment
from specify_cli.status.wp_metadata import WPMetadata, coerce_legacy_dependencies, read_wp_frontmatter

from tests.status.conftest import seed_wp_to_planned

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: walks up to repo kitty-specs/
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]
# ─────────────────────────────────────────────────────────────
# #1753: codebase-wide scope round-trips through the strict parser
# ─────────────────────────────────────────────────────────────


class TestWPMetadataScope:
    """`scope: codebase-wide` must parse (the ownership module reads it)."""

    def test_scope_codebase_wide_accepted(self) -> None:
        meta = WPMetadata(work_package_id="WP04", scope="codebase-wide")
        assert meta.scope == "codebase-wide"

    def test_scope_defaults_to_none(self) -> None:
        assert WPMetadata(work_package_id="WP01").scope is None

    def test_scope_exempts_overlap_via_ownership_manifest(self) -> None:
        """A codebase-wide WP is exempt from owned_files overlap (#1753)."""
        from specify_cli.ownership.models import OwnershipManifest
        from specify_cli.ownership.validation import validate_no_overlap

        wide = OwnershipManifest.from_frontmatter(
            {
                "execution_mode": "code_change",
                "scope": "codebase-wide",
                "owned_files": ["src/**"],
            }
        )
        narrow = OwnershipManifest.from_frontmatter(
            {
                "execution_mode": "code_change",
                "owned_files": ["src/mission_runtime/context.py"],
                "authoritative_surface": "src/mission_runtime/context.py",
            }
        )
        assert validate_no_overlap({"WP04": wide, "WP03": narrow}) == []


# ─────────────────────────────────────────────────────────────
# T012: WPMetadata unit tests
# ─────────────────────────────────────────────────────────────


class TestWPMetadataMinimal:
    """Minimal required fields produce a valid instance."""

    def test_valid_minimal(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="Setup")
        assert meta.work_package_id == "WP01"
        assert meta.title == "Setup"
        assert meta.dependencies == []
        assert meta.base_branch is None
        assert meta.base_commit is None
        assert meta.shell_pid is None

    def test_valid_two_digit_id(self) -> None:
        meta = WPMetadata(work_package_id="WP99", title="Last")
        assert meta.work_package_id == "WP99"

    def test_valid_three_digit_id(self) -> None:
        meta = WPMetadata(work_package_id="WP100", title="Extended")
        assert meta.work_package_id == "WP100"


class TestWPMetadataFull:
    """All fields populated."""

    def test_valid_full(self) -> None:
        meta = WPMetadata(
            work_package_id="WP03",
            title="Full Model Test",
            dependencies=["WP01", "WP02"],
            base_branch="main",
            base_commit="abc1234",
            created_at="2026-04-06T10:00:00Z",
            planning_base_branch="feature/test",
            merge_target_branch="feature/test",
            branch_strategy="standard",
            requirement_refs=["FR-001", "FR-002"],
            execution_mode="code_change",
            owned_files=["src/foo.py"],
            authoritative_surface="src/foo.py",
            subtasks=["T001", "T002"],
            phase="Phase 1",
            assignee="claude",
            agent="claude",
            shell_pid=12345,
            history=[{"at": "2026-01-01", "actor": "system", "action": "created"}],
            mission_id="01ABC",
            wp_code="WP03",
        )
        assert meta.work_package_id == "WP03"
        assert meta.dependencies == ["WP01", "WP02"]
        assert meta.shell_pid == 12345
        assert meta.phase == "Phase 1"
        assert len(meta.history) == 1


class TestWPMetadataRequired:
    """Missing required fields raise ValidationError."""

    def test_missing_work_package_id(self) -> None:
        with pytest.raises(ValidationError, match="work_package_id"):
            WPMetadata(title="No ID")  # type: ignore[call-arg]

    def test_missing_title_defaults_to_none(self) -> None:
        """title is optional — many real WP files omit it."""
        meta = WPMetadata(work_package_id="WP01")
        assert meta.title is None

    def test_title_none_explicit(self) -> None:
        """Explicitly passing title=None is accepted."""
        meta = WPMetadata(work_package_id="WP01", title=None)
        assert meta.title is None


class TestWPMetadataValidators:
    """Field validators enforce patterns and constraints."""

    def test_invalid_wp_id_too_few_digits(self) -> None:
        with pytest.raises(ValidationError, match="work_package_id"):
            WPMetadata(work_package_id="WP1", title="Bad")

    def test_invalid_wp_id_no_digits(self) -> None:
        with pytest.raises(ValidationError, match="work_package_id"):
            WPMetadata(work_package_id="WP", title="Bad")

    def test_invalid_wp_id_lowercase(self) -> None:
        with pytest.raises(ValidationError, match="work_package_id"):
            WPMetadata(work_package_id="wp01", title="Bad")

    def test_empty_title(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            WPMetadata(work_package_id="WP01", title="")

    def test_whitespace_only_title(self) -> None:
        with pytest.raises(ValidationError, match="title"):
            WPMetadata(work_package_id="WP01", title="   ")

    @pytest.mark.fast
    def test_invalid_base_commit(self) -> None:
        with pytest.raises(ValidationError, match="base_commit"):
            WPMetadata(work_package_id="WP01", title="T", base_commit="not-hex")

    def test_valid_base_commit_short(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", base_commit="abc1234")
        assert meta.base_commit == "abc1234"

    def test_valid_base_commit_full(self) -> None:
        sha = "a" * 40
        meta = WPMetadata(work_package_id="WP01", title="T", base_commit=sha)
        assert meta.base_commit == sha

    def test_base_commit_none_is_valid(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", base_commit=None)
        assert meta.base_commit is None

    @pytest.mark.fast
    def test_legacy_unknown_base_commit_is_normalized_to_none(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", base_commit="unknown")
        assert meta.base_commit is None

    def test_invalid_lane_value_raises(self) -> None:
        """Unknown lane string is rejected at construction time."""
        with pytest.raises(ValidationError, match="lane"):
            WPMetadata(work_package_id="WP01", title="T", lane="garbage")

    def test_valid_lane_string_coerced_to_enum(self) -> None:
        """String lane values are coerced to Lane enum members."""
        from specify_cli.status.models import Lane

        meta = WPMetadata(work_package_id="WP01", title="T", lane="in_progress")
        assert meta.lane is Lane.IN_PROGRESS

    def test_lane_enum_value_accepted(self) -> None:
        """Lane enum members are accepted directly."""
        from specify_cli.status.models import Lane

        meta = WPMetadata(work_package_id="WP01", title="T", lane=Lane.FOR_REVIEW)
        assert meta.lane is Lane.FOR_REVIEW

    def test_lane_none_is_valid(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", lane=None)
        assert meta.lane is None

    def test_all_display_lanes_accepted(self) -> None:
        """Every display Lane value is accepted."""
        from specify_cli.status.models import NON_DISPLAY_LANES, Lane

        for lane in Lane:
            if lane in NON_DISPLAY_LANES:
                continue
            meta = WPMetadata(work_package_id="WP01", title="T", lane=lane.value)
            assert meta.lane is lane

    def test_genesis_lane_rejected(self) -> None:
        """Genesis is an event-log seed source, not an authorable WP lane."""
        with pytest.raises(ValidationError, match="Invalid lane value"):
            WPMetadata(work_package_id="WP01", title="T", lane="genesis")

    def test_uninitialized_lane_rejected(self) -> None:
        """Uninitialized is a read sentinel, not an authorable WP lane.

        Mirrors ``test_genesis_lane_rejected``: a WP file must never declare
        ``lane: uninitialized`` in frontmatter — it is only ever produced by
        the lane-reader for a WP with no events.
        """
        with pytest.raises(ValidationError, match="Invalid lane value"):
            WPMetadata(work_package_id="WP01", title="T", lane="uninitialized")


class TestWPMetadataShellPid:
    """shell_pid coercion from string/empty to int/None."""

    def test_string_coercion(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", shell_pid="18377")  # type: ignore[arg-type]
        assert meta.shell_pid == 18377

    def test_empty_string_to_none(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", shell_pid="")  # type: ignore[arg-type]
        assert meta.shell_pid is None

    def test_none_stays_none(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", shell_pid=None)
        assert meta.shell_pid is None

    def test_int_stays_int(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", shell_pid=42)
        assert meta.shell_pid == 42

    def test_large_pid_string(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", shell_pid="2451078")  # type: ignore[arg-type]
        assert meta.shell_pid == 2451078


class TestWPMetadataPhaseCoercion:
    """phase coercion from non-string types."""

    def test_integer_phase(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", phase=1)  # type: ignore[arg-type]
        assert meta.phase == "1"

    def test_string_phase(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", phase="Phase 2")
        assert meta.phase == "Phase 2"

    def test_none_phase(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T", phase=None)
        assert meta.phase is None


class TestWPMetadataExtraFields:
    """extra='forbid' rejects unknown fields; formerly-extra fields are declared."""

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            WPMetadata(
                work_package_id="WP01",
                title="T",
                custom_field="value",  # type: ignore[call-arg]
            )

    def test_lane_as_declared_field(self) -> None:
        """'lane' is now a declared optional field."""
        meta = WPMetadata(
            work_package_id="WP01",
            title="T",
            lane="planned",
        )
        assert meta.lane == "planned"

    def test_task_type_as_declared_field(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            title="T",
            task_type="implement",
        )
        assert meta.task_type == "implement"

    def test_agent_profile_as_declared_field(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            title="T",
            agent_profile="python-implementer",
        )
        assert meta.agent_profile == "python-implementer"


class TestLenientReaderToleratesLegacyFields:
    """FR-011 (#3406): historical import must tolerate retired frontmatter keys.

    The strict authoring reader rejects unknown fields (typo guard); the lenient
    reader used by the import path drops them but still validates known fields.
    """

    _LEGACY_WP = (
        "---\n"
        "work_package_id: WP07\n"
        "title: Legacy Work Package\n"
        "dependencies: [WP06]\n"
        "estimated_lines: 240\n"  # retired field, not on the current schema
        "some_other_dead_key: whatever\n"
        "---\n\nBody\n"
    )

    def test_strict_reader_rejects_legacy_field(self, tmp_path: Path) -> None:
        from specify_cli.status.wp_metadata import read_authored_wp_frontmatter

        wp_file = tmp_path / "WP07-legacy.md"
        wp_file.write_text(self._LEGACY_WP, encoding="utf-8")
        with pytest.raises(ValidationError, match="extra_forbidden"):
            read_authored_wp_frontmatter(wp_file)

    def test_lenient_reader_drops_legacy_field_and_preserves_known(self, tmp_path: Path) -> None:
        from specify_cli.status.wp_metadata import read_authored_wp_frontmatter_lenient

        wp_file = tmp_path / "WP07-legacy.md"
        wp_file.write_text(self._LEGACY_WP, encoding="utf-8")

        meta, body = read_authored_wp_frontmatter_lenient(wp_file)

        assert meta.work_package_id == "WP07"
        assert meta.display_title == "Legacy Work Package"
        assert meta.dependencies == ["WP06"]
        assert body.strip() == "Body"
        # The dropped key does not become an attribute (frozen model, extra keys gone).
        assert not hasattr(meta, "estimated_lines")

    def test_lenient_reader_still_raises_on_invalid_known_field(self, tmp_path: Path) -> None:
        """Tolerance covers unknown keys only -- a bad value for a known field
        (here an id that violates the WP## pattern) still fails loudly, so the
        import scan's malformed-skip path is unchanged for real corruption."""
        from specify_cli.status.wp_metadata import read_authored_wp_frontmatter_lenient

        wp_file = tmp_path / "WPbad.md"
        wp_file.write_text(
            "---\nwork_package_id: not-a-wp-id\ntitle: T\nestimated_lines: 5\n---\n\nBody\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError):
            read_authored_wp_frontmatter_lenient(wp_file)


class TestWPMetadataDisplayTitle:
    """display_title property: safe title with fallback to work_package_id."""

    def test_returns_title_when_set(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="Setup Infrastructure")
        assert meta.display_title == "Setup Infrastructure"

    def test_falls_back_to_wp_id_when_title_is_none(self) -> None:
        meta = WPMetadata(work_package_id="WP03")
        assert meta.display_title == "WP03"

    def test_falls_back_to_wp_id_when_title_is_explicit_none(self) -> None:
        meta = WPMetadata(work_package_id="WP05", title=None)
        assert meta.display_title == "WP05"

    def test_strips_whitespace_from_title(self) -> None:
        meta = WPMetadata(work_package_id="WP02", title="  Padded Title  ")
        assert meta.display_title == "Padded Title"


class TestWPMetadataResolvedAgent:
    """Characterization coverage for legacy resolved_agent input shapes."""

    def test_resolved_agent_when_already_agent_assignment(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            agent=AgentAssignment(tool="claude", model="sonnet"),
        )

        result = meta.resolved_agent()

        assert result.tool == "claude"
        assert result.model == "sonnet"

    def test_resolved_agent_when_string(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            agent="claude",
            model="opus",
        )

        result = meta.resolved_agent()

        assert result.tool == "claude"
        assert result.model == "opus"

    def test_resolved_agent_when_dict(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            agent={"tool": "cursor", "model": "gpt-4o", "profile_id": "arch"},
        )

        result = meta.resolved_agent()

        assert result.tool == "cursor"
        assert result.model == "gpt-4o"
        assert result.profile_id == "arch"

    def test_resolved_agent_when_none_uses_fallbacks(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            agent=None,
            model="haiku",
            agent_profile="architect",
            role="reviewer",
        )

        result = meta.resolved_agent()

        assert result.tool == "unknown"
        assert result.model == "haiku"
        assert result.profile_id == "architect"
        assert result.role == "reviewer"

    def test_resolved_agent_when_empty_dict_uses_fallbacks(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            agent={},
            model="haiku",
            agent_profile="architect",
            role="reviewer",
        )

        result = meta.resolved_agent()

        assert result.tool == "unknown"
        assert result.model == "haiku"
        assert result.profile_id == "architect"
        assert result.role == "reviewer"

    def test_resolved_agent_when_empty_string_uses_fallbacks(self) -> None:
        meta = WPMetadata(
            work_package_id="WP01",
            agent="",
            model="haiku",
            agent_profile="architect",
            role="reviewer",
        )

        result = meta.resolved_agent()

        assert result.tool == "unknown"
        assert result.model == "haiku"
        assert result.profile_id == "architect"
        assert result.role == "reviewer"


class TestWPMetadataFrozen:
    """Model is immutable."""

    def test_frozen_rejects_assignment(self) -> None:
        meta = WPMetadata(work_package_id="WP01", title="T")
        with pytest.raises(ValidationError):
            meta.title = "Changed"


class TestWPMetadataLegacyNormalization:
    """Model-level pre-processing for legacy field names and types."""

    def test_work_package_title_fallback(self) -> None:
        """Legacy 'work_package_title' is used when 'title' is absent."""
        meta = WPMetadata.model_validate(
            {
                "work_package_id": "WP01",
                "work_package_title": "Foundation Layer",
            }
        )
        assert meta.title == "Foundation Layer"

    def test_title_takes_precedence(self) -> None:
        """When both 'title' and 'work_package_title' exist, 'title' wins."""
        meta = WPMetadata.model_validate(
            {
                "work_package_id": "WP01",
                "title": "Preferred",
                "work_package_title": "Fallback",
            }
        )
        assert meta.title == "Preferred"

    def test_dependencies_string_empty_list(self) -> None:
        """Dependencies stored as string '[]' are parsed to empty list."""
        meta = WPMetadata.model_validate(
            {
                "work_package_id": "WP01",
                "title": "T",
                "dependencies": "[]",
            }
        )
        assert meta.dependencies == []

    def test_dependencies_string_csv(self) -> None:
        """Dependencies as comma-separated string are parsed to list."""
        meta = WPMetadata.model_validate(
            {
                "work_package_id": "WP01",
                "title": "T",
                "dependencies": "WP01, WP02",
            }
        )
        assert meta.dependencies == ["WP01", "WP02"]

    def test_dependencies_bare_scalar(self) -> None:
        """A bare scalar ``dependencies: WP01`` is a one-element list."""
        meta = WPMetadata.model_validate({"work_package_id": "WP01", "title": "T", "dependencies": "WP01"})
        assert meta.dependencies == ["WP01"]


class TestRequirementRefsScalarCoercion:
    """T005 / FR-001: legacy scalar ``requirement_refs`` is now tokenised
    through the single grammar authority (``grammar.tokenize_refs``)."""

    def test_comma_scalar_is_unchanged(self) -> None:
        """A comma-separated scalar splits the same way as before WP01."""
        meta = WPMetadata.model_validate({"work_package_id": "WP01", "title": "T", "requirement_refs": "FR-001, FR-002"})
        assert meta.requirement_refs == ["FR-001", "FR-002"]

    def test_whitespace_scalar_now_splits(self) -> None:
        """The new behaviour (FR-001): a whitespace-only-separated scalar now
        splits into two items where it used to stay one."""
        meta = WPMetadata.model_validate({"work_package_id": "WP01", "title": "T", "requirement_refs": "FR-001 FR-002"})
        assert meta.requirement_refs == ["FR-001", "FR-002"]

    def test_list_input_is_left_untouched(self) -> None:
        """A list input never goes through the scalar-coercion branch."""
        meta = WPMetadata.model_validate({"work_package_id": "WP01", "title": "T", "requirement_refs": ["FR-001", "FR-002"]})
        assert meta.requirement_refs == ["FR-001", "FR-002"]


class TestCoerceLegacyDependencies:
    """The shared pure coercion behind ``WPMetadata`` and the FSM shells (single parser, FR-014)."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("[]", []),
            ("  []  ", []),
            ("WP01, WP02", ["WP01", "WP02"]),
            ("WP01", ["WP01"]),
            ("  WP03 ,WP04 , ", ["WP03", "WP04"]),
            ("", []),
        ],
    )
    def test_string_forms(self, raw: str, expected: list[str]) -> None:
        assert coerce_legacy_dependencies(raw) == expected

    @pytest.mark.parametrize("raw", [None, [], ["WP01"], [1, 2], 3, {"a": 1}])
    def test_non_strings_pass_through_unchanged(self, raw: object) -> None:
        assert coerce_legacy_dependencies(raw) is raw

    @pytest.mark.parametrize("raw", ["[]", "WP01, WP02", "WP01"])
    def test_model_uses_the_same_coercion(self, raw: str) -> None:
        meta = WPMetadata.model_validate({"work_package_id": "WP01", "title": "T", "dependencies": raw})
        assert meta.dependencies == coerce_legacy_dependencies(raw)


class TestWPMetadataRoundTrip:
    """NFR-004: Round-trip safe serialization."""

    def test_model_dump_preserves_values(self) -> None:
        data = {
            "work_package_id": "WP01",
            "title": "Setup",
            "dependencies": ["WP02"],
            "phase": "Phase 1",
            "shell_pid": 123,
        }
        meta = WPMetadata.model_validate(data)
        dumped = meta.model_dump()
        assert dumped["work_package_id"] == "WP01"
        assert dumped["title"] == "Setup"
        assert dumped["dependencies"] == ["WP02"]
        assert dumped["phase"] == "Phase 1"
        assert dumped["shell_pid"] == 123

    def test_model_dump_preserves_extra(self) -> None:
        meta = WPMetadata.model_validate(
            {
                "work_package_id": "WP01",
                "title": "T",
                "lane": "planned",
                "task_type": "implement",
            }
        )
        dumped = meta.model_dump()
        assert dumped["lane"] == "planned"
        assert dumped["task_type"] == "implement"


# ─────────────────────────────────────────────────────────────
# T010: read_wp_frontmatter() tests
# ─────────────────────────────────────────────────────────────


class TestReadWpFrontmatter:
    """Tests for the read_wp_frontmatter() convenience loader."""

    def test_valid_wp_file(self, tmp_path: Path) -> None:
        wp_file = tmp_path / "WP01-setup.md"
        wp_file.write_text(
            "---\nwork_package_id: WP01\ntitle: Setup Task\ndependencies: []\n---\n\n# Body\n\nSome content.\n",
            encoding="utf-8",
        )
        meta, body = read_wp_frontmatter(wp_file)
        assert meta.work_package_id == "WP01"
        assert meta.title == "Setup Task"
        assert "Body" in body

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        wp_file = tmp_path / "WP99-bad.md"
        wp_file.write_text(
            "---\ntitle: No ID\n---\n\nBody\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="work_package_id"):
            read_wp_frontmatter(wp_file)

    def test_shell_pid_is_snapshot_sourced_not_frontmatter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Post-cutover (#2816/IC-04, WP04): ``read_wp_frontmatter`` resolves the
        runtime ``shell_pid`` from the reduced event-sourced snapshot, NOT from the
        WP file frontmatter (the retired dual-write, NFR-003 byte-stability).

        Reconciled from the pre-cutover ``test_shell_pid_string_in_file`` (which
        asserted the now-retired frontmatter-read path). A STALE frontmatter
        ``shell_pid: "111"`` is deliberately present and must be IGNORED; the
        snapshot value is surfaced instead (and the ``coerce_shell_pid``
        string->int coercion still applies on the snapshot path). Not weakened:
        this asserts the true snapshot-authority end-state, and that a divergent
        frontmatter value does not leak through.
        """
        # Keep the claim transition local — no SaaS fan-out / dossier sync.
        import specify_cli.status.emit as status_emit

        monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None, raising=False)
        feature_dir = tmp_path / "kitty-specs" / "pid-snapshot"
        (feature_dir / "tasks").mkdir(parents=True)
        (feature_dir / "meta.json").write_text('{"status_phase": 0}', encoding="utf-8")
        wp_file = feature_dir / "tasks" / "WP01.md"
        wp_file.write_text(
            '---\nwork_package_id: WP01\ntitle: PID Test\nshell_pid: "111"\n---\n\nBody\n',
            encoding="utf-8",
        )

        seed_wp_to_planned(feature_dir, "WP01", slug="pid-snapshot")
        emit_status_transition(
            feature_dir=feature_dir,
            mission_slug="pid-snapshot",
            wp_id="WP01",
            to_lane="claimed",
            actor="claude",
            policy_metadata=build_claim_policy_metadata(405597, "2026-07-20T00:00:00Z", "claude"),
        )

        meta, _ = read_wp_frontmatter(wp_file)
        # Snapshot-sourced (string->int coerced), NEVER the stale frontmatter 111.
        assert meta.shell_pid == 405597

    def test_legacy_unknown_base_commit_in_file_is_normalized(self, tmp_path: Path) -> None:
        wp_file = tmp_path / "WP01-legacy-base.md"
        wp_file.write_text(
            "---\nwork_package_id: WP01\ntitle: Legacy Base\nbase_commit: unknown\n---\n\nBody\n",
            encoding="utf-8",
        )
        meta, _ = read_wp_frontmatter(wp_file)
        assert meta.base_commit is None

    def test_extra_fields_in_file(self, tmp_path: Path) -> None:
        """Fields formerly stored as extras are now declared on the model."""
        wp_file = tmp_path / "WP01-extra.md"
        wp_file.write_text(
            "---\nwork_package_id: WP01\ntitle: Extra\nlane: planned\nagent_profile: python-implementer\n---\n\nBody\n",
            encoding="utf-8",
        )
        meta, _ = read_wp_frontmatter(wp_file)
        assert meta.lane == "planned"
        assert meta.agent_profile == "python-implementer"


# ─────────────────────────────────────────────────────────────
# T013: CI validation — all kitty-specs WP files must validate
# ─────────────────────────────────────────────────────────────


class TestCIValidation:
    """SC-004 / C-003: All active WP files pass WPMetadata.model_validate()."""

    @staticmethod
    def _find_kitty_specs_root() -> Path | None:
        """Walk up from cwd to find the kitty-specs directory."""
        cwd = Path.cwd()
        for candidate in [cwd, *cwd.parents]:
            ks = candidate / "kitty-specs"
            if ks.is_dir():
                return ks
        return None

    def test_all_kitty_specs_wp_files_validate(self) -> None:
        """All active WP files pass WPMetadata.model_validate().

        Files with broken YAML (e.g. unresolved merge conflicts) are
        reported separately — they indicate a repo hygiene issue, not a
        model defect.
        """
        ks_root = self._find_kitty_specs_root()
        if ks_root is None:
            pytest.skip("kitty-specs/ not found — likely running outside repo root")

        wp_files = sorted(ks_root.glob("*/tasks/WP*.md"))
        assert len(wp_files) > 0, "No WP files found in kitty-specs/"

        validation_failures: list[str] = []
        yaml_errors: list[str] = []

        for wp_file in wp_files:
            try:
                read_wp_frontmatter(wp_file)
            except ValidationError as e:
                validation_failures.append(f"{wp_file.relative_to(ks_root.parent)}: {e}")
            except Exception as e:
                # FrontmatterError (broken YAML, merge conflicts, etc.)
                yaml_errors.append(f"{wp_file.relative_to(ks_root.parent)}: {e}")

        msg_parts = []
        if validation_failures:
            msg_parts.append(f"{len(validation_failures)} WP file(s) failed model validation:\n" + "\n".join(validation_failures))
        if yaml_errors:
            msg_parts.append(f"{len(yaml_errors)} WP file(s) have broken YAML (merge conflicts?):\n" + "\n".join(yaml_errors))

        # Validation errors are hard failures; YAML errors are warnings
        assert not validation_failures, "\n\n".join(msg_parts)


# ─────────────────────────────────────────────────────────────
# T-update: WPMetadata.update() — immutable field mutation
# ─────────────────────────────────────────────────────────────


class TestWPMetadataUpdate:
    """update() returns a NEW WPMetadata with specified fields changed."""

    def _make_base(self, **overrides: Any) -> WPMetadata:
        defaults = {"work_package_id": "WP01", "title": "Base"}
        return WPMetadata.model_validate({**defaults, **overrides})

    # -- basic single-field update --

    def test_update_single_field(self) -> None:
        base = self._make_base(lane="planned")
        updated = base.update(lane="in_progress")
        assert updated.lane == "in_progress"
        assert updated is not base

    def test_update_preserves_unchanged_fields(self) -> None:
        base = self._make_base(lane="planned", agent="claude", title="Original")
        updated = base.update(lane="in_progress")
        assert updated.title == "Original"
        assert updated.agent == "claude"
        assert updated.work_package_id == "WP01"

    # -- multi-field update --

    def test_update_multiple_fields(self) -> None:
        base = self._make_base()
        updated = base.update(lane="in_progress", agent="gemini", phase="Phase 2")
        assert updated.lane == "in_progress"
        assert updated.agent == "gemini"
        assert updated.phase == "Phase 2"

    # -- list field replacement --

    def test_update_replaces_list_field(self) -> None:
        base = self._make_base(dependencies=["WP02"])
        updated = base.update(dependencies=["WP02", "WP03"])
        assert updated.dependencies == ["WP02", "WP03"]
        assert base.dependencies == ["WP02"]  # original unchanged

    # -- None fields --

    def test_update_can_set_field_to_none(self) -> None:
        base = self._make_base(agent="claude")
        updated = base.update(agent=None)
        assert updated.agent is None

    # -- immutability contract --

    def test_update_does_not_mutate_original(self) -> None:
        base = self._make_base(lane="planned", dependencies=["WP02"])
        _ = base.update(lane="in_progress", dependencies=["WP03"])
        assert base.lane == "planned"
        assert base.dependencies == ["WP02"]

    def test_original_stays_frozen_after_update(self) -> None:
        base = self._make_base()
        _ = base.update(lane="in_progress")
        with pytest.raises(ValidationError):
            base.title = "Mutated"

    # -- validation still fires --

    def test_update_validates_fields(self) -> None:
        base = self._make_base()
        with pytest.raises(ValidationError, match="title"):
            base.update(title="")

    def test_update_validates_base_commit(self) -> None:
        base = self._make_base()
        with pytest.raises(ValidationError, match="base_commit"):
            base.update(base_commit="not-hex")

    # -- rejects unknown fields --

    def test_update_rejects_unknown_field(self) -> None:
        base = self._make_base()
        with pytest.raises(TypeError, match="unknown_field"):
            base.update(unknown_field="bad")

    # -- no-op update returns equal (but new) instance --

    def test_update_no_args_returns_equal_copy(self) -> None:
        base = self._make_base(lane="planned")
        updated = base.update()
        assert updated == base
        assert updated is not base

    # -- chaining --

    def test_chained_updates(self) -> None:
        base = self._make_base()
        result = base.update(lane="planned").update(lane="in_progress").update(agent="claude")
        assert result.lane == "in_progress"
        assert result.agent == "claude"


# ─────────────────────────────────────────────────────────────
# T-builder: WPMetadata.builder() — fluent multi-step composition
# ─────────────────────────────────────────────────────────────


class TestWPMetadataBuilder:
    """builder() returns a _Builder for fluent multi-step field composition."""

    def _make_base(self, **overrides: Any) -> WPMetadata:
        defaults = {"work_package_id": "WP01", "title": "Base"}
        return WPMetadata.model_validate({**defaults, **overrides})

    # -- basic builder flow --

    def test_builder_set_and_build(self) -> None:
        base = self._make_base(lane="planned")
        result = base.builder().set(lane="in_progress").build()
        assert result.lane == "in_progress"
        assert result is not base

    def test_builder_multiple_set_calls(self) -> None:
        base = self._make_base()
        result = base.builder().set(lane="in_progress").set(agent="claude").set(phase="Phase 1").build()
        assert result.lane == "in_progress"
        assert result.agent == "claude"
        assert result.phase == "Phase 1"

    def test_builder_last_set_wins(self) -> None:
        base = self._make_base()
        result = base.builder().set(lane="planned").set(lane="in_progress").build()
        assert result.lane == "in_progress"

    # -- append_to_history --

    def test_builder_append_to_history(self) -> None:
        entry1 = {"at": "2026-01-01", "actor": "system", "action": "created"}
        base = self._make_base(history=[entry1])
        entry2 = {"at": "2026-01-02", "actor": "claude", "action": "started"}
        result = base.builder().append_to_history(entry2).build()
        assert len(result.history) == 2
        assert result.history[0] == entry1
        assert result.history[1] == entry2

    def test_builder_append_to_history_on_empty(self) -> None:
        base = self._make_base()
        entry = {"at": "2026-01-01", "actor": "system", "action": "created"}
        result = base.builder().append_to_history(entry).build()
        assert result.history == [entry]

    def test_builder_append_does_not_mutate_original(self) -> None:
        entry1 = {"at": "2026-01-01", "actor": "system", "action": "created"}
        base = self._make_base(history=[entry1])
        entry2 = {"at": "2026-01-02", "actor": "claude", "action": "started"}
        _ = base.builder().append_to_history(entry2).build()
        assert len(base.history) == 1

    # -- append_dependency --

    def test_builder_append_dependency(self) -> None:
        base = self._make_base(dependencies=["WP02"])
        result = base.builder().append_dependency("WP03").build()
        assert result.dependencies == ["WP02", "WP03"]
        assert base.dependencies == ["WP02"]

    def test_builder_append_dependency_on_empty(self) -> None:
        base = self._make_base()
        result = base.builder().append_dependency("WP02").build()
        assert result.dependencies == ["WP02"]

    # -- combined set + append --

    def test_builder_set_and_append_combined(self) -> None:
        base = self._make_base(lane="planned")
        entry = {"at": "2026-01-01", "actor": "claude", "action": "claimed"}
        result = base.builder().set(lane="in_progress").set(agent="claude").append_to_history(entry).build()
        assert result.lane == "in_progress"
        assert result.agent == "claude"
        assert len(result.history) == 1

    # -- validation fires on build --

    def test_builder_validates_on_build(self) -> None:
        base = self._make_base()
        with pytest.raises(ValidationError, match="title"):
            base.builder().set(title="").build()

    # -- rejects unknown fields in set --

    def test_builder_set_rejects_unknown_field(self) -> None:
        base = self._make_base()
        with pytest.raises(TypeError, match="bogus"):
            base.builder().set(bogus="bad")

    # -- builder does not modify source --

    def test_builder_does_not_modify_source(self) -> None:
        base = self._make_base(lane="planned")
        builder = base.builder()
        builder.set(lane="in_progress")
        # Before build(), base is still unchanged
        assert base.lane == "planned"

    # -- build can be called multiple times for different results --

    def test_builder_reusable_across_builds(self) -> None:
        base = self._make_base(lane="planned")
        builder = base.builder().set(agent="claude")
        r1 = builder.build()
        r2 = builder.set(lane="in_progress").build()
        assert r1.lane == "planned"
        assert r1.agent == "claude"
        assert r2.lane == "in_progress"
        assert r2.agent == "claude"
