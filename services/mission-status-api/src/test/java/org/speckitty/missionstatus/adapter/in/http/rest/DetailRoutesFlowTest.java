package org.speckitty.missionstatus.adapter.in.http.rest;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.EnumSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.flow.DetailFlow;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess.ScopedAccess;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.testsupport.RouteMarker;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * AC-11.1 over the HTTP flow of the eight data routes (the three of #5529 and the five detail routes), run under the recording
 * {@code AllowlistAccess} with the four fixture-built detail services in the request path (D-137): every access of a route is inside that
 * route's (scope, class) set and read-only; no access reaches the wrong directory (a coordination {@code meta.json} is only ever stat-ed, a
 * coordination ledger is never read for a primary Mission); the artifact routes record none of LEDGER, LANES_JSON or a coordination class.
 * The flow covers a Mission whose {@code meta.json} stores no topology (so {@code lanes.json} is read to classify it) and a coord-routed
 * Mission. The control replaces #5529's: a read of {@code tasks/WP01-x.md} during {@code /missions} fails, the same read during
 * {@code getWorkPackage} passes. The helper lives in this package because the flow helpers are package-private to {@code flow}; the shared
 * pieces are public there.
 */
class DetailRoutesFlowTest {

  private static final String P = "AUTHORED:";
  private static final String A = "ARTIFACT:";

  /** The classes every route that resolves a Mission by id may touch: the lookup, the head, the ledger side and the coordination resolver. */
  private static final Set<String> HEAD =
      Set.of(
          P + PathClass.SPECS_DIR,
          P + PathClass.MISSION_DIR,
          P + PathClass.MISSION_META,
          P + PathClass.PROJECT_ROOT,
          P + PathClass.LEDGER,
          P + PathClass.LANES_JSON,
          P + PathClass.COORD_ROOT,
          P + PathClass.COORD_MISSION_DIR,
          P + PathClass.COORD_META,
          P + PathClass.WORKTREES_DIR);

  private static Set<String> plus(Set<String> base, String... more) {
    Set<String> all = new TreeSet<>(base);
    all.addAll(List.of(more));
    return all;
  }

  /** The (scope, class) set of each route. The three of #5529 touch none of the classes of FR-011 (the new ones). */
  static final Map<String, Set<String>> ALLOWED =
      Map.of(
          "getProject", plus(HEAD, P + PathClass.CONFIG_YAML, P + PathClass.METADATA_YAML, P + PathClass.GIT_POINTER, P + PathClass.GIT_HEAD, P + PathClass.GITDIR_HEAD),
          "listMissions", HEAD,
          "getMission", plus(HEAD, P + PathClass.TASKS_DIR, P + PathClass.WP_FILE, P + PathClass.TASKS_MD, P + PathClass.PLANNING_FILE),
          "getWorkPackage", plus(HEAD, P + PathClass.TASKS_DIR, P + PathClass.WP_FILE),
          "getWorkPackageDetail",
              plus(
                  HEAD,
                  P + PathClass.TASKS_DIR,
                  P + PathClass.WP_FILE,
                  P + PathClass.TASKS_MD,
                  P + PathClass.PLANNING_FILE,
                  P + PathClass.WP_CYCLE_DIR,
                  P + PathClass.WP_CYCLE_FILE,
                  P + PathClass.WORKTREE_LANE,
                  P + PathClass.WORKTREE_LANE_GIT),
          "listArtifacts", Set.of(P + PathClass.SPECS_DIR, P + PathClass.MISSION_DIR, P + PathClass.MISSION_META, A + PathClass.ARTIFACT_DIR, A + PathClass.ARTIFACT_FILE),
          "getArtifactContent", Set.of(P + PathClass.SPECS_DIR, P + PathClass.MISSION_DIR, P + PathClass.MISSION_META, A + PathClass.ARTIFACT_DIR, A + PathClass.ARTIFACT_FILE));

  /** The classes the two artifact routes must never record. */
  private static final Set<PathClass> NEVER_ON_ARTIFACT_ROUTES =
      EnumSet.of(PathClass.LEDGER, PathClass.LANES_JSON, PathClass.COORD_ROOT, PathClass.COORD_MISSION_DIR, PathClass.COORD_META);

  private static String key(ScopedAccess access) {
    return access.scope() + ":" + access.pathClass();
  }

  /** The problems of a record: an access outside its route's set, a mode that is not read-only, a route that is not one of the eight, a path on no class. */
  static List<String> problems(List<ScopedAccess> record) {
    List<String> problems = new ArrayList<>();
    for (ScopedAccess access : record) {
      Set<String> allowed = ALLOWED.get(access.route());
      if (allowed == null) {
        problems.add("an access with the route " + access.route() + ": " + access.path());
      } else if (access.pathClass() == null) {
        problems.add(access.route() + " touched a path on no class: " + access.path());
      } else if (!allowed.contains(key(access))) {
        problems.add(access.route() + " touched " + key(access) + " (" + access.mode() + " " + access.path() + ") outside its set");
      }
      if (!access.mode().readOnly()) {
        problems.add(access.route() + " opened " + access.path() + " in the mode " + access.mode());
      }
    }
    return problems;
  }

  /** What one project's flow recorded, with the answers. */
  private record Flowed(DetailFlow.Project project, List<ScopedAccess> record, List<DetailFlow.Answer> answers) {}

  private static Flowed flow(DetailFlow.Project project) {
    RouteMarker marker = RouteMarker.create();
    try (HttpHarness server = DetailFlow.start(project, marker)) {
      List<DetailFlow.Answer> answers = DetailFlow.run(server, marker, project);
      return new Flowed(project, server.allowlistRecorder().scopedAccesses(), answers);
    }
  }

  /** The status of each request of the set, in order, per project: the refusals of each route are in it. */
  private static final List<Integer> STATUSES_NO_TOPOLOGY = List.of(200, 200, 200, 404, 200, 200, 404, 404, 200, 404, 200, 404, 200, 200, 404, 400, 422);

  private static final List<Integer> STATUSES_COORDINATED = List.of(200, 200, 200, 404, 200, 200, 404, 404, 200, 404, 200, 404, 200, 404, 404, 400, 404);

  @Test
  void theFlowAnswersTheStatusesOfEveryRouteAndItsRefusals() {
    Flowed noTopology = flow(DetailFlow.noTopology());
    Flowed coordinated = flow(DetailFlow.coordinated());

    assertThat(noTopology.answers()).extracting(DetailFlow.Answer::status).isEqualTo(STATUSES_NO_TOPOLOGY);
    assertThat(coordinated.answers()).extracting(DetailFlow.Answer::status).isEqualTo(STATUSES_COORDINATED);
    assertThat(noTopology.answers()).as("the Problem codes of the refusals").anySatisfy(answer -> assertThat(answer.body()).contains("\"code\":\"artifact_secret\""));
    assertThat(noTopology.answers()).anySatisfy(answer -> assertThat(answer.body()).contains("\"code\":\"invalid_artifact_path\""));
    assertThat(noTopology.answers().stream().filter(answer -> answer.status() == 404)).allSatisfy(answer -> assertThat(answer.body()).contains("\"code\":\"not_found\""));
  }

  @Test
  void everyAccessOfTheFlowIsInsideItsRoutesSetAndReadOnlyOverBothMissions() {
    for (DetailFlow.Project project : List.of(DetailFlow.noTopology(), DetailFlow.coordinated())) {
      Flowed flowed = flow(project);

      assertThat(problems(flowed.record())).as(project.name()).isEmpty();
      assertThat(flowed.record().stream().map(ScopedAccess::route).distinct().sorted().toList())
          .as("every one of the eight routes recorded an access (a record that saw nothing proves nothing)")
          .containsExactlyInAnyOrder("getProject", "listMissions", "getMission", "getWorkPackage", "getWorkPackageDetail", "listArtifacts", "getArtifactContent");
    }
  }

  @Test
  void theArtifactRoutesRecordNoLedgerNoLanesFileAndNoCoordinationClassOverBothMissions() {
    for (DetailFlow.Project project : List.of(DetailFlow.noTopology(), DetailFlow.coordinated())) {
      Flowed flowed = flow(project);
      List<ScopedAccess> artifacts = flowed.record().stream().filter(access -> access.route().equals("listArtifacts") || access.route().equals("getArtifactContent")).toList();

      assertThat(artifacts).as(project.name()).isNotEmpty();
      assertThat(artifacts).noneMatch(access -> NEVER_ON_ARTIFACT_ROUTES.contains(access.pathClass()));
    }
  }

  @Test
  void theMissionWithoutAStoredTopologyReadsItsLanesFileAndTheCoordinatedOneReadsItsCoordinationLedgerAndNoCoordinationMetaContent() {
    Flowed noTopology = flow(DetailFlow.noTopology());
    Flowed coordinated = flow(DetailFlow.coordinated());

    assertThat(noTopology.record()).anyMatch(access -> access.pathClass() == PathClass.LANES_JSON && access.mode() == OpenMode.READ);
    assertThat(noTopology.record()).as("no coordination folder for a primary Mission").noneMatch(access -> access.path().contains("-coord"));
    assertThat(noTopology.record().stream().filter(access -> access.pathClass() == PathClass.LEDGER)).isNotEmpty().allSatisfy(access -> assertThat(access.path()).startsWith("kitty-specs/"));

    List<ScopedAccess> ledger = coordinated.record().stream().filter(access -> access.pathClass() == PathClass.LEDGER).toList();
    assertThat(ledger).isNotEmpty().allSatisfy(access -> assertThat(access.path()).as("the ledger of a coord-routed Mission is the coordination one").contains(".worktrees/"));
    assertThat(coordinated.record().stream().filter(access -> access.path().startsWith(".worktrees/") && access.path().endsWith("/meta.json"))).allSatisfy(access -> assertThat(access.mode()).isEqualTo(OpenMode.STAT));
    assertThat(coordinated.record()).as("a coord-routed Mission's primary meta.json is read").anyMatch(access -> access.pathClass() == PathClass.MISSION_META && access.mode() == OpenMode.READ);
  }

  @Test
  void theDetailRoutesTouchTheirNewClassesAndTheThreeOldRoutesTouchNone() {
    Flowed flowed = flow(DetailFlow.noTopology());
    Set<PathClass> fresh = EnumSet.of(PathClass.TASKS_DIR, PathClass.WP_FILE, PathClass.TASKS_MD, PathClass.PLANNING_FILE, PathClass.WP_CYCLE_DIR, PathClass.WP_CYCLE_FILE, PathClass.WORKTREE_LANE, PathClass.WORKTREE_LANE_GIT, PathClass.ARTIFACT_DIR, PathClass.ARTIFACT_FILE);

    for (String old : List.of("getProject", "listMissions")) {
      assertThat(flowed.record().stream().filter(access -> access.route().equals(old))).as(old).noneMatch(access -> fresh.contains(access.pathClass()));
    }
    assertThat(flowed.record().stream().filter(access -> access.route().equals("getWorkPackageDetail")).map(ScopedAccess::pathClass).collect(java.util.stream.Collectors.toSet()))
        .contains(PathClass.WP_CYCLE_FILE, PathClass.WORKTREE_LANE_GIT, PathClass.TASKS_MD);
    assertThat(flowed.record().stream().filter(access -> access.route().equals("listArtifacts")).map(ScopedAccess::scope).collect(java.util.stream.Collectors.toSet()))
        .contains(ReadScope.ARTIFACT);
  }

  // ---- the control that replaces #5529's -------------------------------------------------------------------------------------

  @Test
  void controlAReadOfAWorkPackageFileDuringMissionsFailsAndTheSameReadDuringGetWorkPackagePasses() {
    DetailFlow.Project project = DetailFlow.noTopology();
    RouteMarker marker = RouteMarker.create();
    try (HttpHarness server = DetailFlow.start(project, marker)) {
      var recorder = server.allowlistRecorder();
      recorder.clear();
      java.nio.file.Path file = project.fixture().root().resolve("kitty-specs").resolve(project.directory()).resolve("tasks/WP01-x.md");

      marker.set("listMissions");
      recorder.record(file, OpenMode.READ);
      marker.set("getWorkPackage");
      recorder.record(file, OpenMode.READ);

      List<ScopedAccess> duringMissions = recorder.scopedAccesses().stream().filter(access -> access.route().equals("listMissions")).toList();
      List<ScopedAccess> duringWorkPackage = recorder.scopedAccesses().stream().filter(access -> access.route().equals("getWorkPackage")).toList();
      assertThat(problems(duringMissions)).hasSize(1).first().asString().contains("listMissions").contains("WP_FILE");
      assertThat(problems(duringWorkPackage)).isEmpty();
    }
  }

  @Test
  void controlADeliberateExtraAccessAndAWriteModeAreBothRed() {
    DetailFlow.Project project = DetailFlow.noTopology();
    RouteMarker marker = RouteMarker.create();
    try (HttpHarness server = DetailFlow.start(project, marker)) {
      var recorder = server.allowlistRecorder();
      recorder.clear();
      java.nio.file.Path root = project.fixture().root().resolve("kitty-specs").resolve(project.directory());

      marker.set("getArtifactContent");
      recorder.record(root.resolve("status.events.jsonl"), OpenMode.READ);
      marker.set("getMission");
      recorder.record(root.resolve("tasks/WP01-one.md"), OpenMode.APPEND);

      assertThat(problems(recorder.scopedAccesses())).hasSizeGreaterThanOrEqualTo(2).anyMatch(text -> text.contains("getArtifactContent")).anyMatch(text -> text.contains("not read-only") || text.contains("APPEND"));
    }
  }
}
