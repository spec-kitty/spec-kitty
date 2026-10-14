package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.flow.DetailServices;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.application.query.AdmissionGate;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;
import org.speckitty.missionstatus.testsupport.Rows;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/**
 * The NFR-002 scenario (S-13, AC-22.4): 100 concurrent {@code getArtifactContent}, 10 {@code listArtifacts} over a 1000-file Mission, 10
 * {@code getWorkPackageDetail} over a Mission whose {@code tasks.md} is 4 MiB, 10 {@code getWorkPackage} with {@code includePrompt=true} over a
 * Work Package file of 1 MiB, and 20 {@code getMission} over a 40-file Mission, all held at once, over HTTP, through the four services behind one
 * admission gate. Asserted: the heap that stays reachable under the load grows by at most 96 MiB (a ratio to a same-run floor first, the figure beside
 * it), the largest single read per cap is not above cap + 1 (262145, 1048577, 4194305), and the gate's high-water mark is not above 4.
 *
 * <p>"Used heap after a forced collection" is sampled while the load runs: a sampler forces a collection and reads the used heap again and again until
 * every request has answered, and the peak is the figure. The floor is the same sampling over one request of each kind in turn, clamped to
 * {@value #FLOOR_UNIT_MIB} MiB so a near-zero floor does not make the ratio meaningless (as the NFR-004 memory budget does). A miss fails once; there is no retry.
 */
@Tag("perf")
class Nfr002BoundedMemoryScenarioTest {

  /** The spec figure: growth of the used heap after a forced collection, MiB. INITIAL and PROVISIONAL. */
  static final long HEAP_GROWTH_CEILING_MIB = 96;

  /** The floor is never taken below this many MiB. */
  static final long FLOOR_UNIT_MIB = 8;

  /**
   * PROVISIONAL: the growth under the scenario divided by the clamped floor. Five local runs on a 24-cpu machine at load 2 to 5 measured 15.6, 17.4,
   * 20.2, 23.1 and 25.6 MiB, ratios 1.95 to 3.19 over the 8 MiB unit. The limit 10 allows 80 MiB, three times the worst clean figure and under the
   * spec's 96 MiB. A CI-runner measurement amends it; a miss is classified, never retried.
   */
  static final double HEAP_GROWTH_RATIO_LIMIT = 10;

  static final int CONTENT = 100;
  static final int LISTING = 10;
  static final int DETAIL = 10;
  static final int PROMPT = 10;
  static final int MISSION = 20;

  /** The caps, in bytes. */
  static final int ARTIFACT_CAP = 262_144;
  static final int WORK_PACKAGE_CAP = 1_048_576;
  static final int TASKS_MD_CAP = 4_194_304;

  private static final String ART = "heavy-art";
  private static final String TASKS = "heavy-tasks";
  private static final String PROMPT_MISSION = "heavy-prompt";
  private static final String FORTY = "heavy-forty";

  private static final String ART_ID = "01J00000000000000000000A01";
  private static final String TASKS_ID = "01J00000000000000000000A02";
  private static final String PROMPT_ID = "01J00000000000000000000A03";
  private static final String FORTY_ID = "01J00000000000000000000A04";

  /** The size of the largest single read of each kind of file, in bytes, observed on the channels the text source opened. */
  static final class ReadMeter implements AllowlistAccess {
    private final AllowlistAccess delegate = AllowlistAccess.passThrough();
    private final Map<String, AtomicLong> largest = new ConcurrentHashMap<>();

    /** The kind of a path by its name, or null for a file the caps do not govern (a ledger, a {@code meta.json}). */
    static String kind(Path path) {
      String name = path.getFileName().toString();
      if (name.equals("tasks.md")) {
        return "tasks.md";
      }
      Path parent = path.getParent();
      if (parent != null && parent.getFileName() != null && parent.getFileName().toString().equals("tasks") && name.startsWith("WP") && name.endsWith(".md")) {
        return "work-package";
      }
      if (name.equals("status.events.jsonl") || name.equals("meta.json") || name.equals("lanes.json") || name.equals("config.yaml") || name.equals("metadata.yaml")) {
        return null;
      }
      return "artifact";
    }

    long largest(String kind) {
      AtomicLong value = largest.get(kind);
      return value == null ? 0 : value.get();
    }

    @Override
    public SeekableByteChannel openRead(Path path) throws IOException {
      SeekableByteChannel channel = delegate.openRead(path);
      String kind = kind(path);
      return kind == null ? channel : new Counting(channel, largest.computeIfAbsent(kind, key -> new AtomicLong()));
    }

    @Override
    public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
      return delegate.stat(path, followLinks);
    }

    @Override
    public Path realPath(Path path) throws IOException {
      return delegate.realPath(path);
    }

    @Override
    public List<String> listNames(Path dir) throws IOException {
      return delegate.listNames(dir);
    }

    @Override
    public NameWindow listNames(Path dir, int limit) throws IOException {
      return delegate.listNames(dir, limit);
    }
  }

  /** Counts the bytes taken from one channel and keeps the largest total of the kind. */
  private static final class Counting implements SeekableByteChannel {
    private final SeekableByteChannel inner;
    private final AtomicLong largest;
    private long total;

    Counting(SeekableByteChannel inner, AtomicLong largest) {
      this.inner = inner;
      this.largest = largest;
    }

    @Override
    public int read(ByteBuffer destination) throws IOException {
      int count = inner.read(destination);
      if (count > 0) {
        total += count;
        long seen = total;
        largest.accumulateAndGet(seen, Math::max);
      }
      return count;
    }

    @Override
    public int write(ByteBuffer source) throws IOException {
      throw new IOException("read only");
    }

    @Override
    public long position() throws IOException {
      return inner.position();
    }

    @Override
    public SeekableByteChannel position(long newPosition) throws IOException {
      inner.position(newPosition);
      return this;
    }

    @Override
    public long size() throws IOException {
      return inner.size();
    }

    @Override
    public SeekableByteChannel truncate(long size) throws IOException {
      throw new IOException("read only");
    }

    @Override
    public boolean isOpen() {
      return inner.isOpen();
    }

    @Override
    public void close() throws IOException {
      inner.close();
    }
  }

  private static String ledger() {
    return Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed");
  }

  /** The project of the scenario: the four heavy Missions, written at their exact sizes. */
  private static Path project() {
    List<FixtureSpec.Mission> missions = new ArrayList<>();
    for (String[] mission : new String[][] {{ART, ART_ID}, {TASKS, TASKS_ID}, {PROMPT_MISSION, PROMPT_ID}, {FORTY, FORTY_ID}}) {
      missions.add(FixtureSpec.Mission.of(mission[0], Rows.meta(mission[1], mission[0], "2026-08-01T00:00:00+00:00"), ledger()));
    }
    Path root = FilesystemFixtureFactory.fromSpec(FixtureSpec.of(missions.toArray(FixtureSpec.Mission[]::new))).root();
    Path specs = root.resolve("kitty-specs");

    // the artifact Mission: 1000 small files and the file of the content cap
    MissionCorpus.writeFiles(specs.resolve(ART), MissionCorpus.DETAIL_FILES);
    MissionCorpus.writeText(specs.resolve(ART).resolve("big.md"), ARTIFACT_CAP, "");
    MissionCorpus.writeText(specs.resolve(ART).resolve("spec.md"), 200, "");

    // the detail Mission: a Work Package, and a tasks.md of 4 MiB that names the subtasks of WP01 among prose
    String head = "## WP01\n- [ ] T001 First subtask\n- [ ] T002 Second subtask\n\n";
    MissionCorpus.writeText(specs.resolve(TASKS).resolve("tasks.md"), TASKS_MD_CAP, head);
    MissionCorpus.writeString(specs.resolve(TASKS).resolve("tasks/WP01-heavy.md"), MissionDetailServedRoute.workPackageFile("WP01", "Heavy detail", "subtasks: [T001, T002]") + "\nBody.\n");
    MissionCorpus.writeText(specs.resolve(TASKS).resolve("spec.md"), 200, "");

    // the prompt Mission: a Work Package file of exactly 1 MiB
    MissionCorpus.writeText(specs.resolve(PROMPT_MISSION).resolve("tasks/WP01-heavy.md"), WORK_PACKAGE_CAP, MissionDetailServedRoute.workPackageFile("WP01", "Heavy prompt") + "\n");

    // the 40-file Mission
    MissionCorpus.writeWorkPackages(specs.resolve(FORTY), 40);
    return root;
  }

  /** One request: the path and what the scenario calls it. */
  private record Request(String kind, String path) {}

  private static List<Request> scenario() {
    List<Request> requests = new ArrayList<>();
    for (int i = 0; i < CONTENT; i++) {
      requests.add(new Request("content", "/api/v1/missions/" + ART_ID + "/artifacts/content?path=big.md"));
    }
    for (int i = 0; i < LISTING; i++) {
      requests.add(new Request("listing", "/api/v1/missions/" + ART_ID + "/artifacts"));
    }
    for (int i = 0; i < DETAIL; i++) {
      requests.add(new Request("detail", "/api/v1/missions/" + TASKS_ID + "/work-packages/WP01/detail"));
    }
    for (int i = 0; i < PROMPT; i++) {
      requests.add(new Request("prompt", "/api/v1/missions/" + PROMPT_ID + "/work-packages/WP01?includePrompt=true"));
    }
    for (int i = 0; i < MISSION; i++) {
      requests.add(new Request("mission", "/api/v1/missions/" + FORTY_ID));
    }
    return requests;
  }

  private static List<Request> onePerKind() {
    List<Request> all = scenario();
    return List.of(all.get(0), all.get(CONTENT), all.get(CONTENT + LISTING), all.get(CONTENT + LISTING + DETAIL), all.get(CONTENT + LISTING + DETAIL + PROMPT));
  }

  private static long usedAfterGc() {
    System.gc();
    Runtime runtime = Runtime.getRuntime();
    return runtime.totalMemory() - runtime.freeMemory();
  }

  /**
   * Runs the requests, all held at once ({@code concurrent}) or one after the other, and returns the peak used heap after a forced collection
   * observed while they ran, minus the used heap after a collection before they started.
   */
  private static long peakGrowth(HttpHarness server, List<Request> requests, boolean concurrent) throws Exception {
    long before = usedAfterGc();
    long peak = before;
    try (ExecutorService workers = concurrent ? Executors.newVirtualThreadPerTaskExecutor() : Executors.newSingleThreadExecutor()) {
      List<Future<Integer>> answers = new ArrayList<>();
      for (Request request : requests) {
        answers.add(workers.submit(() -> server.get(request.path()).status()));
      }
      while (!answers.stream().allMatch(Future::isDone)) {
        peak = Math.max(peak, usedAfterGc());
        Thread.sleep(20);
      }
      for (Future<Integer> answer : answers) {
        assertThat(answer.get()).as("every request of the scenario answers 200").isEqualTo(200);
      }
    } catch (ExecutionException failure) {
      throw new AssertionError(failure.getCause());
    }
    return peak - before;
  }

  private static String hint() {
    return String.format(
        Locale.ROOT,
        "%d cpus, load %.2f, %d platform threads",
        Runtime.getRuntime().availableProcessors(),
        java.lang.management.ManagementFactory.getOperatingSystemMXBean().getSystemLoadAverage(),
        java.lang.management.ManagementFactory.getThreadMXBean().getThreadCount());
  }

  @Test
  void theScenarioHeldAtOnceStaysWithinTheRatioToTheFloorAndTheCeilingEveryReadWithinItsCapAndTheGateMarkNotAboveFour() throws Exception {
    Path root = project();
    ReadMeter meter = new ReadMeter();
    FilesystemFixtureFactory.Built built = FilesystemFixtureFactory.over(root, ignored -> meter);
    AdmissionGate gate = new AdmissionGate();
    FilesystemTextSource text = new FilesystemTextSource(root, meter, NameEncoding.host());
    MissionReadModel model = new MissionReadModel(built.source(), diagnostic -> {}, LeakPatternsFile.load());
    DetailServices services = DetailServices.over(model, text, diagnostic -> {}, gate);

    try (HttpHarness server = HttpHarness.startWith(built, services.ports())) {
      // warm-up, discarded: class loading, the JIT and the head cache of every Mission
      peakGrowth(server, scenario(), true);
      Thread.sleep(200);

      long floorBytes = peakGrowth(server, onePerKind(), false);
      long scenarioBytes = peakGrowth(server, scenario(), true);

      double floorMiB = Math.max(floorBytes / 1048576.0, FLOOR_UNIT_MIB);
      double scenarioMiB = scenarioBytes / 1048576.0;
      RatioBudget.Outcome outcome = RatioBudget.evaluate("NFR-002 heap growth under the scenario", scenarioMiB, floorMiB, HEAP_GROWTH_RATIO_LIMIT, HEAP_GROWTH_CEILING_MIB, "MiB", hint());
      System.out.println("PERF " + outcome.line() + " [unclamped floor " + floorBytes / 1048576.0 + " MiB, " + scenario().size() + " requests held at once, gate mark " + gate.highWaterMark() + "]; " + hint());

      assertThat(gate.highWaterMark()).as("AC-22.4: the gate's high-water mark over HTTP").isBetween(1, AdmissionGate.PERMITS);
      assertThat(meter.largest("artifact")).as("the content file is read in full, not beyond its cap + 1").isBetween((long) ARTIFACT_CAP, ARTIFACT_CAP + 1L);
      assertThat(meter.largest("work-package")).as("the 1 MiB Work Package file").isBetween((long) WORK_PACKAGE_CAP, WORK_PACKAGE_CAP + 1L);
      assertThat(meter.largest("tasks.md")).as("the 4 MiB tasks.md").isBetween((long) TASKS_MD_CAP, TASKS_MD_CAP + 1L);
    }
  }

  // ---- controls --------------------------------------------------------------------------------------------------------------------

  @Test
  void controlAGrowthOverTheCeilingOrTheRatioIsRed() {
    org.junit.jupiter.api.Assertions.assertThrows(AssertionError.class, () -> RatioBudget.evaluate("control", HEAP_GROWTH_CEILING_MIB + 1, 1000.0, HEAP_GROWTH_RATIO_LIMIT, HEAP_GROWTH_CEILING_MIB, "MiB", "none"));
    org.junit.jupiter.api.Assertions.assertThrows(AssertionError.class, () -> RatioBudget.evaluate("control", HEAP_GROWTH_RATIO_LIMIT * FLOOR_UNIT_MIB + 1, FLOOR_UNIT_MIB, HEAP_GROWTH_RATIO_LIMIT, HEAP_GROWTH_CEILING_MIB, "MiB", "none"));
  }

  @Test
  void controlTheSamplerSeesMemoryThatIsHeldAndNotMemoryThatIsReleased() {
    long before = usedAfterGc();
    byte[][] held = new byte[40][];
    for (int i = 0; i < held.length; i++) {
      held[i] = new byte[1_048_576];
      held[i][0] = 1;
    }
    long whileHeld = usedAfterGc() - before;
    assertThat(whileHeld).as("40 MiB held shows as growth after a forced collection").isGreaterThan(30L * 1_048_576);
    assertThat(held[39][0]).isEqualTo((byte) 1);
  }

  @Test
  void controlTheMeterSeesAReadOfEachKindAndTheScenarioHasTheStatedShape() throws IOException {
    assertThat(scenario()).hasSize(150);
    assertThat(scenario().stream().filter(request -> request.kind().equals("content"))).hasSize(100);
    assertThat(scenario().stream().filter(request -> request.kind().equals("prompt"))).hasSize(10);
    assertThat(ReadMeter.kind(Path.of("a/kitty-specs/m/tasks.md"))).isEqualTo("tasks.md");
    assertThat(ReadMeter.kind(Path.of("a/kitty-specs/m/tasks/WP01-x.md"))).isEqualTo("work-package");
    assertThat(ReadMeter.kind(Path.of("a/kitty-specs/m/big.md"))).isEqualTo("artifact");
    assertThat(ReadMeter.kind(Path.of("a/kitty-specs/m/status.events.jsonl"))).isNull();
  }
}
