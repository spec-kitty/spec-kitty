package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.speckitty.missionstatus.domain.model.LanesResult;

/** The adapter delegates to the lanes codec and opens no file. */
class JsonLanesDecoderTest {

  private final LanesDecoder decoder = new JsonLanesDecoder();

  @Test
  void aManifestACorruptDocumentAndTheLegacyShapeAreEachDecoded() {
    String current = "{\"version\":1,\"mission_slug\":\"a\",\"mission_branch\":\"b\",\"target_branch\":\"main\",\"computed_at\":\"t\",\"computed_from\":\"f\",\"lanes\":[]}";
    assertThat(decoder.decode(current.getBytes(StandardCharsets.UTF_8))).isInstanceOf(LanesResult.Manifest.class);
    assertThat(decoder.decode("nope".getBytes(StandardCharsets.UTF_8))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decoder.decode(current.replace("mission_slug", "feature_slug").getBytes(StandardCharsets.UTF_8))).isInstanceOf(LanesResult.Legacy.class);
  }
}
