package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.domain.model.FrontmatterResult;
import org.speckitty.missionstatus.domain.model.ReviewCycleMeta;

/** The adapter does nothing but delegate to the codec: it parses what the codec parses and rejects what it rejects (D-57). */
class YamlFrontmatterDecoderTest {

  private final FrontmatterDecoder decoder = new YamlFrontmatterDecoder();

  @Test
  void aWorkPackageFileIsDecodedByTheWorkPackageCodec() {
    FrontmatterResult result = decoder.decodeWorkPackage("---\nwork_package_id: WP01\ntitle: T\n---\nbody".getBytes(StandardCharsets.UTF_8));
    assertThat(result).isInstanceOf(FrontmatterResult.Parsed.class);
    assertThat(((FrontmatterResult.Parsed) result).metadata().title()).isEqualTo("T");
    assertThat(decoder.decodeWorkPackage("plain".getBytes(StandardCharsets.UTF_8))).isEqualTo(new FrontmatterResult.Rejected(FrontmatterResult.RejectionClass.NO_FRONTMATTER));
  }

  @Test
  void aReviewCycleFileIsDecodedByTheReviewCycleCodec() {
    String file = "---\ncycle_number: 1\nwp_id: WP01\nmission_slug: m\nreviewer_agent: r\nreviewed_at: '2026-09-01T10:00:00Z'\n---\n";
    assertThat(decoder.decodeReviewCycle(file.getBytes(StandardCharsets.UTF_8))).isEqualTo(new ReviewCycleMeta("2026-09-01T10:00:00Z", "r"));
    assertThat(decoder.decodeReviewCycle(new byte[0])).isEqualTo(ReviewCycleMeta.UNPARSED);
  }
}
