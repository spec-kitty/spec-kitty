package org.speckitty.missionstatus.config;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.ServerSocket;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;

/** Launches the application in a child JVM (the guards end the process with System.exit, which a test cannot take in-process). */
final class AppProcess {

  record Result(boolean exited, int exitCode, String output, long millis) {}

  private AppProcess() {}

  static int freePort() {
    try (ServerSocket socket = new ServerSocket(0)) {
      return socket.getLocalPort();
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  static Process launch(Path log, List<String> jvmArgs, List<String> appArgs) {
    return launch(log, null, java.util.Map.of(), jvmArgs, appArgs);
  }

  /** As {@link #launch(Path, List, List)}, in the working directory {@code cwd} (null: this process's) and with extra environment variables. */
  static Process launch(Path log, Path cwd, java.util.Map<String, String> environment, List<String> jvmArgs, List<String> appArgs) {
    List<String> command = new ArrayList<>();
    command.add(Path.of(System.getProperty("java.home"), "bin", "java").toString());
    command.addAll(jvmArgs);
    command.add("-cp");
    command.add(System.getProperty("java.class.path"));
    command.add("org.speckitty.missionstatus.config.MissionStatusApplication");
    command.addAll(appArgs);
    try {
      ProcessBuilder builder = new ProcessBuilder(command).redirectErrorStream(true).redirectOutput(log.toFile());
      if (cwd != null) {
        builder.directory(cwd.toFile());
      }
      builder.environment().putAll(environment);
      return builder.start();
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** Runs to completion or until the deadline, then reports (and kills a process that is still running). */
  static Result run(Path log, List<String> jvmArgs, List<String> appArgs, long deadlineSeconds) throws InterruptedException {
    long start = System.nanoTime();
    Process process = launch(log, jvmArgs, appArgs);
    boolean exited = process.waitFor(deadlineSeconds, TimeUnit.SECONDS);
    long millis = (System.nanoTime() - start) / 1_000_000;
    if (!exited) {
      process.destroyForcibly();
      process.waitFor(30, TimeUnit.SECONDS);
    }
    try {
      return new Result(exited, exited ? process.exitValue() : -1, Files.readString(log), millis);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }
}
