package kitty.acceptance.driver;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/** Reads one process stream to completion on its own daemon thread, avoiding pipe-buffer deadlock. */
public final class StreamDrainer {

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

    public static StreamDrainer start(InputStream source, String name) {
        StreamDrainer drainer = new StreamDrainer(source, name);
        drainer.thread.start();
        return drainer;
    }

    /**
     * Waits at most {@code timeout} for the stream to reach end-of-file and returns what was read.
     *
     * @throws DrainTimeoutException when the stream is still open after {@code timeout} (for example
     *         because a surviving grandchild holds the pipe); the caller decides how to clean up.
     */
    public String await(Duration timeout) throws InterruptedException {
        thread.join(Math.max(1, timeout.toMillis()));
        if (thread.isAlive()) {
            throw new DrainTimeoutException();
        }
        if (failure != null) {
            throw new IllegalStateException("Failed draining process stream", failure);
        }
        return buffer.toString(StandardCharsets.UTF_8);
    }

    /** The stream did not close within the allowed time. */
    public static final class DrainTimeoutException extends RuntimeException {
        DrainTimeoutException() {
            super("Process output stream did not close in time");
        }
    }
}
