package org.speckitty.missionstatus.application.query;

import java.util.Objects;
import java.util.Optional;
import java.util.function.Consumer;
import org.speckitty.missionstatus.application.query.port.out.MissionEventSource;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;

/**
 * The composition handle of the query side's read path: the probe-free {@link MissionLookup}, the {@link OverviewReader} and so the one
 * {@link ProjectionCache}. It is public so that {@code config} can build it once and hand the same instance to every service; the
 * lookup, the reader and the cache stay package-private, so no adapter can name them. Its operations are package-level for the same
 * reason.
 */
public final class MissionReadModel {

  private final MissionLookup lookup;
  private final OverviewReader reader;

  /** A read model with a cache of its own. */
  public MissionReadModel(MissionEventSource source, Consumer<Diagnostic> diagnostics, LeakClasses leaks) {
    this(source, diagnostics, leaks, new ProjectionCache(new StatusReducer(new AtThenEventId())));
  }

  /** A read model over a given cache (the seven-argument service constructor injects a reducer ordering this way). */
  MissionReadModel(MissionEventSource source, Consumer<Diagnostic> diagnostics, LeakClasses leaks, ProjectionCache cache) {
    this.lookup = new MissionLookup(Objects.requireNonNull(source, "source"));
    this.reader = new OverviewReader(source, diagnostics, cache, new MissionHeadProjection(leaks, diagnostics));
  }

  /** The probe-free lookup of a Mission by id. */
  MissionLookup.Scan find(MissionId id) {
    return lookup.find(id);
  }

  /** Whether a second readable directory carries the id of the match (the continuation of {@link #find}). */
  boolean hasDuplicate(MissionLookup.Scan scan) {
    return lookup.hasDuplicate(scan);
  }

  /** The projected head of the Mission, or empty when a row leaves it out. */
  Optional<MissionHead> head(MissionRef ref) {
    return reader.head(ref);
  }

  /** The overview of the Mission: the head's overview. */
  Optional<MissionOverview> overview(MissionRef ref) {
    return reader.overview(ref);
  }

  ProjectionCache cache() {
    return reader.cache();
  }
}
