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

    private final CommandResolver resolver;
    private final Map<String, String> environment;
    private final Duration timeout;

    public CliProcessDriver(CommandResolver resolver, Map<String, String> environment) {
        this(resolver, environment, DEFAULT_TIMEOUT);
    }

    public CliProcessDriver(CommandResolver resolver, Map<String, String> environment, Duration timeout) {
        this.resolver = resolver;
        this.environment = Map.copyOf(environment);
        this.timeout = timeout;
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
