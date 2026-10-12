package kitty.acceptance.driver;

import java.nio.file.Path;
import java.util.List;

/**
 * Black-box seam between the acceptance steps and the {@code spec-kitty} CLI under test.
 *
 * <p>Steps depend ONLY on this port (mission constraint C-001): they never import the Python
 * package under test and never reach into any internal harness class. The sole production
 * implementation is {@link CliProcessDriver}, which launches the wheel-installed entry point
 * (constraint C-002) inside a fully isolated environment (NFR-002).
 */
public interface SpecKittyDriver {

    /**
     * Run the CLI with {@code args} using {@code cwd} as the working directory.
     *
     * @param args the full token list, e.g. {@code ["spec-kitty", "init", "--non-interactive"]}; a
     *             leading {@code "spec-kitty"} token is resolved to the entry point under test.
     * @param cwd  the working directory the process is launched in; must already exist.
     * @return the captured {@link CliResult} (exit code, drained stdout/stderr,
     *         the real working-tree path).
     */
    CliResult run(List<String> args, Path cwd);
}
