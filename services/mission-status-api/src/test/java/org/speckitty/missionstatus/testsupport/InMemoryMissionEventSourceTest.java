package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerRead;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerWindow;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.exceptions.SourceFault;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;
import org.speckitty.missionstatus.domain.model.TailClassification;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource.Op;

/** FR-013: the in-memory source takes raw bytes and gives typed results; it is the production decoder that makes the lines. */
class InMemoryMissionEventSourceTest {

  private static final String LEDGER = Rows.status("a1", "2026-09-01T10:00:00Z", "WP01", "planned", "claimed") + Rows.status("a2", "2026-09-01T10:05:00Z", "WP01", "claimed", "in_progress");

  private static InMemoryMissionEventSource source(String ledger) {
    return InMemoryMissionEventSource.from(FixtureSpec.of(FixtureSpec.Mission.of("m", Rows.meta(Rows.ALPHA_ID, "m", "2026-09-02T10:00:00+00:00"), ledger)));
  }

  @Test
  void noPublicConstructorOrFactoryAcceptsALedgerLine() {
    for (Class<?> type : new Class<?>[] {InMemoryMissionEventSource.class, FixtureSpec.class, FixtureSpec.Mission.class, FixtureFactory.class}) {
      for (Constructor<?> constructor : type.getConstructors()) {
        assertThat(Arrays.stream(constructor.getParameterTypes())).as(type + " constructor").doesNotContain(LedgerLine.class);
      }
      for (Method method : type.getMethods()) {
        if (Modifier.isStatic(method.getModifiers()) && method.getReturnType().isAssignableFrom(type)) {
          assertThat(Arrays.stream(method.getParameterTypes())).as(type + "." + method.getName()).doesNotContain(LedgerLine.class);
        }
        assertThat(Arrays.stream(method.getParameterTypes()).filter(parameter -> parameter == LedgerLine.class || parameter == LineKind.class)).as(method.toString()).isEmpty();
      }
    }
  }

  @Test
  void rawBytesAreDecodedThroughTheProductionDecoder() {
    InMemoryMissionEventSource source = source(LEDGER + "not json\n" + "{\"half\":");

    LedgerRead read = source.readLedger(new MissionRef("m"), source.stampLedger(new MissionRef("m")));

    assertThat(read.lines()).hasSize(3);
    assertThat(read.lines().get(0).kind()).isInstanceOf(LineKind.Status.class);
    assertThat(read.lines().get(2).kind()).isEqualTo(new LineKind.Malformed(MalformedReason.NOT_JSON));
    assertThat(read.tail()).isEqualTo(TailClassification.NON_WHITESPACE);
  }

  @Test
  void aStampChangesWithEveryWriteAndNotWithoutOne() {
    InMemoryMissionEventSource source = source(LEDGER);
    MissionRef ref = new MissionRef("m");
    LedgerStamp first = source.stampLedger(ref);

    assertThat(source.stampLedger(ref)).isEqualTo(first);
    source.appendLedger("m", Rows.status("a3", "2026-09-01T10:10:00Z", "WP01", "in_progress", "for_review"));
    LedgerStamp appended = source.stampLedger(ref);
    source.replaceLedger("m", LEDGER.getBytes(StandardCharsets.UTF_8));

    assertThat(appended).isNotEqualTo(first);
    assertThat(source.stampLedger(ref)).isNotEqualTo(first);
    assertThat(source.calls("stampLedger")).isEqualTo(4);
  }

  @Test
  void aWindowReportsSizeAlignmentAndThePrecedingLinesDigest() {
    InMemoryMissionEventSource source = source(LEDGER);
    MissionRef ref = new MissionRef("m");
    long firstLine = LEDGER.indexOf('\n') + 1;
    String firstLineText = LEDGER.substring(0, (int) firstLine);

    LedgerWindow whole = source.readLedgerFrom(ref, 0);
    LedgerWindow second = source.readLedgerFrom(ref, firstLine);
    LedgerWindow middle = source.readLedgerFrom(ref, 5);
    LedgerWindow beyond = source.readLedgerFrom(ref, LEDGER.length() + 10);

    assertThat(whole.lines()).hasSize(2);
    assertThat(whole.precedingLineSha256()).isEqualTo(StreamCursor.start().invariant());
    assertThat(second.lines()).hasSize(1);
    assertThat(second.aligned()).isTrue();
    assertThat(second.precedingLineSha256()).isEqualTo(StreamCursor.digestOf(firstLineText.getBytes(StandardCharsets.UTF_8)));
    assertThat(second.size()).isEqualTo(LEDGER.length());
    assertThat(middle.aligned()).isFalse();
    assertThat(beyond.size()).isEqualTo(LEDGER.length());
    assertThat(beyond.lines()).isEmpty();
  }

  @Test
  void anAbsentLedgerIsEmptyAndHasAStampOfItsOwn() {
    InMemoryMissionEventSource source = source(null);
    MissionRef ref = new MissionRef("m");

    assertThat(source.readLedger(ref, source.stampLedger(ref)).lines()).isEmpty();
    assertThat(source.readLedgerFrom(ref, 0).size()).isZero();
    source.appendLedger("m", LEDGER);
    assertThat(source.readLedgerFrom(ref, 0).lines()).hasSize(2);
    source.deleteLedger("m");
    assertThat(source.readLedgerFrom(ref, 0).size()).isZero();
  }

  @Test
  void aStampChangesWhenAnUnterminatedTailIsWrittenAndTheTailLeavesTheTerminatedPrefixAlone() {
    InMemoryMissionEventSource without = source(LEDGER);
    InMemoryMissionEventSource with = source(LEDGER + "{\"hal");
    MissionRef ref = new MissionRef("m");

    assertThat(with.readLedgerFrom(ref, 0).tail()).isEqualTo(TailClassification.NON_WHITESPACE);
    assertThat(with.readLedgerFrom(ref, 0).lines()).as("the tail is not a line").isEqualTo(without.readLedgerFrom(ref, 0).lines());
    assertThat(with.stampLedger(ref)).as("the stamp covers the file length, so a writer in mid-line changes it").isNotEqualTo(without.stampLedger(ref));
    assertThat(without.stampLedger(ref)).isEqualTo(source(LEDGER).stampLedger(ref));
  }

  @Test
  void metaIsReadFromBytesAndEveryUnusableFormIsOneFault() {
    for (byte[] meta : new byte[][] {"".getBytes(StandardCharsets.UTF_8), "[]".getBytes(StandardCharsets.UTF_8), "{".getBytes(StandardCharsets.UTF_8), {(byte) 0xC3, 0x28}, "{}".getBytes(StandardCharsets.UTF_8)}) {
      InMemoryMissionEventSource source = InMemoryMissionEventSource.from(FixtureSpec.of(FixtureSpec.Mission.ofBytes("m", meta, null)));
      assertThatThrownBy(() -> source.readMeta(new MissionRef("m"))).isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(SourceFault.Kind.META_UNPARSEABLE));
    }
    InMemoryMissionEventSource source = source(null);
    assertThat(source.readMeta(new MissionRef("m")).missionId().value()).isEqualTo(Rows.ALPHA_ID);
    source.replaceMeta("m", Rows.meta(Rows.BETA_ID, "m", "2026-09-02T10:00:00+00:00").getBytes(StandardCharsets.UTF_8));
    assertThat(source.readMeta(new MissionRef("m")).missionId().value()).isEqualTo(Rows.BETA_ID);
  }

  @Test
  void faultsCanBeInjectedPerOperationAndCleared() {
    InMemoryMissionEventSource source = source(LEDGER);
    MissionRef ref = new MissionRef("m");
    for (Op op : Op.values()) {
      source.inject("m", op, SourceFault.Kind.LEDGER_UNREADABLE);
    }

    assertThatThrownBy(() -> source.readMeta(ref)).isInstanceOf(SourceFault.class);
    assertThatThrownBy(() -> source.stampLedger(ref)).isInstanceOf(SourceFault.class);
    assertThatThrownBy(() -> source.readLedger(ref, null)).isInstanceOf(SourceFault.class);
    assertThatThrownBy(() -> source.readLedgerFrom(ref, 0)).isInstanceOf(SourceFault.class);
    source.clear("m", Op.STAMP);
    assertThat(source.stampLedger(ref)).isNotNull();
    source.injectUnexpected("m", Op.STAMP);
    assertThatThrownBy(() -> source.stampLedger(ref)).isInstanceOf(IllegalStateException.class);
  }

  @Test
  void aRemovedMissionVanishesFromTheListingAndEveryOperation() {
    InMemoryMissionEventSource source = source(LEDGER);
    source.removeMission("m");

    assertThat(source.listMissions()).isEmpty();
    assertThatThrownBy(() -> source.stampLedger(new MissionRef("m"))).isInstanceOfSatisfying(SourceFault.class, fault -> assertThat(fault.kind()).isEqualTo(SourceFault.Kind.VANISHED));
    assertThatThrownBy(() -> source.appendLedger("m", "x")).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void theListingIsInNameOrderAndCanFail() {
    InMemoryMissionEventSource source =
        InMemoryMissionEventSource.from(
            FixtureSpec.of(
                FixtureSpec.Mission.of("b", Rows.meta(Rows.BETA_ID, "b", "2026-09-02T10:00:00+00:00"), null),
                FixtureSpec.Mission.of("a", Rows.meta(Rows.ALPHA_ID, "a", "2026-09-02T10:00:00+00:00"), null)));

    assertThat(source.listMissions()).extracting(MissionRef::name).containsExactly("a", "b");
    source.failListing(SourceFault.Kind.DIR_UNREADABLE);
    assertThatThrownBy(source::listMissions).isInstanceOf(SourceFault.class);
    assertThat(source.calls("listMissions")).isEqualTo(2);
    source.resetCalls();
    assertThat(source.calls("listMissions")).isZero();
  }

  @Test
  void theProjectInputsComeFromTheSpecAndCanBeReplacedOrFail() {
    InMemoryMissionEventSource source = source(null);
    assertThat(source.projectInputs().name()).isEqualTo("fixture-project");
    source.setProject(new org.speckitty.missionstatus.application.query.port.out.dto.ProjectInputs("other", null, null, null));
    assertThat(source.projectInputs().name()).isEqualTo("other");
    source.failProject(SourceFault.Kind.DIR_UNREADABLE);
    assertThatThrownBy(source::projectInputs).isInstanceOf(SourceFault.class);
  }
}
