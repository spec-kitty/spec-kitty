package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.OptionalLong;
import org.junit.jupiter.api.Test;

/**
 * NFR-002's clock, proved without a binary: a stand-in "process" needs 150 ms to be launched and a further 400 ms before it listens. The
 * measured start-up must include BOTH, so a timer started after the launch (or after the first answer) is red.
 */
class StartupProbeTest {

  private static final long LAUNCH_MILLIS = 150;
  private static final long LISTEN_AFTER_MILLIS = 400;

  /** Answers 200 to every request once it listens; a 403 first when {@code refuseFirst} is set (the Host filter before the port is known). */
  private static final class Stub implements Replay.Running {
    private final ServerSocket server;
    private final Thread acceptor;
    private volatile boolean closed;

    Stub(int port, boolean refuseFirst) {
      try {
        Thread.sleep(LAUNCH_MILLIS);
        this.server = new ServerSocket(port, 50, InetAddress.getLoopbackAddress());
      } catch (IOException | InterruptedException failure) {
        throw new IllegalStateException(failure);
      }
      this.acceptor =
          new Thread(
              () -> {
                try {
                  Thread.sleep(LISTEN_AFTER_MILLIS);
                  boolean first = refuseFirst;
                  while (!closed) {
                    try (Socket socket = server.accept()) {
                      socket.getInputStream().read(new byte[4096]);
                      OutputStream out = socket.getOutputStream();
                      String head = first ? "HTTP/1.1 403 Forbidden\r\n" : "HTTP/1.1 200 OK\r\n";
                      first = false;
                      out.write((head + "Content-Length: 2\r\nConnection: close\r\n\r\n{}").getBytes(StandardCharsets.ISO_8859_1));
                    }
                  }
                } catch (IOException | InterruptedException ended) {
                  // closed
                }
              });
      // the socket is bound at once (the OS queues connections), but nothing answers before LISTEN_AFTER_MILLIS
      acceptor.setDaemon(true);
      acceptor.start();
    }

    @Override
    public void requireAlive() {}

    @Override
    public OptionalLong childProcesses() {
      return OptionalLong.empty();
    }

    @Override
    public void close() {
      closed = true;
      try {
        server.close();
      } catch (IOException ignored) {
        // the stub is over
      }
    }
  }

  @Test
  void theClockStartsBeforeTheLaunchAndStopsAtTheFirstAcceptedAnswer() {
    int port = Replay.freePort();
    try (StartupProbe.Started started = StartupProbe.start(() -> new Stub(port, false), port)) {
      assertThat(started.millis()).as("launch + listen delay are both part of start-up").isGreaterThanOrEqualTo(LAUNCH_MILLIS + LISTEN_AFTER_MILLIS);
      assertThat(started.millis()).as("and little else").isLessThan(LAUNCH_MILLIS + LISTEN_AFTER_MILLIS + 1_500);
    }
  }

  @Test
  void aRefusalByTheHostFilterIsNotAnAcceptedRequest() {
    int port = Replay.freePort();
    try (StartupProbe.Started started = StartupProbe.start(() -> new Stub(port, true), port)) {
      assertThat(started.millis()).isGreaterThanOrEqualTo(LAUNCH_MILLIS + LISTEN_AFTER_MILLIS);
    }
  }

  @Test
  void aDeadProcessFailsTheProbeInsteadOfWaiting() {
    int port = Replay.freePort();
    Replay.Running dead =
        new Replay.Running() {
          @Override
          public void requireAlive() {
            throw new AssertionError("exited");
          }

          @Override
          public OptionalLong childProcesses() {
            return OptionalLong.empty();
          }

          @Override
          public void close() {}
        };
    assertThatThrownBy(() -> StartupProbe.start(() -> dead, port)).isInstanceOf(AssertionError.class).hasMessageContaining("exited");
  }
}
