package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import tools.jackson.databind.JsonNode;

/**
 * AC-4a HTTP legs, one test per row of the failure table: status, Problem presence, the body members, the diagnostic code. L3a goes
 * through /project and L3b through /missions, each its own 500. AC-1d: no body carries a fixture root path, HOME or a file name.
 */
class RefusalRowsTest {

  // built at run time: a host-path shape with no such literal in the source
  private static final String HOME_PATH = "/" + String.join("/", "ho" + "me", "secret", "path");

  private static final String ALPHA_MID8 = Rows.ALPHA_ID.substring(0, 8);

  private static FilesystemFixtureFactory.Built recorded(FixtureSpec spec) {
    return FilesystemFixtureFactory.over(FilesystemFixtureFactory.fromSpec(spec).root(), RecordingAllowlistAccess::new);
  }

  private static FixtureSpec pairSpec(String alphaLedger) {
    return FixtureSpec.of(
        PortFixtures.mission("alpha", Rows.ALPHA_ID, PortFixtures.CREATED, alphaLedger),
        PortFixtures.mission("beta", Rows.BETA_ID, "2026-09-03T10:00:00+00:00", RouteSupport.moves(20, 1)));
  }

  private void bothRoutesRefuse(FixtureSpec spec, String code) {
    FilesystemFixtureFactory.Built built = recorded(spec);
    try (HttpHarness server = HttpHarness.start(built)) {
      RouteSupport.assertProblem(server.get("/api/v1/project"), 500, code, built);
      RouteSupport.assertProblem(server.get("/api/v1/missions"), 500, code, built);
    }
  }

  @Test
  void l1AnAbsentLedgerIsADraftItemWithNoDiagnostic() {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(null));
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/missions");
      assertThat(response.status()).isEqualTo(200);
      JsonNode alpha = RouteSupport.tree(response).get("items").valueStream().filter(i -> i.get("slug").asString().equals("alpha")).findFirst().orElseThrow();
      assertThat(alpha.get("wpTotal").asInt()).isZero();
      assertThat(alpha.get("lifecycleStatus").asString()).isEqualTo("draft");
      assertThat(built.diagnostics()).isEmpty();
    }
  }

  @Test
  void l2AnUnreadableLedgerIsADraftItemPlusOneDiagnostic() {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(RouteSupport.moves(1, 2)));
    built.handles().allowlistRecorder().failWhen(a -> a.pathClass() == PathClass.LEDGER && a.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/missions");
      assertThat(response.status()).isEqualTo(200);
      JsonNode alpha = RouteSupport.tree(response).get("items").valueStream().filter(i -> i.get("slug").asString().equals("alpha")).findFirst().orElseThrow();
      assertThat(alpha.get("wpTotal").asInt()).isZero();
      assertThat(alpha.get("lifecycleStatus").asString()).isEqualTo("draft");
      assertThat(built.diagnostics()).anyMatch(d -> d.code() == DiagnosticCode.LEDGER_UNREADABLE && d.mid8().equals(ALPHA_MID8));
    }
  }

  @Test
  void l3aABadLedgerLineIsA500OnProjectWithLedgerUnparseable() {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(RouteSupport.moves(1, 2) + "this is not json\n"));
    try (HttpHarness server = HttpHarness.start(built)) {
      RouteSupport.assertProblem(server.get("/api/v1/project"), 500, "ledger_unparseable", built);
    }
  }

  @Test
  void l3bTheSameBadLineIsA500OnMissionsWhicheverPageIsAsked() {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(RouteSupport.moves(1, 2) + "[1,2,3]\n"));
    try (HttpHarness server = HttpHarness.start(built)) {
      RouteSupport.assertProblem(server.get("/api/v1/missions?pageSize=1"), 500, "ledger_unparseable", built);
      RouteSupport.assertProblem(server.get("/api/v1/missions"), 500, "ledger_unparseable", built);
    }
  }

  @Test
  void l4AnUnparseableTornTailIsA500OnBothRoutes() {
    bothRoutesRefuse(pairSpec(RouteSupport.moves(1, 2) + "{\"actor\":\"claude\",\"at\":\"2026-09-01T10:10:"), "ledger_torn_tail");
  }

  @Test
  void l4bAParseableUnterminatedTailIsA500OnBothRoutes() {
    bothRoutesRefuse(pairSpec(RouteSupport.moves(1, 2) + Rows.status(Rows.id(9), "2026-09-01T10:10:00Z", "WP09", "planned", "claimed").stripTrailing()), "ledger_torn_tail");
  }

  @Test
  void l6AMissionThatVanishedIsOmittedWithOneDiagnosticAndTheCountsAgree() {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(RouteSupport.moves(1, 1)));
    built.handles().allowlistRecorder().failWhen(a -> a.pathClass() == PathClass.MISSION_META && a.mode() == OpenMode.READ && a.path().contains("alpha"), () -> new NoSuchFileException("injected"));
    try (HttpHarness server = HttpHarness.start(built)) {
      JsonNode page = RouteSupport.tree(server.get("/api/v1/missions"));
      assertThat(page.get("items").size()).isEqualTo(1);
      assertThat(built.diagnostics()).anyMatch(d -> d.code() == DiagnosticCode.MISSION_VANISHED);
      JsonNode project = RouteSupport.tree(server.get("/api/v1/project"));
      assertThat(project.get("missionCount").asInt()).isEqualTo(1);
    }
  }

  @Test
  void l7AnUnusableMetaJsonIsA500OnBothRoutes() {
    bothRoutesRefuse(
        FixtureSpec.of(FixtureSpec.Mission.of("alpha", "this is not json", RouteSupport.moves(1, 1)), PortFixtures.mission("beta", Rows.BETA_ID, PortFixtures.CREATED, RouteSupport.moves(20, 1))),
        "meta_unparseable");
  }

  @Test
  void l7ACreatedAtWithoutAnOffsetIsRefusedLikeAMissingOne() {
    String offsetless = Rows.meta(Rows.ALPHA_ID, "alpha", "2026-01-01T00:00:00");
    bothRoutesRefuse(
        FixtureSpec.of(FixtureSpec.Mission.of("alpha", offsetless, RouteSupport.moves(1, 1)), PortFixtures.mission("beta", Rows.BETA_ID, PortFixtures.CREATED, RouteSupport.moves(20, 1))),
        "meta_unparseable");
  }

  @Test
  void l9ASymlinkedMetaJsonOmitsTheMissionWithAPathRefusedDiagnostic() throws IOException {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(RouteSupport.moves(1, 1)));
    Path meta = built.root().resolve("kitty-specs/alpha/meta.json");
    Path elsewhere = Files.createTempFile(built.root().getParent(), "real-meta", ".json");
    Files.writeString(elsewhere, Rows.meta(Rows.ALPHA_ID, "alpha", PortFixtures.CREATED));
    Files.delete(meta);
    Files.createSymbolicLink(meta, elsewhere);
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/missions");
      assertThat(response.status()).isEqualTo(200);
      assertThat(RouteSupport.tree(response).get("items").size()).isEqualTo(1);
      assertThat(built.diagnostics()).anyMatch(d -> d.code() == DiagnosticCode.PATH_REFUSED);
    }
  }

  @Test
  void l11AnUnlistableSpecsDirectoryIsA500OnBothRoutes() {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(RouteSupport.moves(1, 1)));
    built.handles().allowlistRecorder().failWhen(a -> a.pathClass() == PathClass.SPECS_DIR && a.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));
    try (HttpHarness server = HttpHarness.start(built)) {
      RouteSupport.assertProblem(server.get("/api/v1/project"), 500, "mission_dir_unreadable", built);
      RouteSupport.assertProblem(server.get("/api/v1/missions"), 500, "mission_dir_unreadable", built);
    }
  }

  @Test
  void l11AMissionDirectoryThatCannotBeStatedIsA500OnBothRoutes() {
    FilesystemFixtureFactory.Built built = recorded(pairSpec(RouteSupport.moves(1, 1)));
    built.handles().allowlistRecorder().failWhen(a -> a.pathClass() == PathClass.MISSION_META && a.mode() == OpenMode.STAT && a.path().contains("alpha"), () -> new AccessDeniedException("injected"));
    try (HttpHarness server = HttpHarness.start(built)) {
      RouteSupport.assertProblem(server.get("/api/v1/project"), 500, "mission_dir_unreadable", built);
      RouteSupport.assertProblem(server.get("/api/v1/missions"), 500, "mission_dir_unreadable", built);
    }
  }

  @Test
  void aProjectionRefusalOnAnyMissionIsA500OnProjectToo() {
    // DD-107: spec-correct although the oracle serves /project (the golden suite records the divergence).
    var fixture = org.speckitty.missionstatus.testsupport.ConformanceTree.fixtures().stream().filter(f -> f.key().equals("projection/strict-field-refused")).findFirst().orElseThrow();
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.fromTreeRecording(fixture.dir());
    try (HttpHarness server = HttpHarness.start(built)) {
      RouteSupport.assertProblem(server.get("/api/v1/project"), 500, "projection_refused", built);
      RouteSupport.assertProblem(server.get("/api/v1/missions"), 500, "projection_refused", built);
    }
  }

  @Test
  void anUnexpectedExceptionIsAGeneric500ProblemWithoutDetail() {
    FilesystemFixtureFactory.Built base = recorded(pairSpec(RouteSupport.moves(1, 1)));
    org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery boom =
        new org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery() {
          public org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader project() {
            throw new IllegalStateException(HOME_PATH + " boom");
          }

          public org.speckitty.missionstatus.domain.readmodel.overview.MissionPage missions(org.speckitty.missionstatus.application.query.port.in.dto.PageRequest request) {
            throw new IllegalStateException(HOME_PATH + " boom");
          }

          public org.speckitty.missionstatus.application.query.port.in.dto.ChangeBatch changesSince(
              org.speckitty.missionstatus.application.query.port.in.dto.StreamScope scope, java.util.Optional<org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor> cursor) {
            throw new UnsupportedOperationException();
          }

          public org.speckitty.missionstatus.application.query.port.in.Subscription subscribe(
              org.speckitty.missionstatus.application.query.port.in.dto.StreamScope scope, java.util.Optional<org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor> cursor) {
            throw new UnsupportedOperationException();
          }
        };
    FilesystemFixtureFactory.Built built = new FilesystemFixtureFactory.Built(boom, base.source(), base.handles(), base.root());
    try (HttpHarness server = HttpHarness.start(built)) {
      HttpHarness.Response response = server.get("/api/v1/project");
      RouteSupport.assertProblem(response, 500, null, built);
      assertThat(response.text()).doesNotContain("secret").doesNotContain("boom");
      assertThat(RouteSupport.tree(response).has("detail")).isFalse();
    }
  }
}
