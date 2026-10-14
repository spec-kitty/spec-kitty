package org.speckitty.missionstatus.application.query.port.out;

import org.speckitty.missionstatus.domain.model.FrontmatterResult;
import org.speckitty.missionstatus.domain.model.ReviewCycleMeta;

/**
 * The outbound decoding port of FR-006: bytes in, a typed domain record or a rejection out. It has no path and no file access, and it
 * keeps YAML (a library the application layer may not use) behind the adapter. The Work Package index calls it for every candidate
 * file; the review-cycle reader of the detail route calls the second method.
 */
public interface FrontmatterDecoder {

  /**
   * Decodes the bytes of a Work Package file as {@code FrontmatterManager.read} followed by {@code WPMetadata} validation does, or
   * rejects them. The bytes must be strict UTF-8; nothing is ever replaced.
   */
  FrontmatterResult decodeWorkPackage(byte[] bytes);

  /** The review time and reviewer of a review-cycle file; two nulls when the file does not parse (row M11, D-46). */
  ReviewCycleMeta decodeReviewCycle(byte[] bytes);
}
