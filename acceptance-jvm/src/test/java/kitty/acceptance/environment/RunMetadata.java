package kitty.acceptance.environment;

import java.io.IOException;
import java.io.OutputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Properties;

/**
 * Stamps a pass's Allure results folder with the build that produced it (FR-009).
 *
 * <p>Writes {@code environment.properties} (always) and {@code executor.json} (only inside a GitHub
 * Actions run) into the directory named by the {@code allure.results.directory} system property, which
 * {@code build.gradle} points at {@code build/acceptance/<pass>/allure-results}. Both file names are the
 * ones the Allure report reads. Black-box: nothing here imports or touches the Python project state.
 */
public final class RunMetadata {

    static final String RESULTS_DIRECTORY_PROPERTY = "allure.results.directory";
    static final String PASS_PROPERTY = "acceptance.pass";
    private static final Duration GIT_TIMEOUT = Duration.ofSeconds(30);

    private RunMetadata() {
    }

    /**
     * Writes both metadata files for the given CLI. Idempotent: a second call rewrites identical content.
     *
     * @throws IllegalStateException when {@code allure.results.directory} is not set
     */
    public static void write(CliUnderTest cli) {
        String directory = System.getProperty(RESULTS_DIRECTORY_PROPERTY);
        if (directory == null || directory.isBlank()) {
            throw new IllegalStateException("System property " + RESULTS_DIRECTORY_PROPERTY
                    + " is not set; run the scenarios through the acceptance-jvm Gradle build");
        }
        writeTo(Path.of(directory), cli.version(), System.getenv());
    }

    /** Writes the files into {@code resultsDir} from explicit inputs (the seam for direct tests). */
    static void writeTo(Path resultsDir, String cliVersion, Map<String, String> env) {
        try {
            Files.createDirectories(resultsDir);
            writeEnvironment(resultsDir.resolve("environment.properties"), cliVersion, env);
            if (env.get("GITHUB_RUN_ID") != null) {
                Files.writeString(resultsDir.resolve("executor.json"), executorJson(env), StandardCharsets.UTF_8);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to write run metadata into " + resultsDir, e);
        }
    }

    private static void writeEnvironment(Path file, String cliVersion, Map<String, String> env)
            throws IOException {
        Properties properties = new Properties();
        properties.setProperty("cli.version", cliVersion);
        properties.setProperty("commit.sha", commitSha(env));
        properties.setProperty("os.name", System.getProperty("os.name", "unknown"));
        properties.setProperty("java.version", System.getProperty("java.version", "unknown"));
        properties.setProperty(PASS_PROPERTY, System.getProperty(PASS_PROPERTY, "adhoc"));
        try (OutputStream out = Files.newOutputStream(file)) {
            properties.store(out, "spec-kitty acceptance run");
        }
    }

    private static String commitSha(Map<String, String> env) {
        String fromCi = env.get("GITHUB_SHA");
        if (fromCi != null && !fromCi.isBlank()) {
            return fromCi;
        }
        ProcessBuilder builder = new ProcessBuilder("git", "rev-parse", "HEAD");
        builder.directory(CliUnderTest.findRepoRoot().toFile());
        ProcessRunner.Outcome outcome = ProcessRunner.run(builder, GIT_TIMEOUT, "git rev-parse HEAD");
        return outcome.exitCode() == 0 ? outcome.output().strip() : "unknown";
    }

    private static String executorJson(Map<String, String> env) {
        String runId = env.get("GITHUB_RUN_ID");
        String runNumber = env.getOrDefault("GITHUB_RUN_NUMBER", "");
        Map<String, String> fields = new LinkedHashMap<>();
        fields.put("name", "GitHub Actions");
        fields.put("type", "github");
        fields.put("buildName", "acceptance-" + System.getProperty(PASS_PROPERTY, "adhoc") + " #" + runNumber);
        fields.put("buildOrder", runNumber);
        fields.put("buildUrl", env.getOrDefault("GITHUB_SERVER_URL", "https://github.com") + "/"
                + env.getOrDefault("GITHUB_REPOSITORY", "") + "/actions/runs/" + runId);
        StringBuilder json = new StringBuilder("{\n");
        int remaining = fields.size();
        for (Map.Entry<String, String> field : fields.entrySet()) {
            boolean numeric = "buildOrder".equals(field.getKey()) && field.getValue().matches("\\d+");
            json.append("  \"").append(field.getKey()).append("\": ")
                    .append(numeric ? field.getValue() : quote(field.getValue()))
                    .append(--remaining > 0 ? ",\n" : "\n");
        }
        return json.append("}\n").toString();
    }

    /** Minimal JSON string escaping (quotes, backslashes and control characters). */
    static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (char c : value.toCharArray()) {
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        return out.append('"').toString();
    }
}
