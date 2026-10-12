package kitty.acceptance.environment;

import kitty.acceptance.driver.ProcessTree;
import kitty.acceptance.driver.StreamDrainer;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.time.Duration;
import java.util.concurrent.TimeUnit;

/**
 * Runs a helper process (provisioning, git fixture) with merged stdout/stderr, a drain thread and a
 * hard timeout that actually fires: output is read on a thread, so a hung child cannot block the
 * harness in a read before the timeout is ever consulted.
 */
final class ProcessRunner {

    /** Exit code and merged output of a finished process. */
    record Outcome(int exitCode, String output) {
    }

    private ProcessRunner() {
    }

    /**
     * Starts the process and waits at most {@code timeout} for it and its output.
     *
     * @throws IllegalStateException on timeout (the whole process tree is killed first) or interruption
     */
    static Outcome run(ProcessBuilder builder, Duration timeout, String description) {
        builder.redirectErrorStream(true);
        Process process = null;
        try {
            process = builder.start();
            StreamDrainer drainer = StreamDrainer.start(process.getInputStream(), "helper");
            long deadline = System.nanoTime() + timeout.toNanos();
            if (!process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS)) {
                throw new IllegalStateException(description + " timed out after " + timeout);
            }
            Duration left = Duration.ofNanos(Math.max(0, deadline - System.nanoTime()));
            String output = drainer.await(left);
            return new Outcome(process.exitValue(), output);
        } catch (StreamDrainer.DrainTimeoutException e) {
            throw new IllegalStateException(description + " timed out after " + timeout
                    + " (output stream still open)", e);
        } catch (IOException e) {
            throw new UncheckedIOException(description + " could not start", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted during " + description, e);
        } finally {
            if (process != null && process.isAlive()) {
                ProcessTree.kill(process);
            }
        }
    }
}
