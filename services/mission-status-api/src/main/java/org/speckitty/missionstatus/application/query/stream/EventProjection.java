package org.speckitty.missionstatus.application.query.stream;

import java.util.Objects;
import java.util.Optional;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.LifecycleEvent;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;

/**
 * The only code that turns a raw ledger row into something a consumer can see. It holds the allow-list of the event stream: a work
 * package id must match the contract, a transition to a non-display lane is dropped, every instant must parse with an offset, and every
 * strict field goes through the same {@link Projector} as the overview, so a value that carries a path, an address or a secret is
 * refused. A refusal (for a change or for a truncation) writes one path-free {@code projection_refused} diagnostic and yields no event:
 * the frame is dropped and the stream stays open.
 *
 * <p>It runs on the consuming thread, after the raw signal was queued, so the feed itself is untouched by it.
 */
public final class EventProjection {

  /** The contract's {@code WpId}: a row whose work package id does not match is dropped, never repaired. */
  private static final Pattern WP_ID = Pattern.compile("^WP[0-9]{2,}$");

  /** The contract's bound of {@code eventId} and {@code wpId}; a longer id is no representable value. */
  private static final int MAX_ID_LENGTH = 64;

  private final LeakClasses leaks;
  private final Consumer<Diagnostic> diagnostics;

  public EventProjection(LeakClasses leaks, Consumer<Diagnostic> diagnostics) {
    this.leaks = Objects.requireNonNull(leaks, "leaks");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
  }

  /** The event of a forwarded change, or empty when the row is not a valid event (an invalid work package id, a non-display target lane) or its projection was refused. */
  public Optional<StreamEvent> project(Change change) {
    try {
      Projector projector = new Projector(leaks);
      return switch (change.kind()) {
        case LineKind.Status status -> status(change, status.event(), projector);
        case LineKind.Lifecycle lifecycle -> Optional.of(lifecycle(change, lifecycle.event(), projector));
        default -> throw new IllegalStateException("a change is a status or a lifecycle row");
      };
    } catch (ProjectionError refused) {
      diagnostics.accept(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, change.missionId().mid8(), null));
      return Optional.empty();
    }
  }

  /** The {@code log-truncated} event, or empty (with one diagnostic) when the Mission id cannot be represented. */
  public Optional<StreamEvent> project(FeedSignal.Truncated truncated) {
    try {
      Projector projector = new Projector(leaks);
      String missionId = projector.strict(truncated.missionId().value(), "missionId", false);
      return Optional.of(new StreamEvent.LogTruncated(missionId, truncated.reason().wire(), truncated.detectedAtOffset(), StreamCursor.start()));
    } catch (ProjectionError refused) {
      diagnostics.accept(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, truncated.missionId().mid8(), null));
      return Optional.empty();
    }
  }

  private Optional<StreamEvent> status(Change change, StatusEvent event, Projector projector) {
    if (!WP_ID.matcher(event.wpId()).matches() || !event.toLane().isDisplay()) {
      return Optional.empty();
    }
    String missionId = projector.strict(change.missionId().value(), "missionId", false);
    String eventId = boundedId(projector.strict(event.eventId(), "eventId", false), "eventId");
    String wpId = boundedId(event.wpId(), "wpId");
    String at = instant(event.at(), "at");
    return Optional.of(
        new StreamEvent.StatusTransition(
            missionId, eventId, wpId, displayLane(event.fromLane()), event.toLane().wire(), at, actor(event.actor(), projector), event.force(), change.cursor()));
  }

  private StreamEvent lifecycle(Change change, LifecycleEvent event, Projector projector) {
    String missionId = projector.strict(change.missionId().value(), "missionId", false);
    String eventId = boundedId(projector.strict(event.eventId(), "eventId", false), "eventId");
    String at = instant(event.at(), "timestamp");
    return new StreamEvent.Lifecycle(missionId, eventId, event.type(), at, change.cursor());
  }

  private static String displayLane(Lane lane) {
    return lane.isDisplay() ? lane.wire() : null;
  }

  /** The handles go through the strict projection (nullable): a token-, path- or e-mail-shaped handle is refused (pre-merge fold J8). */
  private static StreamEvent.ActorHandles actor(Actor actor, Projector projector) {
    return new StreamEvent.ActorHandles(
        projector.strict(actor.tool(), "actor.tool", true), projector.strict(actor.role(), "actor.role", true), projector.strict(actor.profile(), "actor.profile", true));
  }

  /**
   * A row's instant, served as written once it parses as one with an offset (the contract's {@code date-time}); a value that is not an
   * instant is not representable, so the event is dropped with one {@code projection_refused} diagnostic (pre-merge fold J6).
   */
  private static String instant(String value, String field) {
    if (value == null) {
      throw new ProjectionError(field, ProjectionError.Reason.MISSING);
    }
    // an instant with an offset: a value without one is no contract date-time (landing fold R-7)
    if (!Instants.hasOffset(value)) {
      throw new ProjectionError(field, ProjectionError.Reason.NOT_REPRESENTABLE);
    }
    return value;
  }

  private static String boundedId(String id, String field) {
    if (id.length() > MAX_ID_LENGTH) {
      throw new ProjectionError(field, ProjectionError.Reason.NOT_REPRESENTABLE);
    }
    return id;
  }
}
