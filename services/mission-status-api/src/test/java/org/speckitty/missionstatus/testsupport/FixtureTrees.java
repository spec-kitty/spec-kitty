package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;

/**
 * Both directions between the source-neutral {@link FixtureSpec} and a project tree on disk: {@link #write} realises a spec as a
 * tree for the filesystem source, {@link #specOf} reads a committed conformance fixture as a spec so that the AC-2a shells can drive
 * any source with it.
 */
final class FixtureTrees {

  private FixtureTrees() {}

  /** Writes a spec the way a live project holds it: configuration, metadata, a HEAD (when a branch is named) and one directory per Mission. */
  static void write(FixtureSpec spec, Path root) {
    try {
      FixtureSpec.Project project = spec.project();
      put(root.resolve(".kittify/config.yaml"), ("project:\n  slug: " + project.name() + "\n").getBytes(StandardCharsets.UTF_8));
      if (project.specKittyVersion() != null || project.schemaVersion() != null) {
        StringBuilder metadata = new StringBuilder("spec_kitty:\n");
        if (project.specKittyVersion() != null) {
          metadata.append("  version: ").append(project.specKittyVersion()).append('\n');
        }
        if (project.schemaVersion() != null) {
          metadata.append("  schema_version: ").append(project.schemaVersion()).append('\n');
        }
        put(root.resolve(".kittify/metadata.yaml"), metadata.toString().getBytes(StandardCharsets.UTF_8));
      }
      if (project.branchName() != null) {
        put(root.resolve(".git/HEAD"), ("ref: refs/heads/" + project.branchName() + "\n").getBytes(StandardCharsets.UTF_8));
      }
      Files.createDirectories(root.resolve("kitty-specs"));
      for (FixtureSpec.Mission mission : spec.missions()) {
        Path dir = root.resolve("kitty-specs").resolve(mission.name());
        put(dir.resolve("meta.json"), mission.metaJson());
        if (mission.ledger() != null) {
          put(dir.resolve("status.events.jsonl"), mission.ledger());
        }
        if (mission.lanesJson() != null) {
          put(dir.resolve("lanes.json"), mission.lanesJson().getBytes(StandardCharsets.UTF_8));
        }
      }
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  private static void put(Path file, byte[] bytes) throws IOException {
    Files.createDirectories(file.getParent());
    Files.write(file, bytes);
  }

  /**
   * A committed conformance fixture as a spec: the project inputs from {@code .kittify}, the branch from {@code HEAD}, and every
   * Mission directory that holds a {@code meta.json}. A tree that needs more than that (a coordination worktree, a husk, a symbolic
   * link, a pointer file) is not source-neutral and is refused.
   */
  static FixtureSpec specOf(ConformanceTree.TreeFixture fixture) {
    try {
      Path dir = fixture.dir();
      for (String name : List.of("coord-worktree", "husk-worktree", "SYMLINK_PLAN", "GITDIR_POINTER")) {
        if (Files.exists(dir.resolve(name))) {
          throw new IllegalArgumentException(fixture.key() + " is not source-neutral: it holds " + name);
        }
      }
      String config = Files.readString(dir.resolve(".kittify/config.yaml"), StandardCharsets.UTF_8);
      Path metadataFile = dir.resolve(".kittify/metadata.yaml");
      String metadata = Files.isRegularFile(metadataFile) ? Files.readString(metadataFile, StandardCharsets.UTF_8) : null;
      Path headFile = dir.resolve("HEAD");
      String branch = null;
      if (Files.isRegularFile(headFile)) {
        String head = Files.readString(headFile, StandardCharsets.UTF_8).strip();
        branch = head.startsWith("ref: refs/heads/") ? head.substring("ref: refs/heads/".length()) : null;
      }
      FixtureSpec.Project project =
          new FixtureSpec.Project(scalar(config, "slug"), metadata == null ? null : scalar(metadata, "version"), metadata == null ? null : integer(scalar(metadata, "schema_version")), branch);
      List<FixtureSpec.Mission> missions = new ArrayList<>();
      Path specs = dir.resolve("kitty-specs");
      if (Files.isDirectory(specs)) {
        try (Stream<Path> entries = Files.list(specs)) {
          for (Path mission : entries.filter(Files::isDirectory).sorted().toList()) {
            Path meta = mission.resolve("meta.json");
            if (!Files.isRegularFile(meta)) {
              continue;
            }
            Path ledger = mission.resolve("status.events.jsonl");
            Path lanes = mission.resolve("lanes.json");
            missions.add(
                new FixtureSpec.Mission(
                    mission.getFileName().toString(),
                    Files.readAllBytes(meta),
                    Files.isRegularFile(ledger) ? Files.readAllBytes(ledger) : null,
                    Files.isRegularFile(lanes) ? Files.readString(lanes, StandardCharsets.UTF_8) : null,
                    null));
          }
        }
      }
      return new FixtureSpec(project, missions);
    } catch (IOException failure) {
      throw new UncheckedIOException(failure);
    }
  }

  /** The value of the first {@code key:} line of a flat YAML text (the fixtures hold two-level scalars only). */
  private static String scalar(String yaml, String key) {
    for (String line : yaml.split("\n")) {
      String trimmed = line.strip();
      if (trimmed.startsWith(key + ":")) {
        return trimmed.substring(key.length() + 1).strip();
      }
    }
    return null;
  }

  private static Integer integer(String text) {
    return text == null ? null : Integer.valueOf(text);
  }
}
