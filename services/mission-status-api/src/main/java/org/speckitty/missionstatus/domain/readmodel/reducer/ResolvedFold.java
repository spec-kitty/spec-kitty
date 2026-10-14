package org.speckitty.missionstatus.domain.readmodel.reducer;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Assignment;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusEvent.SlotText;
import org.speckitty.missionstatus.domain.model.WpResolved;
import org.speckitty.missionstatus.domain.readmodel.derive.HistoryOrder;

/**
 * The slots {@code reduce_parsed} 10.4.4 keeps beside the lane and that the detail routes serve (FR-020, data-model.md sections 3 and 4):
 * the claim {@code agent}, the {@code review_result}, the annotation replace slots, the subtask map, the review override and the
 * {@code actor} of the latest applied change. {@link StatusReducer} feeds it in the order of the Python fold: {@link #applied} for each
 * transition the arbitration applies, {@link #foldLosingSeed} for a reconstruction seed that lost on continuity, then {@link #annotate}
 * for each annotation in sort order. The per-slot provenance of the transition fold ({@code _SlotProvenance}) lives only here and only
 * for the two slots a seed can write that are served; it is never read by the annotation pass.
 */
final class ResolvedFold {

  /** The transition-written slots that are served, as bits of a mask (an {@code EnumSet} per event costs more than the fold itself on a cold JVM). */
  private static final int AGENT = 1;

  private static final int REVIEW_RESULT = 2;

  /** One work package's slots. An unset {@code agent}/{@code verdict} is absent; a set one holding null is the explicit {@code None}. */
  private static final class Slots {
    private String actorIdentity;
    private boolean agentSet;
    private SlotText agent;
    private boolean verdictSet;
    private ReviewResultRecord verdict;
    private final Map<String, SlotText> replaced = new HashMap<>();
    private final Map<String, Lane> subtasks = new LinkedHashMap<>();
    private ReviewOverrideRecord override;
    private int real;
    private int seed;

    private Slots(String actorIdentity) {
      this.actorIdentity = actorIdentity;
    }
  }

  private final Map<String, Slots> byWp = new LinkedHashMap<>();

  /** {@code _wp_state_from_event} and {@code _record_applied_event}: the event applied, so its writes land and its provenance is recorded. */
  void applied(StatusEvent event) {
    Slots slots = byWp.computeIfAbsent(event.wpId(), id -> new Slots(event.actorIdentity()));
    slots.actorIdentity = event.actorIdentity();
    int wrote = 0;
    if (claims(event)) {
      slots.agent = event.claimAgentSlot();
      slots.agentSet = true;
      wrote |= AGENT;
    }
    if (event.reviewResult() != null || event.fromLane() == Lane.IN_REVIEW) {
      slots.verdict = event.reviewResult();
      slots.verdictSet = true;
      wrote |= REVIEW_RESULT;
    }
    if (event.isSeed() && !StatusReducer.isRollback(event)) {
      slots.seed |= wrote;
      return;
    }
    slots.real |= wrote;
    slots.seed &= ~wrote;
  }

  /** {@code _fold_losing_seed} (A4, spec-kitty#6058): a seed that lost on continuity still fills the slots no real event wrote. */
  void foldLosingSeed(StatusEvent event) {
    Slots slots = byWp.get(event.wpId());
    if (claims(event) && (slots.real & AGENT) == 0) {
      slots.agent = event.claimAgentSlot();
      slots.agentSet = true;
      slots.seed |= AGENT;
    }
    if (event.reviewResult() != null && (slots.real & REVIEW_RESULT) == 0) {
      slots.verdict = event.reviewResult();
      slots.verdictSet = true;
      slots.seed |= REVIEW_RESULT;
    }
  }

  /** Whether the event is a {@code planned -> claimed} whose sidecar writes the {@code agent} slot ({@code _claim_sidecar_writes}). */
  private static boolean claims(StatusEvent event) {
    return event.fromLane() == Lane.PLANNED && event.toLane() == Lane.CLAIMED && event.claimAgentSlot() != null;
  }

  /** Whether the work package has an entry from a transition (the annotation pass seeds one for a work package that has none). */
  boolean knows(String wpId) {
    return byWp.containsKey(wpId);
  }

  /** {@code _apply_annotation_delta}: release first, then the replace slots, the per-id subtask merge and the override. */
  void annotate(LineKind.Annotation annotation) {
    Slots slots = byWp.computeIfAbsent(annotation.wpId(), id -> new Slots(annotation.actorIdentity()));
    LineKind.Annotation.Delta delta = annotation.delta();
    if (delta.releaseRuntimeClaim()) {
      slots.agent = null;
      slots.agentSet = true;
    }
    for (Map.Entry<String, SlotText> replace : delta.replaceSlots().entrySet()) {
      if (replace.getKey().equals("agent")) {
        slots.agent = replace.getValue();
        slots.agentSet = true;
      } else {
        slots.replaced.put(replace.getKey(), replace.getValue());
      }
    }
    if (delta.subtasks() != null) {
      slots.subtasks.putAll(delta.subtasks());
    }
    if (delta.review() != null) {
      slots.override = delta.review().releaseSentinel() ? null : delta.review();
    }
  }

  /**
   * The resolved state of every work package the fold met, then of every work package that only has history rows. {@code history} holds the
   * rows of each work package in ledger order; this orders them (the oracle keeps every {@code to_lane} row, de-duplicated by nothing).
   */
  Map<String, WpResolved> resolve(Map<String, List<HistoryRow>> history) {
    Map<String, WpResolved> resolved = new LinkedHashMap<>();
    for (Map.Entry<String, Slots> entry : byWp.entrySet()) {
      resolved.put(entry.getKey(), resolved(entry.getValue(), history.getOrDefault(entry.getKey(), List.of())));
    }
    for (Map.Entry<String, List<HistoryRow>> entry : history.entrySet()) {
      resolved.computeIfAbsent(entry.getKey(), id -> new WpResolved(Assignment.EMPTY, Map.of(), null, null, Actor.NONE, HistoryOrder.order(entry.getValue())));
    }
    return resolved;
  }

  private static WpResolved resolved(Slots slots, List<HistoryRow> history) {
    Assignment assignment =
        new Assignment(
            slots.agentSet && slots.agent != null ? slots.agent.text() : null,
            replaced(slots, "assignee"),
            replaced(slots, "role"),
            replaced(slots, "agent_profile"),
            replaced(slots, "agent_profile_version"),
            replaced(slots, "model"),
            replaced(slots, "provider"));
    return new WpResolved(
        assignment, slots.subtasks, slots.verdictSet ? slots.verdict : null, slots.override, Actor.ofText(slots.actorIdentity), HistoryOrder.order(history));
  }

  private static String replaced(Slots slots, String name) {
    SlotText value = slots.replaced.get(name);
    return value == null ? null : value.text();
  }
}
