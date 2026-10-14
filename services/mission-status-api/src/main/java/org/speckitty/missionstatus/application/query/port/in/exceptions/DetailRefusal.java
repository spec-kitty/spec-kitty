package org.speckitty.missionstatus.application.query.port.in.exceptions;

import java.util.Objects;

/**
 * A refusal of one of the detail operations. It carries its {@link Kind} and nothing else: no text beyond the kind's wire word, no HTTP
 * status, no path and no cause, so no adapter can leak a location through it. The mapping of a kind to a status exists once, in the HTTP
 * adapter.
 */
public final class DetailRefusal extends RuntimeException {

  private static final long serialVersionUID = 1L;

  /** The kinds of refusal; the wire word is the contract's code. */
  public enum Kind {
    NOT_FOUND("not_found"),
    INVALID_ARTIFACT_PATH("invalid_artifact_path"),
    ARTIFACT_TOO_LARGE("artifact_too_large"),
    ARTIFACT_NOT_TEXT("artifact_not_text"),
    ARTIFACT_SECRET("artifact_secret"),
    ARTIFACT_UNREADABLE("artifact_unreadable"),
    ARTIFACT_LISTING_UNREADABLE("artifact_listing_unreadable"),
    SOURCE_UNREADABLE("source_unreadable");

    private final String wire;

    Kind(String wire) {
      this.wire = wire;
    }

    public String wire() {
      return wire;
    }
  }

  private final Kind kind;

  public DetailRefusal(Kind kind) {
    super(Objects.requireNonNull(kind, "kind").wire(), null, false, false);
    this.kind = kind;
  }

  public Kind kind() {
    return kind;
  }

  public static DetailRefusal notFound() {
    return new DetailRefusal(Kind.NOT_FOUND);
  }

  public static DetailRefusal invalidArtifactPath() {
    return new DetailRefusal(Kind.INVALID_ARTIFACT_PATH);
  }

  public static DetailRefusal artifactTooLarge() {
    return new DetailRefusal(Kind.ARTIFACT_TOO_LARGE);
  }

  public static DetailRefusal artifactNotText() {
    return new DetailRefusal(Kind.ARTIFACT_NOT_TEXT);
  }

  public static DetailRefusal artifactSecret() {
    return new DetailRefusal(Kind.ARTIFACT_SECRET);
  }

  public static DetailRefusal artifactUnreadable() {
    return new DetailRefusal(Kind.ARTIFACT_UNREADABLE);
  }

  public static DetailRefusal artifactListingUnreadable() {
    return new DetailRefusal(Kind.ARTIFACT_LISTING_UNREADABLE);
  }

  public static DetailRefusal sourceUnreadable() {
    return new DetailRefusal(Kind.SOURCE_UNREADABLE);
  }
}
