package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** The resolved state of one Work Package: copies are defensive and unmodifiable, insertion order is kept, and the empty value is the no-events value. */
class WpResolvedTest {

  @Test
  void theEmptyValueIsTheNoEventsValue() {
    WpResolved empty = WpResolved.empty();
    assertThat(empty.assignment()).isEqualTo(Assignment.EMPTY);
    assertThat(empty.subtasks()).isEmpty();
    assertThat(empty.reviewResult()).isNull();
    assertThat(empty.reviewOverride()).isNull();
    assertThat(empty.actor()).isEqualTo(Actor.NONE);
    assertThat(empty.history()).isEmpty();
  }

  @Test
  void collectionsAreCopiedAndUnmodifiable() {
    Map<String, Lane> subtasks = new LinkedHashMap<>();
    subtasks.put("T2", Lane.DONE);
    subtasks.put("T1", Lane.PLANNED);
    List<HistoryRow> history = new ArrayList<>();
    history.add(new HistoryRow("WP01", "E1", "t", null, "planned", Actor.NONE, false, null, null));
    WpResolved resolved = new WpResolved(Assignment.EMPTY, subtasks, null, null, Actor.NONE, history);

    subtasks.put("T3", Lane.DONE);
    history.clear();

    assertThat(resolved.subtasks()).containsExactly(Map.entry("T2", Lane.DONE), Map.entry("T1", Lane.PLANNED));
    assertThat(resolved.history()).hasSize(1);
    assertThatThrownBy(() -> resolved.subtasks().put("x", Lane.DONE)).isInstanceOf(UnsupportedOperationException.class);
    assertThatThrownBy(() -> resolved.history().add(null)).isInstanceOf(UnsupportedOperationException.class);
  }

  @Test
  void theAssignmentTheSubtaskMapTheActorAndTheHistoryAreRequired() {
    assertThatThrownBy(() -> new WpResolved(null, Map.of(), null, null, Actor.NONE, List.of())).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WpResolved(Assignment.EMPTY, null, null, null, Actor.NONE, List.of())).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WpResolved(Assignment.EMPTY, Map.of(), null, null, null, List.of())).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new WpResolved(Assignment.EMPTY, Map.of(), null, null, Actor.NONE, null)).isInstanceOf(NullPointerException.class);
  }
}
