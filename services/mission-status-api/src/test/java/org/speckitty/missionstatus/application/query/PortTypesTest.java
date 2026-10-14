package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.dto.Change;
import org.speckitty.missionstatus.application.query.port.in.dto.ChangeBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.Closure;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.Rows;

/** The value types of the two ports refuse what they cannot represent and name nothing they should not. */
class PortTypesTest {

  private static final MissionId ID = new MissionId(Rows.ALPHA_ID);

  @Test
  void streamSettingsRefuseANonPositiveTickAndAnEmptyQueue() {
    // data-model.md: a 500 ms poll, a 1 s re-list and a 1024-signal queue. DeterministicExecutor ignores delays, so nothing else pins them.
    assertThat(StreamSettings.defaults().pollInterval()).isEqualTo(Duration.ofMillis(500));
    assertThat(StreamSettings.defaults().relistInterval()).isEqualTo(Duration.ofSeconds(1));
    assertThat(StreamSettings.defaults().queueCapacity()).isEqualTo(1024);
    assertThat(StreamSettings.defaults().withQueueCapacity(7).queueCapacity()).isEqualTo(7);
    assertThatThrownBy(() -> new StreamSettings(Duration.ZERO, Duration.ofSeconds(1), 1)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new StreamSettings(Duration.ofMillis(-1), Duration.ofSeconds(1), 1)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new StreamSettings(Duration.ofMillis(1), Duration.ofSeconds(1), 0)).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void aChangeIsOnlyAStatusTransitionOrALifecycleEvent() {
    StreamCursor cursor = StreamCursor.start();

    assertThatThrownBy(() -> new Change(ID, new LineKind.Annotation("WP01"), cursor)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new Change(ID, new LineKind.Blank(), cursor)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new Change(ID, null, cursor)).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new Change(null, new LineKind.Ignored(), cursor)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void aBatchKeepsItsOrderAndCannotBeChangedAfterwards() {
    List<Change> changes = new java.util.ArrayList<>();
    ChangeBatch batch = new ChangeBatch(changes, StreamCursor.start());
    changes.add(null);

    assertThat(batch.changes()).isEmpty();
    assertThatThrownBy(() -> batch.changes().add(null)).isInstanceOf(UnsupportedOperationException.class);
  }

  @Test
  void theWireNamesAreStable() {
    assertThat(Closure.SLOW_CONSUMER.wire()).isEqualTo("slow_consumer");
    assertThat(Closure.LEDGER_UNPARSEABLE.wire()).isEqualTo("ledger_unparseable");
    assertThat(StreamSignal.Truncated.Reason.SIZE_SHRINK.wire()).isEqualTo("size_shrink");
    assertThat(StreamSignal.Truncated.Reason.CONTENT_MISMATCH.wire()).isEqualTo("content_mismatch");
    assertThat(StreamRefused.Kind.CURSOR_WITHOUT_MISSION.wire()).isEqualTo("cursor_without_mission");
  }

  @Test
  void theStatusOfEachRefusalIsTheOneTheContractFixes() {
    assertThat(List.of(StreamRefused.Kind.values()))
        .extracting(StreamRefused.Kind::wire, StreamRefused.Kind::status)
        .containsExactlyInAnyOrder(
            org.assertj.core.groups.Tuple.tuple("negative", 400),
            org.assertj.core.groups.Tuple.tuple("misaligned", 400),
            org.assertj.core.groups.Tuple.tuple("cursor_without_mission", 400),
            org.assertj.core.groups.Tuple.tuple("out_of_range", 409),
            org.assertj.core.groups.Tuple.tuple("content_mismatch", 409),
            org.assertj.core.groups.Tuple.tuple("unknown_mission", 404));
  }

  @Test
  void anUnavailableReadNamesTheCodeAndNothingElse() {
    MissionStatusUnavailable unavailable = new MissionStatusUnavailable(new Diagnostic(DiagnosticCode.LEDGER_TORN_TAIL, "01J01000", 3));

    assertThat(unavailable.code()).isEqualTo(DiagnosticCode.LEDGER_TORN_TAIL);
    assertThat(unavailable.diagnostic().line()).isEqualTo(3);
    assertThat(unavailable.getMessage()).isEqualTo("mission status unavailable: ledger_torn_tail");
  }

  @Test
  void aScopeIsEqualByItsMissionAndRefusesNone() {
    assertThat(StreamScope.mission(ID)).isEqualTo(new StreamScope.OneMission(ID));
    assertThatThrownBy(() -> StreamScope.mission(null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void aLedgerStampKeepsItsPartsAndAFaultItsKind() {
    assertThat(new SourceFault(SourceFault.Kind.VANISHED).kind()).isEqualTo(SourceFault.Kind.VANISHED);
    assertThat(LedgerStamp.of(1, 2).parts()).containsExactly(1, 2);
    assertThatThrownBy(() -> new MissionRef(null)).isInstanceOf(NullPointerException.class);
  }
}
