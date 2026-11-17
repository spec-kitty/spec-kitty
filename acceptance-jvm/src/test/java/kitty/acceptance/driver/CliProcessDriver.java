package kitty.acceptance.driver;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * {@link SpecKittyDriver} backed by a real {@code spec-kitty} process (constraint C-002, FR-007).
 *
 * <p>The cross-OS stability discipline lives here:
 * <ul>
 *   <li>stdout and stderr are drained on <em>separate</em> threads so a chatty child can never
 *       deadlock the harness;</li>
 *   <li>a hard timeout bounds every invocation; on expiry the whole descendant process tree is
 *       {@code destroyForcibly()}'d (the part that matters most on Windows);</li>
 *   <li>captured output is normalised CRLF&rarr;LF before any assertion;</li>
 *   <li>the working-tree path is canonicalised with {@link Path#toRealPath()} so symlinked temp
 *       roots (common on macOS) compare equal.</li>
 * </ul>
 */
public final class CliProcessDriver implements SpecKittyDriver {

    /** Hard ceiling on a single CLI invocation; a slower run is a defect, not a wait. */
    static final Duration DEFAULT_TIMEOUT = Duration.ofMinutes(2);

    /**
     * Ceiling for {@code spec-kitty consolidate} (#7689), a budget tune with evidence, never a retry.
     *
     * <p>One consolidate run of a one-work-package Mission timed out at {@link #DEFAULT_TIMEOUT} on
     * a Windows nightly runner (run 44009807449). That runner was 7-9x slower than Linux on every CLI
     * step of the scenario, and consolidate takes 15-18 s on Linux, so it needs about 105-165 s
     * there. The git read cache (#7689) cut its git processes from 671 to 470 but cannot give that
     * margin alone. Four minutes is about 1.5x the worst estimate. See the #7689 row of
     * docs/development/testing/testing-flakiness.md; the guard in tests/ci/test_acceptance_cli_ceilings.py
     * keeps every named ceiling at or below {@link #MAX_COMMAND_TIMEOUT}.
     */
    static final Duration CONSOLIDATE_TIMEOUT = Duration.ofMinutes(4);

    /** No named ceiling may exceed this; a command that needs more is a defect to fix, not to wait for. */
    static final Duration MAX_COMMAND_TIMEOUT = Duration.ofMinutes(5);

    /** Named per-subcommand ceilings; every other command keeps {@link #DEFAULT_TIMEOUT}. */
    static final Map<String, Duration> COMMAND_TIMEOUTS = Map.of("consolidate", CONSOLIDATE_TIMEOUT);

    private final CommandResolver resolver;
    private final Map<String, String> environment;
    /** A fixed timeout for every command, or {@code null} for the default and named ceilings. */
    private final Duration timeout;

    public CliProcessDriver(CommandResolver resolver, Map<String, String> environment) {
        this.resolver = resolver;
        this.environment = Map.copyOf(environment);
        this.timeout = null;
    }

    public CliProcessDriver(CommandResolver resolver, Map<String, String> environment, Duration timeout) {
        this.resolver = resolver;
        this.environment = Map.copyOf(environment);
        this.timeout = timeout;
    }

    /** The ceiling for *args*: the fixed timeout if one was given, else the subcommand's named ceiling or the default. */
    Duration timeoutFor(List<String> args) {
        if (timeout != null) {
            return timeout;
        }
        if (args.size() > 1 && "spec-kitty".equals(args.get(0))) {
            return COMMAND_TIMEOUTS.getOrDefault(args.get(1), DEFAULT_TIMEOUT);
        }
        return DEFAULT_TIMEOUT;
    }

    @Override
    public CliResult run(List<String> args, Path cwd) {
        if (args.isEmpty()) {
            throw new IllegalArgumentException("Refusing to run an empty command");
        }
        List<String> command = new ArrayList<>(args);
        command.set(0, resolver.resolve(args.get(0)));

        ProcessBuilder builder = new ProcessBuilder(command);
        builder.directory(cwd.toFile());
        builder.environment().clear();
        builder.environment().putAll(environment);
        builder.redirectErrorStream(false);

        Duration timeout = timeoutFor(args);
        Process process = null;
        try {
            process = builder.start();
            StreamDrainer out = StreamDrainer.start(process.getInputStream(), "stdout");
            StreamDrainer err = StreamDrainer.start(process.getErrorStream(), "stderr");

            long deadline = System.nanoTime() + timeout.toNanos();
            boolean finished = process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS);
            if (!finished) {
                ProcessTree.kill(process);
                throw new CliTimeoutException(command, timeout);
            }
            int exit = process.exitValue();
            String stdout;
            String stderr;
            try {
                // A grandchild that outlives the CLI can hold the pipes open; bound the wait too.
                stdout = normaliseLineEndings(out.await(remaining(deadline)));
                stderr = normaliseLineEndings(err.await(remaining(deadline)));
            } catch (StreamDrainer.DrainTimeoutException e) {
                ProcessTree.kill(process);
                throw new CliTimeoutException(command, timeout);
            }
            return CliResult.of(exit, stdout, stderr, realPath(cwd));
        } catch (IOException e) {
            throw new CliExecutionException("Failed to launch " + command, e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new CliExecutionException("Interrupted while running " + command, e);
        } finally {
            if (process != null && process.isAlive()) {
                ProcessTree.kill(process);
            }
        }
    }

    private static Duration remaining(long deadlineNanos) {
        return Duration.ofNanos(Math.max(0, deadlineNanos - System.nanoTime()));
    }

    private static Path realPath(Path path) {
        try {
            return path.toRealPath();
        } catch (IOException e) {
            return path.toAbsolutePath().normalize();
        }
    }

    private static String normaliseLineEndings(String text) {
        return text.replace("\r\n", "\n").replace("\r", "\n");
    }

    /** Resolves a command token (e.g. {@code "spec-kitty"}) to an absolute executable path. */
    @FunctionalInterface
    public interface CommandResolver {
        String resolve(String token);
    }

    /** Thrown when a CLI invocation exceeds its timeout. */
    public static final class CliTimeoutException extends RuntimeException {
        CliTimeoutException(List<String> command, Duration timeout) {
            super("Command timed out after " + timeout + ": " + command);
        }
    }

    /** Thrown when a CLI invocation cannot be launched or is interrupted. */
    public static final class CliExecutionException extends RuntimeException {
        CliExecutionException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
