package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.domain.readmodel.cursor.InvalidPageCursor;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.overview.Health;
import org.speckitty.missionstatus.domain.readmodel.overview.LifecycleStatus;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionPage;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.Rows;

class MissionStatusQueryServiceTest {

  private static final String CREATED_OLD = "2026-09-02T10:00:00+00:00";
  private static final String CREATED_NEW = "2026-09-03T10:00:00+00:00";

  private static FixtureSpec threeMissions() {
    return FixtureSpec.of(
        Fx.mission("alpha", Rows.ALPHA_ID, CREATED_OLD, Fx.twoMoves("WP01", 1)),
        Fx.mission("beta", Rows.BETA_ID, CREATED_NEW, Rows.status(Rows.id(3), Fx.T2, "WP01", "planned", "claimed")),
        Fx.mission("gamma", Rows.GAMMA_ID, CREATED_NEW, null));
  }

  @Test
  void theProjectHeaderCountsMissionsAndTakesTheLatestActivity() {
    Fx fx = new Fx(threeMissions());

    ProjectHeader header = fx.service.project();

    assertThat(header.name()).isEqualTo("fixture-project");
    assertThat(header.missionCount()).isEqualTo(3);
    assertThat(header.health()).isEqualTo(Health.HEALTHY);
    assertThat(header.currentBranch()).isEqualTo("main");
    assertThat(header.lastActivityAt()).isEqualTo(Fx.T2);
  }

  @Test
  void missionsAreServedInContractOrderCreatedAtDescendingThenMissionId() {
    Fx fx = new Fx(threeMissions());

    MissionPage page = fx.service.missions(new PageRequest(null, null));

    assertThat(page.items()).extracting(item -> item.slug()).containsExactly("beta", "gamma", "alpha");
    assertThat(page.missionCount()).isEqualTo(3);
    assertThat(page.pageSize()).isEqualTo(50);
    assertThat(page.nextPageCursor()).isNull();
  }

  @Test
  void anOverviewIsDerivedFromMetaAndTheReducedLedger() {
    Fx fx = new Fx(threeMissions());

    MissionOverview alpha = fx.service.missions(new PageRequest(null, null)).items().stream().filter(item -> item.slug().equals("alpha")).findFirst().orElseThrow();

    assertThat(alpha.wpTotal()).isEqualTo(1);
    assertThat(alpha.statusLaneCounts().get(Lane.IN_PROGRESS)).isEqualTo(1);
    assertThat(alpha.lifecycleStatus()).isEqualTo(LifecycleStatus.ACTIVE);
    assertThat(alpha.eventCount()).isEqualTo(2);
    assertThat(alpha.lastEventId()).isEqualTo(Rows.id(2));
    assertThat(alpha.lastActivityAt()).isEqualTo(Fx.T1);
  }

  @Test
  void theStreamCursorOfAnOverviewDescribesTheTerminatedPrefix() {
    String ledger = Fx.twoMoves("WP01", 1);
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, CREATED_OLD, ledger)));

    StreamCursor cursor = fx.service.missions(new PageRequest(null, null)).items().getFirst().streamCursor();

    byte[] bytes = ledger.getBytes(StandardCharsets.UTF_8);
    String lastLine = ledger.substring(ledger.indexOf('\n') + 1);
    assertThat(cursor.offset()).isEqualTo(bytes.length);
    assertThat(cursor.invariant()).isEqualTo(StreamCursor.digestOf(lastLine.getBytes(StandardCharsets.UTF_8)));
  }

  @Test
  void aMissionWithoutALedgerIsADraftAtOffsetZero() {
    Fx fx = new Fx(threeMissions());

    MissionOverview gamma = fx.service.missions(new PageRequest(null, null)).items().stream().filter(item -> item.slug().equals("gamma")).findFirst().orElseThrow();

    assertThat(gamma.lifecycleStatus()).isEqualTo(LifecycleStatus.DRAFT);
    assertThat(gamma.streamCursor()).isEqualTo(StreamCursor.start());
    assertThat(gamma.eventCount()).isZero();
    assertThat(fx.handles.diagnostics()).isEmpty();
  }

  @Test
  void anAnnotationOnlyWorkPackageCountsInWpTotalButInNoLaneCount() {
    String ledger = Rows.annotation(Rows.id(1), Fx.T0, "WP09");
    Fx fx = new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, CREATED_OLD, ledger)));

    MissionOverview overview = fx.service.missions(new PageRequest(null, null)).items().getFirst();

    assertThat(overview.wpTotal()).isEqualTo(1);
    assertThat(overview.statusLaneCounts().values().stream().mapToInt(Integer::intValue).sum()).isZero();
  }

  @Test
  void pagingWithPageSizeOneYieldsEveryMissionOnceInOrder() {
    Fx fx = new Fx(threeMissions());
    List<String> seen = new ArrayList<>();
    String cursor = null;

    do {
      MissionPage page = fx.service.missions(new PageRequest(1, cursor));
      page.items().forEach(item -> seen.add(item.slug()));
      assertThat(page.missionCount()).isEqualTo(3);
      cursor = page.nextPageCursor();
    } while (cursor != null);

    assertThat(seen).containsExactly("beta", "gamma", "alpha");
  }

  @ParameterizedTest(name = "requested {0} is served as {1}")
  @CsvSource({"500,200", "201,200", "200,200", "50,50", "1,1", "0,1", "-7,1"})
  void thePageSizeIsClampedAtBothEndsAndNeverRefused(int requested, int served) {
    Fx fx = new Fx(threeMissions());

    assertThat(fx.service.missions(new PageRequest(requested, null)).pageSize()).isEqualTo(served);
  }

  @Test
  void aForgedPageCursorIsRefusedWithTheDomainException() {
    Fx fx = new Fx(threeMissions());

    assertThatThrownBy(() -> fx.service.missions(new PageRequest(null, "abc"))).isInstanceOf(InvalidPageCursor.class);
  }

  @Test
  void aProjectionRefusalBecomesProjectionRefusedWithoutTheValue() {
    String leakyMeta = Rows.meta(Rows.ALPHA_ID, "/home/someone/secret", CREATED_OLD);
    Fx fx = new Fx(FixtureSpec.of(FixtureSpec.Mission.of("alpha", leakyMeta, null)));

    assertThatThrownBy(() -> fx.service.missions(new PageRequest(null, null)))
        .isInstanceOfSatisfying(
            MissionStatusUnavailable.class,
            refusal -> {
              assertThat(refusal.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
              assertThat(refusal.getMessage()).doesNotContain("someone");
            });
    assertThat(fx.handles.diagnostics()).singleElement().satisfies(d -> assertThat(d.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED));
  }

  @Test
  void aDateOrEventIdOfTheWrongShapeIsNulledNotServed() {
    String meta =
        Rows.metaWith(
            Rows.ALPHA_ID,
            "alpha",
            CREATED_OLD,
            "\"accepted_at\":\"/home/alice/notes alice@corp.com\",\"merged_at\":\"/tmp/x\",\"discarded_at\":\"" + Fx.T2 + "\"");
    String ledger = Rows.status("/Users/alice/x", Fx.T0, "WP01", "planned", "claimed");
    Fx fx = new Fx(FixtureSpec.of(FixtureSpec.Mission.of("alpha", meta, ledger)));

    MissionOverview item = fx.service.missions(new PageRequest(null, null)).items().getFirst();

    assertThat(item.acceptedAt()).isNull();
    assertThat(item.mergedAt()).isNull();
    assertThat(item.discardedAt()).isEqualTo(Fx.T2);
    assertThat(item.lastEventId()).isNull();
  }

  @Test
  void aHumanFieldIsRedactedNotRefused() {
    String meta = Rows.metaWith(Rows.ALPHA_ID, "alpha", CREATED_OLD, "\"friendly_name\":\"see /home/someone/x for mail a@b.example\"");
    Fx fx = new Fx(FixtureSpec.of(FixtureSpec.Mission.of("alpha", meta, null)));

    String friendly = fx.service.missions(new PageRequest(null, null)).items().getFirst().friendlyName();

    assertThat(friendly).contains("[path]").contains("[email]").doesNotContain("someone");
  }

  @Test
  void anEmptyProjectServesAnEmptyPageAndAZeroCountHeader() {
    Fx fx = new Fx(new FixtureSpec(FixtureSpec.Project.healthy(), List.of()));

    assertThat(fx.service.missions(new PageRequest(null, null)).items()).isEmpty();
    ProjectHeader header = fx.service.project();
    assertThat(header.missionCount()).isZero();
    assertThat(header.lastActivityAt()).isNull();
  }
}
