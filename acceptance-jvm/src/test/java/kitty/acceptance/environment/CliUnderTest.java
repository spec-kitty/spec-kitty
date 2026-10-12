package kitty.acceptance.environment;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
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

    private final Path entryPoint;
    private final Path binDir;

    private CliUnderTest(Path entryPoint, Path binDir) {
        this.entryPoint = entryPoint;
        this.binDir = binDir;
    }

    /** The provisioned CLI, built once and shared across every scenario in the run. */
    public static CliUnderTest instance() {
        CliUnderTest local = instance;
        if (local == null) {
            synchronized (CliUnderTest.class) {
                local = instance;
                if (local == null) {
                    local = provision();
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
            return new CliUnderTest(entry, binDir);
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

    private static Path findRepoRoot() {
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
        builder.redirectErrorStream(true);
        try {
            Process process = builder.start();
            // Drain before waitFor; redirectErrorStream merges to one modest-sized stream.
            String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            boolean finished = process.waitFor(PROVISION_TIMEOUT_MINUTES, TimeUnit.MINUTES);
            if (!finished) {
                process.descendants().forEach(ProcessHandle::destroyForcibly);
                process.destroyForcibly();
                throw new IllegalStateException("Provisioning command timed out: " + List.of(command));
            }
            if (process.exitValue() != 0) {
                throw new IllegalStateException("Provisioning command failed (" + process.exitValue()
                        + "): " + List.of(command) + System.lineSeparator() + output);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Provisioning command could not start: " + List.of(command), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted during provisioning: " + List.of(command), e);
        }
    }
}
