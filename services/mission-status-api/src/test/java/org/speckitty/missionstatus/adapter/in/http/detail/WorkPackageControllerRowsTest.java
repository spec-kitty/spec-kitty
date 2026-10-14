package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;
import java.util.function.Supplier;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.WorkPackageQueryService;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.conformance.golden.served.WorkPackageServedRoute;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageView;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.RealPermissionFixture;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.Utf8Host;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * AC-2.6 and AC-12.1: one fixture and one assertion for each row of the FR-012 table that applies to {@code getWorkPackage}, at the port (a
 * typed result, {@link DetailRefusal} or {@link MissionStatusUnavailable} carrying the diagnostic code) and at the HTTP leg (status, Problem
 * code, content type, no path or injected message in the body), plus the diagnostic codes written, in order (AC-12.2, AC-12.4). A
 * permission-failure row is an injected fault, always; the real-permission leg runs only when the operating system refuses it.
 *
 * <p>The class also holds the helpers the other tests of the route share: the service over a fixture and the server with it installed.
 * {@link #everyRowOfTheTableThatAppliesHasAFixture} is the discovered-row floor: delete a row and it goes red.
 */
public class WorkPackageControllerRowsTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String ID = Rows.ALPHA_ID;
  private static final String CREATED = "2026-09-01T10:00:00+00:00";
  private static final String TREE_MISSION = "00000000000000000000000001";

  /** The table rows that apply to getWorkPackage and that this class owns a fixture for (C1 is the controller test's). */
  private static final Set<String> REQUIRED_ROWS =
      Set.of("C2", "C3", "C4", "C5", "C6", "C7", "M1", "M2", "M3", "M4a", "M5", "M6", "M7", "M10", "M13", "W1");

  /** What a row answers: 200 (code null), or the status and Problem code, and the diagnostic codes written, in order. */
  private record Expect(int status, String code, List<DiagnosticCode> diagnostics) {}

  private record Row(String id, String name, Supplier<DetailFixture> make, String askedMission, String askedWp, Expect expect) {
    @Override
    public String toString() {
      return id + " " + name;
    }
  }

  private static Expect ok(DiagnosticCode... diagnostics) {
    return new Expect(200, null, List.of(diagnostics));
  }

  private static Expect refused(DiagnosticCode code, DiagnosticCode... diagnostics) {
    return new Expect(500, code.wire(), List.of(diagnostics));
  }

  private static Expect notFound(DiagnosticCode... diagnostics) {
    return new Expect(404, "not_found", List.of(diagnostics));
  }

  // ---- the service over a fixture (the route's tests share these) ---------------------------------------------------------------------

  /** The real service over the fixture and this gate: its read model, a Work Package index over its text source, its diagnostics recorder. */
  public static WorkPackageQueryService serviceOver(DetailFixture fixture, AdmissionGate gate) {
    WorkPackageIndex index = new WorkPackageIndex(fixture.textSource(), new YamlFrontmatterDecoder());
    return new WorkPackageQueryService(fixture.readModel(), index, fixture.built().handles().recorder(), LeakPatternsFile.load(), gate);
  }

  public static WorkPackageQueryService serviceOver(DetailFixture fixture) {
    return serviceOver(fixture, new AdmissionGate());
  }

  /** The production application on a real socket, with {@link #serviceOver} installed as the Work Package port. */
  public static HttpHarness serve(DetailFixture fixture) {
    return HttpHarness.startWith(fixture.built(), Map.of(WorkPackageQuery.class, serviceOver(fixture)));
  }

  public static WorkPackageView view(DetailFixture fixture, String missionId, String wpId, boolean includePrompt) {
    return serviceOver(fixture).workPackage(new MissionId(missionId), new WpId(wpId), includePrompt);
  }

  // ---- fixture builders ----------------------------------------------------------------------------------------------------------

  static String ledger() {
    return Rows.status(Rows.id(1), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed");
  }

  private static FixtureSpec.Mission alpha(String ledger) {
    return PortFixtures.mission("alpha", ID, CREATED, ledger);
  }

  private static void wpFile(Path root) {
    MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One"));
  }

  /** A Mission {@code alpha} with one valid Work Package file WP01 and the given extras, plus the given sibling Missions. */
  public static DetailFixture build(Consumer<Path> extras, FixtureSpec.Mission... siblings) {
    List<FixtureSpec.Mission> missions = new ArrayList<>(List.of(siblings));
    if (missions.stream().noneMatch(mission -> mission.name().equals("alpha"))) {
      missions.add(alpha(ledger()));
    }
    return MissionDetailServedRoute.fixtureOf(new FixtureSpec(FixtureSpec.Project.healthy(), missions), root -> {
      wpFile(root);
      extras.accept(root);
    });
  }

  private static DetailFixture buildAlpha(String ledger, Consumer<Path> extras) {
    return MissionDetailServedRoute.fixtureOf(FixtureSpec.of(alpha(ledger)), root -> {
      wpFile(root);
      extras.accept(root);
    });
  }

  /** WP01 has only a file whose frontmatter is unusable. */
  private static DetailFixture onlyABadFile() {
    return MissionDetailServedRoute.fixtureOf(FixtureSpec.of(alpha(ledger())), root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-bad.md", "no frontmatter at all\n"));
  }

  private static FixtureSpec.Mission brokenMeta(String name) {
    return FixtureSpec.Mission.of(name, "{not json", null);
  }

  private static void symlink(Path link, Path target) {
    try {
      Files.createSymbolicLink(link, target);
    } catch (IOException | UnsupportedOperationException unsupported) {
      Assumptions.abort("symbolic links cannot be made here");
    }
  }

  private static String secret() {
    return "gh" + "p_" + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2Yz3";
  }

  private static TreeFixture fixture(String key) {
    return ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow();
  }

  private static Row row(String id, String name, Supplier<DetailFixture> make, String mission, String wp, Expect expect) {
    return new Row(id, name, make, mission, wp, expect);
  }

  // ---- the rows --------------------------------------------------------------------------------------------------------------------

  static Stream<Row> rows() {
    List<Row> rows = new ArrayList<>();
    String gamma = Rows.GAMMA_ID;

    rows.add(row("C2", "a well-formed id that no Mission holds", () -> build(root -> {}), gamma, "WP01", notFound()));
    rows.add(row("C3", "a Mission directory refused by the link rule is the first fault, no Mission holds the id", () -> build(root -> symlink(root.resolve("kitty-specs/aaa-link"), root.resolve("kitty-specs/alpha"))), gamma, "WP01", notFound(DiagnosticCode.PATH_REFUSED)));
    rows.add(row("C4", "the first fault of the scan is an unusable meta.json", () -> build(root -> {}, brokenMeta("broken")), gamma, "WP01", refused(DiagnosticCode.META_UNPARSEABLE, DiagnosticCode.META_UNPARSEABLE)));
    rows.add(row("C5", "kitty-specs cannot be listed", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.SPECS_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, "WP01", refused(DiagnosticCode.MISSION_DIR_UNREADABLE, DiagnosticCode.MISSION_DIR_UNREADABLE)));
    rows.add(row("C5", "the first fault of the scan is a Mission directory that cannot be read", () -> {
      DetailFixture fixture = build(root -> {}, alpha(ledger()), PortFixtures.mission("aaa-sibling", Rows.BETA_ID, CREATED, ""));
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.MISSION_META && access.path().contains("aaa-sibling"), () -> new AccessDeniedException("injected"));
      return fixture;
    }, gamma, "WP01", refused(DiagnosticCode.MISSION_DIR_UNREADABLE, DiagnosticCode.MISSION_DIR_UNREADABLE)));
    rows.add(row("C6", "two readable directories hold the id, the first in byte order is served", () -> build(root -> {}, alpha(ledger()), PortFixtures.mission("alpha-copy", ID, CREATED, ledger())), ID, "WP01", ok(DiagnosticCode.MISSION_ID_DUPLICATE)));
    rows.add(row("C7", "a faulted sibling before and one after the match", () -> build(root -> {}, brokenMeta("aaa-broken"), alpha(ledger()), brokenMeta("zzz-broken")), ID, "WP01", ok()));

    rows.add(row("M1", "the ledger is absent: the Work Package has a file and no lane", () -> buildAlpha(null, root -> {}), ID, "WP01", ok()));
    rows.add(row("M2", "the ledger is unreadable: 200 and the diagnostic together", () -> {
      DetailFixture fixture = buildAlpha(ledger(), root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.LEDGER && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, "WP01", ok(DiagnosticCode.LEDGER_UNREADABLE)));
    rows.add(row("M3", "the ledger is not decodable", () -> buildAlpha("this is not json\n", root -> {}), ID, "WP01", refused(DiagnosticCode.LEDGER_UNPARSEABLE, DiagnosticCode.LEDGER_UNPARSEABLE)));
    rows.add(row("M3", "the ledger has a torn tail", () -> buildAlpha(ledger() + "{\"event_id\": \"torn", root -> {}), ID, "WP01", refused(DiagnosticCode.LEDGER_TORN_TAIL, DiagnosticCode.LEDGER_TORN_TAIL)));

    rows.add(row("M4a", "tasks/ cannot be listed", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.TASKS_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, "WP01", refused(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(row("M4a", "a Work Package file cannot be read", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.WP_FILE && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, "WP01", refused(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(row("M4a", "another Work Package file is over 1 MiB: the index is refused as a whole", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP02-big.md", MissionDetailServedRoute.workPackageFile("WP02", "Big") + "x".repeat(1_048_577))), ID, "WP01", refused(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(row("M5", "the only file of the Work Package has unusable frontmatter: 404 and the skip diagnostic (AC-2.6)", WorkPackageControllerRowsTest::onlyABadFile, ID, "WP01", notFound(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(row("M5", "a file of another Work Package is skipped, the requested one is served", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP02-bad.md", "no frontmatter at all\n")), ID, "WP01", ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(row("M5", "a symbolic link is skipped and its target is never read", () -> build(root -> {
      MissionDetailServedRoute.write(root, "alpha", "elsewhere/WP02-target.md", MissionDetailServedRoute.workPackageFile("WP02", "Target"));
      symlink(root.resolve("kitty-specs/alpha/tasks/WP02-link.md"), root.resolve("kitty-specs/alpha/elsewhere/WP02-target.md"));
    }), ID, "WP01", ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(row("M5", "a directory named like a Work Package file is skipped", () -> build(root -> {
      try {
        Files.createDirectories(root.resolve("kitty-specs/alpha/tasks/WP02-dir.md"));
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, "WP01", ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(row("M6", "a later file holds an id already indexed: the first file is served", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-two.md", MissionDetailServedRoute.workPackageFile("WP01", "Second"))), ID, "WP01", ok(DiagnosticCode.WP_ID_DUPLICATE)));

    rows.add(row("M7", "a class-3 human field (title) holds a credential", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "Rotate " + secret()))), ID, "WP01", refused(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(row("M7", "a strict list member (ownedFiles) is a path (the Java-only fixture owned-file-pattern-leak)", () -> DetailFixture.of(fixture("projection-refusals/owned-file-pattern-leak").dir()), TREE_MISSION, "WP01", refused(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(row("M7", "a dependency id that is a path (the Java-only fixture dependency-id-leak)", () -> DetailFixture.of(fixture("projection-refusals/dependency-id-leak").dir()), TREE_MISSION, "WP01", refused(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    // the leaking event id is the last event: the head nulls lastEventId (T2/T11, nullable strict) so getMission answers 200, and the history of this route refuses it (T12)
    rows.add(row("M3", "the last event id is a path (the Java-only fixture history-event-id-leak): the history refuses it", () -> DetailFixture.of(fixture("projection-refusals/history-event-id-leak").dir()), TREE_MISSION, "WP01", refused(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(row("M7", "subtasks written as mappings (SK-353, V20)", () -> DetailFixture.of(fixture("wp-malformed-frontmatter/wpm-28").dir()), TREE_MISSION, "WP01", refused(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));

    rows.add(row("M10", "tasks/ is a regular file", () -> buildAlpha(ledger(), root -> {
      try {
        Files.delete(root.resolve("kitty-specs/alpha/tasks/WP01-one.md"));
        Files.delete(root.resolve("kitty-specs/alpha/tasks"));
        Files.writeString(root.resolve("kitty-specs/alpha/tasks"), "not a directory", StandardCharsets.UTF_8);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, "WP01", refused(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(row("M10", "tasks/ is a link", () -> buildAlpha(ledger(), root -> {
      try {
        Path real = root.resolve("kitty-specs/alpha/tasks");
        Path moved = root.resolve("kitty-specs/alpha/real-tasks");
        Files.move(real, moved);
        symlink(real, moved);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, "WP01", refused(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(row("M13", "the host cannot decode file names and a candidate is not ASCII", () -> withEncoding(nonAscii(), NameEncoding.fixed(false)), ID, "WP01", refused(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(row("W1", "a Work Package known only to the ledger is not found", () -> buildAlpha(ledger() + Rows.status(Rows.id(2), "2026-09-01T10:02:00Z", "WP09", "planned", "claimed"), root -> {}), ID, "WP09", notFound()));
    rows.add(row("W1", "a well-formed Work Package id that nothing names", () -> build(root -> {}), ID, "WP99", notFound()));
    return rows.stream();
  }

  private static DetailFixture nonAscii() {
    return build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP02-é.md", MissionDetailServedRoute.workPackageFile("WP02", "Accent")));
  }

  /** The same fixture read through a text source with a given answer to "can this host decode file names?". */
  private static DetailFixture withEncoding(DetailFixture fixture, NameEncoding encoding) {
    return new DetailFixture(fixture.built(), new FilesystemTextSource(fixture.root(), fixture.recorder(), encoding), fixture.readModel());
  }

  // ---- the two legs ----------------------------------------------------------------------------------------------------------------

  @ParameterizedTest(name = "{0}")
  @MethodSource("rows")
  void thePortAnswersTheRow(Row row) {
    DetailFixture fixture = row.make().get();
    WorkPackageQueryService service = serviceOver(fixture);
    MissionId mission = new MissionId(row.askedMission());
    WpId wp = new WpId(row.askedWp());

    switch (row.expect().status()) {
      case 200 -> {
        WorkPackageView view = service.workPackage(mission, wp, false);
        assertThat(view.wpId()).isEqualTo(wp);
        assertThat(view.promptMarkdown()).isNull();
      }
      case 404 -> assertThatThrownBy(() -> service.workPackage(mission, wp, false)).isInstanceOfSatisfying(DetailRefusal.class, refusal -> assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND));
      default ->
          assertThatThrownBy(() -> service.workPackage(mission, wp, false))
              .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code().wire()).isEqualTo(row.expect().code()));
    }
    assertDiagnostics(fixture, row.expect());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("rows")
  void theHttpLegAnswersTheRow(Row row) {
    DetailFixture fixture = row.make().get();
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get(WorkPackageServedRoute.path(row.askedMission(), row.askedWp(), false));

      assertThat(response.status()).isEqualTo(row.expect().status());
      JsonNode body = JSON.readTree(response.body());
      if (row.expect().status() == 200) {
        assertThat(response.header("Content-Type")).startsWith("application/json");
        assertThat(body.get("wpId").asString()).isEqualTo(row.askedWp());
        assertThat(body.has("promptMarkdown")).as("absent, not null, without the parameter").isFalse();
      } else {
        assertThat(response.header("Content-Type")).startsWith("application/problem+json");
        assertThat(body.get("code").asString()).isEqualTo(row.expect().code());
        assertThat(body.get("status").asInt()).isEqualTo(row.expect().status());
        assertThat(response.text()).doesNotContain(fixture.root().toString()).doesNotContain("kitty-specs").doesNotContain(".md").doesNotContain("injected");
      }
    }
    assertDiagnostics(fixture, row.expect());
  }

  /** AC-12.2 and AC-12.4: the codes in order, one line per occurrence, a mid8 field or none, and no path in any line. */
  private static void assertDiagnostics(DetailFixture fixture, Expect expect) {
    List<Diagnostic> written = fixture.diagnostics();
    assertThat(written.stream().map(Diagnostic::code).toList()).isEqualTo(expect.diagnostics());
    for (Diagnostic diagnostic : written) {
      assertThat(diagnostic.mid8()).matches("[0-9A-Z]{8}|" + Diagnostic.NONE);
      assertThat(diagnostic.toString()).doesNotContain(fixture.root().toString()).doesNotContain("kitty-specs");
    }
  }

  // ---- the rows that are not a one-line table entry -----------------------------------------------------------------------------

  @Test
  void everyRowOfTheTableThatAppliesHasAFixture() {
    List<Row> rows = rows().toList();

    assertThat(rows.stream().map(Row::id).collect(Collectors.toSet())).containsAll(REQUIRED_ROWS);
    assertThat(rows).hasSizeGreaterThanOrEqualTo(28);
  }

  @Test
  void aNonAsciiFileNameIsServedWhenTheHostDecodesNamesWhateverTheLocale() {
    DetailFixture fixture = withEncoding(nonAscii(), NameEncoding.fixed(true));

    WorkPackageView accented = view(fixture, ID, "WP02", false);

    assertThat(accented.title()).isEqualTo("Accent");
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void aRealNonAsciiNameOnAUtf8HostIsServed(org.junit.jupiter.api.TestInfo info) {
    Utf8Host.assumeUtf8(info.getTestClass().orElseThrow().getName() + "#" + info.getTestMethod().orElseThrow().getName());

    assertThat(view(nonAscii(), ID, "WP02", false).title()).isEqualTo("Accent");
  }

  @Test
  void aRealPermissionRefusalOfTasksIsTheSameRowWhenTheOperatingSystemRefusesIt(org.junit.jupiter.api.TestInfo info) {
    DetailFixture fixture = build(root -> {});
    Path tasks = fixture.root().resolve("kitty-specs/alpha/tasks");
    try (RealPermissionFixture ignored = RealPermissionFixture.refusedForThisUser(tasks, info.getTestClass().orElseThrow().getName() + "#" + info.getTestMethod().orElseThrow().getName())) {
      assertThatThrownBy(() -> view(fixture, ID, "WP01", false))
          .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
    }
  }
}
