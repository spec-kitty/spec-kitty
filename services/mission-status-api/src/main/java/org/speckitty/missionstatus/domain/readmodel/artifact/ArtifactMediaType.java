package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Map;

/** The media type of an artifact, decided from the extension of its file name by a fixed table and never from its content. */
public final class ArtifactMediaType {

  /** The media type of any extension the table does not name. */
  public static final String DEFAULT = "text/plain";

  private static final Map<String, String> BY_EXTENSION =
      Map.of(
          "md", "text/markdown",
          "json", "application/json",
          "yaml", "application/yaml",
          "yml", "application/yaml",
          "jsonl", "application/x-ndjson",
          "csv", "text/csv");

  private ArtifactMediaType() {}

  /** The media type of {@code path}: the text after the last dot of the file name, matched with its case, else {@link #DEFAULT}. */
  public static String of(String path) {
    String name = path.substring(path.lastIndexOf('/') + 1);
    int dot = name.lastIndexOf('.');
    String extension = dot < 0 ? "" : name.substring(dot + 1);
    return BY_EXTENSION.getOrDefault(extension, DEFAULT);
  }
}
