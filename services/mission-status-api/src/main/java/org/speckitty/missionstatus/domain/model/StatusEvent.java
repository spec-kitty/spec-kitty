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
 *
 * <p>Three members carry what the resolved Work Package state reads (FR-020, data-model.md sections 4.2 and 4.8). {@code claimAgentSlot} is
 * the {@code policy_metadata.agent} a {@code planned -> claimed} event writes into the {@code agent} slot (written only when truthy, stored
 * as it is whatever its JSON type; null when the event writes nothing); {@code claimAgent} stays the text-only view the implementer
 * projection reads. {@code actorIdentity} is {@code actor_identity_str} of the row's actor: the text the snapshot {@code actor} slot holds,
 * which {@link Actor} (three projected handles) cannot give back. {@code reviewResult} is the populated {@code review_result} (null when the
 * row carries none). Each defaults from the older members, so the older constructors keep their meaning.
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
    String seedKey,
    SlotText claimAgentSlot,
    String actorIdentity,
    ReviewResultRecord reviewResult) {

  /**
   * The Python {@code str()} of a scalar slot value (an {@code agent} that is a number, a boolean and so on is stored as it is and shown as
   * its text). {@link #UNSHOWN} is a written slot whose text Java does not reproduce (a float, a list or an object); the oracle's handle
   * shape reads every such text as no handle except a float, so it serves null.
   */
  public record SlotText(String text) {
    public static final SlotText UNSHOWN = new SlotText(null);

    public static SlotText of(String text) {
      return new SlotText(Objects.requireNonNull(text, "text"));
    }
  }

  /** A real or seed transition without the resolved-state members (they default from the older members). */
  public StatusEvent(
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
    this(eventId, at, wpId, fromLane, toLane, force, reviewRef, reason, reasonSource, claimAgent, actor, seedKey, null, null, null);
  }

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
    if (claimAgentSlot == null && claimAgent != null && !claimAgent.isEmpty()) {
      claimAgentSlot = SlotText.of(claimAgent);
    }
    if (actorIdentity == null) {
      actorIdentity = identityOf(actor);
    }
  }

  private static String identityOf(Actor actor) {
    return actor.tool() != null ? actor.tool() : actor.role() != null ? actor.role() : "";
  }

  /** Whether this is a reconstruction seed, not a recorded decision. */
  public boolean isSeed() {
    return seedKey != null;
  }
}
