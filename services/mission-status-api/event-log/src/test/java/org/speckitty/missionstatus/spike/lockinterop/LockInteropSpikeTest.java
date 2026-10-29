package org.speckitty.missionstatus.spike.lockinterop;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileAlreadyExistsException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;
import java.util.function.IntFunction;
import java.util.stream.Stream;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.LedgerLineDecoder;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.TailClassification;
import tools.jackson.databind.json.JsonMapper;

/**
 * The lock-interop spike of #6193 (Mission Write API step 3): does a Java writer exclude, and is it excluded by, the Python writer that
 * takes the interim event-log lock of {@code kernel.event_log_append} ({@code fcntl.flock} on Linux and macOS, {@code msvcrt.locking}
 * on Windows), and do appends from both sides land as whole lines that the Python reader and this module's {@link LedgerLineDecoder}
 * accept?
 *
 * <p>It runs only when {@value PythonPeer#PYTHON_ENV} names the interpreter of a synced checkout (the {@code lock-interop} job of
 * {@code mission-status-api.yml}); an ordinary {@code ./gradlew check} skips it. Each Java lock of {@link #locks()} gets its own
 * repository. Every run writes its observations to {@code build/lock-interop/} (one JSON and one Markdown row per lock), and the
 * verdict the spike report records is read from there. The assertions pin what the spike established, so a JDK or OS change that
 * moves a result turns this red. Report: {@code docs/development/spikes/2026-10-27-lock-interop-spike.md}.
 */
@EnabledIfEnvironmentVariable(named = PythonPeer.PYTHON_ENV, matches = ".+")
class LockInteropSpikeTest {

  private static final int PYTHON_WRITERS = 3;
  private static final int JAVA_WRITER = 9;
  private static final int ROUNDS = 60;
  private static final int APPENDS = 100;
  private static final Duration WAIT = Duration.ofSeconds(60);
  private static final Path OUT = Path.of("build", "lock-interop");
  private static final JsonMapper JSON = JsonMapper.builder().build();
  private static final String OS = osKey();

  @TempDir Path repo;

  static Stream<JavaLock> locks() {
    return OS.equals("windows") ? Stream.of(new FileChannelLock()) : Stream.of(new FileChannelLock(), new FlockLock());
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("locks")
  @Timeout(value = 15, unit = TimeUnit.MINUTES)
  void pythonAndJavaWriters(JavaLock lock) throws Exception {
    PythonPeer peer = PythonPeer.fromEnvironment();
    run(repo, "git", "init", "-q");
    Path log = repo.resolve("status.events.jsonl");
    Path lockFile = Path.of(peer.run("lock-path", log.toString()).get("lock_path").asString());
    Files.createDirectories(lockFile.getParent());
    Map<String, Object> result = new LinkedHashMap<>();
    result.put("os", OS);
    result.put("java_lock", lock.name());
    result.put("python_lock", OS.equals("windows") ? "msvcrt.locking" : "fcntl.flock");

    // Harness sanity: both sides render a row with the same bytes, and each side acquires a free lock (no vacuous "contended").
    String pythonRow = peer.runRaw("render-row", "--writer", "1", "--index", "7").stripTrailing();
    assertThat(pythonRow).isEqualTo(SpikeRows.render(1, 7));
    assertThat(peer.run("try", log.toString()).get("acquired").asBoolean()).as("python acquires the free lock").isTrue();
    try (JavaLock.Held held = lock.tryAcquire(lockFile)) {
      assertThat(held).as("java acquires the free lock").isNotNull();
    }

    result.put("python_holds_java_excluded", pythonHoldsJavaTries(peer, log, lock, lockFile));
    result.put("java_holds_python_excluded", javaHoldsPythonTries(peer, log, lock, lockFile));
    result.putAll(contention(peer, log, lock, lockFile));
    result.putAll(appends(peer, log, lock, lockFile));

    boolean excludes =
        (boolean) result.get("python_holds_java_excluded")
            && (boolean) result.get("java_holds_python_excluded")
            && (long) result.get("overlaps") == 0;
    boolean appendsAccepted =
        (long) result.get("refused_appends") == 0
            && (boolean) result.get("appends_intact")
            && (boolean) result.get("python_reader_accepts")
            && (boolean) result.get("java_reader_accepts");
    result.put("mutual_exclusion", excludes);
    result.put("verdict", excludes && appendsAccepted ? "GO" : "NO-GO");
    record(result);

    // What the spike established (report section "Verdict"). The JDK lock and flock(2) are independent on Linux; FFM flock(2) is the
    // same lock as Python's on Linux and macOS; on Windows both sides take LockFileEx byte-range locks that overlap at byte 0.
    if (lock instanceof FlockLock || OS.equals("windows")) {
      assertThat(result.get("verdict")).as(String.valueOf(result)).isEqualTo("GO");
    }
    if (lock instanceof FileChannelLock && OS.equals("linux")) {
      assertThat(excludes).as("FileChannel.lock and flock(2) are independent on Linux: " + result).isFalse();
    }
  }

  private static boolean pythonHoldsJavaTries(PythonPeer peer, Path log, JavaLock lock, Path lockFile) throws Exception {
    Path dir = Files.createTempDirectory("hold");
    Path ready = dir.resolve("ready");
    Path release = dir.resolve("release");
    Process holder = peer.start("hold", log.toString(), "--ready", ready.toString(), "--release", release.toString());
    awaitFile(ready);
    boolean excluded;
    try (JavaLock.Held held = lock.tryAcquire(lockFile)) {
      excluded = held == null;
    } finally {
      Files.createFile(release);
    }
    PythonPeer.finish(holder);
    return excluded;
  }

  private static boolean javaHoldsPythonTries(PythonPeer peer, Path log, JavaLock lock, Path lockFile) throws Exception {
    try (JavaLock.Held held = lock.tryAcquire(lockFile)) {
      assertThat(held).isNotNull();
      return !peer.run("try", log.toString()).get("acquired").asBoolean();
    }
  }

  /** Every writer, both languages at once, enters a critical section under the lock; an overlap is two holders inside it together. */
  private static Map<String, Object> contention(PythonPeer peer, Path log, JavaLock lock, Path lockFile) throws Exception {
    Path dir = Files.createTempDirectory("contend");
    Path sentinel = dir.resolve("inside");
    List<Process> pythons =
        startAll(peer, dir, i -> List.of("contend", log.toString(), "--sentinel", sentinel.toString(), "--rounds", String.valueOf(ROUNDS)));
    long javaOverlaps = 0;
    int javaRounds = 0;
    while (javaRounds < ROUNDS || pythons.stream().anyMatch(Process::isAlive)) {
      try (JavaLock.Held held = lock.acquire(lockFile, WAIT)) {
        if (!enterCriticalSection(sentinel)) {
          javaOverlaps++;
        }
      }
      javaRounds++;
      jitter();
    }
    long pythonOverlaps = 0;
    for (Process python : pythons) {
      pythonOverlaps += PythonPeer.json(PythonPeer.finish(python)).get("overlaps").asLong();
    }
    Map<String, Object> out = new LinkedHashMap<>();
    out.put("rounds", (long) ROUNDS * PYTHON_WRITERS + javaRounds);
    out.put("overlaps", javaOverlaps + pythonOverlaps);
    return out;
  }

  private static boolean enterCriticalSection(Path sentinel) throws IOException, InterruptedException {
    try {
      Files.createFile(sentinel);
    } catch (FileAlreadyExistsException e) {
      return false;
    }
    Thread.sleep(2);
    Files.deleteIfExists(sentinel);
    return true;
  }

  /** Every writer appends rows at once; then the bytes, the Python reader and the Java decoder are checked against what was written. */
  private static Map<String, Object> appends(PythonPeer peer, Path log, JavaLock lock, Path lockFile) throws Exception {
    Path dir = Files.createTempDirectory("append");
    List<Process> pythons =
        startAll(peer, dir, i -> List.of("append", log.toString(), "--writer", String.valueOf(i + 1), "--count", String.valueOf(APPENDS)));
    Set<String> expected = new HashSet<>();
    long refused = 0;
    int javaRows = 0;
    while (javaRows < APPENDS || pythons.stream().anyMatch(Process::isAlive)) {
      String row = SpikeRows.render(JAVA_WRITER, javaRows);
      try (JavaLock.Held held = lock.acquire(lockFile, WAIT)) {
        SpikeRows.appendUnderLock(log, row);
        expected.add(row);
      } catch (SpikeRows.TornTailException e) {
        refused++;
      }
      javaRows++;
      jitter();
    }
    for (int i = 0; i < pythons.size(); i++) {
      var report = PythonPeer.json(PythonPeer.finish(pythons.get(i)));
      Set<Integer> refusedIndexes = new HashSet<>();
      report.get("refused").forEach(index -> refusedIndexes.add(index.asInt()));
      refused += refusedIndexes.size();
      for (int index = 0; index < APPENDS; index++) {
        if (!refusedIndexes.contains(index)) {
          expected.add(SpikeRows.render(i + 1, index));
        }
      }
    }
    byte[] bytes = Files.readAllBytes(log);
    String text = new String(bytes, StandardCharsets.UTF_8);
    List<String> lines = new ArrayList<>(List.of(text.split("\n", -1)));
    boolean endsWithLf = lines.removeLast().isEmpty();
    boolean intact = endsWithLf && text.indexOf('\r') < 0 && lines.size() == expected.size() && new HashSet<>(lines).equals(expected);

    LedgerLineDecoder.Decoded decoded = LedgerLineDecoder.decode(bytes);
    long statusLines = decoded.lines().stream().map(LedgerLine::kind).filter(LineKind.Status.class::isInstance).count();
    boolean javaAccepts = decoded.tail() == TailClassification.NONE && statusLines == expected.size() && decoded.lines().size() == expected.size();

    var python = peer.run("read", log.toString());
    boolean pythonAccepts = python.get("events").asLong() == expected.size() && python.get("sha256").asString().equals(sha256(bytes));

    Map<String, Object> out = new LinkedHashMap<>();
    out.put("rows", (long) expected.size());
    out.put("refused_appends", refused);
    out.put("writer_switches", writerSwitches(lines));
    out.put("appends_intact", intact);
    out.put("python_reader_accepts", pythonAccepts);
    out.put("java_reader_accepts", javaAccepts);
    return out;
  }

  /** How often the writer changes from one line to the next: proof that the appends really interleaved. */
  private static long writerSwitches(List<String> lines) {
    long switches = 0;
    for (int i = 1; i < lines.size(); i++) {
      if (!actor(lines.get(i)).equals(actor(lines.get(i - 1)))) {
        switches++;
      }
    }
    return switches;
  }

  private static String actor(String line) {
    int start = line.indexOf("lock-interop-");
    return start < 0 ? "" : line.substring(start, line.indexOf('"', start));
  }

  /** Starts {@value #PYTHON_WRITERS} Python writers (the arguments of writer {@code i}), waits until each has loaded, then releases them together. */
  private static List<Process> startAll(PythonPeer peer, Path dir, IntFunction<List<String>> arguments) throws Exception {
    Path start = dir.resolve("start");
    List<Process> pythons = new ArrayList<>();
    for (int i = 0; i < PYTHON_WRITERS; i++) {
      Path ready = dir.resolve("ready-" + i);
      List<String> args = new ArrayList<>(arguments.apply(i));
      args.addAll(List.of("--ready", ready.toString(), "--start", start.toString()));
      pythons.add(peer.start(args.toArray(String[]::new)));
    }
    for (int i = 0; i < PYTHON_WRITERS; i++) {
      awaitFile(dir.resolve("ready-" + i));
    }
    Files.createFile(start);
    return pythons;
  }

  private static void awaitFile(Path path) throws IOException, InterruptedException {
    long deadline = System.nanoTime() + WAIT.toNanos();
    while (!Files.exists(path)) {
      if (System.nanoTime() >= deadline) {
        throw new IOException(path + " did not appear within " + WAIT);
      }
      Thread.sleep(10);
    }
  }

  private static void jitter() throws InterruptedException {
    Thread.sleep(ThreadLocalRandom.current().nextInt(0, 6));
  }

  private static void record(Map<String, Object> result) throws IOException {
    Files.createDirectories(OUT);
    String stem = result.get("os") + "-" + result.get("java_lock");
    Files.writeString(OUT.resolve(stem + ".json"), JSON.writeValueAsString(result) + "\n");
    String row =
        "| %s | %s vs %s | %s | %s | %s / %s | %s / %s | %s / %s / %s | %s | **%s** |%n"
            .formatted(
                result.get("os"),
                result.get("java_lock"),
                result.get("python_lock"),
                result.get("python_holds_java_excluded"),
                result.get("java_holds_python_excluded"),
                result.get("overlaps"),
                result.get("rounds"),
                result.get("refused_appends"),
                result.get("rows"),
                result.get("appends_intact"),
                result.get("python_reader_accepts"),
                result.get("java_reader_accepts"),
                result.get("writer_switches"),
                result.get("verdict"));
    Files.writeString(OUT.resolve(stem + ".md"), row);
    System.out.println("lock-interop result: " + JSON.writeValueAsString(result));
  }

  private static String sha256(byte[] bytes) throws NoSuchAlgorithmException {
    return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
  }

  private static void run(Path dir, String... command) throws IOException, InterruptedException {
    Process process = new ProcessBuilder(command).directory(dir.toFile()).inheritIO().start();
    assertThat(process.waitFor()).as(String.join(" ", command)).isZero();
  }

  private static String osKey() {
    String name = System.getProperty("os.name").toLowerCase(Locale.ROOT);
    if (name.contains("win")) {
      return "windows";
    }
    return name.contains("mac") ? "macos" : "linux";
  }
}
