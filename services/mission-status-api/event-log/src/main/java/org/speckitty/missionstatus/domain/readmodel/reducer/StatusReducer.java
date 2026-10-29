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
 * The port of the reduction {@code materialize_snapshot} runs: {@code spec_kitty_events.diary.reduce_parsed} 10.4.6 plus the
 * cancellation-provenance and implementer projections of {@code reducer.py}. Steps: (1) deduplicate by {@code event_id}, first occurrence
 * in file order wins, except that rows which are all reconstruction seeds keep the canonical-minimum one (the two projections sort first,
 * then deduplicate); (2) sort by the injected ordering; (3) fold with rollback-aware precedence; (4) a separate annotation pass; (5) the
 * display lane counts (taken from the snapshot). It is pure: no clock, no I/O, no framework.
 *
 * <p>Ported from 10.4.0 to 10.4.6 (#5967, #4941, #6058, #6061, #87): arm (ii) of the precedence drops an unforced, non-rollback transition whose
 * {@code from_lane} differs from the lane in force for every setter; the reconstruction-seed exemptions (a rollback seed must continue the lane
 * in force unless it meets its bare sibling approval, an applied rollback seed yields to a real event); the same-id seed dedup; and the order
 * in which a real {@code approved -> X} follows its same-{@code at} approval. The 10.4.3 seed payload fold (a seed that loses arm (ii) still fills the claim slots and {@code review_result} that no real event
 * wrote) is not ported, because it writes only slots this service never serves; it touches none of the lane-setter slots.
 */
public final class StatusReducer {

  /**
   * The {@code spec-kitty-events} release whose {@code reduce_parsed} this class is coupled to. {@code ManifestCouplingTest} holds it
   * equal to the version the conformance goldens were generated with, so a {@code uv.lock} bump of the oracle cannot land without a port review.
   *
   * <p>Advanced to 10.5.1 as a pin-only step (spec-kitty#6261, operator ruling): the 10.5.1 change to {@code _order_transitions} — a
   * non-seed departure from {@code approved} lifted to sort after the clock-ahead approval it followed (spec-kitty#4941,
   * spec-kitty-events#102) — is NOT yet ported here. No conformance golden exercises that case, so the goldens and this coupling stay
   * green at the bumped pin; the reduction below still implements the 10.4.6-level behaviour described above. The behaviour port (plus a
   * fixture that exercises the clock-ahead case) is tracked by spec-kitty#6268.
   *
   * <p>Advanced to 11.0.0 after a port review (spec-kitty#6399): between 10.5.1 and 11.0.0 the ordering, precedence and fold of
   * {@code diary.reduce_parsed} are unchanged. The {@code diary} changes are the subtask vocabulary of {@code parse_diary} (the
   * line codec follows the CLI partition, not {@code parse_diary}), a docstring and a comment; the {@code status} module changes are on the
   * Lamport path ({@code status_event_sort_key}, unclocked envelopes), which this class does not port. All 88 conformance goldens are
   * byte-identical under 11.0.0. The 10.5.1 gap above is unchanged.
   *
   * <p>Advanced to 11.3.0 after a port review (spec-kitty#6602): {@code diary.py} and {@code status.py} are byte-identical between
   * 11.0.0 and 11.3.0, so the ordering, precedence and fold of {@code diary.reduce_parsed} are unchanged. The releases add the
   * {@code decision_significance} models, a producer-registry row and the {@code cloudevents} package, none of which this class reads.
   * Every conformance golden is byte-identical under 11.3.0; only the manifest's {@code specKittyEventsVersion} moved. The 10.5.1 gap above
   * is unchanged.
   */
  public static final String PORTED_EVENTS_VERSION = "11.3.0";

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
      if (shouldApply(current, event, byId, sorted)) {
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
    return approvedFollowsItsApproval(unique);
  }

  /**
   * {@code _order_transitions} (10.4.6, spec-kitty-events#87): a real {@code approved -> X} that shares its {@code at} with a real
   * {@code -> approved} of the same work package sorts after every other row of that {@code at}, whatever its {@code event_id}.
   */
  private static List<StatusEvent> approvedFollowsItsApproval(List<StatusEvent> sorted) {
    Set<String> approvals = new HashSet<>();
    for (StatusEvent event : sorted) {
      if (event.toLane() == Lane.APPROVED && event.fromLane() != Lane.APPROVED && !event.isSeed()) {
        approvals.add(event.wpId() + '\0' + event.at());
      }
    }
    if (approvals.isEmpty()) {
      return sorted;
    }
    List<StatusEvent> result = new ArrayList<>(sorted.size());
    int start = 0;
    while (start < sorted.size()) {
      int end = start;
      while (end < sorted.size() && sorted.get(end).at().equals(sorted.get(start).at())) {
        end++;
      }
      List<StatusEvent> late = new ArrayList<>();
      for (StatusEvent event : sorted.subList(start, end)) {
        if (event.fromLane() == Lane.APPROVED && !event.isSeed() && approvals.contains(event.wpId() + '\0' + event.at())) {
          late.add(event);
        } else {
          result.add(event);
        }
      }
      result.addAll(late);
      start = end;
    }
    return result;
  }

  private static boolean isRollback(StatusEvent event) {
    boolean fromReview = event.fromLane() == Lane.IN_REVIEW || (event.fromLane() == Lane.FOR_REVIEW && event.reviewRef() != null);
    return fromReview && ROLLBACK_TARGETS.contains(event.toLane());
  }

  /**
   * {@code _arbitrate_event}: rollback-aware precedence, in two arms. Arm (i) is the same-{@code at} verdict (a rollback beats a forward setter; a
   * forward event never beats a rollback setter), arm (ii) enforces {@code from_lane} continuity against EVERY setter (10.4.2, #5967), unless the
   * event is exempt. Reconstruction seeds are narrowed by 10.4.6 (#6061, rules R1 to R3): a rollback seed beats a forward setter only at its bare
   * sibling approval and must otherwise continue the lane in force; an applied rollback seed yields to a real event; a seed never rides the
   * forward-seed-setter exemption. It runs on the sorted, deduplicated rows, so the setter is the row the dedup kept.
   */
  private static boolean shouldApply(WpState current, StatusEvent event, Map<String, StatusEvent> byId, List<StatusEvent> all) {
    if (current == null) {
      return true;
    }
    StatusEvent setter = byId.get(current.lastEventId());
    if (current.lastTransitionAt().equals(event.at())) {
      Boolean sameAt = sameTimestampVerdict(event, setter, all);
      if (sameAt != null) {
        return sameAt;
      }
    }
    return setter == null || event.force() || event.fromLane() == current.lane() || continuityExempt(event, setter, all);
  }

  /** Arm (i): {@code TRUE} applies, {@code FALSE} drops, {@code null} abstains and leaves the event to arm (ii). */
  private static Boolean sameTimestampVerdict(StatusEvent event, StatusEvent setter, List<StatusEvent> all) {
    if (setter == null) {
      return null;
    }
    if (isRollback(event)) {
      if (isRollback(setter)) {
        return null;
      }
      return !event.isSeed() || isBareSibling(setter, event, all) ? Boolean.TRUE : null;
    }
    return isRollback(setter) && !yieldsToReal(setter, event, all) ? Boolean.FALSE : null;
  }

  /** Arm (ii) exemptions ({@code _continuity_exempt}): whether the event may break {@code from_lane} continuity. */
  private static boolean continuityExempt(StatusEvent event, StatusEvent setter, List<StatusEvent> all) {
    if (isRollback(event)) {
      return !event.isSeed() || isRollbackSeed(setter) || isBareSibling(setter, event, all);
    }
    if (event.isSeed()) {
      return false;
    }
    return (setter.isSeed() && !isRollback(setter)) || yieldsToReal(setter, event, all);
  }

  private static boolean isRollbackSeed(StatusEvent event) {
    return event.isSeed() && isRollback(event);
  }

  /**
   * {@code _is_bare_sibling}: a non-rollback {@code -> approved} that left the lane the rollback seed left, and that no real event leaving
   * {@code approved} follows in {@code (at, event_id)} order.
   */
  private static boolean isBareSibling(StatusEvent approval, StatusEvent seed, List<StatusEvent> all) {
    if (isRollback(approval) || approval.toLane() != Lane.APPROVED || approval.fromLane() != seed.fromLane()) {
      return false;
    }
    for (StatusEvent other : all) {
      if (other.wpId().equals(approval.wpId())
          && other.fromLane() == Lane.APPROVED
          && !other.isSeed()
          && (CodePoints.compare(other.at(), approval.at()) > 0
              || (other.at().equals(approval.at()) && CodePoints.compare(other.eventId(), approval.eventId()) > 0))) {
        return false;
      }
    }
    return true;
  }

  /** {@code _yields_to_real}: an applied rollback seed holds the lane only against its bare sibling and against other seeds. */
  private static boolean yieldsToReal(StatusEvent setter, StatusEvent event, List<StatusEvent> all) {
    return isRollbackSeed(setter) && !event.isSeed() && !isBareSibling(event, setter, all);
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
