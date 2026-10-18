package org.speckitty.missionstatus.adapter.in.http;

import java.util.List;

/**
 * The bodies of the two artifact routes as the contract writes them ({@code ArtifactListing}, {@code ArtifactEntry},
 * {@code ArtifactContent}). Hand-written rather than generated: the generated model types {@code sizeBytes} as a 32-bit
 * {@code Integer}, and a listing reports the size of any file, including one beyond 2 GiB. They live beside {@link ProblemBody}, not in
 * the hand-mode {@code dto} package, which stays empty while the service runs in generated mode.
 */
public final class ArtifactBodies {

  private ArtifactBodies() {}

  /** {@code ArtifactEntry}. */
  public record Entry(String path, String kind, long sizeBytes, String modifiedAt, boolean readable) {}

  /** {@code ArtifactListing}. */
  public record Listing(String missionId, List<Entry> entries, boolean truncated) {

    public Listing {
      entries = List.copyOf(entries);
    }
  }

  /** {@code ArtifactContent}. */
  public record Content(String path, String kind, String mediaType, String encoding, long sizeBytes, boolean redacted, String content) {}
}
