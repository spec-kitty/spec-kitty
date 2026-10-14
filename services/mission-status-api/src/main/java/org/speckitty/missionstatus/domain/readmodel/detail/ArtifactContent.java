package org.speckitty.missionstatus.domain.readmodel.detail;

import java.util.Objects;

/**
 * The text of one artifact. The contract's {@code encoding} member is the constant {@code utf-8}: it is not a member here, the mapper
 * writes it.
 *
 * @param mediaType the media type decided from the path
 * @param redacted whether host paths or addresses in the text were replaced
 * @param content the text, after screening
 */
public record ArtifactContent(String path, ArtifactKind kind, String mediaType, long sizeBytes, boolean redacted, String content) {

  public ArtifactContent {
    Objects.requireNonNull(path, "path");
    Objects.requireNonNull(kind, "kind");
    Objects.requireNonNull(mediaType, "mediaType");
    Objects.requireNonNull(content, "content");
    if (sizeBytes < 0) {
      throw new IllegalArgumentException("size is not negative");
    }
  }
}
