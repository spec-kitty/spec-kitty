package org.speckitty.missionstatus.domain.model;

import java.util.Map;
import java.util.Objects;

/** What one decoded physical line is. The domain never sees JSON text. */
public sealed interface LineKind {

  record Status(StatusEvent event) implements LineKind {}

  record Lifecycle(LifecycleEvent event) implements LineKind {}

  /**
   * An annotation row ({@code kind: annotation}) of one work package. It feeds the annotation pass: a work package with no transition is still
   * counted in {@code wpTotal} and in the progress denominator, in no lane count (operator ruling 2026-10-11), and the decoded {@link Delta}
   * is folded into the resolved state (FR-020).
   *
   * <p>The identity of an annotation line is its work package: {@code equals} and {@code hashCode} read {@code wpId} only, as they did before
   * the payload was added, so the payload ({@code at}, {@code eventId}, {@code actorIdentity}, {@code delta}) is carried, not compared.
   *
   * @param at the row's {@code at}, {@code str()}-coerced by the decoder, the sort key of the annotation pass
   * @param eventId the row's ULID, the tie-break of that sort
   * @param actorIdentity {@code actor_identity_str} of the row's actor, the {@code actor} of a work package known only from annotations
   */
  record Annotation(String wpId, String at, String eventId, String actorIdentity, Delta delta) implements LineKind {

    /** The delta of {@code WPInnerStateDelta} as far as the served members read it. */
    public record Delta(boolean releaseRuntimeClaim, Map<String, StatusEvent.SlotText> replaceSlots, Map<String, Lane> subtasks, ReviewOverrideRecord review) {

      /** The delta of an annotation that touches no served slot. */
      public static final Delta NONE = new Delta(false, Map.of(), null, null);

      public Delta {
        replaceSlots = Map.copyOf(Objects.requireNonNull(replaceSlots, "replaceSlots"));
        subtasks = subtasks == null ? null : java.util.Collections.unmodifiableMap(new java.util.LinkedHashMap<>(subtasks));
      }
    }

    public Annotation {
      Objects.requireNonNull(wpId, "wpId");
      Objects.requireNonNull(at, "at");
      Objects.requireNonNull(eventId, "eventId");
      Objects.requireNonNull(actorIdentity, "actorIdentity");
      Objects.requireNonNull(delta, "delta");
    }

    /** An annotation of {@code wpId} with no payload. */
    public Annotation(String wpId) {
      this(wpId, "", "", "", Delta.NONE);
    }

    @Override
    public boolean equals(Object other) {
      return other instanceof Annotation annotation && wpId.equals(annotation.wpId);
    }

    @Override
    public int hashCode() {
      return wpId.hashCode();
    }
  }

  /** Any other well-formed JSON object (decisions, retrospectives, unknown types). */
  record Ignored() implements LineKind {}

  record Blank() implements LineKind {}

  record Malformed(MalformedReason reason) implements LineKind {}
}
