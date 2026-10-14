package org.speckitty.missionstatus.application.query.port.in.dto;

import java.util.List;
import java.util.Objects;

/**
 * The {@code path} of an artifact request as the transport saw it, without any transport type: every value of the parameter in the order
 * it was given ({@link Values}), or the fact that a percent sequence was not valid UTF-8 ({@link Undecodable}). The port, not the adapter,
 * decides what an absent, repeated or malformed path is (a typed {@code invalid_artifact_path} refusal).
 */
public sealed interface ArtifactPathInput {

  /** The decoded values of the {@code path} parameter: none when it is absent, several when it is repeated. */
  record Values(List<String> values) implements ArtifactPathInput {
    public Values {
      Objects.requireNonNull(values, "values");
      values = List.copyOf(values);
    }
  }

  /** A percent-encoded value that is not valid UTF-8: never replaced by U+FFFD, never decoded in part. */
  record Undecodable() implements ArtifactPathInput {}
}
