package kitty.acceptance.environment;

import kitty.acceptance.driver.CliProcessDriver;

import java.io.File;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The per-scenario hermetic environment: a temp dir holding a redirected home, a working tree, and
 * the process environment the CLI is launched with (NFR-002, FR-008).
 *
 * <p>Every home-ish location ({@code HOME}, {@code USERPROFILE}, {@code SPEC_KITTY_HOME}, the XDG
 * dirs, {@code LOCALAPPDATA}) is redirected inside the temp dir, and output is forced colourless,
 * UTF-8 and fixed-width.
 */
public final class ScenarioEnvironment {

    private static final String UTF8_LOCALE = "C.UTF-8";
    private static final String GIT_NAME = "Acceptance Harness";
    private static final String GIT_EMAIL = "harness@example.invalid";

    private final Path tempRoot;
    private final Path homeDir;
    private final Path workDir;
    private final Path tmpDir;
    private final CliUnderTest cli;
    private final Map<String, String> environment;

    private ScenarioEnvironment(Path tempRoot, Path homeDir, Path workDir, Path tmpDir, CliUnderTest cli) {
        this.tempRoot = tempRoot;
        this.homeDir = homeDir;
        this.workDir = workDir;
        this.tmpDir = tmpDir;
        this.cli = cli;
        this.environment = buildEnvironment();
    }

    public static ScenarioEnvironment create(CliUnderTest cli) {
        try {
            Path tempRoot = Files.createTempDirectory("spec-kitty-scenario-");
            Path homeDir = Files.createDirectories(tempRoot.resolve("home"));
            Path workDir = Files.createDirectories(tempRoot.resolve("work"));
            Path tmpDir = Files.createDirectories(tempRoot.resolve("tmp"));
            return new ScenarioEnvironment(tempRoot, homeDir, workDir, tmpDir, cli);
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
        env.put("TEMP", tmpDir.toString());
        env.put("TMP", tmpDir.toString());
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
        env.put("GIT_CONFIG_NOSYSTEM", "1");

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

    /** The redirected home directory, for the collaborators that watch or tear it down. */
    public Path homeDir() {
        return homeDir;
    }

    /** The scenario's temp root (parent of home, work and tmp), for teardown. */
    public Path tempRoot() {
        return tempRoot;
    }
}
