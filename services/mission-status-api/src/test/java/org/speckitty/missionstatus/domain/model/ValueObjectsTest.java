package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import org.junit.jupiter.api.Test;

/** Plain unit tests of the domain vocabulary; no Spring context is started. */
class ValueObjectsTest {

  private static final String ULID = "01J01000000000000000000001";

  @Test
  void laneWireValuesFollowTheContractOrderAndTheTwoNonDisplayValuesAreKnown() {
    assertThat(Lane.displayLanes().stream().map(Lane::wire))
        .containsExactly("planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done", "blocked", "canceled");
    assertThat(Lane.fromWire("genesis")).isEqualTo(Lane.GENESIS);
    assertThat(Lane.GENESIS.isDisplay()).isFalse();
    assertThat(Lane.UNINITIALIZED.isDisplay()).isFalse();
    assertThat(Lane.IN_REVIEW.isDisplay()).isTrue();
    for (Lane lane : Lane.values()) {
      assertThat(Lane.fromWire(lane.wire())).isSameAs(lane);
    }
  }

  @Test
  void anUnknownOrMissingLaneIsMalformedInput() {
    assertThatThrownBy(() -> Lane.fromWire("sideways")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> Lane.fromWire(null)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> Lane.fromWire("Planned")).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void missionIdIsAUlidAndMid8IsItsFirstEightCharacters() {
    assertThat(new MissionId(ULID).mid8()).isEqualTo("01J01000");
    assertThat(new MissionId(ULID).value()).isEqualTo(ULID);
    assertThatThrownBy(() -> new MissionId("short")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new MissionId("01J0100000000000000000000I")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new MissionId(null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void aStatusEventCarriesNoLogicalClockAndRequiresItsCoreMembers() {
    StatusEvent event = new StatusEvent("E1", "2026-09-01T10:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, "agent-x");
    assertThat(event.eventId()).isEqualTo("E1");
    assertThat(event.at()).isEqualTo("2026-09-01T10:00:00Z");
    assertThat(event.wpId()).isEqualTo("WP01");
    assertThat(event.fromLane()).isEqualTo(Lane.PLANNED);
    assertThat(event.toLane()).isEqualTo(Lane.CLAIMED);
    assertThat(event.force()).isFalse();
    assertThat(event.reviewRef()).isNull();
    assertThat(event.reason()).isNull();
    assertThat(event.reasonSource()).isNull();
    assertThat(event.claimAgent()).isEqualTo("agent-x");
    assertThat(StatusEvent.class.getRecordComponents()).extracting(c -> c.getName()).noneMatch(n -> n.toLowerCase().contains("clock") || n.toLowerCase().contains("lamport"));
    assertThatThrownBy(() -> new StatusEvent(null, "t", "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void onlyTheSevenLifecycleTypesAreLifecycleEvents() {
    List<String> seven = List.of("MissionCreated", "SpecifyStarted", "SpecifyCompleted", "PlanStarted", "PlanCompleted", "TasksStarted", "TasksCompleted");
    for (String type : seven) {
      assertThat(LifecycleEvent.isForwarded(type)).isTrue();
      assertThat(new LifecycleEvent("L1", type, "2026-09-01T10:00:00Z").type()).isEqualTo(type);
    }
    assertThat(LifecycleEvent.isForwarded("DecisionPointOpened")).isFalse();
    assertThat(new LifecycleEvent("L1", "PlanStarted", "2026-09-01T10:00:00Z").eventId()).isEqualTo("L1");
    assertThat(new LifecycleEvent("L1", "PlanStarted", "2026-09-01T10:00:00Z").at()).isEqualTo("2026-09-01T10:00:00Z");
    assertThatThrownBy(() -> new LifecycleEvent("L1", "DecisionPointOpened", "t")).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void topologyKnowsTheFourStoredShapesAndFallsBackToUnknown() {
    assertThat(Topology.fromStored("single_branch")).isEqualTo(Topology.SINGLE_BRANCH);
    assertThat(Topology.fromStored("lanes")).isEqualTo(Topology.LANES);
    assertThat(Topology.fromStored("coord")).isEqualTo(Topology.COORD);
    assertThat(Topology.fromStored("lanes_with_coord")).isEqualTo(Topology.LANES_WITH_COORD);
    assertThat(Topology.fromStored("unknown")).isEqualTo(Topology.UNKNOWN);
    assertThat(Topology.fromStored("something_else")).isEqualTo(Topology.UNKNOWN);
    assertThat(Topology.fromStored(null)).isEqualTo(Topology.UNKNOWN);
    assertThat(Topology.LANES_WITH_COORD.wire()).isEqualTo("lanes_with_coord");
    assertThat(Topology.COORD.routesThroughCoordination()).isTrue();
    assertThat(Topology.LANES_WITH_COORD.routesThroughCoordination()).isTrue();
    assertThat(Topology.LANES.routesThroughCoordination()).isFalse();
    assertThat(Topology.SINGLE_BRANCH.routesThroughCoordination()).isFalse();
    assertThat(Topology.UNKNOWN.routesThroughCoordination()).isFalse();
  }

  @Test
  void missionMetaTreatsEmptyOptionalTextAsAbsent() {
    MissionMeta meta = new MissionMeta(new MissionId(ULID), "slug", "Friendly", 7, "software-dev", "main", Topology.LANES, "2026-09-01T10:00:00Z", "", "2026-09-02T00:00:00Z", null, true);
    assertThat(meta.missionId().value()).isEqualTo(ULID);
    assertThat(meta.slug()).isEqualTo("slug");
    assertThat(meta.friendlyName()).isEqualTo("Friendly");
    assertThat(meta.displayNumber()).isEqualTo(7);
    assertThat(meta.missionType()).isEqualTo("software-dev");
    assertThat(meta.targetBranch()).isEqualTo("main");
    assertThat(meta.topology()).isEqualTo(Topology.LANES);
    assertThat(meta.createdAt()).isEqualTo("2026-09-01T10:00:00Z");
    assertThat(meta.acceptedAt()).isNull();
    assertThat(meta.mergedAt()).isEqualTo("2026-09-02T00:00:00Z");
    assertThat(meta.discardedAt()).isNull();
    assertThat(meta.hasBaseline()).isTrue();
    assertThatThrownBy(() -> new MissionMeta(null, "s", null, null, null, "main", Topology.LANES, "t", null, null, null, false)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void diagnosticsUseTheClosedCodeSetAndNeverCarryAPathOrText() {
    assertThat(java.util.Arrays.stream(DiagnosticCode.values()).map(DiagnosticCode::wire))
        .containsExactly(
            "ledger_unreadable", "ledger_unparseable", "ledger_torn_tail", "meta_unparseable", "mission_vanished", "path_refused", "mission_dir_unreadable", "projection_refused", "mission_id_duplicate");
    Diagnostic withLine = new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, "01J01000", 12);
    assertThat(withLine.code()).isEqualTo(DiagnosticCode.LEDGER_UNPARSEABLE);
    assertThat(withLine.mid8()).isEqualTo("01J01000");
    assertThat(withLine.line()).isEqualTo(12);
    assertThat(new Diagnostic(DiagnosticCode.MISSION_DIR_UNREADABLE, Diagnostic.NONE, null).mid8()).isEqualTo("none");
    assertThatThrownBy(() -> new Diagnostic(null, "none", null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void theSupportedSchemaRangeIsThePythonConstant() {
    assertThat(SupportedSchemaRange.MIN).isEqualTo(3);
    assertThat(SupportedSchemaRange.MAX).isEqualTo(3);
    assertThat(SupportedSchemaRange.contains(3)).isTrue();
    assertThat(SupportedSchemaRange.contains(2)).isFalse();
    assertThat(SupportedSchemaRange.contains(4)).isFalse();
  }

  @Test
  void ledgerLinesCarryOneOfSixKinds() {
    StatusEvent event = new StatusEvent("E1", "2026-09-01T10:00:00Z", "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, null);
    LifecycleEvent lifecycle = new LifecycleEvent("L1", "PlanStarted", "2026-09-01T10:00:00Z");
    List<LineKind> kinds =
        List.of(new LineKind.Status(event), new LineKind.Lifecycle(lifecycle), new LineKind.Annotation("WP09"), new LineKind.Ignored(), new LineKind.Blank(), new LineKind.Malformed(MalformedReason.NOT_JSON));
    String digest = "0".repeat(64);
    for (LineKind kind : kinds) {
      LedgerLine line = new LedgerLine(3, digest, 120, kind);
      assertThat(line.lineNumber()).isEqualTo(3);
      assertThat(line.rawLineSha256()).isEqualTo(digest);
      assertThat(line.byteLength()).isEqualTo(120);
      assertThat(line.kind()).isSameAs(kind);
    }
    assertThat(((LineKind.Status) kinds.get(0)).event()).isSameAs(event);
    assertThat(((LineKind.Lifecycle) kinds.get(1)).event()).isSameAs(lifecycle);
    assertThat(((LineKind.Annotation) kinds.get(2)).wpId()).isEqualTo("WP09");
    assertThat(((LineKind.Malformed) kinds.get(5)).reason()).isEqualTo(MalformedReason.NOT_JSON);
    assertThatThrownBy(() -> new LineKind.Annotation(null)).isInstanceOf(NullPointerException.class);
    assertThat(MalformedReason.values()).containsExactly(MalformedReason.NOT_JSON, MalformedReason.NOT_OBJECT, MalformedReason.NOT_UTF8, MalformedReason.UNUSABLE_ROW);
    assertThat(TailClassification.values()).containsExactly(TailClassification.NONE, TailClassification.WHITESPACE, TailClassification.NON_WHITESPACE);
    assertThatThrownBy(() -> new LedgerLine(1, digest, 1, null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void pythonTextHelpersMatchStrStripAndEmptyChecks() {
    assertThat(PyText.isBlank(null)).isTrue();
    assertThat(PyText.isBlank("")).isTrue();
    assertThat(PyText.isBlank(" \t\n \u0085 ")).isTrue();
    assertThat(PyText.isBlank(" x ")).isFalse();
    assertThat(PyText.strip("   name  ")).isEqualTo("name");
    assertThat(PyText.strip("name")).isEqualTo("name");
    assertThat(PyText.nullIfEmpty("")).isNull();
    assertThat(PyText.nullIfEmpty(null)).isNull();
    assertThat(PyText.nullIfEmpty(" ")).isEqualTo(" ");
    assertThat(PyText.nullIfEmpty("a")).isEqualTo("a");
  }

  @Test
  void codePointOrderingDiffersFromUtf16OrderingForSupplementaryCharacters() {
    String supplementary = new String(Character.toChars(0x1F600));
    String highBmp = "～";
    assertThat(supplementary.compareTo(highBmp)).isLessThan(0);
    assertThat(CodePoints.compare(supplementary, highBmp)).isGreaterThan(0);
    assertThat(CodePoints.compare(highBmp, supplementary)).isLessThan(0);
    assertThat(CodePoints.compare("a", "a")).isZero();
    assertThat(CodePoints.compare("a", "ab")).isLessThan(0);
    assertThat(CodePoints.compare("ab", "a")).isGreaterThan(0);
    assertThat(CodePoints.compare("a", "b")).isLessThan(0);
  }
}
