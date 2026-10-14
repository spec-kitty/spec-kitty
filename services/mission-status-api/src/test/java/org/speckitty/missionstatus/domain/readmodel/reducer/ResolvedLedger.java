package org.speckitty.missionstatus.domain.readmodel.reducer;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.ReviewOverrideRecord;
import org.speckitty.missionstatus.domain.model.ReviewResultRecord;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusEvent.SlotText;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;

/**
 * A hand-built ledger of already decoded lines for the reducer tests (the codec is out of reach of this package by rule 11c, so these
 * fixtures are domain objects; the end-to-end text ledgers are in {@code LedgerLineDecoderResolvedStateTest}).
 */
final class ResolvedLedger {

  private static final String SEED_ACTOR = "migration:backfill";

  private final List<LedgerLine> lines = new ArrayList<>();

  static ResolvedLedger ledger() {
    return new ResolvedLedger();
  }

  private ResolvedLedger add(LineKind kind, String eventType, HistoryRow history) {
    lines.add(new LedgerLine(lines.size() + 1L, "0".repeat(64), 10, kind, eventType, history));
    return this;
  }

  /** A real transition by {@code actor} (its identity is the actor text). */
  ResolvedLedger move(String id, String at, String wp, Lane from, Lane to, String actor) {
    return transition(new StatusEvent(id, at, wp, from, to, false, null, null, null, null, Actor.ofText(actor), null, null, actor, null));
  }

  ResolvedLedger forced(String id, String at, String wp, Lane from, Lane to, String actor) {
    return transition(new StatusEvent(id, at, wp, from, to, true, null, null, null, null, Actor.ofText(actor), null, null, actor, null));
  }

  /** A {@code planned -> claimed} whose sidecar writes {@code agent}. */
  ResolvedLedger claim(String id, String at, String wp, String actor, SlotText agent) {
    return transition(new StatusEvent(id, at, wp, Lane.PLANNED, Lane.CLAIMED, false, null, null, null, null, Actor.ofText(actor), null, agent, actor, null));
  }

  /** A transition that carries a populated review result. */
  ResolvedLedger judged(String id, String at, String wp, Lane from, Lane to, String actor, ReviewResultRecord result) {
    return transition(new StatusEvent(id, at, wp, from, to, false, null, null, null, null, Actor.ofText(actor), null, null, actor, result));
  }

  /** A reconstruction seed ({@code migration:} actor) carrying an optional claim agent and an optional review result. */
  ResolvedLedger seed(String id, String at, String wp, Lane from, Lane to, SlotText agent, ReviewResultRecord result) {
    return transition(new StatusEvent(id, at, wp, from, to, false, null, null, null, null, Actor.ofText(SEED_ACTOR), "key-" + id, agent, SEED_ACTOR, result));
  }

  ResolvedLedger transition(StatusEvent event) {
    return add(new LineKind.Status(event), null, null);
  }

  /** An annotation row. */
  ResolvedLedger annotation(String wp, String at, String eventId, String actorIdentity, LineKind.Annotation.Delta delta) {
    return add(new LineKind.Annotation(wp, at, eventId, actorIdentity, delta), null, null);
  }

  /** A history row (the codec attaches one to every line with a {@code to_lane} key and a string {@code wp_id}). */
  ResolvedLedger history(HistoryRow row) {
    return add(new LineKind.Ignored(), null, row);
  }

  /** A line of the given kind that carries an event type. */
  ResolvedLedger typed(String eventType) {
    return add(new LineKind.Ignored(), eventType, null);
  }

  StatusSnapshot reduce() {
    return new StatusReducer(new AtThenEventId()).reduceLines(lines);
  }

  // ---- delta builders ------------------------------------------------------------------------------------------------------

  static LineKind.Annotation.Delta replace(String slot, String value) {
    return new LineKind.Annotation.Delta(false, Map.of(slot, SlotText.of(value)), null, null);
  }

  static LineKind.Annotation.Delta replace(Map<String, SlotText> slots) {
    return new LineKind.Annotation.Delta(false, slots, null, null);
  }

  static LineKind.Annotation.Delta release() {
    return new LineKind.Annotation.Delta(true, Map.of(), null, null);
  }

  static LineKind.Annotation.Delta releaseAndReplace(String slot, String value) {
    return new LineKind.Annotation.Delta(true, Map.of(slot, SlotText.of(value)), null, null);
  }

  static LineKind.Annotation.Delta subtasks(Map<String, Lane> subtasks) {
    return new LineKind.Annotation.Delta(false, Map.of(), subtasks, null);
  }

  static LineKind.Annotation.Delta override(String at, String actor, String wpId, String reason) {
    return new LineKind.Annotation.Delta(false, Map.of(), null, new ReviewOverrideRecord(at, actor, wpId, reason));
  }

  static HistoryRow historyRow(String wp, String id, String at, String from, String to) {
    return new HistoryRow(wp, id, at, from, to, Actor.NONE, false, null, null);
  }
}
