package org.speckitty.missionstatus.adapter.in.http.flow;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.speckitty.missionstatus.adapter.out.filesystem.RecordingAllowlistAccess;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;
import org.speckitty.missionstatus.testsupport.ConformanceTree;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.SseClient;
import org.speckitty.missionstatus.testsupport.http.StreamRig;

/**
 * AC-9g: canary values planted in {@code .kittify/config.yaml}, {@code .kittify/metadata.yaml}, {@code meta.json} and the text fields of
 * event payloads, in a token shape, an absolute-path shape and an e-mail shape, each with its own marker. Every response body and header of
 * the three routes (the contract document, every refusal and the frames of the event streams included) and every log line of the whole
 * flow is scanned for each canary, for the fixture root and for HOME. The free-text fields that the oracle projects through its redaction
 * classes are served redacted; a strict field that cannot be represented is refused with a path-free diagnostic.
 */
@ExtendWith(OutputCaptureExtension.class)
class CanaryScanTest {

  private static final String TOKEN = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  // built at run time: a host-path shape the leak classes catch, with no such literal in the source
  private static final String PATH = "/" + String.join("/", "ho" + "me", "canary-user", "CANARY-PATH-7");
  private static final String LEAKY_ID_PATH = "/" + String.join("/", "ho" + "me", "canary-user", "CANARY-EVENT-ID-8");
  private static final String LEAKY_ID_MISSION = "01J08000000000000000000008";
  private static final String EMAIL = "canary-7@example.invalid";
  private static final String SHAPED_ID = "01J07000000000000000000007";

  /** The planted tree, copied, with the shaped canaries added to every file the spec names and one more Mission whose title carries two. */
  private static FilesystemFixtureFactory.Built plant() throws IOException {
    FilesystemFixtureFactory.Built built =
        FilesystemFixtureFactory.fromTree(ConformanceTree.root().resolve("secret-canaries").resolve("planted-canaries"), RecordingAllowlistAccess::new);
    Path root = built.root();
    for (String file : List.of(".kittify/config.yaml", ".kittify/metadata.yaml")) {
      Files.writeString(root.resolve(file), "\nshaped_token: " + TOKEN + "\nshaped_path: " + PATH + "\nshaped_mail: " + EMAIL + "\n", java.nio.file.StandardOpenOption.APPEND);
    }
    Path meta = root.resolve("kitty-specs/canary-mission/meta.json");
    String text = Files.readString(meta);
    Files.writeString(meta, text.replace("\"canary\":", "\"shaped\": \"" + TOKEN + " " + PATH + " " + EMAIL + "\",\n  \"canary\":"));
    Path shaped = Files.createDirectories(root.resolve("kitty-specs/shaped"));
    Files.writeString(
        shaped.resolve("meta.json"),
        Rows.meta(SHAPED_ID, "shaped", "2026-09-06T10:00:00+00:00").replace("Fixture shaped", "Docs at " + PATH + " mail " + EMAIL));
    Files.writeString(shaped.resolve("status.events.jsonl"), Rows.status(Rows.id(70), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"));
    Path leaky = Files.createDirectories(root.resolve("kitty-specs/leaky-id"));
    Files.writeString(leaky.resolve("meta.json"), Rows.meta(LEAKY_ID_MISSION, "leaky-id", "2026-09-07T10:00:00+00:00"));
    Files.writeString(leaky.resolve("status.events.jsonl"), Rows.status(LEAKY_ID_PATH, "2026-09-01T10:00:00Z", "WP01", "planned", "claimed"));
    return built;
  }

  private static Set<String> canaries(Path root) throws IOException {
    Set<String> found = new LinkedHashSet<>(List.of(TOKEN, PATH, EMAIL, "CANARY-PATH-7", "CANARY-EVENT-ID-8", "canary-user", root.toString()));
    String home = System.getenv("HOME");
    if (home != null && !home.isBlank()) {
      found.add(home);
    }
    found.add(System.getProperty("user.home"));
    Pattern marker = Pattern.compile("CANARY-NOT-A-SECRET-[A-Z0-9-]+");
    try (var walk = Files.walk(root)) {
      for (Path file : walk.filter(Files::isRegularFile).toList()) {
        Matcher matcher = marker.matcher(Files.readString(file, StandardCharsets.UTF_8));
        while (matcher.find()) {
          found.add(matcher.group());
        }
      }
    }
    found.removeIf(String::isBlank);
    return found;
  }

  @Test
  void noResponseHeaderFrameOrLogLineCarriesACanaryTheFixtureRootOrHome(CapturedOutput output) throws Exception {
    FilesystemFixtureFactory.Built built = plant();
    Set<String> canaries = canaries(built.root());
    assertThat(canaries).as("every marker of the planted tree was found").contains("CANARY-NOT-A-SECRET-CONFIG", "CANARY-NOT-A-SECRET-METADATA", "CANARY-NOT-A-SECRET-META", "CANARY-NOT-A-SECRET-EVENT-PAYLOAD");
    List<String> scanned = new ArrayList<>();
    try (StreamRig rig = StreamRig.over(built)) {
      List<Flow.Captured> responses = Flow.requests(rig.http);
      assertThat(responses).extracting(Flow.Captured::status).as("the three routes, the document and the refusals all answered").contains(200, 400, 404);
      responses.forEach(captured -> scanned.add(captured.everything()));
      scanned.addAll(Flow.streams(rig, "canary-mission", "01J6000000000000000000001W", "shaped", "reason " + TOKEN + " " + PATH + " " + EMAIL + " CANARY-NOT-A-SECRET-EVENT-PAYLOAD"));
      // a refusal at the stream route, with its body
      try (SseClient refused = rig.scoped("01J09000000000000000000009")) {
        scanned.add(refused.status() + refused.body());
      }
      Flow.Captured page = responses.stream().filter(captured -> captured.request().equals("GET /api/v1/missions")).findFirst().orElseThrow();
      assertThat(page.body()).as("the title is served redacted, not dropped").contains("Docs at [path] mail [email]");
      // lastEventId is a nullable strict field: a leak-shaped value is served as null, never verbatim (the stream refuses the same value)
      var items = new tools.jackson.databind.json.JsonMapper().readTree(page.body()).get("items");
      for (var item : items) {
        if (item.get("slug").asString().equals("leaky-id")) {
          assertThat(item.get("lastEventId").isNull()).as("lastEventId of the leaky Mission").isTrue();
        }
        if (item.get("slug").asString().equals("shaped")) {
          assertThat(item.get("lastEventId").asString()).as("a clean id is served as is").isEqualTo(Rows.id(70));
        }
      }
    }
    scanned.add(output.getAll());

    for (String canary : canaries) {
      for (String text : scanned) {
        assertThat(text).as("canary or root or HOME: " + (canary.startsWith("/") || canary.length() > 30 ? "(a path or a token)" : canary)).doesNotContain(canary);
      }
    }
    assertThat(scanned.stream().mapToInt(String::length).sum()).as("the scan saw real content").isGreaterThan(5000);
  }

  @Test
  void aStrictFieldThatCannotBeRepresentedIsRefusedOnTheStreamWithAPathFreeDiagnosticAndNoEvent(CapturedOutput output) throws Exception {
    FilesystemFixtureFactory.Built built = plant();
    try (StreamRig rig = StreamRig.over(built);
        SseClient client = rig.scoped(SHAPED_ID)) {
      rig.append(
          "shaped",
          "{\"actor\":\"claude\",\"at\":\"2026-09-01T11:00:00Z\",\"event_id\":\"" + PATH + "\",\"execution_mode\":\"worktree\",\"force\":false,\"from_lane\":\"claimed\",\"to_lane\":\"in_progress\",\"wp_id\":\"WP01\"}\n");
      rig.tick();

      assertThat(client.next(StreamRig.QUIET)).as("the row whose id is a path is not forwarded").isNull();
      assertThat(client.transcript()).doesNotContain(PATH).doesNotContain("CANARY-PATH-7");
      assertThat(output.getAll()).contains("code=projection_refused mid8=" + SHAPED_ID.substring(0, 8)).doesNotContain(PATH).doesNotContain("CANARY-PATH-7");
      assertThat(DiagnosticCode.PROJECTION_REFUSED.wire()).isEqualTo("projection_refused");
    }
  }

  // ---- pre-merge fold J6, J7, J8 (rulings of 2026-10-13) -----------------------------------------------------------------------------

  private static final String AT_PATH = "/" + String.join("/", "ho" + "me", "canary-user", "CANARY-AT-9");
  private static final String TS_TOKEN = "ghp_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

  @Test
  void anAtOrATimestampThatIsNotAnInstantDropsTheEventWithOneDiagnosticEach(CapturedOutput output) throws Exception {
    FilesystemFixtureFactory.Built built = plant();
    try (StreamRig rig = StreamRig.over(built);
        SseClient client = rig.scoped(SHAPED_ID)) {
      rig.append(
          "shaped",
          "{\"actor\":\"claude\",\"at\":\"" + AT_PATH + "\",\"event_id\":\"" + Rows.id(80) + "\",\"execution_mode\":\"worktree\",\"force\":false,\"from_lane\":\"claimed\",\"to_lane\":\"in_progress\",\"wp_id\":\"WP01\"}\n"
              + Rows.lifecycle(Rows.id(81), "PlanStarted", TS_TOKEN)
              + Rows.status(Rows.id(82), "2026-09-01T12:00:00Z", "WP01", "claimed", "in_progress"));
      rig.tick();

      SseClient.Event only = client.nextEvent(StreamRig.BOUND);
      assertThat(only.data()).as("the clean row after the two refused ones is the first event").contains(Rows.id(82));
      assertThat(client.next(StreamRig.QUIET)).as("nothing else was forwarded").isNull();
      assertThat(client.transcript()).doesNotContain("CANARY-AT-9").doesNotContain(TS_TOKEN).doesNotContain("canary-user");
      assertThat(output.getAll().split("code=projection_refused mid8=" + SHAPED_ID.substring(0, 8), -1)).as("one diagnostic per refused event").hasSize(3);
      assertThat(output.getAll()).contains("code=projection_refused mid8=" + SHAPED_ID.substring(0, 8)).doesNotContain("CANARY-AT-9").doesNotContain(TS_TOKEN);
    }
  }

  @Test
  void aTokenShapedActorHandleIsServedAsNullOnTheStream() throws Exception {
    FilesystemFixtureFactory.Built built = plant();
    try (StreamRig rig = StreamRig.over(built);
        SseClient client = rig.scoped(SHAPED_ID)) {
      rig.append(
          "shaped",
          "{\"actor\":\"" + TOKEN + "\",\"at\":\"2026-09-01T12:00:00Z\",\"event_id\":\"" + Rows.id(83) + "\",\"execution_mode\":\"worktree\",\"force\":false,\"from_lane\":\"claimed\",\"to_lane\":\"in_progress\",\"wp_id\":\"WP01\"}\n");
      rig.tick();

      var actor = new tools.jackson.databind.json.JsonMapper().readTree(client.nextEvent(StreamRig.BOUND).data()).get("actor");
      assertThat(actor.get("tool").isNull()).as("the token-shaped handle").isTrue();
      assertThat(actor.get("role").isNull()).isTrue();
      assertThat(actor.get("profile").isNull()).isTrue();
      assertThat(client.transcript()).doesNotContain(TOKEN);
    }
  }

  @Test
  void aJunkAcceptedMergedOrDiscardedDateIsServedAsNullAndCannotFlipTheLifecycleStatus() throws Exception {
    FilesystemFixtureFactory.Built built = plant();
    Path root = built.root();
    for (String[] mission : new String[][] {{"junkdates", "01J0A000000000000000000010"}, {"gooddates", "01J0A000000000000000000011"}}) {
      boolean junk = mission[0].equals("junkdates");
      Path dir = Files.createDirectories(root.resolve("kitty-specs/" + mission[0]));
      String extra =
          junk
              ? "\"accepted_at\":\"" + AT_PATH + "\",\"merged_at\":\"" + TS_TOKEN + "\",\"discarded_at\":\"" + EMAIL + "\""
              : "\"accepted_at\":\"2026-09-02T10:00:00+00:00\",\"merged_at\":\"2026-09-03T10:00:00+00:00\"";
      Files.writeString(dir.resolve("meta.json"), Rows.metaWith(mission[1], mission[0], "2026-09-06T10:00:00+00:00", extra));
      Files.writeString(dir.resolve("status.events.jsonl"), Rows.status(Rows.id(90), "2026-09-01T10:00:00Z", "WP01", "planned", "done"));
    }
    try (StreamRig rig = StreamRig.over(built)) {
      var response = rig.http.get("/api/v1/missions");
      assertThat(response.status()).isEqualTo(200);
      var items = new tools.jackson.databind.json.JsonMapper().readTree(response.text()).get("items");
      boolean sawJunk = false;
      boolean sawGood = false;
      for (var item : items) {
        String slug = item.get("slug").asString();
        if (slug.equals("junkdates")) {
          sawJunk = true;
          assertThat(item.get("acceptedAt").isNull()).isTrue();
          assertThat(item.get("mergedAt").isNull()).isTrue();
          assertThat(item.get("discardedAt").isNull()).isTrue();
          assertThat(item.get("lifecycleStatus").asString()).as("junk cannot make the Mission done or discarded").isEqualTo("active");
        }
        if (slug.equals("gooddates")) {
          sawGood = true;
          assertThat(item.get("acceptedAt").asString()).isEqualTo("2026-09-02T10:00:00+00:00");
          assertThat(item.get("mergedAt").asString()).isEqualTo("2026-09-03T10:00:00+00:00");
          assertThat(item.get("lifecycleStatus").asString()).isEqualTo("done");
        }
      }
      assertThat(sawJunk && sawGood).isTrue();
      assertThat(response.text()).doesNotContain("CANARY-AT-9").doesNotContain(TS_TOKEN).doesNotContain(EMAIL);
    }
  }

  // ---- landing fold A1: the Project name is a strict field ---------------------------------------------------------------------------

  private static final String NAME_PATH = "/" + String.join("/", "ho" + "me", "canary-user", "CANARY-NAME-10");

  @Test
  void aProjectSlugShapedLikeAPathOrAnAddressIsRefusedAndNeverServedOrLogged(CapturedOutput output) throws Exception {
    for (String slug : List.of(NAME_PATH + " " + EMAIL, TOKEN, EMAIL)) {
      FilesystemFixtureFactory.Built built = plant();
      Files.writeString(built.root().resolve(".kittify/config.yaml"), "project:\n  slug: \"" + slug + "\"\n");
      try (StreamRig rig = StreamRig.over(built)) {
        var response = rig.http.get("/api/v1/project");
        assertThat(response.status()).as("a strict field that cannot be represented refuses the read: " + slug).isEqualTo(500);
        assertThat(response.text()).contains("projection_refused").doesNotContain("CANARY-NAME-10").doesNotContain("canary-user").doesNotContain(EMAIL).doesNotContain(TOKEN);
        assertThat(built.handles().diagnostics()).as("one path-free diagnostic").singleElement().satisfies(d -> {
          assertThat(d.code()).isEqualTo(DiagnosticCode.PROJECTION_REFUSED);
          assertThat(d.mid8()).isEqualTo("none");
        });
      }
    }
    assertThat(output.getAll()).doesNotContain("CANARY-NAME-10").doesNotContain("canary-user").doesNotContain(TOKEN);
  }

  @Test
  void aCleanProjectSlugIsServedAsTheName() throws Exception {
    FilesystemFixtureFactory.Built built = plant();
    try (StreamRig rig = StreamRig.over(built)) {
      var response = rig.http.get("/api/v1/project");
      assertThat(response.status()).isEqualTo(200);
      assertThat(new tools.jackson.databind.json.JsonMapper().readTree(response.text()).get("name").asString()).isEqualTo("fixture-project");
    }
  }

  // ---- WP18 (T126, AC-8.3): the five detail routes -------------------------------------------------------------------------------

  /**
   * Canaries planted in a Work Package body and title, an artifact, {@code tasks.md} and {@code lanes.json}: no response and no log line of the
   * detail flow carries one, EXCEPT the {@code promptMarkdown} of the request that asks for the prompt, where the path and the address must be
   * found (the control that proves the scan can see them). Everything else of that response is scanned too.
   */
  @Test
  void theDetailRoutesCarryNoCanaryExceptThePromptOfTheRequestThatAsksForIt(CapturedOutput output) throws Exception {
    DetailFlow.Project project = DetailFlow.canaries();
    org.speckitty.missionstatus.testsupport.RouteMarker marker = org.speckitty.missionstatus.testsupport.RouteMarker.create();
    List<String> scanned = new ArrayList<>();
    String prompt = null;
    try (var server = DetailFlow.start(project, marker)) {
      for (DetailFlow.Answer answer : DetailFlow.run(server, marker, project)) {
        if (answer.request().path().endsWith("includePrompt=true") && answer.status() == 200) {
          var tree = new tools.jackson.databind.json.JsonMapper().readTree(answer.body());
          prompt = tree.get("promptMarkdown").asString();
          ((tools.jackson.databind.node.ObjectNode) tree).remove("promptMarkdown");
          scanned.add(answer.everything().replace(answer.body(), tree.toString()));
        } else {
          scanned.add(answer.everything());
        }
      }
    }
    scanned.add(output.getAll());
    List<String> canaries = List.of(DetailFlow.CANARY_PATH, DetailFlow.CANARY_ADDRESS, DetailFlow.CANARY_TOKEN, "CANARY-DETAIL-11", "canary-user", project.fixture().root().toString());

    assertThat(prompt).as("the control: the prompt of the request that asks for it carries the body").isNotNull().contains(DetailFlow.CANARY_PATH).contains(DetailFlow.CANARY_ADDRESS);
    assertThat(scanned.stream().mapToInt(String::length).sum()).as("the scan saw real content").isGreaterThan(3000);
    for (String canary : canaries) {
      for (String text : scanned) {
        assertThat(text).as("canary " + (canary.length() > 30 ? "(a root)" : canary.substring(0, Math.min(8, canary.length())) + "...")).doesNotContain(canary);
      }
    }
  }

  @Test
  void theDetailCanaryScanCanSeeACanaryInAResponseSoItIsNotVacuous() throws Exception {
    DetailFlow.Project project = DetailFlow.canaries();
    org.speckitty.missionstatus.testsupport.RouteMarker marker = org.speckitty.missionstatus.testsupport.RouteMarker.create();
    try (var server = DetailFlow.start(project, marker)) {
      String everything = DetailFlow.run(server, marker, project).stream().map(DetailFlow.Answer::everything).collect(java.util.stream.Collectors.joining("\n"));

      assertThat(everything).as("the unfiltered flow does contain the prompt, so a scan of it finds the planted path").contains(DetailFlow.CANARY_PATH);
    }
  }
}
