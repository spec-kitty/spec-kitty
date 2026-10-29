package org.speckitty.missionstatus.spike.lockinterop;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/** The Python side of the spike: {@code scripts/ci/lock_interop_peer.py}, run with the interpreter of the synced repository venv. */
final class PythonPeer {

  /** The interpreter; the spike runs only when it is set. */
  static final String PYTHON_ENV = "SPEC_KITTY_LOCK_INTEROP_PYTHON";

  private static final String SCRIPT = "scripts/ci/lock_interop_peer.py";
  private static final long TIMEOUT_S = 300;
  private static final JsonMapper JSON = JsonMapper.builder().build();

  private final String python;
  private final Path script;

  private PythonPeer(String python, Path script) {
    this.python = python;
    this.script = script;
  }

  /** The peer of this checkout: the script is found by walking up from the working directory. */
  static PythonPeer fromEnvironment() {
    String python = System.getenv(PYTHON_ENV);
    Path dir = Path.of("").toAbsolutePath();
    while (dir != null && !Files.isRegularFile(dir.resolve(SCRIPT))) {
      dir = dir.getParent();
    }
    if (python == null || dir == null) {
      throw new IllegalStateException(PYTHON_ENV + " is unset or " + SCRIPT + " was not found above the working directory");
    }
    return new PythonPeer(python, dir.resolve(SCRIPT));
  }

  /** Starts the peer; its stderr goes to the test log. */
  Process start(String... args) throws IOException {
    List<String> command = new ArrayList<>(List.of(python, script.toString()));
    command.addAll(List.of(args));
    return new ProcessBuilder(command).redirectError(ProcessBuilder.Redirect.INHERIT).start();
  }

  /** Waits for a started peer and returns the raw stdout; a non-zero exit is a harness error. */
  static String finish(Process process) throws IOException, InterruptedException {
    String out = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
    if (!process.waitFor(TIMEOUT_S, TimeUnit.SECONDS)) {
      process.destroyForcibly();
      throw new IOException("python peer timed out");
    }
    if (process.exitValue() != 0) {
      throw new IOException("python peer exited " + process.exitValue() + ": " + out);
    }
    return out;
  }

  static JsonNode json(String out) {
    return JSON.readTree(out);
  }

  JsonNode run(String... args) throws IOException, InterruptedException {
    return json(finish(start(args)));
  }

  String runRaw(String... args) throws IOException, InterruptedException {
    return finish(start(args));
  }
}
