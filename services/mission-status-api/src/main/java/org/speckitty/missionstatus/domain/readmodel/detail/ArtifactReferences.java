package org.speckitty.missionstatus.domain.readmodel.detail;

/**
 * The artifacts a Work Package detail points at.
 *
 * @param prompt the prompt file, or null when it is no eligible artifact
 * @param spec the Mission specification, or null
 */
public record ArtifactReferences(ArtifactReference prompt, ArtifactReference spec) {}
