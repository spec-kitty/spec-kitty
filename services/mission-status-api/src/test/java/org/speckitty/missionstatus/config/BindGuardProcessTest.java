package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

/**
 * AC-9a and AC-9e, in a child JVM: a non-loopback bind makes the process exit non-zero within the (provisional, wall-clock) 10 seconds,
 * naming the refused address, and a TCP connect to that address on the configured port is refused afterwards. A port already in use
 * exits non-zero and names the port.
 */
class BindGuardProcessTest {

  private static final long BOUND_SECONDS = 10;

  /** AC-9e only: the port-in-use failure goes through Boot's full start-up, so it gets a wider ceiling. The spec's wall-clock note makes every bound an initial, provisional ceiling that a measurement amends. */
  private static final long PORT_IN_USE_BOUND_SECONDS = 30;

  /** A local non-loopback IPv4 address, when the machine has one. */
  private static String lanAddress() throws IOException {
    for (NetworkInterface nic : Collections.list(NetworkInterface.getNetworkInterfaces())) {
      if (nic.isUp() && !nic.isLoopback()) {
        for (InetAddress address : Collections.list(nic.getInetAddresses())) {
          if (address instanceof java.net.Inet4Address && !address.isLoopbackAddress()) {
            return address.getHostAddress();
          }
        }
      }
    }
    return null;
  }

  static Stream<String> refusedBinds() throws IOException {
    String lan = lanAddress();
    return Stream.of("0.0.0.0", "::", "localhost", lan == null ? "192.0.2.77" : lan, "[::]");
  }

  @ParameterizedTest(name = "bind {0}")
  @MethodSource("refusedBinds")
  @Timeout(60)
  void aNonLoopbackBindExitsNonZeroNamesTheAddressAndListensOnNothing(String address, @TempDir Path dir) throws Exception {
    int port = AppProcess.freePort();
    AppProcess.Result result =
        AppProcess.run(dir.resolve("out.log"), List.of(), List.of("--server.address=" + address, "--server.port=" + port, "--mission-status.project-root=" + dir), BOUND_SECONDS);

    assertThat(result.exited()).as("exited within the bound").isTrue();
    assertThat(result.exitCode()).isNotZero();
    assertThat(result.output()).contains(address);
    String target = address.equals("[::]") ? "::" : address;
    assertThatThrownBy(() -> {
          try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(InetAddress.getByName(target), port), 2000);
          }
        })
        .as("a connect to the refused address and the configured port")
        .isInstanceOf(IOException.class);
  }

  @Test
  @Timeout(60)
  void aBlankAddressExitsNonZeroNamingUnset(@TempDir Path dir) throws Exception {
    int port = AppProcess.freePort();
    AppProcess.Result result = AppProcess.run(dir.resolve("out.log"), List.of(), List.of("--server.address=", "--server.port=" + port, "--mission-status.project-root=" + dir), BOUND_SECONDS);
    assertThat(result.exited()).isTrue();
    assertThat(result.exitCode()).isNotZero();
    assertThat(result.output()).contains("unset");
    assertThatThrownBy(() -> new Socket().connect(new InetSocketAddress("127.0.0.1", port), 1000)).isInstanceOf(IOException.class);
  }

  @Test
  @Timeout(60)
  void ac9eAPortAlreadyInUseExitsNonZeroAndNamesThePort(@TempDir Path dir) throws Exception {
    try (ServerSocket holder = new ServerSocket(0, 1, InetAddress.getByName("127.0.0.1"))) {
      int port = holder.getLocalPort();
      AppProcess.Result result = AppProcess.run(dir.resolve("out.log"), List.of(), List.of("--server.port=" + port, "--mission-status.project-root=" + dir), PORT_IN_USE_BOUND_SECONDS);
      assertThat(result.exited()).as("exited within the bound").isTrue();
      assertThat(result.exitCode()).isNotZero();
      assertThat(result.output()).contains(Integer.toString(port));
    }
  }

  @Test
  @Timeout(60)
  void withTheShippedDefaultsTheServerListensOnLoopbackOnlyAndRefusesTheLanAddress(@TempDir Path dir) throws Exception {
    int port = AppProcess.freePort();
    Process process = AppProcess.launch(dir.resolve("out.log"), List.of(), List.of("--server.port=" + port, "--mission-status.project-root=" + dir));
    try {
      long deadline = System.nanoTime() + BOUND_SECONDS * 4_000_000_000L;
      boolean up = false;
      while (!up && System.nanoTime() < deadline && process.isAlive()) {
        try (Socket socket = new Socket()) {
          socket.connect(new InetSocketAddress("127.0.0.1", port), 500);
          up = true;
        } catch (IOException notYet) {
          Thread.sleep(200);
        }
      }
      assertThat(up).as("the service came up on 127.0.0.1: " + Files.readString(dir.resolve("out.log"))).isTrue();
      String lan = lanAddress();
      assumeTrue(lan != null, "this machine has no non-loopback IPv4 address");
      assertThatThrownBy(() -> new Socket().connect(new InetSocketAddress(lan, port), 1000)).isInstanceOf(IOException.class);
    } finally {
      process.destroyForcibly();
      // Windows keeps out.log and the working directory locked until the child has really exited; @TempDir deletes them next.
      process.waitFor(30, TimeUnit.SECONDS);
    }
  }

  /**
   * F6: -Dspring.aot.processing=true skips the pre-start check (the build runs main() for AOT processing with no server). Setting it by
   * hand must not open a non-loopback bind: the post-start connector check still ends the process.
   */
  @Test
  @Timeout(90)
  void theAotProcessingSwitchDoesNotLetANonLoopbackBindThrough(@TempDir Path dir) throws Exception {
    int port = AppProcess.freePort();
    AppProcess.Result result =
        AppProcess.run(dir.resolve("out.log"), List.of("-Dspring.aot.processing=true"), List.of("--server.address=0.0.0.0", "--server.port=" + port, "--mission-status.project-root=" + dir), PORT_IN_USE_BOUND_SECONDS);
    assertThat(result.exited()).isTrue();
    assertThat(result.exitCode()).isNotZero();
    assertThat(result.output()).contains("0.0.0.0");
    // J11: the PRE-start check still refuses a non-blank address under the switch (only "unset" is skipped), so the server never starts
    assertThat(result.output()).contains("refused address 0.0.0.0").doesNotContain("the connector is bound");
    assertThatThrownBy(() -> new Socket().connect(new InetSocketAddress("127.0.0.1", port), 1000)).isInstanceOf(IOException.class);
  }
}
