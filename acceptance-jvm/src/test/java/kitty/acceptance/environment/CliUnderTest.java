package kitty.acceptance.environment;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Locale;
import java.util.stream.Stream;

/**
 * The {@code spec-kitty} CLI under test, provisioned <em>exactly as it ships</em> (FR-009, C-002).
 *
 * <p>Once per JVM run (cached as a lazy singleton, so every scenario reuses it) this:
 * <ol>
 *   <li>builds a wheel from the repository with {@code uv build --wheel} (never PyPI, never an
 *       editable install);</li>
 *   <li>creates a throwaway virtual environment with {@code uv venv};</li>
 *   <li>installs the built wheel into it with {@code uv pip install}.</li>
 * </ol>
 * The venv's {@code spec-kitty} entry point is then handed to {@link kitty.acceptance.driver.CliProcessDriver}.
 */
public final class CliUnderTest {

    private static final long PROVISION_TIMEOUT_MINUTES = 15;
    private static volatile CliUnderTest instance;
    private static volatile RuntimeException provisioningFailure;

    private final Path entryPoint;
    private final Path binDir;
    private final String version;

    private CliUnderTest(Path entryPoint, Path binDir, String version) {
        this.entryPoint = entryPoint;
        this.binDir = binDir;
        this.version = version;
    }

    /** The provisioned CLI, built once and shared across every scenario in the run. */
    public static CliUnderTest instance() {
        CliUnderTest local = instance;
        if (local == null) {
            synchronized (CliUnderTest.class) {
                local = instance;
                if (local == null) {
                    if (provisioningFailure != null) {
                        // Fail fast: a broken build stays broken, so do not rebuild per scenario.
                        throw new IllegalStateException("Provisioning already failed earlier in this run",
                                provisioningFailure);
                    }
                    try {
                        local = provision();
                    } catch (RuntimeException e) {
                        provisioningFailure = e;
                        throw e;
                    }
                    instance = local;
                }
            }
        }
        return local;
    }

    /** Absolute path to the venv {@code spec-kitty} console script. */
    public Path entryPoint() {
        return entryPoint;
    }

    /** The venv {@code bin}/{@code Scripts} directory, placed first on the scenario {@code PATH}. */
    public Path binDir() {
        return binDir;
    }

    /** The version of the wheel under test, read from its file name (never by running the CLI). */
    public String version() {
        return version;
    }

    /**
     * Extracts the version from a wheel file name {@code <distribution>-<version>-<tags>.whl}
     * (PEP 427: the version is the second {@code -}-separated field).
     *
     * @throws IllegalStateException when the name does not have that shape
     */
    static String versionOfWheel(String wheelFileName) {
        String[] fields = wheelFileName.split("-");
        if (fields.length < 3 || fields[1].isEmpty() || !wheelFileName.endsWith(".whl")) {
            throw new IllegalStateException("Cannot read the version from wheel name '" + wheelFileName + "'");
        }
        return fields[1];
    }

    private static CliUnderTest provision() {
        try {
            Path repoRoot = findRepoRoot();
            Path workArea = Files.createTempDirectory("spec-kitty-cut-");
            Path wheelDir = Files.createDirectories(workArea.resolve("wheel"));
            Path venvDir = workArea.resolve("venv");

            execOrThrow(repoRoot, "uv", "build", "--wheel",
                    "--out-dir", wheelDir.toString(), repoRoot.toString());
            Path wheel = findWheel(wheelDir);

            execOrThrow(repoRoot, "uv", "venv", venvDir.toString());
            Path venvPython = binOf(venvDir).resolve(isWindows() ? "python.exe" : "python");
            execOrThrow(repoRoot, "uv", "pip", "install",
                    "--python", venvPython.toString(), wheel.toString());

            Path binDir = binOf(venvDir);
            Path entry = binDir.resolve(isWindows() ? "spec-kitty.exe" : "spec-kitty");
            if (!Files.exists(entry)) {
                throw new IllegalStateException("spec-kitty entry point was not installed at " + entry);
            }
            return new CliUnderTest(entry, binDir, versionOfWheel(wheel.getFileName().toString()));
        } catch (IOException e) {
            throw new IllegalStateException("Failed to provision the spec-kitty wheel under test", e);
        }
    }

    private static Path binOf(Path venvDir) {
        return venvDir.resolve(isWindows() ? "Scripts" : "bin");
    }

    private static Path findWheel(Path wheelDir) throws IOException {
        try (Stream<Path> files = Files.list(wheelDir)) {
            return files.filter(p -> p.getFileName().toString().endsWith(".whl"))
                    .findFirst()
                    .orElseThrow(() -> new IllegalStateException("uv build produced no wheel in " + wheelDir));
        }
    }

    /** The repository root: the nearest ancestor of the working directory holding {@code pyproject.toml}. */
    static Path findRepoRoot() {
        Path start = Path.of("").toAbsolutePath();
        for (Path dir = start; dir != null; dir = dir.getParent()) {
            if (Files.exists(dir.resolve("pyproject.toml"))) {
                return dir;
            }
        }
        throw new IllegalStateException("Could not locate the repo root (no pyproject.toml above " + start + ")");
    }

    private static boolean isWindows() {
        return System.getProperty("os.name", "").toLowerCase(Locale.ROOT).contains("win");
    }

    private static void execOrThrow(Path cwd, String... command) {
        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(cwd.toFile());
        ProcessRunner.Outcome outcome = ProcessRunner.run(builder,
                Duration.ofMinutes(PROVISION_TIMEOUT_MINUTES), "Provisioning command " + List.of(command));
        if (outcome.exitCode() != 0) {
            throw new IllegalStateException("Provisioning command failed (" + outcome.exitCode()
                    + "): " + List.of(command) + System.lineSeparator() + outcome.output());
        }
    }
}
