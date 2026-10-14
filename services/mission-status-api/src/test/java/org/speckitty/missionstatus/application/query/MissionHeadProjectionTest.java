package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionMeta;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.domain.redaction.ProjectionError;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.Rows;

/** The head projection moved out of the service unchanged: the dates of {@code meta.json} and the strict and human fields of the overview. */
class MissionHeadProjectionTest {

  private static final String CREATED = "2026-09-02T10:00:00+00:00";

  private final List<Diagnostic> diagnostics = Collections.synchronizedList(new ArrayList<>());
  private final MissionHeadProjection projection = new MissionHeadProjection(LeakPatternsFile.load(), diagnostics::add);

  private static MissionMeta metaWith(String members) {
    FixtureSpec spec = FixtureSpec.of(FixtureSpec.Mission.of("alpha", Rows.metaWith(Rows.ALPHA_ID, "alpha", CREATED, members), null));
    return InMemoryMissionEventSource.from(spec).readMeta(new MissionRef("alpha"));
  }

  private MissionOverview cleanOverview() {
    FixtureSpec spec = FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, CREATED, Fx.twoMoves("WP01", 1)));
    var reader = new OverviewReader(InMemoryMissionEventSource.from(spec), diagnostics::add, new ProjectionCache(new StatusReducer(new AtThenEventId())), projection);
    return reader.overview(new MissionRef("alpha")).orElseThrow();
  }

  private static MissionOverview withSlug(MissionOverview o, String slug) {
    return new MissionOverview(
        o.missionId(), o.mid8(), slug, o.friendlyName(), o.displayNumber(), o.missionType(), o.targetBranch(), o.topology(), o.createdAt(), o.statusLaneCounts(),
        o.wpTotal(), o.blockedCount(), o.progress(), o.lifecycleStatus(), o.acceptedAt(), o.mergedAt(), o.discardedAt(), o.lastEventId(), o.lastActivityAt(),
        o.eventCount(), o.streamCursor(), o.nextAction());
  }

  @Test
  void aDateWithAnOffsetIsKeptAndWritesNoDiagnostic() {
    MissionMeta meta = metaWith("\"accepted_at\":\"2026-09-02T10:00:00+00:00\",\"merged_at\":\"2026-09-03T10:00:00Z\"");

    MissionMeta projected = projection.withProjectedDates(meta);

    assertThat(projected.acceptedAt()).isEqualTo("2026-09-02T10:00:00+00:00");
    assertThat(projected.mergedAt()).isEqualTo("2026-09-03T10:00:00Z");
    assertThat(projected.discardedAt()).isNull();
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aDateWithoutAnOffsetOrShapedLikeAPathIsServedAsNullWithOneDiagnosticEach() {
    MissionMeta meta = metaWith("\"accepted_at\":\"2026-09-02T10:00:00\",\"merged_at\":\"/home/alice/work\",\"discarded_at\":\"2026-09-04T10:00:00+00:00\"");

    MissionMeta projected = projection.withProjectedDates(meta);

    assertThat(projected.acceptedAt()).isNull();
    assertThat(projected.mergedAt()).isNull();
    assertThat(projected.discardedAt()).isEqualTo("2026-09-04T10:00:00+00:00");
    assertThat(diagnostics).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED);
    assertThat(diagnostics).extracting(Diagnostic::mid8).containsOnly(meta.missionId().mid8());
  }

  @Test
  void aCleanOverviewIsServedAsDerived() {
    MissionOverview overview = cleanOverview();
    diagnostics.clear();

    assertThat(projection.projected(overview, overview.mid8())).isEqualTo(overview);
    assertThat(diagnostics).isEmpty();
  }

  @Test
  void aStrictFieldShapedLikeAHostPathIsRefused() {
    MissionOverview overview = cleanOverview();

    assertThatThrownBy(() -> projection.projected(withSlug(overview, "/home/alice/project"), overview.mid8())).isInstanceOf(ProjectionError.class);
  }
}
