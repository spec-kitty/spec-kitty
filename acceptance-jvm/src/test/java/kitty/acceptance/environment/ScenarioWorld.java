package kitty.acceptance.environment;

import kitty.acceptance.driver.CliProcessDriver;

import java.io.File;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;

/**
 * Per-scenario isolation: a temp dir holding a redirected home, a working tree / git fixture, and
 * the environment the CLI is launched with (NFR-002, FR-008).
 *
 * <p>Every home-ish location ({@code HOME}, {@code USERPROFILE}, {@code SPEC_KITTY_HOME}, the XDG
 * dirs, {@code LOCALAPPDATA}) is redirected inside the temp dir, output is forced colourless, UTF-8
 * and fixed-width, and a positive control proves the run actually wrote inside the temp dir — so
 * "never touched the real home" is non-vacuous. The instance also records and compares filesystem
 * and git state for the ratchet/positive-control step pairs.
 */
public final class ScenarioWorld {

    private static final String UTF8_LOCALE = "C.UTF-8";
    private static final String GIT_NAME = "Acceptance Harness";
    private static final String GIT_EMAIL = "harness@example.invalid";

    private final Path tempRoot;
    private final Path homeDir;
    private final Path workDir;
    private final Path tmpDir;
    private final CliUnderTest cli;
    private final Map<String, String> environment;
    private final Map<String, String> recordedDigests = new HashMap<>();
    private final long startEpochMillis = System.currentTimeMillis();

    private String recordedHead;
    private Integer recordedCommitCount;
    private boolean commandObserved;

    private ScenarioWorld(Path tempRoot, Path homeDir, Path workDir, Path tmpDir, CliUnderTest cli) {
        this.tempRoot = tempRoot;
        this.homeDir = homeDir;
        this.workDir = workDir;
        this.tmpDir = tmpDir;
        this.cli = cli;
        this.environment = buildEnvironment();
    }

    public static ScenarioWorld create(CliUnderTest cli) {
        try {
            Path tempRoot = Files.createTempDirectory("spec-kitty-scenario-");
            Path homeDir = Files.createDirectories(tempRoot.resolve("home"));
            Path workDir = Files.createDirectories(tempRoot.resolve("work"));
            Path tmpDir = Files.createDirectories(tempRoot.resolve("tmp"));
            return new ScenarioWorld(tempRoot, homeDir, workDir, tmpDir, cli);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not create the scenario temp dir", e);
        }
    }

    private Map<String, String> buildEnvironment() {
        Map<String, String> env = new LinkedHashMap<>();
        String home = homeDir.toString();

        // The throwaway venv first, so the shipped entry point and its deps win; then the inherited
        // PATH so git and other tools stay reachable.
        String inheritedPath = System.getenv().getOrDefault("PATH", "");
        env.put("PATH", cli.binDir() + File.pathSeparator + inheritedPath);

        // Redirect every home-ish location into the temp dir (NFR-002 hermeticity).
        env.put("HOME", home);
        env.put("USERPROFILE", home);
        env.put("SPEC_KITTY_HOME", home);
        env.put("XDG_CONFIG_HOME", homeDir.resolve(".config").toString());
        env.put("XDG_DATA_HOME", homeDir.resolve(".local/share").toString());
        env.put("XDG_CACHE_HOME", homeDir.resolve(".cache").toString());
        env.put("XDG_STATE_HOME", homeDir.resolve(".local/state").toString());
        env.put("LOCALAPPDATA", homeDir.resolve("AppData/Local").toString());
        env.put("APPDATA", homeDir.resolve("AppData/Roaming").toString());
        env.put("TMPDIR", tmpDir.toString());
        env.put("VIRTUAL_ENV", cli.binDir().getParent().toString());

        // Deterministic, colourless, fixed-width, UTF-8 output on every OS.
        env.put("LANG", UTF8_LOCALE);
        env.put("LC_ALL", UTF8_LOCALE);
        env.put("PYTHONUTF8", "1");
        env.put("PYTHONIOENCODING", "utf-8");
        env.put("NO_COLOR", "1");
        env.put("COLUMNS", "100");

        // A git identity without reading the developer's global config (HOME is redirected).
        env.put("GIT_AUTHOR_NAME", GIT_NAME);
        env.put("GIT_AUTHOR_EMAIL", GIT_EMAIL);
        env.put("GIT_COMMITTER_NAME", GIT_NAME);
        env.put("GIT_COMMITTER_EMAIL", GIT_EMAIL);

        // Preserve the handful of OS-essential vars a process needs to start (Windows only; absent
        // and therefore skipped on POSIX).
        for (String key : List.of("SystemRoot", "SYSTEMROOT", "ComSpec", "COMSPEC", "PATHEXT",
                "SystemDrive", "WINDIR")) {
            String value = System.getenv(key);
            if (value != null) {
                env.put(key, value);
            }
        }
        return env;
    }

    public Map<String, String> environment() {
        return new LinkedHashMap<>(environment);
    }

    /** Maps the {@code "spec-kitty"} token to the provisioned venv entry point; passes anything else through. */
    public CliProcessDriver.CommandResolver commandResolver() {
        return token -> "spec-kitty".equals(token) ? cli.entryPoint().toString() : token;
    }

    public Path workDir() {
        return workDir;
    }

    public Path resolve(String relative) {
        return workDir.resolve(relative);
    }

    public void markCommandObserved() {
        commandObserved = true;
    }

    // --- filesystem snapshots -------------------------------------------

    public void recordState(String relative) {
        recordedDigests.put(relative, digest(resolve(relative)));
    }

    public boolean isUnchanged(String relative) {
        String recorded = recordedDigests.get(relative);
        if (recorded == null) {
            throw new IllegalStateException("No recorded state for '" + relative + "'");
        }
        return recorded.equals(digest(resolve(relative)));
    }

    // --- git fixture -----------------------------------------------------

    public void initGitRepoWithCommit() {
        git("init");
        try {
            Files.writeString(workDir.resolve("README.md"), "seed\n");
        } catch (IOException e) {
            throw new UncheckedIOException("Could not write the seed file", e);
        }
        git("add", "README.md");
        git("commit", "-m", "seed commit");
    }

    /** Records HEAD and the commit count, and returns the recorded count. */
    public int recordRepoState() {
        recordedHead = git("rev-parse", "HEAD").trim();
        recordedCommitCount = Integer.parseInt(git("rev-list", "--count", "HEAD").trim());
        return recordedCommitCount;
    }

    public boolean headUnchanged() {
        return recordedHead != null && recordedHead.equals(git("rev-parse", "HEAD").trim());
    }

    public boolean commitCountUnchanged() {
        return recordedCommitCount != null
                && recordedCommitCount == Integer.parseInt(git("rev-list", "--count", "HEAD").trim());
    }

    private String git(String... args) {
        List<String> command = new ArrayList<>();
        command.add("git");
        command.add("-c");
        command.add("user.name=" + GIT_NAME);
        command.add("-c");
        command.add("user.email=" + GIT_EMAIL);
        command.add("-c");
        command.add("commit.gpgsign=false");
        command.addAll(List.of(args));

        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(workDir.toFile());
        builder.environment().clear();
        builder.environment().putAll(environment);
        builder.redirectErrorStream(true);
        try {
            Process process = builder.start();
            String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            boolean finished = process.waitFor(60, TimeUnit.SECONDS);
            if (!finished) {
                process.descendants().forEach(ProcessHandle::destroyForcibly);
                process.destroyForcibly();
                throw new IllegalStateException("git " + List.of(args) + " timed out");
            }
            if (process.exitValue() != 0) {
                throw new IllegalStateException("git " + List.of(args) + " failed:" + System.lineSeparator() + output);
            }
            return output;
        } catch (IOException e) {
            throw new UncheckedIOException("git " + List.of(args) + " could not start", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted during git " + List.of(args), e);
        }
    }

    // --- positive control + teardown ------------------------------------

    /**
     * NFR-002 positive control: after a CLI invocation, assert the run observably wrote inside the
     * isolated temp dir. Without this, a vacuously "clean" real home could pass for the wrong reason.
     */
    public void assertObservedWriteInsideTempDir() {
        if (!commandObserved) {
            return;
        }
        try (Stream<Path> tree = Files.walk(tempRoot)) {
            boolean wrote = tree.filter(Files::isRegularFile).anyMatch(this::createdDuringScenario);
            if (!wrote) {
                throw new AssertionError("Positive control failed: the CLI run wrote nothing inside the "
                        + "isolated temp dir " + tempRoot + " - environment redirection may not be in effect");
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Could not walk the temp dir for the positive control", e);
        }
    }

    private boolean createdDuringScenario(Path file) {
        try {
            return Files.getLastModifiedTime(file).toMillis() >= startEpochMillis;
        } catch (IOException e) {
            return false;
        }
    }

    public void cleanUp() {
        if (!Files.exists(tempRoot)) {
            return;
        }
        try (Stream<Path> tree = Files.walk(tempRoot)) {
            tree.sorted(Comparator.reverseOrder()).forEach(ScenarioWorld::deleteQuietly);
        } catch (IOException ignored) {
            // Best-effort teardown; a leaked temp dir is not worth failing a passing scenario.
        }
    }

    private static void deleteQuietly(Path path) {
        try {
            Files.deleteIfExists(path);
        } catch (IOException ignored) {
            // Best-effort teardown.
        }
    }

    // --- digest helpers --------------------------------------------------

    private static String digest(Path path) {
        if (!Files.exists(path)) {
            return "ABSENT";
        }
        MessageDigest md = newSha256();
        if (Files.isDirectory(path)) {
            Map<String, String> entries = new TreeMap<>();
            try (Stream<Path> tree = Files.walk(path)) {
                tree.forEach(p -> {
                    String rel = path.relativize(p).toString().replace('\\', '/');
                    if (Files.isDirectory(p)) {
                        entries.put("d:" + rel, "");
                    } else {
                        entries.put("f:" + rel, sha256(p));
                    }
                });
            } catch (IOException e) {
                throw new UncheckedIOException("Could not walk " + path, e);
            }
            for (Map.Entry<String, String> entry : entries.entrySet()) {
                md.update(entry.getKey().getBytes(StandardCharsets.UTF_8));
                md.update((byte) 0);
                md.update(entry.getValue().getBytes(StandardCharsets.UTF_8));
                md.update((byte) 0);
            }
        } else {
            md.update(readAllBytes(path));
        }
        return HexFormat.of().formatHex(md.digest());
    }

    private static String sha256(Path file) {
        MessageDigest md = newSha256();
        md.update(readAllBytes(file));
        return HexFormat.of().formatHex(md.digest());
    }

    private static byte[] readAllBytes(Path path) {
        try {
            return Files.readAllBytes(path);
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read " + path, e);
        }
    }

    private static MessageDigest newSha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is unavailable", e);
        }
    }
}
