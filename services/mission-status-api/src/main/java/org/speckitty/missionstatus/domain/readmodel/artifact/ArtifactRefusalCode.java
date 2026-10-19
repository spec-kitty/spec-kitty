package org.speckitty.missionstatus.domain.readmodel.artifact;

/**
 * Why a read of the artifacts was refused ({@code ArtifactRefusalCode}), with the status the contract fixes for each code and the
 * title and detail the reference reader writes. The detail never repeats the requested path, a Mission directory or any content.
 */
public enum ArtifactRefusalCode {
  INVALID_ARTIFACT_PATH("invalid_artifact_path", 400, "The artifact path was refused", "The path is not a relative path of forward-slash segments."),
  NOT_FOUND("not_found", 404, "The artifact was not found", "No eligible artifact has this path in the Mission."),
  ARTIFACT_TOO_LARGE("artifact_too_large", 413, "The artifact is too large", "The file is larger than " + ArtifactText.MAX_CONTENT_BYTES + " bytes."),
  ARTIFACT_NOT_TEXT("artifact_not_text", 415, "The artifact is not text", "The file holds a NUL byte or is not valid UTF-8."),
  ARTIFACT_SECRET("artifact_secret", 422, "The artifact holds a credential", "The file holds a credential, so its content is not served."),
  ARTIFACT_UNREADABLE("artifact_unreadable", 500, "The artifact could not be read", "The file could not be read."),
  ARTIFACT_LISTING_UNREADABLE("artifact_listing_unreadable", 500, "The artifacts could not be listed", "The Mission directory could not be listed.");

  private final String wire;
  private final int status;
  private final String title;
  private final String detail;

  ArtifactRefusalCode(String wire, int status, String title, String detail) {
    this.wire = wire;
    this.status = status;
    this.title = title;
    this.detail = detail;
  }

  public String wire() {
    return wire;
  }

  public int status() {
    return status;
  }

  public String title() {
    return title;
  }

  public String detail() {
    return detail;
  }
}
