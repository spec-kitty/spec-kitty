package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.stream.StreamSettings;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.testsupport.DeterministicExecutor;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.Rows;

/** The composition handle: one lookup, one head derivation and one cache, however many consumers hold it. */
class MissionReadModelTest {

  private static final String CREATED = "2026-09-02T10:00:00+00:00";

  private final List<Diagnostic> diagnostics = Collections.synchronizedList(new ArrayList<>());
  private final InMemoryMissionEventSource source =
      InMemoryMissionEventSource.from(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, CREATED, Fx.twoMoves("WP01", 1)), Fx.mission("beta", Rows.BETA_ID, CREATED, null)));
  private final MissionReadModel model = new MissionReadModel(source, diagnostics::add, LeakPatternsFile.load());

  private MissionStatusQueryService serviceOver(MissionReadModel shared) {
    return new MissionStatusQueryService(
        source, Clock.fixed(Instant.parse("2026-10-01T12:00:00Z"), ZoneOffset.UTC), diagnostics::add, new DeterministicExecutor(), StreamSettings.defaults(), LeakPatternsFile.load(), shared);
  }

  @Test
  void twoConsumersOfOneInstanceReduceOneLedgerOnce() {
    model.head(new MissionRef("alpha"));
    model.overview(new MissionRef("alpha"));
    assertThat(model.cache().reductions()).as("the second derivation of alpha is a cache hit").isEqualTo(1);

    serviceOver(model).missions(new PageRequest(null, null));

    assertThat(model.cache().reductions()).as("the service reduces beta only; alpha is served from the shared cache").isEqualTo(2);
  }

  @Test
  void aServiceBuiltFromTheModelServesFromTheModelsCache() {
    MissionStatusQueryService service = serviceOver(model);

    assertThat(service.cache()).isSameAs(model.cache());
  }

  @Test
  void theSixArgumentServiceBuildsItsOwnModelAndCache() {
    MissionStatusQueryService first = serviceOver(model);
    MissionStatusQueryService own =
        new MissionStatusQueryService(source, Clock.systemUTC(), diagnostics::add, new DeterministicExecutor(), StreamSettings.defaults(), LeakPatternsFile.load());

    assertThat(own.cache()).isNotSameAs(first.cache());
  }

  @Test
  void theSevenArgumentConstructorOverAGivenCacheKeepsThatCache() {
    ProjectionCache given = new ProjectionCache(new StatusReducer(new AtThenEventId()));

    MissionStatusQueryService service =
        new MissionStatusQueryService(source, Clock.systemUTC(), diagnostics::add, new DeterministicExecutor(), StreamSettings.defaults(), LeakPatternsFile.load(), given);
    MissionReadModel overGiven = new MissionReadModel(source, diagnostics::add, LeakPatternsFile.load(), given);

    assertThat(service.cache()).isSameAs(given);
    assertThat(overGiven.cache()).isSameAs(given);
  }

  @Test
  void findAndTheContinuationAreTheLookupsAnswers() {
    MissionLookup.Scan scan = model.find(new MissionId(Rows.ALPHA_ID));

    assertThat(scan.found().ref()).isEqualTo(new MissionRef("alpha"));
    assertThat(model.hasDuplicate(scan)).isFalse();
  }
}
