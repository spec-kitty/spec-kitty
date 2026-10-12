package kitty.acceptance.driver;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
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

            boolean finished = process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS);
            if (!finished) {
                killTree(process);
                throw new CliTimeoutException(command, timeout);
            }
            int exit = process.exitValue();
            String stdout = normaliseLineEndings(out.await());
            String stderr = normaliseLineEndings(err.await());
            Object json = maybeParseJson(args, stdout);
            return CliResult.of(exit, stdout, stderr, json, realPath(cwd));
        } catch (IOException e) {
            throw new CliExecutionException("Failed to launch " + command, e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new CliExecutionException("Interrupted while running " + command, e);
        } finally {
            if (process != null && process.isAlive()) {
                killTree(process);
            }
        }
    }

    private static Object maybeParseJson(List<String> args, String stdout) {
        if (!args.contains("--json") || stdout.isBlank()) {
            return null;
        }
        try {
            return Json.parse(stdout.trim());
        } catch (Json.JsonParseException ignored) {
            return null; // not fatal: the caller inspects exit/stderr for malformed output
        }
    }

    private static void killTree(Process process) {
        process.descendants().forEach(ProcessHandle::destroyForcibly);
        process.toHandle().destroyForcibly();
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

    /** Reads one process stream to completion on its own daemon thread, avoiding pipe-buffer deadlock. */
    private static final class StreamDrainer {

        private final Thread thread;
        private final ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        private volatile IOException failure;

        private StreamDrainer(InputStream source, String name) {
            this.thread = new Thread(() -> {
                try (InputStream in = source) {
                    in.transferTo(buffer);
                } catch (IOException e) {
                    failure = e;
                }
            }, "cli-" + name + "-drainer");
            this.thread.setDaemon(true);
        }

        static StreamDrainer start(InputStream source, String name) {
            StreamDrainer drainer = new StreamDrainer(source, name);
            drainer.thread.start();
            return drainer;
        }

        String await() throws InterruptedException {
            thread.join();
            if (failure != null) {
                throw new CliExecutionException("Failed draining process stream", failure);
            }
            return buffer.toString(StandardCharsets.UTF_8);
        }
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
