package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;

/** AC-13b: the factory builds the real service over the given source and hides the recorder and the executor behind the handles. */
class FixtureFactoryTest {

  private static FixtureSpec spec() {
    return FixtureSpec.of(
        FixtureSpec.Mission.of("alpha", Rows.meta(Rows.ALPHA_ID, "alpha", "2026-09-02T10:00:00+00:00"), Rows.status("e1", "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")),
        FixtureSpec.Mission.of("broken", "{", null));
  }

  @Test
  void itBuildsTheRealServiceAndReturnsOnlyTheInboundPort() {
    FixtureFactory.Built built = FixtureFactory.build(FixtureSpec.of(spec().missions().getFirst()));

    assertThat(built.query()).isInstanceOf(MissionStatusQueryService.class).isInstanceOf(MissionStatusQuery.class);
    assertThat(built.query().missions(new PageRequest(null, null)).items()).hasSize(1);
    assertThat(built.source().listMissions()).hasSize(1);
    assertThat(built.diagnostics()).isEmpty();
  }

  @Test
  void theRecorderAndTheExecutorAreReachableOnlyThroughTheHandles() {
    FixtureFactory.Built built = FixtureFactory.build(spec());

    org.assertj.core.api.Assertions.assertThatThrownBy(() -> built.query().project()).isNotNull();
    assertThat(built.handles().diagnostics()).extracting(d -> d.code()).containsExactly(DiagnosticCode.META_UNPARSEABLE);
    assertThat(built.diagnostics()).isEqualTo(built.handles().diagnostics());
    assertThat(built.handles().executor().liveTasks()).isZero();
    assertThat(built.handles().clock().instant()).isEqualTo(Instant.parse("2026-10-01T12:00:00Z"));
    built.handles().clock().advance(Duration.ofSeconds(5));
    assertThat(built.handles().clock().instant()).isEqualTo(Instant.parse("2026-10-01T12:00:05Z"));
  }

  @Test
  void theSpecCanReplaceItsProjectInputs() {
    FixtureSpec replaced = FixtureSpec.of().with(new FixtureSpec.Project("renamed", "1.0", 3, "dev"));

    assertThat(FixtureFactory.build(replaced).query().project().name()).isEqualTo("renamed");
    assertThat(FixtureFactory.leakClasses()).isNotNull();
  }
}
