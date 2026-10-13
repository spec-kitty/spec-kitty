package org.speckitty.missionstatus.domain.readmodel.overview;

/** The seven members of the contract's {@code Project}; {@code schemaVersion} is the integer the CLI's coercion gives. */
public record ProjectHeader(
    String name, int missionCount, String specKittyVersion, Integer schemaVersion, Health health, String currentBranch, String lastActivityAt) {}
