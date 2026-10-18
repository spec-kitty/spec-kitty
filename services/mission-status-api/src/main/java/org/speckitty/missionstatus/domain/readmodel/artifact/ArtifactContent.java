package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Objects;

/** The text content of one artifact ({@code ArtifactContent}); {@code encoding} is always {@code utf-8}. */
public record ArtifactContent(String path, ArtifactKind kind, String mediaType, long sizeBytes, boolean redacted, String content) {

  /** The one encoding of {@link #content}. */
  public static final String ENCODING = "utf-8";

  public ArtifactContent {
    Objects.requireNonNull(path, "path");
    Objects.requireNonNull(kind, "kind");
    Objects.requireNonNull(mediaType, "mediaType");
    Objects.requireNonNull(content, "content");
  }
}
