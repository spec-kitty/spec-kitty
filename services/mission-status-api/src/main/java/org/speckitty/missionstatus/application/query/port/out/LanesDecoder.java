package org.speckitty.missionstatus.application.query.port.out;

import org.speckitty.missionstatus.domain.model.LanesResult;

/** The outbound decoding port for {@code lanes.json}: bytes in, a manifest, or the corrupt or legacy refusal out. No path, no file access. */
public interface LanesDecoder {

  LanesResult decode(byte[] bytes);
}
