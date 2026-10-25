package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * One lane transition. {@code at} is text and is compared as text. There is no logical-clock member: the reduction never reads
 * one. {@code reviewRef}, {@code reason}, {@code reasonSource} and {@code claimAgent} (the {@code policy_metadata.agent} of a
 * claim) are the members the fold and the two projections of {@code materialize_snapshot} read; each may be null. {@code actor} is who
 * made the transition (the stream's {@code status-transition} event carries it); it is never null, {@link Actor#NONE} when there is none.
 *
 * <p>{@code seedKey} is null for a real event. A reconstruction seed (spec-kitty-events 10.4.4: an actor identity starting {@code migration:})
 * carries here the canonical text of its row, the key by which the canonical-minimum of same-id seeds is chosen; the reducer reads a
 * non-null key as "this is a seed".
 */
public record StatusEvent(
    String eventId,
    String at,
    String wpId,
    Lane fromLane,
    Lane toLane,
    boolean force,
    String reviewRef,
    String reason,
    String reasonSource,
    String claimAgent,
    Actor actor,
    String seedKey) {

  /** A real (non-seed) transition. */
  public StatusEvent(
      String eventId, String at, String wpId, Lane fromLane, Lane toLane, boolean force, String reviewRef, String reason, String reasonSource, String claimAgent, Actor actor) {
    this(eventId, at, wpId, fromLane, toLane, force, reviewRef, reason, reasonSource, claimAgent, actor, null);
  }

  /** A transition with no recorded actor. */
  public StatusEvent(
      String eventId, String at, String wpId, Lane fromLane, Lane toLane, boolean force, String reviewRef, String reason, String reasonSource, String claimAgent) {
    this(eventId, at, wpId, fromLane, toLane, force, reviewRef, reason, reasonSource, claimAgent, Actor.NONE);
  }

  public StatusEvent {
    Objects.requireNonNull(eventId, "eventId");
    Objects.requireNonNull(at, "at");
    Objects.requireNonNull(wpId, "wpId");
    Objects.requireNonNull(fromLane, "fromLane");
    Objects.requireNonNull(toLane, "toLane");
    Objects.requireNonNull(actor, "actor");
  }

  /** Whether this is a reconstruction seed, not a recorded decision. */
  public boolean isSeed() {
    return seedKey != null;
  }
}
