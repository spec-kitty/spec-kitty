package org.speckitty.missionstatus.adapter.in.http.detail;

import java.util.ArrayList;
import java.util.List;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactContent;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactEntry;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactListing;

/**
 * The read-model records of the two artifact routes to the contract's bodies. Pure shaping: no decision, no ordering, no text work. The
 * contract's {@code encoding} member is the constant {@code utf-8}, written here. This route carries no {@code @ProjectionRow} pair.
 */
public final class ArtifactMapper {

  private ArtifactMapper() {}

  /** The listing body: the entries in the order the application gave them. */
  public static ArtifactListing listing(org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing listing) {
    List<ArtifactEntry> entries = new ArrayList<>();
    for (org.speckitty.missionstatus.domain.readmodel.detail.ArtifactEntry entry : listing.entries()) {
      entries.add(
          new ArtifactEntry()
              .path(entry.path())
              .kind(ArtifactEntry.KindEnum.fromValue(entry.kind().wire()))
              .sizeBytes(entry.sizeBytes())
              .modifiedAt(entry.modifiedAt())
              .readable(entry.readable()));
    }
    return new ArtifactListing().missionId(listing.missionId().value()).entries(entries).truncated(listing.truncated());
  }

  /** The content body. */
  public static ArtifactContent content(org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent content) {
    return new ArtifactContent()
        .path(content.path())
        .kind(ArtifactContent.KindEnum.fromValue(content.kind().wire()))
        .mediaType(content.mediaType())
        .encoding(ArtifactContent.EncodingEnum.UTF_8)
        .sizeBytes(content.sizeBytes())
        .redacted(content.redacted())
        .content(content.content());
  }
}
