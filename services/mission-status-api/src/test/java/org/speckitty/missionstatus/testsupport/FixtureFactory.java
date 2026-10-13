package org.speckitty.missionstatus.testsupport;

import java.time.Instant;
import java.util.List;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;

/**
 * Realises a {@link FixtureSpec} in memory and builds the real {@link MissionStatusQueryService} over it, with a fixed clock, a recording
 * diagnostics consumer and a deterministic scheduled executor that it owns. The result exposes the inbound port and the source; the
 * recorder and the executor are reachable only through {@link FixtureHandles}.
 */
public final class FixtureFactory {

  /** The built fixture. */
  public record Built(MissionStatusQuery query, InMemoryMissionEventSource source, FixtureHandles handles) implements Fixture {

    @Override
    public List<Diagnostic> diagnostics() {
      return handles.diagnostics();
    }
  }

  private FixtureFactory() {}

  public static Built build(FixtureSpec spec) {
    return build(spec, StreamSettings.defaults());
  }

  public static Built build(FixtureSpec spec, StreamSettings settings) {
    InMemoryMissionEventSource source = InMemoryMissionEventSource.from(spec);
    FixtureHandles handles = new FixtureHandles(new MutableClock(Instant.parse("2026-10-01T12:00:00Z")));
    MissionStatusQuery query = new MissionStatusQueryService(source, handles.clock(), handles.recorder(), handles.executor(), settings, leakClasses());
    return new Built(query, source, handles);
  }

  /** The leak patterns of the oracle, written out for tests (the service reads them from the classpath in production). */
  public static LeakClasses leakClasses() {
    return LeakFixtures.python();
  }
}
