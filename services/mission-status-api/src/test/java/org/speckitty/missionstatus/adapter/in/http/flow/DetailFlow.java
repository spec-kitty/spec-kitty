package org.speckitty.missionstatus.adapter.in.http.flow;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import org.speckitty.missionstatus.application.query.detail.DetailRoute;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.DetailFixture;
import org.speckitty.missionstatus.testsupport.RouteMarker;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The curated request set of the five detail routes (WP18, T126): the Missions the flow runs over, the requests of each route with the route
 * name the recorder notes for it, and the server with the four fixture-built services installed so the recording seam of the fixture is in the
 * request path. The three routes of #5529 are in the same flow under {@link #PROJECT} and {@link #MISSIONS}, so "all eight data routes" is one list.
 */
public final class DetailFlow {

  public static final String PROJECT = "getProject";
  public static final String MISSIONS = "listMissions";
  public static final String MISSION = "getMission";
  public static final String WORK_PACKAGE = "getWorkPackage";
  public static final String DETAIL = "getWorkPackageDetail";
  public static final String LISTING = "listArtifacts";
  public static final String CONTENT = "getArtifactContent";

  /** The five detail routes by the name the recorder notes. */
  public static final List<String> DETAIL_ROUTES = List.of(MISSION, WORK_PACKAGE, DETAIL, LISTING, CONTENT);

  /** The canary values of the scan: a host path, an address and a token-shaped string (assembled here, so no committed byte matches a pattern). */
  public static final String CANARY_PATH = "/" + String.join("/", "ho" + "me", "canary-user", "CANARY-DETAIL-11");
  public static final String CANARY_ADDRESS = "canary-11@example.invalid";
  public static final String CANARY_TOKEN = "gh" + "p_" + "c".repeat(36);

  private DetailFlow() {}

  /** A Mission of the flow: the fixture, the id and the primary directory name. */
  public record Project(String name, DetailFixture fixture, String missionId, String directory) {
    @Override
    public String toString() {
      return name;
    }
  }

  /** The Mission {@code alpha}: its {@code meta.json} stores no topology, so {@code lanes.json} is read to classify it. */
  public static Project noTopology() {
    DetailFixture fixture =
        DetailRoute.fixture(
            root -> {
              DetailRoute.write(root, "tasks.md", "## WP01\n- [ ] T001 First subtask\n- [x] T002 Second subtask\n");
              DetailRoute.write(root, "spec.md", "# Specification\n");
              DetailRoute.write(root, "plan.md", "# Plan\n");
              DetailRoute.write(root, "lanes.json", DetailRoute.lanes("alpha", "lane-a:WP01"));
              DetailRoute.write(root, "tasks/WP01-one/review-cycle-1.md", DetailRoute.cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
              DetailRoute.write(root, "notes/readme.md", "Notes for the Mission.\n");
              DetailRoute.write(root, "data.csv", "a,b\n1,2\n");
              DetailRoute.write(root, "leaky.md", "token " + DetailRoute.secret() + "\n");
              DetailRoute.writeAtRoot(root, ".worktrees/alpha-lane-a/.git", "gitdir: elsewhere\n");
              tryLink(root.resolve("kitty-specs/alpha/linked.md"), Path.of("spec.md"));
              tryLink(root.resolve("kitty-specs/alpha/linked-dir"), Path.of("notes"));
            });
    // the fixture is a copy of the tree just written, with fresh modification times: pin them after the copy
    pinMtimes(fixture.root(), PINNED_MTIME);
    return new Project("no-topology", fixture, DetailRoute.ID, "alpha");
  }

  /** The instant the committed conformance fixtures use; every file of a flow fixture carries it, so no two fixtures differ by a second boundary. */
  static final java.time.Instant PINNED_MTIME = java.time.Instant.parse("2026-09-21T14:13:20Z");

  /** Sets the modification time of every regular file and directory under the root (links are not followed). */
  static void pinMtimes(Path root, java.time.Instant at) {
    try (var walk = Files.walk(root)) {
      for (Path path : (Iterable<Path>) walk::iterator) {
        if (!Files.isSymbolicLink(path)) {
          Files.setLastModifiedTime(path, java.nio.file.attribute.FileTime.from(at));
        }
      }
    } catch (java.io.IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    }
  }

  /** A symbolic link where the platform allows one (the flow holds links so the fingerprint sees them); nothing happens where it does not. */
  private static void tryLink(Path link, Path target) {
    try {
      Files.createSymbolicLink(link, target);
    } catch (java.io.IOException | UnsupportedOperationException unsupported) {
      // no links on this host: the flow runs without them
    }
  }

  /**
   * The Mission {@code alpha} with the canaries planted in a Work Package body and title, in an artifact that is redacted, in an artifact that is
   * refused for a credential, in {@code tasks.md} and in {@code lanes.json}. Only the body of {@code WP01} may carry a canary into a response, and
   * only in the {@code promptMarkdown} of the request that asks for the prompt.
   */
  public static Project canaries() {
    String planted = CANARY_PATH + " " + CANARY_ADDRESS;
    DetailFixture fixture =
        DetailRoute.fixture(
            root -> {
              DetailRoute.write(root, "tasks/WP01-one.md", DetailRoute.wpFile("WP01", "Fix " + planted, "owned_files: [src/**]") + "\nBody with " + planted + " and " + CANARY_TOKEN + ".\n");
              DetailRoute.write(root, "tasks.md", "## WP01\n- [ ] T001 Subtask " + planted + "\n");
              DetailRoute.write(root, "spec.md", "# Specification\n");
              DetailRoute.write(root, "lanes.json", DetailRoute.lanes("alpha", "lane-a:WP01").replace("\"write_scope\":[]", "\"write_scope\":[\"" + planted + " " + CANARY_TOKEN + "\"]"));
              DetailRoute.write(root, "notes/canary.md", "Contact " + planted + " about it.\n");
              DetailRoute.write(root, "notes/secret.md", "token " + CANARY_TOKEN + "\n");
              DetailRoute.write(root, "tasks/WP01-one/review-cycle-1.md", DetailRoute.cycleFile(1, "reviewer-renata", "2026-09-21T09:15:00+00:00"));
            });
    return new Project("canaries", fixture, DetailRoute.ID, "alpha");
  }

  /** The committed coord-routed Mission, given a Work Package, a spec and an artifact in its primary directory. */
  public static Project coordinated() {
    Path tree = ConformanceTree.root().resolve("coordination").resolve("coordinated-mission");
    DetailFixture fixture = DetailFixture.of(tree);
    Path primary = fixture.root().resolve("kitty-specs").resolve("coordinated-01J03000");
    try {
      Files.createDirectories(primary.resolve("tasks"));
      Files.writeString(primary.resolve("tasks/WP01-coordinated.md"), DetailRoute.wpFile("WP01", "Coordinated"));
      Files.writeString(primary.resolve("spec.md"), "# Specification\n");
      Files.writeString(primary.resolve("tasks.md"), "## WP01\n- [ ] T001 Coordinated subtask\n");
    } catch (java.io.IOException failure) {
      throw new java.io.UncheckedIOException(failure);
    }
    return new Project("coordinated", fixture, "01J03000000000000000000003", "coordinated-01J03000");
  }

  /** The server over the project's fixture with the four detail services installed and the marker on the recorder. */
  public static HttpHarness start(Project project, RouteMarker marker) {
    return HttpHarness.startWith(project.fixture().built(), DetailServices.over(project.fixture()).ports(), marker);
  }

  /** One request of the set: the route the recorder notes for it, and the path. */
  public record Request(String route, String path) {}

  /** The curated set over one Mission: each route, its refusals, and the three routes of #5529. */
  public static List<Request> requests(Project project) {
    String base = "/api/v1/missions/" + project.missionId();
    String unknown = "/api/v1/missions/01J09999999999999999999999";
    List<Request> all = new ArrayList<>();
    all.add(new Request(PROJECT, "/api/v1/project"));
    all.add(new Request(MISSIONS, "/api/v1/missions"));
    all.add(new Request(MISSION, base));
    all.add(new Request(MISSION, unknown));
    all.add(new Request(WORK_PACKAGE, base + "/work-packages/WP01"));
    all.add(new Request(WORK_PACKAGE, base + "/work-packages/WP01?includePrompt=true"));
    all.add(new Request(WORK_PACKAGE, base + "/work-packages/WP99"));
    all.add(new Request(WORK_PACKAGE, unknown + "/work-packages/WP01"));
    all.add(new Request(DETAIL, base + "/work-packages/WP01/detail"));
    all.add(new Request(DETAIL, base + "/work-packages/WP99/detail"));
    all.add(new Request(LISTING, base + "/artifacts"));
    all.add(new Request(LISTING, unknown + "/artifacts"));
    all.add(new Request(CONTENT, base + "/artifacts/content?path=spec.md"));
    all.add(new Request(CONTENT, base + "/artifacts/content?path=notes/readme.md"));
    all.add(new Request(CONTENT, base + "/artifacts/content?path=missing.md"));
    all.add(new Request(CONTENT, base + "/artifacts/content?path=..%2Fmeta.json"));
    all.add(new Request(CONTENT, base + "/artifacts/content?path=leaky.md"));
    if (project.name().equals("canaries")) {
      all.add(new Request(CONTENT, base + "/artifacts/content?path=notes/canary.md"));
      all.add(new Request(CONTENT, base + "/artifacts/content?path=notes/secret.md"));
    }
    return all;
  }

  /** Runs every request of the set, marking the route before each one, and returns what was answered. */
  public static List<Answer> run(HttpHarness server, RouteMarker marker, Project project) {
    List<Answer> answers = new ArrayList<>();
    for (Request request : requests(project)) {
      marker.set(request.route());
      Flow.Captured captured = Flow.http(server, request.path());
      answers.add(new Answer(request, captured.status(), captured.body(), captured.everything().replaceAll("(?m)^date: .*$", "date: <clock>")));
    }
    marker.clear();
    return answers;
  }

  /** One answer: the request, the status, the body, and the whole transcript (request line, status, headers, body) with the clock header neutralised. */
  public record Answer(Request request, int status, String body, String everything) {}
}
