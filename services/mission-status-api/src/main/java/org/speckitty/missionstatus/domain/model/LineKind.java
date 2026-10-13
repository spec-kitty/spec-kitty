package org.speckitty.missionstatus.domain.model;

/** What one decoded physical line is. The domain never sees JSON text. */
public sealed interface LineKind {

  record Status(StatusEvent event) implements LineKind {}

  record Lifecycle(LifecycleEvent event) implements LineKind {}

  /**
   * An annotation row ({@code kind: annotation}) of one work package. It feeds the annotation pass: a work package with no transition is still
   * counted in {@code wpTotal} and in the progress denominator, in no lane count (operator ruling 2026-10-11).
   */
  record Annotation(String wpId) implements LineKind {
    public Annotation {
      java.util.Objects.requireNonNull(wpId, "wpId");
    }
  }

  /** Any other well-formed JSON object (decisions, retrospectives, unknown types). */
  record Ignored() implements LineKind {}

  record Blank() implements LineKind {}

  record Malformed(MalformedReason reason) implements LineKind {}
}
