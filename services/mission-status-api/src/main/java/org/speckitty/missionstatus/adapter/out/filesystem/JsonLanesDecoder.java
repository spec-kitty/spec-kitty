package org.speckitty.missionstatus.adapter.out.filesystem;

import org.speckitty.missionstatus.adapter.out.filesystem.codec.LanesCodec;
import org.speckitty.missionstatus.application.query.port.out.LanesDecoder;
import org.speckitty.missionstatus.domain.model.LanesResult;

/** The {@link LanesDecoder} of the file-system adapter: a delegation to the pure {@link LanesCodec}, opening no file (FR-006, D-57). */
public final class JsonLanesDecoder implements LanesDecoder {

  @Override
  public LanesResult decode(byte[] bytes) {
    return LanesCodec.decode(bytes);
  }
}
