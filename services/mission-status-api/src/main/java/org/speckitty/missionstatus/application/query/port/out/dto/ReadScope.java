package org.speckitty.missionstatus.application.query.port.out.dto;

/**
 * Why a read is made, which decides its class in the read fence (FR-011, D-27). {@code AUTHORED} is for the authored files and the
 * ledger side; {@code ARTIFACT} is for the two artifact routes. Mission #5533 adds exactly one value, {@code GOVERNANCE}.
 */
public enum ReadScope {
  AUTHORED,
  ARTIFACT
}
