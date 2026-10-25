package org.speckitty.missionstatus.adapter.in.http.contract;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Stream;
import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.junit.jupiter.api.io.TempDir;

/**
 * AC-11c, generated mode (WP10 T056 step 2; DD-63, DD-66, DD-67): a nested build of a COPY of the service sources and a COPY of the
 * contract compiles when the copy is unmutated, and FAILS with a missing-symbol error when one property of MissionOverview is renamed
 * or one required property of Project is removed in the contract copy. The hand-written {@code ContractDriftProbe} holds one compile
 * time reference per mutation target. Runs in the kit source set (name ends in NestedBuildTest) through {@code ./gradlew kitTest}.
 */
class ContractDriftNestedBuildTest {

  /** The library modules settings.gradle.kts includes (#6117 decision 12, #6192); a nested build needs each one's directory. */
  private static final List<String> LIBRARY_MODULES = List.of("domain-model", "event-log");

  private static final String CANNOT_FIND = "cannot find symbol";

  @Test
  @Timeout(1800)
  void theBuildIsInGeneratedModeAndTheProbeLivesInTheHttpPackage() throws IOException {
    Path project = Path.of(requiredProperty("kit.projectDir"));
    String script = Files.readString(project.resolve("build.gradle.kts"), StandardCharsets.UTF_8);
    assertThat(script).as("generated mode").contains("generatorName.set(\"spring\")").contains("org.speckitty.missionstatus.adapter.in.http.api").contains("org.speckitty.missionstatus.adapter.in.http.model");
    Path probe = project.resolve("src/main/java/org/speckitty/missionstatus/adapter/in/http/ContractDriftProbe.java");
    assertThat(probe).as("the probe was moved, not dropped").isRegularFile();
    String text = Files.readString(probe, StandardCharsets.UTF_8);
    assertThat(text).contains("new MissionOverview().blockedCount(1)").contains("new Project().currentBranch(\"main\")");
  }

  @Test
  @Timeout(1800)
  void renamingAMissionOverviewPropertyOrRemovingARequiredProjectPropertyBreaksTheNestedBuild(@TempDir Path workDir) throws IOException {
    Path original = Path.of(requiredProperty("kit.projectDir"));
    Path copy = workDir.resolve("service");
    copyService(original, copy);

    // positive control: the unmutated copy of the contract compiles
    Path control = workDir.resolve("contract-control");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), control);
    BuildResult built = runner(copy, control).build();
    assertThat(built.getOutput()).doesNotContain(CANNOT_FIND);

    // mutation 1: rename blockedCount (property and required entry) in the MissionOverview source schema
    Path renamed = workDir.resolve("contract-rename");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), renamed);
    Path head = renamed.resolve("mission-status/schemas/MissionHead.yaml");
    String before = Files.readString(head, StandardCharsets.UTF_8);
    String after = before.replace("blockedCount", "blockedTotal");
    assertThat(after).as("the mutation changed the schema").isNotEqualTo(before);
    Files.writeString(head, after, StandardCharsets.UTF_8);
    BuildResult renamedResult = runner(copy, renamed).buildAndFail();
    assertThat(renamedResult.getOutput()).contains(CANNOT_FIND).contains("blockedCount");

    // mutation 2: remove the required property currentBranch from Project
    Path removed = workDir.resolve("contract-remove");
    copyTree(Path.of(requiredProperty("kit.contractRoot")), removed);
    Path projectSchema = removed.resolve("mission-status/schemas/Project.yaml");
    String projectBefore = Files.readString(projectSchema, StandardCharsets.UTF_8);
    String projectAfter = dropCurrentBranch(projectBefore);
    assertThat(projectAfter).as("the mutation changed the schema").isNotEqualTo(projectBefore).doesNotContain("currentBranch:");
    Files.writeString(projectSchema, projectAfter, StandardCharsets.UTF_8);
    BuildResult removedResult = runner(copy, removed).buildAndFail();
    assertThat(removedResult.getOutput()).contains(CANNOT_FIND).contains("currentBranch");
  }

  /** Removes currentBranch from the required list and deletes its property block. */
  static String dropCurrentBranch(String yaml) {
    String withoutRequired = yaml.replace("currentBranch, ", "");
    StringBuilder out = new StringBuilder();
    boolean skipping = false;
    for (String line : withoutRequired.split("\n", -1)) {
      if (line.startsWith("  currentBranch:")) {
        skipping = true;
        continue;
      }
      if (skipping && (line.startsWith("    ") || line.isBlank())) {
        continue;
      }
      skipping = false;
      out.append(line).append('\n');
    }
    return out.substring(0, out.length() - 1);
  }

  private static GradleRunner runner(Path copy, Path contractRoot) {
    return GradleRunner.create()
        .withProjectDir(copy.toFile())
        .withTestKitDir(Path.of(requiredProperty("kit.gradleUserHome")).toFile())
        .withArguments(List.of("--offline", "-PcontractRoot=" + contractRoot, "compileJava"));
  }

  private static void copyService(Path original, Path copy) throws IOException {
    Files.createDirectories(copy);
    for (String name : List.of("build.gradle.kts", "settings.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat")) {
      Files.copy(original.resolve(name), copy.resolve(name));
    }
    copyTree(original.resolve("gradle"), copy.resolve("gradle"));
    copyTree(original.resolve("src/main/java"), copy.resolve("src/main/java"));
    // settings.gradle.kts includes the library modules (#6192), and the service sources compile against them.
    for (String library : LIBRARY_MODULES) {
      Files.createDirectories(copy.resolve(library));
      Files.copy(original.resolve(library).resolve("build.gradle.kts"), copy.resolve(library).resolve("build.gradle.kts"));
      copyTree(original.resolve(library).resolve("src/main/java"), copy.resolve(library).resolve("src/main/java"));
    }
  }

  private static void copyTree(Path from, Path to) throws IOException {
    try (Stream<Path> paths = Files.walk(from)) {
      for (Path path : (Iterable<Path>) paths::iterator) {
        Path target = to.resolve(from.relativize(path).toString());
        if (Files.isDirectory(path)) {
          Files.createDirectories(target);
        } else {
          Files.copy(path, target);
        }
      }
    } catch (UncheckedIOException e) {
      throw e.getCause();
    }
  }

  private static String requiredProperty(String name) {
    String value = System.getProperty(name);
    assertThat(value).as("system property %s (set by the kitTest task)", name).isNotBlank();
    return value;
  }
}
