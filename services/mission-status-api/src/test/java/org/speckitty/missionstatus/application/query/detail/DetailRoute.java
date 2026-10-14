package org.speckitty.missionstatus.application.query.detail;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;
import org.speckitty.missionstatus.adapter.out.filesystem.JsonLanesDecoder;
import org.speckitty.missionstatus.adapter.out.filesystem.YamlFrontmatterDecoder;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.WorkPackageDetailQueryService;
import org.speckitty.missionstatus.application.query.index.WorkPackageIndex;
import org.speckitty.missionstatus.application.query.port.in.WorkPackageDetailQuery;
import org.speckitty.missionstatus.application.query.port.out.TextSource;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.readmodel.detail.WorkPackageDetail;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * What every test of the Work Package detail route shares: the real service over a fixture, the production application with that service
 * installed as the port, and builders for the one Mission {@code alpha} these tests describe (a ledger, Work Package files, {@code tasks.md},
 * {@code lanes.json}, review cycles and lane worktrees). Test support only.
 */
public final class DetailRoute {

  public static final String ID = Rows.ALPHA_ID;
  public static final String MID8 = ID.substring(0, 8);
  public static final String MISSION = "alpha";
  public static final String CREATED = "2026-09-01T10:00:00+00:00";

  private DetailRoute() {}

  // ---- the service ------------------------------------------------------------------------------------------------------------------

  /** The real service over the fixture with its own gate. */
  public static WorkPackageDetailQueryService serviceOver(DetailFixture fixture) {
    return serviceOver(fixture, fixture.textSource(), new AdmissionGate());
  }

  /** The real service over the fixture's read model with another text source and another gate. */
  public static WorkPackageDetailQueryService serviceOver(DetailFixture fixture, TextSource text, AdmissionGate gate) {
    YamlFrontmatterDecoder decoder = new YamlFrontmatterDecoder();
    return new WorkPackageDetailQueryService(
        fixture.readModel(), new WorkPackageIndex(text, decoder), text, decoder, new JsonLanesDecoder(), gate, fixture.built().handles().recorder(), LeakPatternsFile.load());
  }

  /** The production application on a real socket with {@link #serviceOver} installed as the Work Package detail port. */
  public static HttpHarness serve(DetailFixture fixture) {
    return HttpHarness.startWith(fixture.built(), Map.of(WorkPackageDetailQuery.class, serviceOver(fixture)));
  }

  public static WorkPackageDetail detail(DetailFixture fixture, String wpId) {
    return serviceOver(fixture).workPackageDetail(new MissionId(ID), new WpId(wpId));
  }

  /** The detail of a Work Package of a Mission of a committed fixture, whose synthetic id is not {@link #ID}. */
  public static WorkPackageDetail detail(DetailFixture fixture, String missionId, String wpId) {
    return serviceOver(fixture).workPackageDetail(new MissionId(missionId), new WpId(wpId));
  }

  public static String path(String wpId) {
    return "/api/v1/missions/" + ID + "/work-packages/" + wpId + "/detail";
  }

  // ---- fixtures ---------------------------------------------------------------------------------------------------------------------

  /** The status of WP01 moving to {@code claimed}: the ledger every test starts from. */
  public static String ledger() {
    return Rows.status(Rows.id(1), "2026-09-01T10:01:00Z", "WP01", "planned", "claimed");
  }

  /** The Mission {@code alpha} with this ledger, the file {@code tasks/WP01-one.md} and whatever {@code extras} add below the project root. */
  public static DetailFixture fixture(String ledger, Consumer<Path> extras) {
    return MissionDetailServedRoute.fixtureOf(
        FixtureSpec.of(PortFixtures.mission(MISSION, ID, CREATED, ledger)),
        root -> {
          write(root, "tasks/WP01-one.md", wpFile("WP01", "One"));
          extras.accept(root);
        });
  }

  public static DetailFixture fixture(Consumer<Path> extras) {
    return fixture(ledger(), extras);
  }

  /** A Work Package file: the identifier, the title and the given frontmatter lines (YAML, one per line). */
  public static String wpFile(String id, String title, String... lines) {
    return MissionDetailServedRoute.workPackageFile(id, title, lines);
  }

  /** A text file below the Mission directory, creating the directories. */
  public static void write(Path root, String relative, String text) {
    MissionDetailServedRoute.write(root, MISSION, relative, text);
  }

  /** A file below the project root (for example under {@code .worktrees/}), creating the directories. */
  public static void writeAtRoot(Path root, String relative, String text) {
    Path file = root.resolve(relative);
    try {
      Files.createDirectories(file.getParent());
      Files.writeString(file, text, StandardCharsets.UTF_8);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Deletes a file below the Mission directory. */
  public static void delete(Path root, String relative) {
    try {
      Files.delete(root.resolve("kitty-specs").resolve(MISSION).resolve(relative));
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  public static void directory(Path root, String relative) {
    try {
      Files.createDirectories(root.resolve(relative));
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  public static void symlink(Path link, Path target) {
    try {
      Files.createDirectories(link.getParent());
      Files.createSymbolicLink(link, target);
    } catch (IOException | UnsupportedOperationException unsupported) {
      org.junit.jupiter.api.Assumptions.abort("symbolic links cannot be made here");
    }
  }

  /** A current-shape {@code lanes.json}: each lane is {@code "lane-a:WP01,WP02"}. */
  public static String lanes(String missionSlug, String... lanes) {
    StringBuilder out = new StringBuilder("{\"computed_at\":\"2026-09-01T10:00:00+00:00\",\"computed_from\":\"fixture\",\"lanes\":[");
    for (int i = 0; i < lanes.length; i++) {
      String[] parts = lanes[i].split(":", 2);
      List<String> ids = parts.length > 1 && !parts[1].isEmpty() ? List.of(parts[1].split(",")) : List.of();
      out.append(i == 0 ? "" : ",").append("{\"depends_on_lanes\":[],\"lane_id\":\"").append(parts[0]).append("\",\"parallel_group\":0,\"predicted_surfaces\":[],\"wp_ids\":[");
      for (int j = 0; j < ids.size(); j++) {
        out.append(j == 0 ? "" : ",").append('"').append(ids.get(j)).append('"');
      }
      out.append("],\"write_scope\":[]}");
    }
    return out.append("],\"mission_branch\":\"kitty/mission-").append(missionSlug).append("\",\"mission_id\":\"").append(ID).append("\",\"mission_slug\":\"").append(missionSlug).append("\",\"target_branch\":\"main\",\"version\":1}").toString();
  }

  /** A review-cycle file that parses. */
  public static String cycleFile(int number, String reviewer, String reviewedAt) {
    return "---\naffected_files: []\ncycle_number: " + number + "\nmission_slug: " + MISSION + "\nreviewed_at: '" + reviewedAt + "'\nreviewer_agent: " + reviewer + "\nwp_id: WP01\n---\n\nFeedback.\n";
  }

  /** A ledger row that moves a Work Package and carries a review result. */
  public static String review(int n, String at, String wpId, String from, String to, String reference, String verdict) {
    return "{\"actor\":\"claude\",\"at\":\"" + at + "\",\"event_id\":\"" + Rows.id(n) + "\",\"evidence\":null,\"execution_mode\":\"worktree\",\"force\":false,\"from_lane\":\"" + from
        + "\",\"reason\":null,\"review_ref\":null,\"review_result\":{\"reference\":" + reference + ",\"reviewer\":\"reviewer-renata\",\"verdict\":\"" + verdict + "\"},\"to_lane\":\"" + to
        + "\",\"wp_id\":\"" + wpId + "\"}\n";
  }

  /** An annotation row that sets the status of subtasks. */
  public static String subtasks(int n, String at, String wpId, String statuses) {
    return "{\"actor\":\"claude\",\"at\":\"" + at + "\",\"delta\":{\"subtasks\":" + statuses + "},\"event_id\":\"" + Rows.id(n) + "\",\"kind\":\"annotation\",\"wp_id\":\"" + wpId + "\"}\n";
  }

  /** Text that is a credential only when assembled here: no committed byte of this file matches the pattern (D-48). */
  public static String secret() {
    return "gh" + "p_" + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7Op8Qr9St0Uv1Wx2Yz3";
  }
}
