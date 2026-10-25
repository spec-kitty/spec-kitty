package org.speckitty.missionstatus.domain.model;

/**
 * Why a physical line is malformed. {@link #UNUSABLE_ROW} is a well-formed JSON object that is no usable row (a missing required key,
 * an unknown lane or an unknown {@code kind}): a request route refuses it like any other reason, a stream skips it and stays open.
 */
public enum MalformedReason {
  NOT_JSON,
  NOT_OBJECT,
  NOT_UTF8,
  UNUSABLE_ROW
}
