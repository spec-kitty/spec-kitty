package org.speckitty.missionstatus.application.query;

import java.util.Objects;
import java.util.function.Consumer;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.domain.redaction.Projector;

/**
 * The projection of a Mission head: the fields the oracle routes through its projector, and the three nullable dates of
 * {@code meta.json}. Extracted unchanged from {@code MissionStatusQueryService}. {@link OverviewReader} is its only caller, so the
 * list and every detail route share one projection by construction.
 */
final class MissionHeadProjection {

  /** The shape of an event id the projector serves: a ULID, anchored at the start as the oracle's pattern is. */
  private static final Pattern EVENT_ID = Pattern.compile("^[0-9A-HJKMNP-TV-Z]{26}$");

  private final LeakClasses leaks;
  private final Consumer<Diagnostic> diagnostics;

  MissionHeadProjection(LeakClasses leaks, Consumer<Diagnostic> diagnostics) {
    this.leaks = Objects.requireNonNull(leaks, "leaks");
    this.diagnostics = Objects.requireNonNull(diagnostics, "diagnostics");
  }

  /**
   * {@code acceptedAt}, {@code mergedAt} and {@code discardedAt} are projected strictly and are nullable (pre-merge fold J7, ruling 1 of
   * 2026-10-13): a value that is not an instant, or that is shaped like a path, an address or a secret, is served as null. This runs before
   * the overview is derived, so a junk value can neither be served nor decide the lifecycle status (an {@code accepted_at} of junk would
   * otherwise make a finished Mission {@code done}). The conformance oracle does the same, so the goldens agree.
   */
  MissionMeta withProjectedDates(MissionMeta meta) {
    Projector projector = new Projector(leaks);
    String mid8 = meta.missionId().mid8();
    return new MissionMeta(
        meta.missionId(),
        meta.slug(),
        meta.friendlyName(),
        meta.displayNumber(),
        meta.missionType(),
        meta.targetBranch(),
        meta.topology(),
        meta.createdAt(),
        instantOrNull(projector, meta.acceptedAt(), "acceptedAt", mid8),
        instantOrNull(projector, meta.mergedAt(), "mergedAt", mid8),
        instantOrNull(projector, meta.discardedAt(), "discardedAt", mid8),
        meta.hasBaseline());
  }

  /**
   * A served date-time: clean, and an instant with an offset (landing fold R-7: the contract's {@code date-time} needs one). Anything else
   * is null, and a value that was there and is dropped writes one {@code projection_refused} diagnostic.
   */
  private String instantOrNull(Projector projector, String value, String field, String mid8) {
    String clean = projector.strict(value, field, true);
    if (clean != null && Instants.hasOffset(clean)) {
      return clean;
    }
    if (value != null) {
      diagnostics.accept(new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, mid8, null));
    }
    return null;
  }

  /**
   * The fields the oracle routes through its projector; the Mission id is a validated ULID and needs no pass.
   *
   * @return the projected overview
   * @throws ProjectionError when a strict field is shaped like a path, an address or a secret
   */
  MissionOverview projected(MissionOverview o, String mid8) {
    Projector projector = new Projector(leaks);
    String slug = projector.strict(o.slug(), "slug", false);
    String friendlyName = projector.human(o.friendlyName(), "friendlyName");
    String missionType = projector.strict(o.missionType() == null || o.missionType().isEmpty() ? null : o.missionType(), "missionType", true);
    String targetBranch = projector.strict(o.targetBranch(), "targetBranch", false);
    String nextAction = projector.human(o.nextAction(), "nextAction");
    // Ledger ids are not shaped by the writer: a value that is not the contract's shape is nulled (AC-9g, nullable strict fields).
    // The meta dates were projected before the overview was derived (withProjectedDates), so they pass through unchanged.
    String lastEventId = projector.strict(o.lastEventId(), "lastEventId", true, EVENT_ID);
    String lastActivityAt = instantOrNull(projector, o.lastActivityAt(), "lastActivityAt", mid8);
    return new MissionOverview(
        o.missionId(),
        o.mid8(),
        slug,
        friendlyName,
        o.displayNumber(),
        missionType,
        targetBranch,
        o.topology(),
        o.createdAt(),
        o.statusLaneCounts(),
        o.wpTotal(),
        o.blockedCount(),
        o.progress(),
        o.lifecycleStatus(),
        o.acceptedAt(),
        o.mergedAt(),
        o.discardedAt(),
        lastEventId,
        lastActivityAt,
        o.eventCount(),
        o.streamCursor(),
        nextAction);
  }
}
