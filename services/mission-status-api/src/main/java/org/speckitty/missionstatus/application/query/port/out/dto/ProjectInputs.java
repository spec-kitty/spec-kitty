package org.speckitty.missionstatus.application.query.port.out.dto;

/**
 * What the project header needs from the project files: the configuration slug, the metadata's version and schema version (null when
 * absent) and the branch name (null when there is none to serve).
 */
public record ProjectInputs(String name, String specKittyVersion, Integer schemaVersion, String branchName) {}
