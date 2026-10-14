package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.CREATED;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ID;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.ledger;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.secret;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.serve;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.serviceOver;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.write;
import static org.speckitty.missionstatus.application.query.detail.DetailRoute.wpFile;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.AccessDeniedException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.function.Consumer;
import java.util.function.Supplier;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.application.query.WorkPackageDetailQueryService;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.ConformanceTree.TreeFixture;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/**
 * AC-3.8 and AC-12.1: one fixture and one assertion for each row of the FR-012 table that applies to {@code getWorkPackageDetail}, at the port (a
 * typed result, {@link DetailRefusal} or {@link MissionStatusUnavailable} carrying the diagnostic code) and at the HTTP leg (status and the
 * route's Problem), with the diagnostics the service wrote. On this route every 500 is {@code source_unreadable} at the HTTP leg whatever the
 * diagnostic says (the contract has no other 500), and every 404 is {@code not_found}. A permission failure is an injected fault, always; the real
 * file-system leg has its own class ({@code WorkPackageDetailPermissionTest}).
 *
 * <p>Every row is a {@link Row}; {@link #everyRowOfTheTableThatAppliesHasAFixture} is the discovered-row floor: delete one row and it goes red.
 */
public class WorkPackageDetailRowsTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  /** The table rows that apply to the detail and that this class owns a fixture for (C1 is the controller test's; C2 and W1 have their own methods). */
  private static final Set<String> REQUIRED_ROWS =
      Set.of("C3", "C4", "C5", "C6", "C7", "M1", "M2", "M3", "M4a", "M4b", "M5", "M6", "M7", "M9", "M10", "M11", "M12", "M13", "M14", "W1", "W3");

  /** What a row answers: 200, 404 or 500, the diagnostic code of the port's refusal, and the diagnostic codes written, in order. */
  private record Expect(int status, DiagnosticCode refusal, List<DiagnosticCode> diagnostics) {}

  private record Row(String id, String name, Supplier<DetailFixture> make, String askedMission, String askedWp, Expect expect) {
    @Override
    public String toString() {
      return id + " " + name;
    }
  }

  private static Expect ok(DiagnosticCode... diagnostics) {
    return new Expect(200, null, List.of(diagnostics));
  }

  private static Expect unreadable(DiagnosticCode refusal, DiagnosticCode... diagnostics) {
    return new Expect(500, refusal, List.of(diagnostics));
  }

  private static Expect notFound(DiagnosticCode... diagnostics) {
    return new Expect(404, null, List.of(diagnostics));
  }

  // ---- fixture builders ---------------------------------------------------------------------------------------------------------------

  private static FixtureSpec.Mission alpha(String ledger) {
    return PortFixtures.mission("alpha", ID, CREATED, ledger);
  }

  private static FixtureSpec.Mission brokenMeta(String name) {
    return FixtureSpec.Mission.of(name, "{not json", null);
  }

  /** A Mission {@code alpha} with the Work Package file WP01 and the given extras, plus the given sibling Missions. */
  private static DetailFixture build(Consumer<Path> extras, FixtureSpec.Mission... siblings) {
    List<FixtureSpec.Mission> missions = new ArrayList<>(List.of(siblings));
    if (missions.stream().noneMatch(mission -> mission.name().equals("alpha"))) {
      missions.add(alpha(ledger()));
    }
    return MissionDetailServedRoute.fixtureOf(
        new FixtureSpec(FixtureSpec.Project.healthy(), missions),
        root -> {
          write(root, "tasks/WP01-one.md", wpFile("WP01", "One"));
          extras.accept(root);
        });
  }

  private static DetailFixture buildLedger(String ledger, Consumer<Path> extras) {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(alpha(ledger)),
        root -> {
          write(root, "tasks/WP01-one.md", wpFile("WP01", "One"));
          extras.accept(root);
        });
  }

  private static void symlink(Path link, Path target) {
    DetailRoute.symlink(link, target);
  }

  private static DetailFixture failing(DetailFixture fixture, PathClass pathClass, OpenMode mode) {
    fixture.recorder().failWhen(access -> access.pathClass() == pathClass && access.mode() == mode, () -> new AccessDeniedException("injected"));
    return fixture;
  }

  private static TreeFixture treeFixture(String key) {
    return ConformanceTree.detailFixtures().stream().filter(candidate -> candidate.key().equals(key)).findFirst().orElseThrow();
  }

  private static void replace(Path root, String relative, byte[] content) {
    try {
      Files.write(root.resolve("kitty-specs/alpha").resolve(relative), content);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static byte[] padded(String head, int size) {
    byte[] out = new byte[size];
    java.util.Arrays.fill(out, (byte) ' ');
    byte[] bytes = head.getBytes(StandardCharsets.UTF_8);
    System.arraycopy(bytes, 0, out, 0, bytes.length);
    return out;
  }

  // ---- the rows --------------------------------------------------------------------------------------------------------------------

  static Stream<Row> rows() {
    List<Row> rows = new ArrayList<>();
    String gamma = Rows.GAMMA_ID;

    rows.add(new Row("C3", "a Mission directory refused by the link rule is the first fault and no Mission holds the id", () -> build(root -> symlink(root.resolve("kitty-specs/aaa-link"), root.resolve("kitty-specs/alpha"))), gamma, "WP01", notFound(DiagnosticCode.PATH_REFUSED)));
    rows.add(new Row("C4", "the first fault of the scan is an unusable meta.json", () -> build(root -> {}, brokenMeta("broken")), gamma, "WP01", unreadable(DiagnosticCode.META_UNPARSEABLE, DiagnosticCode.META_UNPARSEABLE)));
    rows.add(new Row("C5", "kitty-specs cannot be listed", () -> failing(build(root -> {}), PathClass.SPECS_DIR, OpenMode.LIST), ID, "WP01", unreadable(DiagnosticCode.MISSION_DIR_UNREADABLE, DiagnosticCode.MISSION_DIR_UNREADABLE)));
    rows.add(new Row("C5", "the first fault of the scan is a Mission directory that cannot be read", () -> {
      DetailFixture fixture = build(root -> {}, alpha(ledger()), PortFixtures.mission("aaa-sibling", Rows.BETA_ID, CREATED, ""));
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.MISSION_META && access.path().contains("aaa-sibling"), () -> new AccessDeniedException("injected"));
      return fixture;
    }, gamma, "WP01", unreadable(DiagnosticCode.MISSION_DIR_UNREADABLE, DiagnosticCode.MISSION_DIR_UNREADABLE)));
    rows.add(new Row("C6", "two readable directories hold the id, the first in byte order is served", () -> build(root -> {}, alpha(ledger()), PortFixtures.mission("alpha-copy", ID, CREATED, ledger())), ID, "WP01", ok(DiagnosticCode.MISSION_ID_DUPLICATE)));
    rows.add(new Row("C7", "a faulted sibling before and one after the match", () -> build(root -> {}, brokenMeta("aaa-broken"), alpha(ledger()), brokenMeta("zzz-broken")), ID, "WP01", ok()));
    rows.add(new Row("C7", "a faulted sibling after a duplicate", () -> build(root -> {}, alpha(ledger()), PortFixtures.mission("alpha-copy", ID, CREATED, ledger()), brokenMeta("zzz-broken")), ID, "WP01", ok(DiagnosticCode.MISSION_ID_DUPLICATE)));

    rows.add(new Row("M1", "the ledger is absent: the state of an empty ledger", () -> buildLedger(null, root -> {}), ID, "WP01", ok()));
    rows.add(new Row("M2", "the ledger is unreadable: 200 and the diagnostic together", () -> failing(buildLedger(ledger(), root -> {}), PathClass.LEDGER, OpenMode.READ), ID, "WP01", ok(DiagnosticCode.LEDGER_UNREADABLE)));
    rows.add(new Row("M3", "the ledger is not decodable", () -> buildLedger("this is not json\n", root -> {}), ID, "WP01", unreadable(DiagnosticCode.LEDGER_UNPARSEABLE, DiagnosticCode.LEDGER_UNPARSEABLE)));
    rows.add(new Row("M3", "the ledger has a torn tail", () -> buildLedger(ledger() + "{\"event_id\": \"torn", root -> {}), ID, "WP01", unreadable(DiagnosticCode.LEDGER_TORN_TAIL, DiagnosticCode.LEDGER_TORN_TAIL)));

    rows.add(new Row("M4a", "tasks/ cannot be listed", () -> failing(build(root -> {}), PathClass.TASKS_DIR, OpenMode.LIST), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4a", "a Work Package file cannot be read", () -> failing(build(root -> {}), PathClass.WP_FILE, OpenMode.READ), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4a", "a Work Package file is over 1 MiB", () -> build(root -> write(root, "tasks/WP02-big.md", wpFile("WP02", "Big") + "x".repeat(1_048_577))), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M4b", "tasks.md is over 4 MiB", () -> build(root -> replace(root, "tasks.md", padded("## WP01\n", 4_194_305))), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4b", "tasks.md is not UTF-8", () -> build(root -> replace(root, "tasks.md", new byte[] {'#', '#', ' ', (byte) 0xC3, (byte) 0x28})), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4b", "tasks.md cannot be read", () -> failing(build(root -> write(root, "tasks.md", "## WP01\n")), PathClass.TASKS_MD, OpenMode.READ), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4b", "a review-cycle directory cannot be listed", () -> failing(build(root -> write(root, "tasks/WP01-one/review-cycle-1.md", DetailRoute.cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"))), PathClass.WP_CYCLE_DIR, OpenMode.LIST), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M4b", "a .worktrees stat fails other than absent", () -> failing(build(root -> {
      write(root, "lanes.json", DetailRoute.lanes("alpha", "lane-a:WP01"));
      DetailRoute.directory(root, ".worktrees/alpha-lane-a");
    }), PathClass.WORKTREE_LANE, OpenMode.STAT), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M5", "a file with unusable frontmatter is skipped and the Work Package of another file is served", () -> build(root -> write(root, "tasks/WP02-bad.md", "no frontmatter at all\n")), ID, "WP01", ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(new Row("M5", "the only file of the requested Work Package is skipped: it is not found", () -> build(root -> write(root, "tasks/WP02-bad.md", "no frontmatter at all\n")), ID, "WP02", notFound(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(new Row("M5", "a symbolic link is skipped and its target is never read", () -> build(root -> {
      write(root, "elsewhere/WP02-target.md", wpFile("WP02", "Target"));
      symlink(root.resolve("kitty-specs/alpha/tasks/WP02-link.md"), root.resolve("kitty-specs/alpha/elsewhere/WP02-target.md"));
    }), ID, "WP02", notFound(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(new Row("M5", "a directory named like a Work Package file is skipped", () -> build(root -> DetailRoute.directory(root, "kitty-specs/alpha/tasks/WP02-dir.md")), ID, "WP01", ok(DiagnosticCode.WP_FILE_SKIPPED)));
    rows.add(new Row("M6", "a later file holds an id already indexed: the first file is served", () -> build(root -> write(root, "tasks/WP01-two.md", wpFile("WP01", "Second"))), ID, "WP01", ok(DiagnosticCode.WP_ID_DUPLICATE)));

    rows.add(new Row("M7", "a subtask reference that is a path", () -> build(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks:", "  - /home/someone/private"))), ID, "WP01", unreadable(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(new Row("M7", "an owned-file pattern that is a path (the Java-only fixture owned-file-pattern-leak)", () -> DetailFixture.of(treeFixture("projection-refusals/owned-file-pattern-leak").dir()), "00000000000000000000000001", "WP01", unreadable(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(new Row("M7", "a dependency id that is a path (the Java-only fixture dependency-id-leak)", () -> DetailFixture.of(treeFixture("projection-refusals/dependency-id-leak").dir()), "00000000000000000000000001", "WP01", unreadable(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(new Row("M7", "a subtask status that is not a display lane", () -> buildLedger(ledger() + DetailRoute.subtasks(2, "2026-09-01T10:02:00Z", "WP01", "{\"T001\":\"genesis\"}"), root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"))), ID, "WP01", unreadable(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(new Row("M7", "subtasks written as mappings (SK-353)", () -> build(root -> write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks:", "  - id: T001"))), ID, "WP01", unreadable(DiagnosticCode.PROJECTION_REFUSED, DiagnosticCode.PROJECTION_REFUSED)));

    rows.add(new Row("M9", "a stat of spec.md fails other than absent while the references are built", () -> {
      DetailFixture fixture = build(root -> write(root, "spec.md", "# Spec\n"));
      fixture.recorder().failWhen(access -> access.pathClass() == PathClass.PLANNING_FILE && access.path().endsWith("spec.md") && access.mode() == OpenMode.STAT, () -> new AccessDeniedException("injected"));
      return fixture;
    }, ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M10", "tasks/ is a regular file", () -> buildLedger(ledger(), root -> {
      try {
        Files.delete(root.resolve("kitty-specs/alpha/tasks/WP01-one.md"));
        Files.delete(root.resolve("kitty-specs/alpha/tasks"));
        Files.writeString(root.resolve("kitty-specs/alpha/tasks"), "not a directory", StandardCharsets.UTF_8);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("M10", "tasks/ is a link", () -> buildLedger(ledger(), root -> {
      try {
        Path real = root.resolve("kitty-specs/alpha/tasks");
        Path moved = root.resolve("kitty-specs/alpha/real-tasks");
        Files.move(real, moved);
        symlink(real, moved);
      } catch (IOException failure) {
        throw new UncheckedIOException(failure);
      }
    }), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M11", "a review-cycle file that does not parse is an entry with null members", () -> build(root -> write(root, "tasks/WP01-one/review-cycle-1.md", "no frontmatter\n")), ID, "WP01", ok()));
    rows.add(new Row("M11", "a review-cycle file over 262144 bytes is an entry with null members", () -> build(root -> write(root, "tasks/WP01-one/review-cycle-1.md", "x".repeat(262_145))), ID, "WP01", ok()));

    rows.add(new Row("M12", "a subtask title holds a credential", () -> build(root -> {
      write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "subtasks: [T001]"));
      write(root, "tasks.md", "## WP01\n- [ ] T001 Rotate " + secret() + "\n");
    }), ID, "WP01", ok(DiagnosticCode.PROJECTION_REFUSED)));
    rows.add(new Row("M12", "a dependency title holds a credential", () -> build(root -> {
      write(root, "tasks/WP01-one.md", wpFile("WP01", "One", "dependencies: [WP02]"));
      write(root, "tasks/WP02-two.md", wpFile("WP02", "Rotate " + secret()));
    }), ID, "WP01", ok(DiagnosticCode.PROJECTION_REFUSED)));

    rows.add(new Row("M13", "the host cannot decode file names and a candidate is not ASCII", () -> withEncoding(nonAscii(), NameEncoding.fixed(false)), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));

    rows.add(new Row("M14", "a planning branch that cannot be shown is null (planning-branch-too-long)", () -> DetailFixture.of(treeFixture("projection-nulls/planning-branch-too-long").dir()), "00000000000000000000000001", "WP01", ok()));
    rows.add(new Row("M14", "a lane id that fails the pattern is null (lane-id-fails-pattern)", () -> DetailFixture.of(treeFixture("projection-nulls/lane-id-fails-pattern").dir()), "00000000000000000000000001", "WP01", ok()));
    rows.add(new Row("M14", "a review time that is not a date-time is null (reviewed-at-junk)", () -> DetailFixture.of(treeFixture("projection-nulls/reviewed-at-junk").dir()), "00000000000000000000000001", "WP01", ok()));

    rows.add(new Row("W1", "an unknown Work Package", () -> build(root -> {}), ID, "WP99", notFound()));
    rows.add(new Row("W1", "a Work Package only the ledger knows", () -> buildLedger(ledger() + Rows.status(Rows.id(2), "2026-09-01T10:02:00Z", "WP07", "planned", "claimed"), root -> {}), ID, "WP07", notFound()));

    rows.add(new Row("W3", "lanes.json is of the legacy shape (legacy-lanes-json)", () -> DetailFixture.of(treeFixture("legacy-lanes-json/legacy-lanes-json").dir()), "00000000000000000000000001", "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("W3", "lanes.json is corrupt", () -> build(root -> write(root, "lanes.json", "{not json")), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    rows.add(new Row("W3", "lanes.json is over 1 MiB", () -> build(root -> replace(root, "lanes.json", padded(DetailRoute.lanes("alpha", "lane-a:WP01"), 1_048_577))), ID, "WP01", unreadable(DiagnosticCode.SOURCE_UNREADABLE, DiagnosticCode.SOURCE_UNREADABLE)));
    return rows.stream();
  }

  private static DetailFixture nonAscii() {
    return build(root -> write(root, "tasks/WP02-\u00e9.md", wpFile("WP02", "Accent")));
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
    WorkPackageDetailQueryService service = serviceOver(fixture);
    MissionId mission = new MissionId(row.askedMission());
    WpId wp = new WpId(row.askedWp());

    switch (row.expect().status()) {
      case 200 -> {
        WorkPackageDetail detail = service.workPackageDetail(mission, wp);
        assertThat(detail.missionId()).isEqualTo(mission);
        assertThat(detail.wpId()).isEqualTo(wp);
      }
      case 404 -> assertThatThrownBy(() -> service.workPackageDetail(mission, wp)).isInstanceOfSatisfying(DetailRefusal.class, refusal -> assertThat(refusal.kind()).isEqualTo(DetailRefusal.Kind.NOT_FOUND));
      default ->
          assertThatThrownBy(() -> service.workPackageDetail(mission, wp))
              .isInstanceOfSatisfying(MissionStatusUnavailable.class, unavailable -> assertThat(unavailable.code()).isEqualTo(row.expect().refusal()));
    }
    assertDiagnostics(fixture, row.expect());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("rows")
  void theHttpLegAnswersTheRowWithTheRoutesOwnProblem(Row row) {
    DetailFixture fixture = row.make().get();
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get("/api/v1/missions/" + row.askedMission() + "/work-packages/" + row.askedWp() + "/detail");

      assertThat(response.status()).isEqualTo(row.expect().status());
      JsonNode body = JSON.readTree(response.body());
      if (row.expect().status() == 200) {
        assertThat(response.header("Content-Type")).startsWith("application/json");
        assertThat(body.get("missionId").asString()).isEqualTo(row.askedMission());
        assertThat(body.get("wpId").asString()).isEqualTo(row.askedWp());
      } else {
        assertThat(response.header("Content-Type")).startsWith("application/problem+json");
        boolean missing = row.expect().status() == 404;
        assertThat(body.get("code").asString()).isEqualTo(missing ? "not_found" : "source_unreadable");
        assertThat(body.get("status").asInt()).isEqualTo(row.expect().status());
        assertThat(body.get("type").asString()).isEqualTo("about:blank");
        assertThat(body.get("title").asString()).isEqualTo(missing ? "The work package was not found" : "A source of the work package could not be read");
        assertThat(body.get("detail").asString()).isEqualTo(missing ? "No work package with this identifier exists in the Mission." : "A file the detail is built from could not be read.");
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
    assertThat(rows).hasSizeGreaterThanOrEqualTo(44);
  }

  @ParameterizedTest(name = "[{index}]")
  @ValueSource(strings = {"01J01000", "alpha", "7", "01j01000000000000000000001", "01J0100000000000000000000", "01J010000000000000000000011"})
  void aMissionIdThatIsNotAUlidIsNotFoundNeverABadRequest(String asked) {
    DetailFixture fixture = build(root -> {});
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get("/api/v1/missions/" + asked + "/work-packages/WP01/detail");

      assertThat(response.status()).as("a mid8, a slug, a display number, a lowercase ULID, 25 and 27 characters: 404, never 400").isEqualTo(404);
      assertThat(JSON.readTree(response.body()).get("code").asString()).isEqualTo("not_found");
    }
    assertThat(MissionId.parse(asked)).isEmpty();
    assertThat(fixture.diagnostics()).isEmpty();
  }

  @ParameterizedTest(name = "[{index}]")
  @ValueSource(strings = {"wp01", "WP1", "WP01x", "WP-01", "WP\uff10\uff11", "WP01%0A", "WP", "01", "WP0000000000000000000000000000000000000000000000000000000000000000000000"})
  void aWorkPackageIdThatIsNotWellFormedIsNotFoundNeverABadRequest(String asked) {
    DetailFixture fixture = build(root -> {});
    try (HttpHarness server = serve(fixture)) {
      HttpHarness.Response response = server.get("/api/v1/missions/" + ID + "/work-packages/" + asked + "/detail");

      assertThat(response.status()).isEqualTo(404);
      assertThat(JSON.readTree(response.body()).get("code").asString()).isEqualTo("not_found");
    }
    assertThat(WpId.parse(asked)).isEmpty();
    assertThat(fixture.diagnostics()).isEmpty();
  }
}
