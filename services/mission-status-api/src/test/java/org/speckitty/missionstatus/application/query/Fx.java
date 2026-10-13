package org.speckitty.missionstatus.application.query;

import java.time.Instant;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.testsupport.DeterministicExecutor;
import org.speckitty.missionstatus.testsupport.FixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureHandles;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource;
import org.speckitty.missionstatus.testsupport.MutableClock;
import org.speckitty.missionstatus.testsupport.Rows;

/** Test wiring for the application package: the real service and the package-private seams around it. */
public final class Fx {

  public static final String T0 = "2026-09-01T10:00:00Z";
  public static final String T1 = "2026-09-01T10:05:00Z";
  public static final String T2 = "2026-09-01T10:10:00Z";

  public final InMemoryMissionEventSource source;
  public final FixtureHandles handles;
  public final MissionStatusQueryService service;
  public final DeterministicExecutor executor;
  final ProjectionCache cache;
  public final MutableClock clock;

  public Fx(FixtureSpec spec) {
    this(spec, StreamSettings.defaults());
  }

  public Fx(FixtureSpec spec, StreamSettings settings) {
    FixtureFactory.Built built = FixtureFactory.build(spec, settings);
    this.source = built.source();
    this.handles = built.handles();
    this.executor = handles.executor();
    this.clock = handles.clock();
    this.cache = ((MissionStatusQueryService) built.query()).cache();
    this.service = (MissionStatusQueryService) built.query();
  }

  /** A Mission directory with a standard meta and the given ledger text (null: no ledger file). */
  public static FixtureSpec.Mission mission(String name, String missionId, String createdAt, String ledger) {
    return FixtureSpec.Mission.of(name, Rows.meta(missionId, name, createdAt), ledger);
  }

  /** Two lane rows of one work package: planned, claimed, then in progress. */
  public static String twoMoves(String wp, int first) {
    return Rows.status(Rows.id(first), T0, wp, "planned", "claimed") + Rows.status(Rows.id(first + 1), T1, wp, "claimed", "in_progress");
  }

  public int reductions() {
    return cache.reductions();
  }

  public static Instant instant(String text) {
    return Instant.parse(text);
  }
}
