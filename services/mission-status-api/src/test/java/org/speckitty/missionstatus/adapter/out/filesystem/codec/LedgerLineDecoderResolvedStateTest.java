package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpResolved;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;

/**
 * FR-020 end to end, from ledger bytes to the resolved state: every ledger below was written by hand and its expected text was produced by
 * the Python oracle code itself (spec-kitty-events 10.4.4 {@code reduce}, {@code reconstruct_wp_view}, {@code materialize_snapshot} and the
 * oracle's {@code _review_result}, {@code review_override}, {@code history_entries} and {@code _lifecycle_types}; one line per work package,
 * {@code -} for null). The Java side prints the same canonical text from the {@link StatusSnapshot}, so a difference of one member of one
 * work package fails a case. Cases the oracle serves that Java deliberately does not (a float scalar, a list or object in an override
 * member) are not here: they are the recorded knownDivergence candidates, pinned in {@code LedgerLineDecoderDivergencesTest}.
 */
class LedgerLineDecoderResolvedStateTest {

  private static final String BINDING_LEDGER =
      """
      {"event_id": "E01", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-01T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "claude", "shell_pid": 7}}
      {"event_id": "E02", "wp_id": "WP01", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-01T10:10:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree"}
      {"event_id": "E03", "wp_id": "WP01", "from_lane": "in_progress", "to_lane": "for_review", "at": "2026-09-01T10:20:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree"}
      {"event_id": "E04", "wp_id": "WP01", "from_lane": "for_review", "to_lane": "in_review", "at": "2026-09-01T10:25:00+00:00", "actor": "rev", "force": false, "execution_mode": "worktree"}
      {"event_id": "E05", "wp_id": "WP01", "from_lane": "in_review", "to_lane": "approved", "at": "2026-09-01T10:30:00+00:00", "actor": "rev", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "rev", "verdict": "approved", "reference": "cycle-1"}}
      {"event_id": "E06", "wp_id": "WP01", "from_lane": "approved", "to_lane": "done", "at": "2026-09-01T10:40:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "01HA0000000000000000000001", "kind": "annotation", "wp_id": "WP01", "at": "2026-09-01T10:35:00+00:00", "actor": "claude", "delta": {"subtasks": {"T2": "done", "T3": "blocked"}, "review": {"at": "2026-09-01T10:35:00+00:00", "actor": "arbiter", "wp_id": "WP01", "reason": "ok"}}}
      {"event_id": "01HA0000000000000000000002", "kind": "annotation", "wp_id": "WP01", "at": "2026-09-01T10:05:00+00:00", "actor": "claude", "delta": {"role": "implementer", "agent_profile": "java-jenny", "agent_profile_version": "1", "model": "__resolved_model_absent__", "provider": "anthropic"}}
      {"event_id": "01HA0000000000000000000003", "kind": "annotation", "wp_id": "WP01", "at": "2026-09-01T10:15:00+00:00", "actor": "claude", "delta": {"model": "sonnet", "assignee": "carol", "subtasks": {"T1": "done", "T2": "planned"}}}
      {"event_id": "E11", "wp_id": "WP02", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-01T11:00:00+00:00", "actor": "dave", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "dev"}}
      {"event_id": "01HA0000000000000000000004", "kind": "annotation", "wp_id": "WP02", "at": "2026-09-01T11:05:00+00:00", "actor": "claude", "delta": {"release_runtime_claim": true, "assignee": "keep"}}
      {"event_id": "01HA0000000000000000000005", "kind": "annotation", "wp_id": "WP02", "at": "2026-09-01T11:10:00+00:00", "actor": "claude", "delta": {"release_runtime_claim": true, "agent": "dev2"}}
      {"event_id": "01HA0000000000000000000006", "kind": "annotation", "wp_id": "WP02", "at": "2026-09-01T11:20:00+00:00", "actor": "claude", "delta": {"review": {"at": "", "actor": "x", "wp_id": "WP02", "reason": ""}}}
      {"event_id": "01HA0000000000000000000007", "kind": "annotation", "wp_id": "WP03", "at": "2026-09-01T12:30:00+00:00", "actor": "ann-2", "delta": {"role": "r"}}
      {"event_id": "01HA0000000000000000000008", "kind": "annotation", "wp_id": "WP03", "at": "2026-09-01T12:00:00+00:00", "actor": "ann-1", "delta": {"assignee": "zed", "subtasks": {"S": "done"}}}
      {"event_id": "E21", "wp_id": "WP04", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-01T13:00:00+00:00", "actor": "eve", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "gone"}}
      {"event_id": "01HA0000000000000000000009", "kind": "annotation", "wp_id": "WP04", "at": "2026-09-01T13:10:00+00:00", "actor": "claude", "delta": {"model": "sonnet", "review": {"at": "x", "actor": "y", "wp_id": "WP04", "reason": "z"}}}
      {"event_id": "01HA0000000000000000000010", "kind": "annotation", "wp_id": "WP04", "at": "2026-09-01T13:20:00+00:00", "actor": "claude", "delta": {"model": "__resolved_model_absent__", "review": {"at": "", "actor": "", "wp_id": "", "reason": ""}}}
      """;

  private static final String BINDING_EXPECTED =
      """
      WP01|agent=claude|assignee=carol|role=implementer|profile=java-jenny|version=1|model=sonnet|provider=anthropic|actor=alice|subtasks=T1:done,T2:done,T3:blocked|result=rev;approved;cycle-1|override=c=1,at=2026-09-01T10:35:00+00:00,actor=arbiter,reason=ok|history=E01,2026-09-01T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-;E02,2026-09-01T10:10:00+00:00,claimed,in_progress,bob/-/-,0,-,-;E03,2026-09-01T10:20:00+00:00,in_progress,for_review,bob/-/-,0,-,-;E04,2026-09-01T10:25:00+00:00,for_review,in_review,rev/-/-,0,-,-;E05,2026-09-01T10:30:00+00:00,in_review,approved,rev/-/-,0,-,approved;E06,2026-09-01T10:40:00+00:00,approved,done,alice/-/-,0,-,-
      WP02|agent=dev2|assignee=keep|role=-|profile=-|version=-|model=-|provider=-|actor=dave|subtasks=-|result=-|override=c=0,at=-,actor=x,reason=-|history=E11,2026-09-01T11:00:00+00:00,planned,claimed,dave/-/-,0,-,-
      WP03|agent=-|assignee=zed|role=r|profile=-|version=-|model=-|provider=-|actor=ann-1|subtasks=S:done|result=-|override=-|history=-
      WP04|agent=gone|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=eve|subtasks=-|result=-|override=-|history=E21,2026-09-01T13:00:00+00:00,planned,claimed,eve/-/-,0,-,-
      types=
      """;

  private static final String REVIEWS_LEDGER =
      """
      {"event_id": "F01", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-02T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F02", "wp_id": "WP01", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-02T10:10:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F03", "wp_id": "WP01", "from_lane": "in_progress", "to_lane": "approved", "at": "2026-09-02T10:20:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "r", "verdict": "approved", "reference": "x"}}
      {"event_id": "F04", "wp_id": "WP01", "from_lane": "approved", "to_lane": "done", "at": "2026-09-02T10:30:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "review_result": {}}
      {"event_id": "F11", "wp_id": "WP02", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-02T11:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F12", "wp_id": "WP02", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-02T11:10:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F13", "wp_id": "WP02", "from_lane": "in_progress", "to_lane": "for_review", "at": "2026-09-02T11:20:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F14", "wp_id": "WP02", "from_lane": "for_review", "to_lane": "in_review", "at": "2026-09-02T11:30:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "r2", "verdict": "changes_requested", "reference": "feedback://y", "feedback_path": "/x"}}
      {"event_id": "F15", "wp_id": "WP02", "from_lane": "in_review", "to_lane": "approved", "at": "2026-09-02T11:40:00+00:00", "actor": "alice", "force": true, "execution_mode": "worktree"}
      {"event_id": "F21", "wp_id": "WP03", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-02T12:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F22", "wp_id": "WP03", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-02T12:10:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F23", "wp_id": "WP03", "from_lane": "in_progress", "to_lane": "for_review", "at": "2026-09-02T12:20:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F24", "wp_id": "WP03", "from_lane": "for_review", "to_lane": "in_review", "at": "2026-09-02T12:30:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F25", "wp_id": "WP03", "from_lane": "in_review", "to_lane": "planned", "at": "2026-09-02T12:40:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "r3", "verdict": "changes_requested", "reference": null}}
      {"event_id": "F26", "wp_id": "WP03", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-02T12:50:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F31", "wp_id": "WP04", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-02T13:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F41", "wp_id": "WP05", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-02T14:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "F42", "wp_id": "WP05", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-02T14:10:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": 5, "verdict": "approved", "reference": 7}}
      """;

  private static final String REVIEWS_EXPECTED =
      """
      WP01|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=r;approved;x|override=-|history=F01,2026-09-02T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-;F02,2026-09-02T10:10:00+00:00,claimed,in_progress,alice/-/-,0,-,-;F03,2026-09-02T10:20:00+00:00,in_progress,approved,alice/-/-,0,-,approved;F04,2026-09-02T10:30:00+00:00,approved,done,alice/-/-,0,-,-
      WP02|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=F11,2026-09-02T11:00:00+00:00,planned,claimed,alice/-/-,0,-,-;F12,2026-09-02T11:10:00+00:00,claimed,in_progress,alice/-/-,0,-,-;F13,2026-09-02T11:20:00+00:00,in_progress,for_review,alice/-/-,0,-,-;F14,2026-09-02T11:30:00+00:00,for_review,in_review,alice/-/-,0,-,changes_requested;F15,2026-09-02T11:40:00+00:00,in_review,approved,alice/-/-,1,-,-
      WP03|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=r3;changes_requested;|override=-|history=F21,2026-09-02T12:00:00+00:00,planned,claimed,alice/-/-,0,-,-;F22,2026-09-02T12:10:00+00:00,claimed,in_progress,alice/-/-,0,-,-;F23,2026-09-02T12:20:00+00:00,in_progress,for_review,alice/-/-,0,-,-;F24,2026-09-02T12:30:00+00:00,for_review,in_review,alice/-/-,0,-,-;F25,2026-09-02T12:40:00+00:00,in_review,planned,alice/-/-,0,-,changes_requested;F26,2026-09-02T12:50:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP04|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=F31,2026-09-02T13:00:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP05|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-;approved;7|override=-|history=F41,2026-09-02T14:00:00+00:00,planned,claimed,alice/-/-,0,-,-;F42,2026-09-02T14:10:00+00:00,claimed,in_progress,alice/-/-,0,-,approved
      types=
      """;

  private static final String SEED_LEDGER =
      """
      {"event_id": "G01", "wp_id": "WP01", "from_lane": "planned", "to_lane": "blocked", "at": "2026-09-03T10:00:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree"}
      {"event_id": "G02", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-03T10:30:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "seed-agent"}}
      {"event_id": "G11", "wp_id": "WP02", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-03T11:00:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "real-agent"}}
      {"event_id": "G12", "wp_id": "WP02", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-03T11:30:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "seed2"}}
      {"event_id": "G21", "wp_id": "WP03", "from_lane": "planned", "to_lane": "blocked", "at": "2026-09-03T12:00:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree"}
      {"event_id": "G22", "wp_id": "WP03", "from_lane": "in_review", "to_lane": "approved", "at": "2026-09-03T12:30:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "seed-rev", "verdict": "approved", "reference": "s"}}
      {"event_id": "G31", "wp_id": "WP04", "from_lane": "planned", "to_lane": "blocked", "at": "2026-09-03T13:00:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree"}
      {"event_id": "G32", "wp_id": "WP04", "from_lane": "in_review", "to_lane": "approved", "at": "2026-09-03T13:30:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree"}
      {"event_id": "G41", "wp_id": "WP05", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-03T14:00:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "s5"}}
      {"event_id": "G42", "wp_id": "WP05", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-03T14:30:00+00:00", "actor": "carol", "force": false, "execution_mode": "worktree"}
      {"event_id": "G51", "wp_id": "WP06", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-03T15:00:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": "real6"}}
      {"event_id": "G52", "wp_id": "WP06", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-03T15:10:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree"}
      {"event_id": "G53", "wp_id": "WP06", "from_lane": "in_review", "to_lane": "approved", "at": "2026-09-03T15:20:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "late", "verdict": "approved", "reference": "r"}}
      {"event_id": "G61", "wp_id": "WP07", "from_lane": "planned", "to_lane": "blocked", "at": "2026-09-03T16:00:00+00:00", "actor": "bob", "force": false, "execution_mode": "worktree"}
      {"event_id": "G62", "wp_id": "WP07", "from_lane": "in_review", "to_lane": "approved", "at": "2026-09-03T16:10:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "first", "verdict": "approved", "reference": "1"}}
      {"event_id": "G63", "wp_id": "WP07", "from_lane": "in_review", "to_lane": "done", "at": "2026-09-03T16:20:00+00:00", "actor": "migration:backfill", "force": false, "execution_mode": "worktree", "review_result": {"reviewer": "second", "verdict": "approved", "reference": "2"}}
      """;

  private static final String SEED_EXPECTED =
      """
      WP01|agent=seed-agent|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=bob|subtasks=-|result=-|override=-|history=G01,2026-09-03T10:00:00+00:00,planned,blocked,bob/-/-,0,-,-;G02,2026-09-03T10:30:00+00:00,planned,claimed,migration:backfill/-/-,0,-,-
      WP02|agent=real-agent|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=bob|subtasks=-|result=-|override=-|history=G11,2026-09-03T11:00:00+00:00,planned,claimed,bob/-/-,0,-,-;G12,2026-09-03T11:30:00+00:00,planned,claimed,migration:backfill/-/-,0,-,-
      WP03|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=bob|subtasks=-|result=seed-rev;approved;s|override=-|history=G21,2026-09-03T12:00:00+00:00,planned,blocked,bob/-/-,0,-,-;G22,2026-09-03T12:30:00+00:00,in_review,approved,migration:backfill/-/-,0,-,approved
      WP04|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=bob|subtasks=-|result=-|override=-|history=G31,2026-09-03T13:00:00+00:00,planned,blocked,bob/-/-,0,-,-;G32,2026-09-03T13:30:00+00:00,in_review,approved,migration:backfill/-/-,0,-,-
      WP05|agent=s5|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=carol|subtasks=-|result=-|override=-|history=G41,2026-09-03T14:00:00+00:00,planned,claimed,migration:backfill/-/-,0,-,-;G42,2026-09-03T14:30:00+00:00,claimed,in_progress,carol/-/-,0,-,-
      WP06|agent=real6|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=bob|subtasks=-|result=late;approved;r|override=-|history=G51,2026-09-03T15:00:00+00:00,planned,claimed,bob/-/-,0,-,-;G52,2026-09-03T15:10:00+00:00,claimed,in_progress,bob/-/-,0,-,-;G53,2026-09-03T15:20:00+00:00,in_review,approved,migration:backfill/-/-,0,-,approved
      WP07|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=bob|subtasks=-|result=second;approved;2|override=-|history=G61,2026-09-03T16:00:00+00:00,planned,blocked,bob/-/-,0,-,-;G62,2026-09-03T16:10:00+00:00,in_review,approved,migration:backfill/-/-,0,-,approved;G63,2026-09-03T16:20:00+00:00,in_review,done,migration:backfill/-/-,0,-,approved
      types=
      """;

  private static final String TYPES_LEDGER =
      """
      {"event_id": "H01", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": 123}}
      {"event_id": "H02", "wp_id": "WP02", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": true}}
      {"event_id": "H03", "wp_id": "WP03", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": ["x"]}}
      {"event_id": "H04", "wp_id": "WP04", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": {"a": 1}}}
      {"event_id": "H05", "wp_id": "WP05", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": ""}}
      {"event_id": "H06", "wp_id": "WP06", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": "alice", "force": false, "execution_mode": "worktree", "policy_metadata": {"agent": 0}}
      {"event_id": "H07", "wp_id": "WP07", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": null, "force": false, "execution_mode": "worktree"}
      {"event_id": "H08", "wp_id": "WP08", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": 123, "force": false, "execution_mode": "worktree"}
      {"event_id": "H09", "wp_id": "WP09", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": {"role": "r", "profile": "p", "tool": "t", "model": "m"}, "force": false, "execution_mode": "worktree"}
      {"event_id": "H10", "wp_id": "WP10", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": {"role": "rr", "profile": null, "tool": null, "model": null}, "force": false, "execution_mode": "worktree"}
      {"event_id": "H11", "wp_id": "WP11", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": {"role": null, "profile": null, "tool": null, "model": null}, "force": false, "execution_mode": "worktree"}
      {"event_id": "H12", "wp_id": "WP12", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-04T10:00:00+00:00", "actor": true, "force": false, "execution_mode": "worktree"}
      {"event_id": "01HA0000000000000000000011", "kind": "annotation", "wp_id": "WP13", "at": "2026-09-04T11:00:00+00:00", "actor": "claude", "delta": {"agent": 5, "assignee": true, "role": [1], "model": {"a": 1}, "provider": 0, "agent_profile": "", "agent_profile_version": 2}}
      {"event_id": "01HA0000000000000000000012", "kind": "annotation", "wp_id": "WP14", "at": 5, "actor": "claude", "delta": {"role": "r5"}}
      {"event_id": "01HA0000000000000000000013", "kind": "annotation", "wp_id": "WP14", "at": null, "actor": "claude", "delta": {"role": "rnull"}}
      {"event_id": "01HA0000000000000000000014", "kind": "annotation", "wp_id": "WP14", "at": "2026-09-04T10:00:00Z", "actor": "claude", "delta": {"role": "r2026"}}
      {"event_id": "01HA0000000000000000000015", "kind": "annotation", "wp_id": "WP15", "at": "2026-09-04T11:00:00+00:00", "actor": "claude", "delta": {"review": {"at": null, "actor": null, "wp_id": null, "reason": null}}}
      {"event_id": "01HA0000000000000000000016", "kind": "annotation", "wp_id": "WP16", "at": "2026-09-04T11:00:00+00:00", "actor": "claude", "delta": {"review": {"at": 5, "actor": 6, "wp_id": true, "reason": 7}}}
      {"event_id": "01HA0000000000000000000017", "kind": "annotation", "wp_id": 5, "at": "2026-09-04T11:00:00+00:00", "actor": null, "delta": {"assignee": "numeric-wp"}}
      """;

  private static final String TYPES_EXPECTED =
      """
      5|agent=-|assignee=numeric-wp|role=-|profile=-|version=-|model=-|provider=-|actor=None|subtasks=-|result=-|override=-|history=-
      WP01|agent=123|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=H01,2026-09-04T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP02|agent=True|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=H02,2026-09-04T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP03|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=H03,2026-09-04T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP04|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=H04,2026-09-04T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP05|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=H05,2026-09-04T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP06|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=H06,2026-09-04T10:00:00+00:00,planned,claimed,alice/-/-,0,-,-
      WP07|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=None|subtasks=-|result=-|override=-|history=H07,2026-09-04T10:00:00+00:00,planned,claimed,-/-/-,0,-,-
      WP08|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=123|subtasks=-|result=-|override=-|history=H08,2026-09-04T10:00:00+00:00,planned,claimed,-/-/-,0,-,-
      WP09|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=t|subtasks=-|result=-|override=-|history=H09,2026-09-04T10:00:00+00:00,planned,claimed,t/r/p,0,-,-
      WP10|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=rr|subtasks=-|result=-|override=-|history=H10,2026-09-04T10:00:00+00:00,planned,claimed,-/rr/-,0,-,-
      WP11|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=-|subtasks=-|result=-|override=-|history=H11,2026-09-04T10:00:00+00:00,planned,claimed,-/-/-,0,-,-
      WP12|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=True|subtasks=-|result=-|override=-|history=H12,2026-09-04T10:00:00+00:00,planned,claimed,-/-/-,0,-,-
      WP13|agent=5|assignee=True|role=-|profile=-|version=2|model=-|provider=0|actor=claude|subtasks=-|result=-|override=-|history=-
      WP14|agent=-|assignee=-|role=rnull|profile=-|version=-|model=-|provider=-|actor=claude|subtasks=-|result=-|override=-|history=-
      WP15|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=claude|subtasks=-|result=-|override=ERR|history=-
      WP16|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=claude|subtasks=-|result=-|override=ERR|history=-
      types=
      """;

  private static final String HISTORY_LEDGER =
      """
      {"event_id": "E5", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-01T12:00:00+02:00", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_id": "E3", "wp_id": "WP01", "from_lane": "claimed", "to_lane": "in_progress", "at": "2026-09-01T10:00:00Z", "actor": {"role": "dev", "profile": "jenny", "tool": "claude", "model": "m"}, "force": false, "execution_mode": "worktree"}
      {"event_id": "E4", "wp_id": "WP01", "from_lane": "in_progress", "to_lane": "for_review", "at": "2026-09-01T10:00:00.5Z", "actor": "bob", "force": false, "execution_mode": "worktree", "reason": "why"}
      {"event_id": "01HA0000000000000000000018", "kind": "annotation", "wp_id": "WP01", "at": "2026-09-01T10:01:00Z", "actor": "claude", "delta": {"note": "x"}}
      {"event_id": "E7", "event_type": "DecisionX", "wp_id": "WP01", "from_lane": "for_review", "to_lane": "in_review", "at": "2026-09-01T10:02:00Z", "actor": "dec", "force": true}
      {"event_id": "E4", "wp_id": "WP01", "from_lane": "for_review", "to_lane": "in_review", "at": "2026-09-01T09:00:00Z", "actor": "bob", "force": true, "execution_mode": "worktree", "review_result": {"reviewer": "r", "verdict": "approved", "reference": "q"}}
      {"event_id": "E8", "wp_id": "WP01", "from_lane": "in_review", "to_lane": "approved", "at": "2026-09-01T10:03:00Z", "actor": "rev", "force": 1, "execution_mode": "worktree"}
      {"event_id": "E9", "wp_id": "WP01", "from_lane": "approved", "to_lane": "done", "at": "2026-09-01T10:04:00Z", "actor": "rev", "force": "true", "execution_mode": "worktree"}
      {"event_id": "EA", "wp_id": "WP01", "from_lane": "done", "to_lane": "canceled", "at": "2026-09-01T10:05:00Z", "actor": "lead", "force": false, "execution_mode": "worktree", "reason": "stop"}
      {"event_id": "EB", "wp_id": "WP01", "from_lane": "in_progress", "to_lane": "for_review", "at": "2026-09-01T10:06:00Z", "actor": "late", "force": false, "execution_mode": "worktree"}
      {"event_id": "EC", "wp_id": "WP01", "from_lane": "genesis", "to_lane": "planned", "at": "2026-09-01T08:00:00Z", "actor": "boot", "force": false, "execution_mode": "worktree"}
      {"event_id": "ED", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "garbage", "actor": "junk", "force": false, "execution_mode": "worktree"}
      {"event_id": "EE", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-01T10:00:00.000001Z", "actor": "micro", "force": false, "execution_mode": "worktree"}
      {"event_id": "EF", "wp_id": "WP02", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-01T10:00:00Z", "actor": "other", "force": false, "execution_mode": "worktree"}
      """;

  private static final String HISTORY_EXPECTED =
      """
      WP01|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=lead|subtasks=-|result=-|override=-|history=EC,2026-09-01T08:00:00Z,-,planned,boot/-/-,0,-,-;E4,2026-09-01T09:00:00Z,for_review,in_review,bob/-/-,1,-,approved;E3,2026-09-01T10:00:00Z,claimed,in_progress,claude/dev/jenny,0,-,-;E5,2026-09-01T12:00:00+02:00,planned,claimed,alice/-/-,0,-,-;EE,2026-09-01T10:00:00.000001Z,planned,claimed,micro/-/-,0,-,-;E4,2026-09-01T10:00:00.5Z,in_progress,for_review,bob/-/-,0,why,-;E7,2026-09-01T10:02:00Z,for_review,in_review,dec/-/-,1,-,-;E8,2026-09-01T10:03:00Z,in_review,approved,rev/-/-,0,-,-;E9,2026-09-01T10:04:00Z,approved,done,rev/-/-,0,-,-;EA,2026-09-01T10:05:00Z,done,canceled,lead/-/-,0,stop,-;EB,2026-09-01T10:06:00Z,in_progress,for_review,late/-/-,0,-,-;ED,garbage,planned,claimed,junk/-/-,0,-,-
      WP02|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=other|subtasks=-|result=-|override=-|history=EF,2026-09-01T10:00:00Z,planned,claimed,other/-/-,0,-,-
      types=DecisionX
      """;

  private static final String LIFECYCLE_LEDGER =
      """
      {"event_type": "PlanStarted", "timestamp": "2026-09-05T10:00:00Z"}
      {"event_type": "SpecifyStarted", "event_id": "L1", "timestamp": "2026-09-05T10:01:00Z"}
      {"event_type": 5, "event_id": "L2", "timestamp": "2026-09-05T10:02:00Z"}
      {"event_type": "DecisionPointOpened", "event_id": "L3", "timestamp": "2026-09-05T10:03:00Z"}
      {"event_type": null, "wp_id": "WP01"}
      {"event_id": "01HA0000000000000000000019", "kind": "annotation", "wp_id": "WP01", "at": "2026-09-05T10:04:00Z", "actor": "claude", "delta": {"note": "x"}, "event_type": "WeirdAnnotation"}
      {"event_id": "K1", "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed", "at": "2026-09-05T10:05:00Z", "actor": "alice", "force": false, "execution_mode": "worktree"}
      {"event_type": "PlanStarted", "event_id": "L4", "timestamp": "t"}
      """;

  private static final String LIFECYCLE_EXPECTED =
      """
      WP01|agent=-|assignee=-|role=-|profile=-|version=-|model=-|provider=-|actor=alice|subtasks=-|result=-|override=-|history=K1,2026-09-05T10:05:00Z,planned,claimed,alice/-/-,0,-,-
      types=DecisionPointOpened,PlanStarted,SpecifyStarted,WeirdAnnotation
      """;

  @Test
  void theClaimTheBindingTheSubtasksTheOverrideAndTheReleaseResolveAsPythonDoes() {
    assertThat(canonical(reduce(BINDING_LEDGER))).isEqualTo(BINDING_EXPECTED);
  }

  @Test
  void theReviewResultIsStickyForcedNullAndWrittenByAnyEventThatCarriesOne() {
    assertThat(canonical(reduce(REVIEWS_LEDGER))).isEqualTo(REVIEWS_EXPECTED);
  }

  @Test
  void aSeedThatLostOnContinuityStillFoldsItsClaimAndVerdictOnlyWhereNoRealEventWroteThem() {
    assertThat(canonical(reduce(SEED_LEDGER))).isEqualTo(SEED_EXPECTED);
  }

  @Test
  void scalarSlotsAreStoredRawAndStringifiedLikePythonStr() {
    assertThat(canonical(reduce(TYPES_LEDGER))).isEqualTo(TYPES_EXPECTED);
  }

  @Test
  void theHistoryIsEveryToLaneRowOrderedByInstantThenEventIdWithNoDedupAndNoArbitration() {
    assertThat(canonical(reduce(HISTORY_LEDGER))).isEqualTo(HISTORY_EXPECTED);
  }

  @Test
  void lifecycleTypesAreEveryTextEventTypeOfTheLedger() {
    assertThat(canonical(reduce(LIFECYCLE_LEDGER))).isEqualTo(LIFECYCLE_EXPECTED);
  }

  private static StatusSnapshot reduce(String ledger) {
    byte[] bytes = (ledger.endsWith("\n") ? ledger : ledger + "\n").getBytes(StandardCharsets.UTF_8);
    return new StatusReducer(new AtThenEventId()).reduceLines(LedgerLineDecoder.decode(bytes).lines());
  }

  /** One line per work package in code point order of the id, then the sorted lifecycle types: the format of the oracle probe. */
  static String canonical(StatusSnapshot snapshot) {
    List<String> ids = new ArrayList<>(snapshot.resolved().keySet());
    Collections.sort(ids);
    StringBuilder text = new StringBuilder();
    for (String id : ids) {
      WpResolved resolved = snapshot.resolved().get(id);
      text.append(id)
          .append("|agent=").append(n(resolved.assignment().agent()))
          .append("|assignee=").append(n(resolved.assignment().assignee()))
          .append("|role=").append(n(resolved.assignment().role()))
          .append("|profile=").append(n(resolved.assignment().agentProfile()))
          .append("|version=").append(n(resolved.assignment().agentProfileVersion()))
          .append("|model=").append(n(resolved.assignment().model()))
          .append("|provider=").append(n(resolved.assignment().provider()))
          .append("|actor=").append(n(resolved.actor().tool()))
          .append("|subtasks=").append(subtasks(resolved.subtasks()))
          .append("|result=").append(result(resolved.reviewResult()))
          .append("|override=").append(override(resolved.reviewOverride()))
          .append("|history=").append(history(resolved.history()))
          .append('\n');
    }
    text.append("types=").append(snapshot.lifecycleTypes().stream().sorted().collect(Collectors.joining(","))).append('\n');
    return text.toString();
  }

  private static String n(Object value) {
    return value == null ? "-" : value.toString();
  }

  private static String subtasks(Map<String, Lane> subtasks) {
    return subtasks.isEmpty() ? "-" : subtasks.entrySet().stream().map(entry -> entry.getKey() + ":" + entry.getValue().wire()).collect(Collectors.joining(","));
  }

  private static String result(ReviewResultRecord record) {
    return record == null ? "-" : n(record.reviewer()) + ";" + n(record.verdict()) + ";" + (record.reference() == null ? "" : record.reference());
  }

  /** The oracle's {@code review_override}: a time is shown only with an offset, and a complete record without one cannot be shown. */
  private static String override(ReviewOverrideRecord record) {
    if (record == null) {
      return "-";
    }
    boolean dated = !record.at().isEmpty() && Instants.hasOffset(record.at());
    if (record.complete() && !dated) {
      return "ERR";
    }
    return "c=" + (record.complete() ? 1 : 0)
        + ",at=" + (dated ? record.at() : "-")
        + ",actor=" + (record.actor().isEmpty() ? "-" : n(Actor.ofText(record.actor()).tool()))
        + ",reason=" + (record.reason().isEmpty() ? "-" : record.reason());
  }

  private static String history(List<HistoryRow> rows) {
    return rows.isEmpty()
        ? "-"
        : rows.stream()
            .map(
                row ->
                    n(row.eventId()) + "," + n(row.at()) + "," + lane(row.fromLane()) + "," + lane(row.toLane()) + ","
                        + n(row.actor().tool()) + "/" + n(row.actor().role()) + "/" + n(row.actor().profile()) + ","
                        + (row.force() ? 1 : 0) + "," + n(row.reason()) + "," + n(row.reviewVerdict()))
            .collect(Collectors.joining(";"));
  }

  /** {@code Projector.lane}: null for no lane and for the non-display lanes. */
  private static String lane(String stored) {
    return stored == null || !Lane.fromWire(stored).isDisplay() ? "-" : stored;
  }
}
