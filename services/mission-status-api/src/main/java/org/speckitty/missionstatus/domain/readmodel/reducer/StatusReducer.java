package org.speckitty.missionstatus.domain.readmodel.reducer;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.PyText;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpState;

/**
 * The port of the reduction {@code materialize_snapshot} runs: {@code spec_kitty_events.diary.reduce_parsed} 10.4.4 plus the
 * cancellation-provenance and implementer projections of {@code reducer.py}. Steps: (1) deduplicate by {@code event_id}, first occurrence
 * in file order wins, except that rows which are all reconstruction seeds keep the canonical-minimum one (the two projections sort first,
 * then deduplicate); (2) sort by the injected ordering; (3) fold with rollback-aware precedence; (4) a separate annotation pass; (5) the
 * display lane counts (taken from the snapshot). It is pure: no clock, no I/O, no framework.
 *
 * <p>Ported from 10.4.0 to 10.4.4 (#5967, #4941, #6058): arm (ii) of the precedence drops an unforced, non-rollback transition whose
 * {@code from_lane} differs from the lane in force for every setter, except a seed that is not itself a rollback; and the same-id seed
 * dedup. The 10.4.3 seed payload fold (a seed that loses arm (ii) still fills the claim slots and {@code review_result} that no real event
 * wrote) is not ported, because it writes only slots this service never serves; it touches none of the lane-setter slots.
 */
public final class StatusReducer {

  private static final String[] SYNTHETIC_PREFIXES = {"Force move to ", "move-task: "};
  private static final Set<Lane> ROLLBACK_TARGETS = Set.of(Lane.PLANNED, Lane.CLAIMED, Lane.IN_PROGRESS);

  private final EventOrdering ordering;

  public StatusReducer(EventOrdering ordering) {
    this.ordering = Objects.requireNonNull(ordering, "ordering");
  }

  /**
   * The one public path. Reduce decoded ledger lines: lifecycle, ignored and blank lines are skipped in place, a malformed line is fatal, and an
   * annotation line feeds the annotation pass.
   */
  public StatusSnapshot reduceLines(List<LedgerLine> lines) {
    List<StatusEvent> events = new ArrayList<>();
    List<String> annotatedWpIds = new ArrayList<>();
    for (LedgerLine line : lines) {
      switch (line.kind()) {
        case LineKind.Status status -> events.add(status.event());
        case LineKind.Annotation annotation -> annotatedWpIds.add(annotation.wpId());
        case LineKind.Malformed malformed -> throw new UnreducibleLedgerException(line.lineNumber(), malformed.reason());
        case LineKind.Lifecycle ignored -> {}
        case LineKind.Ignored ignored -> {}
        case LineKind.Blank ignored -> {}
      }
    }
    return reduce(events, annotatedWpIds);
  }

  /**
   * The fold runs over dedup-then-sort ({@code reduce_parsed}: the first copy in file order wins); the two projections run over sort-then-dedup
   * ({@code reducer.py}: the first copy in sorted order wins). A duplicated {@code event_id} with different {@code at} values separates them.
   *
   * @param annotatedWpIds the work packages that carry annotation rows; one with no transition is held in the non-display {@code uninitialized}
   *     lane, as the oracle's annotation pass does (it counts in {@code wpTotal}, never in a lane count)
   */
  private StatusSnapshot reduce(List<StatusEvent> transitions, Collection<String> annotatedWpIds) {
    List<StatusEvent> sorted = sortedUnique(transitions);
    Map<String, StatusEvent> byId = new HashMap<>();
    for (StatusEvent event : sorted) {
      byId.put(event.eventId(), event);
    }
    Map<String, WpState> states = new LinkedHashMap<>();
    for (StatusEvent event : sorted) {
      WpState current = states.get(event.wpId());
      if (shouldApply(current, event, byId)) {
        states.put(event.wpId(), fold(event, current));
      }
    }
    project(uniqueOfSorted(transitions), states);
    for (String wpId : annotatedWpIds) {
      states.putIfAbsent(wpId, new WpState(Lane.UNINITIALIZED, null, null, 0, null, null, null));
    }
    StatusEvent last = sorted.isEmpty() ? null : sorted.getLast();
    return new StatusSnapshot(states, sorted.size(), last == null ? null : last.eventId(), last == null ? "" : last.at());
  }

  /** Sort every row first, then keep the first copy of each {@code event_id} in sorted order. */
  private List<StatusEvent> uniqueOfSorted(List<StatusEvent> transitions) {
    List<StatusEvent> all = new ArrayList<>(transitions);
    all.sort(ordering);
    Set<String> seen = new HashSet<>();
    List<StatusEvent> unique = new ArrayList<>();
    for (StatusEvent event : all) {
      if (seen.add(event.eventId())) {
        unique.add(event);
      }
    }
    return unique;
  }

  /**
   * {@code _dedup_transitions}, then the sort: the first row of an {@code event_id} wins, unless every row sharing the id is a reconstruction
   * seed, when the canonical-minimum row wins whatever the file order.
   */
  private List<StatusEvent> sortedUnique(List<StatusEvent> transitions) {
    Map<String, List<StatusEvent>> groups = new LinkedHashMap<>();
    for (StatusEvent event : transitions) {
      groups.computeIfAbsent(event.eventId(), id -> new ArrayList<>()).add(event);
    }
    List<StatusEvent> unique = new ArrayList<>();
    for (List<StatusEvent> rows : groups.values()) {
      boolean allSeeds = rows.size() > 1 && rows.stream().allMatch(StatusEvent::isSeed);
      unique.add(allSeeds ? rows.stream().min(Comparator.comparing(StatusEvent::seedKey, CodePoints::compare)).orElseThrow() : rows.getFirst());
    }
    unique.sort(ordering);
    return unique;
  }

  private static boolean isRollback(StatusEvent event) {
    boolean fromReview = event.fromLane() == Lane.IN_REVIEW || (event.fromLane() == Lane.FOR_REVIEW && event.reviewRef() != null);
    return fromReview && ROLLBACK_TARGETS.contains(event.toLane());
  }

  /**
   * {@code _arbitrate_event}: rollback-aware precedence, in two arms. Arm (ii) enforces {@code from_lane} continuity against EVERY setter
   * (10.4.2, #5967: a stale forward step after a cancel or after a reclaimed rework is dropped, not only one after a rollback), except
   * that a reconstruction seed which is not a rollback yields to the recorded live lifecycle (10.4.3), and a rollback or a forced event
   * always applies. It runs on the sorted, deduplicated rows, so the setter is the row the dedup kept.
   */
  private static boolean shouldApply(WpState current, StatusEvent event, Map<String, StatusEvent> byId) {
    if (current == null) {
      return true;
    }
    StatusEvent setter = byId.get(current.lastEventId());
    boolean setterIsRollback = setter != null && isRollback(setter);
    boolean eventIsRollback = isRollback(event);
    if (current.lastTransitionAt().equals(event.at())) {
      if (eventIsRollback && setter != null && !setterIsRollback) {
        return true;
      }
      if (setterIsRollback && !eventIsRollback) {
        return false;
      }
    }
    boolean setterIsDecision = setter != null && !(setter.isSeed() && !setterIsRollback);
    return !(setterIsDecision && !eventIsRollback && !event.force() && event.fromLane() != current.lane());
  }

  /** {@code _wp_state_from_event}; the projections are filled in afterwards. */
  private static WpState fold(StatusEvent event, WpState previous) {
    int prior = previous == null ? 0 : previous.forceCount();
    return new WpState(event.toLane(), event.at(), event.eventId(), prior + (event.force() ? 1 : 0), null, null, null);
  }

  /** The two read-only projections over the unique, sorted events: cancellation provenance, then implementer of record. */
  private static void project(List<StatusEvent> sorted, Map<String, WpState> states) {
    for (StatusEvent event : sorted) {
      WpState state = states.get(event.wpId());
      if (state == null) {
        continue;
      }
      if (event.toLane() == Lane.CANCELED && state.lane() == Lane.CANCELED) {
        states.put(
            event.wpId(),
            new WpState(state.lane(), state.lastTransitionAt(), state.lastEventId(), state.forceCount(), event.reason(), reasonSource(event), state.implementerOfRecord()));
      } else if (event.fromLane() == Lane.PLANNED && event.toLane() == Lane.CLAIMED && event.claimAgent() != null && !event.claimAgent().isEmpty()) {
        states.put(
            event.wpId(),
            new WpState(state.lane(), state.lastTransitionAt(), state.lastEventId(), state.forceCount(), state.cancellationReason(), state.reasonSource(), event.claimAgent()));
      }
    }
  }

  /** {@code _cancellation_reason_source}. */
  private static String reasonSource(StatusEvent event) {
    if (event.reasonSource() != null) {
      return event.reasonSource();
    }
    String reason = event.reason();
    if (PyText.isBlank(reason)) {
      return "synthetic";
    }
    for (String prefix : SYNTHETIC_PREFIXES) {
      if (reason.startsWith(prefix)) {
        return "synthetic";
      }
    }
    return "operator";
  }
}
