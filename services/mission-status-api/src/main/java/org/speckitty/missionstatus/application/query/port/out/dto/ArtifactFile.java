package org.speckitty.missionstatus.application.query.port.out.dto;

/** The size in bytes and the modification time (whole seconds since the epoch, floored) of one file. */
public record ArtifactFile(long sizeBytes, long modifiedEpochSecond) {}
