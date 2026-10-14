package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * What decoding the bytes of a {@code lanes.json} gave. Both {@link Corrupt} and {@link Legacy} are a refusal of the Work Package
 * detail (500 {@code source_unreadable}, row W3); they are two results so that a caller and a test can tell the legacy shape of ledger
 * entry SK-351 from a document that is simply not a manifest.
 */
public sealed interface LanesResult {

  /** The document is a current-shape manifest. */
  record Manifest(LanesManifest manifest) implements LanesResult {
    public Manifest {
      Objects.requireNonNull(manifest, "manifest");
    }
  }

  /** The bytes are not a manifest the oracle's {@code read_lanes_json} reads. */
  record Corrupt() implements LanesResult {}

  /** The legacy shape: the pre-identity slug key and no {@code mission_slug} (SK-351). */
  record Legacy() implements LanesResult {}
}
