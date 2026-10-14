package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactContent;
import org.speckitty.missionstatus.adapter.in.http.model.ArtifactListing;
import org.speckitty.missionstatus.config.MissionStatusApplicationJson;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactEntry;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactKind;

/** The read-model records of the two artifact routes to the contract's bodies, as the canonical writer serialises them. */
class ArtifactMapperTest {

  private static final MissionId ID = MissionId.parse("00000000000000000000000001").orElseThrow();

  private static String json(Object body) {
    return MissionStatusApplicationJson.mapper().writeValueAsString(body);
  }

  @Test
  void aListingKeepsEveryMemberItsOrderAndTheTruncatedFlag() {
    var listing =
        new org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing(
            ID,
            List.of(
                new ArtifactEntry("spec.md", ArtifactKind.SPEC, 16, "2026-09-21T14:13:20Z", true),
                new ArtifactEntry("tasks/WP01-x/review-cycle-1.md", ArtifactKind.REVIEW_CYCLE, 0, "2026-09-21T14:13:21Z", false)),
            true);

    ArtifactListing body = ArtifactMapper.listing(listing);

    assertThat(json(body))
        .isEqualTo(
            "{\"entries\":[{\"kind\":\"spec\",\"modifiedAt\":\"2026-09-21T14:13:20Z\",\"path\":\"spec.md\",\"readable\":true,\"sizeBytes\":16},"
                + "{\"kind\":\"review_cycle\",\"modifiedAt\":\"2026-09-21T14:13:21Z\",\"path\":\"tasks/WP01-x/review-cycle-1.md\",\"readable\":false,\"sizeBytes\":0}],"
                + "\"missionId\":\"00000000000000000000000001\",\"truncated\":true}");
  }

  @Test
  void anEmptyListingIsAnEmptyArrayNeverNull() {
    ArtifactListing body = ArtifactMapper.listing(new org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing(ID, List.of(), false));

    assertThat(json(body)).isEqualTo("{\"entries\":[],\"missionId\":\"00000000000000000000000001\",\"truncated\":false}");
  }

  @ParameterizedTest
  @EnumSource(ArtifactKind.class)
  void everyKindIsWrittenAsItsContractWordInBothBodies(ArtifactKind kind) {
    ArtifactListing listing =
        ArtifactMapper.listing(new org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing(ID, List.of(new ArtifactEntry("x", kind, 1, "2026-01-01T00:00:00Z", true)), false));
    ArtifactContent content = ArtifactMapper.content(new org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent("x", kind, "text/plain", 1, false, "x"));

    assertThat(json(listing)).contains("\"kind\":\"" + kind.wire() + "\"");
    assertThat(json(content)).contains("\"kind\":\"" + kind.wire() + "\"");
  }

  @Test
  void aContentBodyCarriesTheConstantEncodingTheByteSizeAndTheRedactedFlag() {
    ArtifactContent body =
        ArtifactMapper.content(new org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent("café.md", ArtifactKind.OTHER, "text/markdown", 6, true, "café\n"));

    assertThat(json(body))
        .isEqualTo("{\"content\":\"café\\n\",\"encoding\":\"utf-8\",\"kind\":\"other\",\"mediaType\":\"text/markdown\",\"path\":\"café.md\",\"redacted\":true,\"sizeBytes\":6}");
  }

  @Test
  void aSizeBeyondThirtyTwoBitsIsServedExactlyNeverClamped() {
    var entry = new ArtifactEntry("big.bin", ArtifactKind.OTHER, 5_000_000_000L, "2026-01-01T00:00:00Z", false);

    ArtifactListing body = ArtifactMapper.listing(new org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing(ID, List.of(entry), false));

    assertThat(json(body)).contains("\"sizeBytes\":5000000000");
    assertThat(body.getEntries().getFirst().getSizeBytes()).isEqualTo(5_000_000_000L);
  }

  @Test
  void aContentSizeBeyondThirtyTwoBitsIsServedExactlyToo() {
    ArtifactContent body =
        ArtifactMapper.content(new org.speckitty.missionstatus.domain.readmodel.detail.ArtifactContent("a.md", ArtifactKind.OTHER, "text/markdown", 5_000_000_000L, false, ""));

    assertThat(json(body)).contains("\"sizeBytes\":5000000000");
  }
}
