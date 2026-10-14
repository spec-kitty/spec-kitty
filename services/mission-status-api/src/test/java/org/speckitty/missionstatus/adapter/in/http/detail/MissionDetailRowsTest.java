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
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;
import java.util.function.Supplier;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInfo;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.MissionDetailQueryService;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.MissionDetailQuery;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.MissionDetail;
import org.speckitty.missionstatus.domain.readmodel.overview.LifecycleStatus;
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
 * AC-1.6 and AC-12.1: one fixture and one assertion for each row of the FR-012 table that applies to {@code getMission}, at the port (a typed
 * result, {@link DetailRefusal} or {@link MissionStatusUnavailable} carrying the diagnostic code) and at the HTTP leg (status, Problem
 * {@code code}), with the diagnostics the service wrote. Rows M2 and M5 assert the 200 and the diagnostic together. A permission failure is
 * an injected fault ({@code AccessDeniedException}), always; the real-permission leg runs only when the operating system refuses it.
 *
 * <p>Every row is a {@link Row}; {@link #everyRowOfTheTableThatAppliesHasAFixture} is the discovered-row floor: delete one row and it
 * goes red (AC-1.6).
 */
public class MissionDetailRowsTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String ID = Rows.ALPHA_ID;
  private static final String MID8 = ID.substring(0, 8);
  private static final String CREATED = "2026-09-01T10:00:00+00:00";

  /** The table rows that apply to getMission and that this class owns a fixture for (C1 is the controller test's, C2 has its own method). */
  private static final Set<String> REQUIRED_ROWS =
      Set.of("C3", "C4", "C5", "C6", "C7", "M1", "M2", "M3", "M4a", "M5", "M6", "M7", "M8", "M10", "M13", "M14");

  /** What a row answers: 200 (code null), or the status and Problem code, and the diagnostic codes written, in order. */
  private record Expect(int status, String code, List<DiagnosticCode> diagnostics) {}

  private record Row(String id, String name, Supplier<DetailFixture> make, String askedId, Expect expect) {
    @Override
    public String toString() {
      return id + " " + name;
    }
  }

  private static Expect ok(DiagnosticCode... diagnostics) {
    return new Expect(200, null, List.of(diagnostics));
  }

  private static Expect refused(int status, DiagnosticCode code, DiagnosticCode... diagnostics) {
    return new Expect(status, code.wire(), List.of(diagnostics));
  }

  private static Expect notFound(DiagnosticCode... diagnostics) {
    return new Expect(404, "not_found", List.of(diagnostics));
  }

  // ---- the service over a fixture (the route's tests share these) ---------------------------------------------------------------------

  /** The real service over the fixture: its read model, a Work Package index over its text source, and its diagnostics recorder. */
  public static MissionDetailQueryService serviceOver(DetailFixture fixture) {
    WorkPackageIndex index = new WorkPackageIndex(fixture.textSource(), new YamlFrontmatterDecoder());
    return new MissionDetailQueryService(fixture.readModel(), index, fixture.textSource(), fixture.built().handles().recorder(), LeakPatternsFile.load());
  }

  /** The production application on a real socket, with {@link #serviceOver} installed as the Mission detail port. */
  public static HttpHarness serve(DetailFixture fixture) {
    return HttpHarness.startWith(fixture.built(), Map.of(MissionDetailQuery.class, serviceOver(fixture)));
  }

  // ---- fixture builders ----------------------------------------------------------------------------------------------------------

  private static String ledger() {
    return Rows.status(Rows.id(1), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed");
  }

  private static FixtureSpec.Mission alpha(String ledger) {
    return PortFixtures.mission("alpha", ID, CREATED, ledger);
  }

  private static void wpFile(Path root) {
    MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One"));
  }

  /** A Mission {@code alpha} with one valid Work Package file and the given extras, plus the given sibling Missions. */
  private static DetailFixture build(Consumer<Path> extras, FixtureSpec.Mission... siblings) {
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

  // ---- the rows --------------------------------------------------------------------------------------------------------------------

  static Stream<Row> rows() {
    List<Row> rows = new ArrayList<>();

    rows.add(new Row("C3", "a Mission directory refused by the link rule is the first fault, no Mission holds the id", () -> build(root -> symlink(root.resolve("kitty-specs/aaa-link"), root.resolve("kitty-specs/alpha"))), Rows.GAMMA_ID, notFound(DiagnosticCode.PATH_REFUSED)));
    rows.add(new Row("C4", "the first fault of the scan is an unusable meta.json", () -> build(root -> {}, brokenMeta("broken")), Rows.GAMMA_ID, refused(500, DiagnosticCode.META_UNPARSEABLE, DiagnosticCode.META_UNPARSEABLE)));
    rows.add(new Row("C5", "kitty-specs cannot be listed", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.SPECS_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, refused(500, DiagnosticCode.MISSION_DIR_UNREADABLE, DiagnosticCode.MISSION_DIR_UNREADABLE)));
    rows.add(new Row("C5", "the first fault of the scan is a Mission directory that cannot be read", () -> {
      DetailFixture fixture = build(root -> {}, alpha(ledger()), PortFixtures.mission("aaa-sibling", Rows.BETA_ID, CREATED, ""));
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.MISSION_META && access.path().contains("aaa-sibling"), () -> new AccessDeniedException("injected"));
      return fixture;
    }, Rows.GAMMA_ID, refused(500, DiagnosticCode.MISSION_DIR_UNREADABLE, DiagnosticCode.MISSION_DIR_UNREADABLE)));
    rows.add(new Row("C6", "two readable directories hold the id, the first in byte order is served", () -> build(root -> {}, alpha(ledger()), PortFixtures.mission("alpha-copy", ID, CREATED, ledger())), ID, ok(DiagnosticCode.MISSION_ID_DUPLICATE)));
    rows.add(new Row("C7", "a faulted sibling before and one after the match", () -> build(root -> {}, brokenMeta("aaa-broken"), alpha(ledger()), brokenMeta("zzz-broken")), ID, ok()));
    rows.add(new Row("C7", "a faulted sibling after a duplicate", () -> build(root -> {}, alpha(ledger()), PortFixtures.mission("alpha-copy", ID, CREATED, ledger()), brokenMeta("zzz-broken")), ID, ok(DiagnosticCode.MISSION_ID_DUPLICATE)));

    rows.add(new Row("M1", "the ledger is absent: the draft head", () -> buildAlpha(null, root -> {}), ID, ok()));
    rows.add(new Row("M2", "the ledger is unreadable: 200 and the diagnostic together", () -> {
      DetailFixture fixture = buildAlpha(ledger(), root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.LEDGER && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, ok(DiagnosticCode.LEDGER_UNREADABLE)));
    rows.add(new Row("M3", "the ledger is not decodable", () -> buildAlpha("this is not json\n", root -> {}), ID, refused(500, DiagnosticCode.LEDGER_UNPARSEABLE, DiagnosticCode.LEDGER_UNPARSEABLE)));
    rows.add(new Row("M3", "the ledger has a torn tail", () -> buildAlpha(ledger() + "{\"event_id\": \"torn", root -> {}), ID, refused(500, DiagnosticCode.LEDGER_TORN_TAIL, DiagnosticCode.LEDGER_TORN_TAIL)));

    rows.add(new Row("M4a", "tasks/ cannot be listed", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.TASKS_DIR && access.mode() == OpenMode.LIST, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4a", "a Work Package file cannot be read", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.WP_FILE && access.mode() == OpenMode.READ, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4a", "a Work Package file is over 1 MiB", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP02-big.md", MissionDetailServedRoute.workPackageFile("WP02", "Big") + "x".repeat(1_048_577))), ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M5", "a file with unusable frontmatter is skipped, the others are listed", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP02-bad.md", "no frontmatter at all\n")), ID, ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(new Row("M5", "a symbolic link is skipped and its target is never read", () -> build(root -> {
      MissionDetailServedRoute.write(root, "alpha", "elsewhere/WP02-target.md", MissionDetailServedRoute.workPackageFile("WP02", "Target"));
      symlink(root.resolve("kitty-specs/alpha/tasks/WP02-link.md"), root.resolve("kitty-specs/alpha/elsewhere/WP02-target.md"));
    }), ID, ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(new Row("M5", "a directory named like a Work Package file is skipped", () -> build(root -> {
      try {
        Files.createDirectories(root.resolve("kitty-specs/alpha/tasks/WP02-dir.md"));
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(new Row("M6", "a later file holds an id already indexed: the first file is served", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-two.md", MissionDetailServedRoute.workPackageFile("WP01", "Second"))), ID, ok(DiagnosticCode.WP_ID_DUPLICATE)));

    rows.add(new Row("M7", "a class-3 human field (title) holds a credential", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "Rotate " + secret()))), ID, refused(500, DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(new Row("M7", "a class-3 human field (phase label) holds a credential", () -> build(root -> MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One", "phase: \"" + secret() + "\""))), ID, refused(500, DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(new Row("M7", "a dependency id that is a path (the Java-only fixture dependency-id-leak)", () -> DetailFixture.of(fixture("projection-refusals/dependency-id-leak").dir()), "00000000000000000000000001", refused(500, DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));

    rows.add(new Row("M8", "a stat of plan.md fails other than absent", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.PLANNING_FILE && access.path().endsWith("plan.md") && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M8", "a stat of tasks.md fails other than absent", () -> {
      DetailFixture fixture = build(root -> {});
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.TASKS_MD && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M10", "tasks/ is a regular file", () -> buildAlpha(ledger(), root -> {
      try {
        Files.delete(root.resolve("kitty-specs/alpha/tasks/WP01-one.md"));
        Files.delete(root.resolve("kitty-specs/alpha/tasks"));
        Files.writeString(root.resolve("kitty-specs/alpha/tasks"), "not a directory", StandardCharsets.UTF_8);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M10", "tasks/ is a link", () -> buildAlpha(ledger(), root -> {
      try {
        Path real = root.resolve("kitty-specs/alpha/tasks");
        Path moved = root.resolve("kitty-specs/alpha/real-tasks");
        Files.move(real, moved);
        symlink(real, moved);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M13", "the host cannot decode file names and a candidate is not ASCII", () -> withEncoding(nonAscii(), NameEncoding.fixed(false)), ID, refused(500, DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M14", "nullable head dates that are not instants are served as null (head-dates-nulled)", () -> DetailFixture.of(fixture("projection-nulls/head-dates-nulled").dir()), "00000000000000000000000001", ok(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    return rows.stream();
  }

  private static TreeFixture fixture(String key) {
    return ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow();
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
    MissionDetailQueryService service = serviceOver(fixture);
    MissionId asked = new MissionId(row.askedId());

    switch (row.expect().status()) {
      case 200 -> {
        MissionDetail detail = service.mission(asked);
        assertThat(detail.overview().missionId()).isEqualTo(asked);
        assertThat(detail.phases()).hasSize(5);
        assertThat(detail.workPackages()).as("AC-12.3: no 200 with an empty list unless a row says so").isNotEmpty();
      }
      case 404 -> assertThatThrownBy(() -> service.mission(asked)).isInstanceOfSatisfying(DetailRefusal.class, refusal -> assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND));
      default ->
          assertThatThrownBy(() -> service.mission(asked))
              .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code().wire()).isEqualTo(row.expect().code()));
    }
    assertDiagnostics(fixture, row.expect());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("rows")
  void theHttpLegAnswersTheRow(Row row) {
    DetailFixture fixture = row.make().get();
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get(MissionDetailServedRoute.path(row.askedId()));

      assertThat(response.status()).isEqualTo(row.expect().status());
      JsonNode body = JSON.readTree(response.body());
      if (row.expect().status() == 200) {
        assertThat(response.header("Content-Type")).startsWith("application/json");
        assertThat(body.get("missionId").asString()).isEqualTo(row.askedId());
        assertThat(body.get("phases")).hasSize(5);
        assertThat(body.get("workPackages")).as("AC-12.3").isNotEmpty();
      } else {
        assertThat(response.header("Content-Type")).startsWith("application/problem+json");
        assertThat(body.get("code").asString()).isEqualTo(row.expect().code());
        assertThat(body.get("status").asInt()).isEqualTo(row.expect().status());
        String text = response.text();
        assertThat(text).doesNotContain(fixture.root().toString()).doesNotContain("kitty-specs").doesNotContain(".md").doesNotContain("injected");
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
    assertThat(rows).hasSizeGreaterThanOrEqualTo(24);
  }

  @ParameterizedTest(name = "[{index}]")
  @ValueSource(strings = {"01J01000", "alpha", "7", "01j01000000000000000000001", "01J0100000000000000000000", "01J010000000000000000000011"})
  void anIdThatIsNotAUlidIsNotFoundNeverABadRequest(String asked) {
    DetailFixture fixture = build(root -> {});
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get(MissionDetailServedRoute.path(asked));

      assertThat(response.status()).as("a mid8, a slug, a display number, a lowercase ULID, 25 and 27 characters: 404, never 400").isEqualTo(404);
      assertThat(JSON.readTree(response.body()).get("code").asString()).isEqualTo("not_found");
    }
    assertThat(MissionId.parse(asked)).isEmpty();
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void aWellFormedIdThatNoMissionHoldsIsNotFoundWithNoDiagnostic() {
    DetailFixture fixture = build(root -> {});

    assertThatThrownBy(() -> serviceOver(fixture).mission(new MissionId(Rows.GAMMA_ID))).isInstanceOfSatisfying(DetailRefusal.class, refusal -> assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND));
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @Test
  void anAbsentLedgerIsTheDraftHeadAndAnAbsentTasksDirectoryIsAnEmptyIndexAnd200() {
    DetailFixture absentLedger = buildAlpha(null, root -> {});
    MissionDetail draft = serviceOver(absentLedger).mission(new MissionId(ID));
    assertThat(draft.overview().lifecycleStatus()).isEqualTo(LifecycleStatus.DRAFT);
    assertThat(draft.overview().wpTotal()).isZero();

    DetailFixture noTasks = MissionDetailServedRoute.fixtureOf(FixtureSpec.of(alpha(ledger())), root -> {});
    MissionDetail empty = serviceOver(noTasks).mission(new MissionId(ID));
    assertThat(empty.workPackages()).isEmpty();
    assertThat(empty.overview().wpTotal()).as("the ledger still counts the Work Package").isEqualTo(1);
    assertThat(noTasks.diagnostics()).isEmpty();
  }

  @Test
  void aWorkPackageWithEventsAndNoFileIsNotListedButCountsAndOneWithAFileAndNoEventsHasANullLane() {
    // the ledger knows WP01 (file below) and WP09 (no file)
    DetailFixture both =
        MissionDetailServedRoute.fixtureOf(
            FixtureSpec.of(alpha(ledger() + Rows.status(Rows.id(2), "2026-09-01T10:02:00Z", "WP09", "planned", "claimed"))),
            root -> {
              MissionDetailServedRoute.write(root, "alpha", "tasks/WP01-one.md", MissionDetailServedRoute.workPackageFile("WP01", "One"));
              MissionDetailServedRoute.write(root, "alpha", "tasks/WP02-new.md", MissionDetailServedRoute.workPackageFile("WP02", "No events yet"));
            });

    MissionDetail detail = serviceOver(both).mission(new MissionId(ID));

    assertThat(detail.workPackages()).extracting(summary -> summary.wpId().value()).containsExactly("WP01", "WP02");
    assertThat(detail.workPackages().get(0).statusLane()).isNotNull();
    assertThat(detail.workPackages().get(1).statusLane()).as("a file and no events").isNull();
    assertThat(detail.workPackages().get(1).lastTransitionAt()).isNull();
    assertThat(detail.overview().wpTotal()).as("WP01 and WP09 count, WP02 has no event and WP09 has no file").isEqualTo(2);
    assertThat(both.diagnostics()).isEmpty();
  }

  @ParameterizedTest(name = "{0}")
  @ValueSource(strings = {"ps-link-file", "ps-link-completed", "ps-link-started", "ps-link-neither"})
  void aSymbolicPlanningFileIsNoArtifactAndWritesOnePathRefusedEach(String name) {
    DetailFixture fixture = DetailFixture.of(fixture("phases-matrix/" + name).dir());

    MissionDetail detail = serviceOver(fixture).mission(new MissionId("00000000000000000000000001"));

    boolean completed = name.equals("ps-link-completed");
    boolean started = name.equals("ps-link-started");
    for (int i = 0; i < 3; i++) {
      assertThat(detail.phases().get(i).basis().wire()).isEqualTo(completed || started ? "lifecycle_event" : "artifact");
      assertThat(detail.phases().get(i).status().wire()).isEqualTo(completed ? "complete" : started ? "in_progress" : "pending");
    }
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PATH_REFUSED, DiagnosticCode.PATH_REFUSED, DiagnosticCode.PATH_REFUSED);
  }

  @Test
  void subtasksWrittenAsMappingsAreProjectionRefusedNotStringified() {
    DetailFixture fixture = DetailFixture.of(fixture("wp-malformed-frontmatter/wpm-28").dir());

    assertThatThrownBy(() -> serviceOver(fixture).mission(new MissionId("00000000000000000000000001")))
        .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED));
    assertThat(fixture.diagnostics()).extracting(Diagnostic::code).containsExactly(DiagnosticCode.PROJECTION_REFUSED);
  }

  @Test
  void aNonAsciiFileNameIsServedWhenTheHostDecodesNamesWhateverTheLocale() {
    DetailFixture fixture = withEncoding(nonAscii(), NameEncoding.fixed(true));

    MissionDetail detail = serviceOver(fixture).mission(new MissionId(ID));

    assertThat(detail.workPackages()).extracting(summary -> summary.wpId().value()).containsExactly("WP01", "WP02");
  }

  @Test
  void aRealNonAsciiNameOnAUtf8HostIsServed(TestInfo info) {
    Utf8Host.assumeUtf8(info.getTestClass().orElseThrow().getName() + "#" + info.getTestMethod().orElseThrow().getName());
    DetailFixture fixture = nonAscii();

    MissionDetail detail = serviceOver(fixture).mission(new MissionId(ID));

    assertThat(detail.workPackages()).hasSize(2);
  }

  @Test
  void aRealPermissionRefusalOfTasksIsTheSameRowWhenTheOperatingSystemRefusesIt(TestInfo info) {
    DetailFixture fixture = build(root -> {});
    Path tasks = fixture.root().resolve("kitty-specs/alpha/tasks");
    try (RealPermissionFixture ignored = RealPermissionFixture.refusedForThisUser(tasks, info.getTestClass().orElseThrow().getName() + "#" + info.getTestMethod().orElseThrow().getName())) {
      assertThatThrownBy(() -> serviceOver(fixture).mission(new MissionId(ID)))
          .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code()).isEqualTo(DiagnosticCode.SOURCE_UNREADABLE));
    }
  }

  @Test
  void aMissionIsReadFromThePrimaryDirectoryAndTheStatLeavesTheCoordinationCopyAlone() {
    DetailFixture fixture = build(root -> MissionDetailServedRoute.write(root, "alpha", "plan.md", "# plan\n"));
    fixture.recorder().clear();

    serviceOver(fixture).mission(new MissionId(ID));

    List<String> stats = fixture.recorder().accesses().stream().filter(access -> access.pathClass() == PathClass.PLANNING_FILE).map(access -> access.path()).toList();
    assertThat(stats).containsExactlyInAnyOrder("kitty-specs/alpha/spec.md", "kitty-specs/alpha/plan.md");
    assertThat(Arrays.asList(OpenMode.values())).contains(OpenMode.STAT);
  }
}
