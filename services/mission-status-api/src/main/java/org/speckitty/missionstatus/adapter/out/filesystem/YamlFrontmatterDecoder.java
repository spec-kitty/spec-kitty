package org.speckitty.missionstatus.adapter.out.filesystem;

import org.speckitty.missionstatus.adapter.out.filesystem.codec.ReviewCycleCodec;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.WpFrontmatterCodec;
import org.speckitty.missionstatus.application.query.port.out.FrontmatterDecoder;
import org.speckitty.missionstatus.domain.model.FrontmatterResult;
import org.speckitty.missionstatus.domain.model.ReviewCycleMeta;

/**
 * The {@link FrontmatterDecoder} of the file-system adapter (FR-006, D-57). It sits directly in this package, where rule 4 admits an
 * {@code application.query.port.out} interface, and does nothing but delegate to the pure codecs: it opens no file and holds no state.
 */
public final class YamlFrontmatterDecoder implements FrontmatterDecoder {

  @Override
  public FrontmatterResult decodeWorkPackage(byte[] bytes) {
    return WpFrontmatterCodec.decode(bytes);
  }

  @Override
  public ReviewCycleMeta decodeReviewCycle(byte[] bytes) {
    return ReviewCycleCodec.decode(bytes);
  }
}
