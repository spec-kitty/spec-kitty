package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.StatusEvent.SlotText;

/** The additive members of the line and the row carriers (FR-020, D-98): the older constructors keep their meaning. */
class LedgerLineMembersTest {

  private static final String DIGEST = "0".repeat(64);

  @Test
  void theFourArgumentLineCarriesNoEventTypeAndNoHistoryRow() {
    LedgerLine line = new LedgerLine(3, DIGEST, 10, new LineKind.Blank());
    assertThat(line.eventType()).isNull();
    assertThat(line.historyRow()).isNull();
    assertThat(line).isEqualTo(new LedgerLine(3, DIGEST, 10, new LineKind.Blank(), null, null));
  }

  @Test
  void aLineMayCarryAnEventTypeAndAHistoryRow() {
    HistoryRow row = new HistoryRow("WP01", "E1", "t", null, "planned", Actor.NONE, false, null, null);
    LedgerLine line = new LedgerLine(1, DIGEST, 10, new LineKind.Ignored(), "PlanStarted", row);
    assertThat(line.eventType()).isEqualTo("PlanStarted");
    assertThat(line.historyRow()).isSameAs(row);
    assertThatThrownBy(() -> new LedgerLine(1, DIGEST, 10, null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void anAnnotationIsIdentifiedByItsWorkPackageAlone() {
    LineKind.Annotation bare = new LineKind.Annotation("WP09");
    LineKind.Annotation loaded =
        new LineKind.Annotation("WP09", "2026-09-01T10:00:00Z", "01HXYZ0000000000000000000A", "claude", new LineKind.Annotation.Delta(true, Map.of("agent", SlotText.of("a")), null, null));
    assertThat(loaded).isEqualTo(bare).hasSameHashCodeAs(bare);
    assertThat(loaded.delta().releaseRuntimeClaim()).isTrue();
    assertThat(bare.delta()).isEqualTo(LineKind.Annotation.Delta.NONE);
    assertThat(bare).isNotEqualTo(new LineKind.Annotation("WP10"));
  }

  @Test
  void aDeltaCopiesItsMapsAndKeepsTheSubtaskOrder() {
    Map<String, Lane> subtasks = new java.util.LinkedHashMap<>();
    subtasks.put("T2", Lane.DONE);
    subtasks.put("T1", Lane.PLANNED);
    LineKind.Annotation.Delta delta = new LineKind.Annotation.Delta(false, Map.of(), subtasks, null);
    subtasks.put("T3", Lane.DONE);
    assertThat(delta.subtasks()).containsExactly(Map.entry("T2", Lane.DONE), Map.entry("T1", Lane.PLANNED));
    assertThatThrownBy(() -> delta.subtasks().put("x", Lane.DONE)).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> delta.replaceSlots().put("agent", SlotText.UNSHOWN)).isInstanceOf(UnsupportedOperationException.class);
  }

  @Test
  void theOlderStatusEventConstructorsDefaultTheResolvedMembersFromTheOlderOnes() {
    StatusEvent claim = new StatusEvent("E1", "t", "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, "claude", new Actor("tool-x", "role-y", null));
    assertThat(claim.claimAgentSlot()).isEqualTo(SlotText.of("claude"));
    assertThat(claim.actorIdentity()).isEqualTo("tool-x");
    assertThat(claim.reviewResult()).isNull();

    StatusEvent noActor = new StatusEvent("E1", "t", "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, "");
    assertThat(noActor.claimAgentSlot()).as("an empty agent writes nothing").isNull();
    assertThat(noActor.actorIdentity()).isEmpty();
    assertThat(new StatusEvent("E1", "t", "WP01", Lane.PLANNED, Lane.CLAIMED, false, null, null, null, null, new Actor(null, "role-y", null)).actorIdentity()).isEqualTo("role-y");
  }

  @Test
  void aSlotTextIsAWrittenSlotAndUnshownIsAWrittenSlotWithoutAText() {
    assertThat(SlotText.of("123").text()).isEqualTo("123");
    assertThat(SlotText.UNSHOWN.text()).isNull();
    assertThatThrownBy(() -> SlotText.of(null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void anAnnotationEqualsOnlyAnotherAnnotationOfTheSameWorkPackage() {
    LineKind.Annotation annotation = new LineKind.Annotation("WP09");
    assertThat(annotation.equals(annotation)).isTrue();
    assertThat(annotation.equals(null)).isFalse();
    assertThat(annotation.equals("WP09")).isFalse();
    assertThat(annotation.equals(new LineKind.Ignored())).isFalse();
  }
}
