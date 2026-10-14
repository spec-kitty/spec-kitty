package org.speckitty.missionstatus.adapter.in.http;

import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.readmodel.cursor.InvalidPageCursor;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

/**
 * Maps every refusal of the inbound port to the contract's Problem. A body carries a stable {@code code}, a fixed title and, where the
 * contract requires one, a fixed detail: never a path, line text, operating-system message, exception text or enum name.
 */
public final class ProblemMapper {

  public static final MediaType PROBLEM_JSON = MediaType.APPLICATION_PROBLEM_JSON;

  static final String INVALID_PAGE_CURSOR = "invalid_page_cursor";
  static final String INVALID_PARAMETER = "invalid_parameter";
  static final String STREAM_CAPACITY = "stream_capacity_reached";

  private ProblemMapper() {}

  /** The whole-read rows and the projection refusal: 500 with the diagnostic code. */
  public static ResponseEntity<ProblemBody> unavailable(MissionStatusUnavailable refusal) {
    return respond(new ProblemBody(refusal.code().wire(), null, 500, "The Mission status could not be read."));
  }

  /** A forged, malformed or no-longer-valid page cursor: 400 {@code invalid_page_cursor}. */
  public static ResponseEntity<ProblemBody> pageCursor(InvalidPageCursor refusal) {
    return respond(new ProblemBody(INVALID_PAGE_CURSOR, "The page cursor is malformed, forged or no longer valid.", 400, "The page cursor was refused."));
  }

  /** A stream refusal; the status follows the kind. {@code detail} is the fixed text for the kind unless the caller passes its own. */
  public static ResponseEntity<ProblemBody> stream(StreamRefused refusal, String detail) {
    return respond(new ProblemBody(refusal.code(), detail != null ? detail : detailOf(refusal.kind()), statusOf(refusal.kind()), "The stream request was refused."));
  }

  public static ResponseEntity<ProblemBody> stream(StreamRefused refusal) {
    return stream(refusal, null);
  }

  /** The event-stream admission bound is used up: 503 with a fixed code and detail (the contract's {@code default} Problem response). */
  public static ResponseEntity<ProblemBody> streamCapacity() {
    return respond(new ProblemBody(STREAM_CAPACITY, "The service holds the most event streams it admits; close one and retry.", 503, "The stream capacity is used up."));
  }

  /**
   * A refused detail operation: the one table from a kind to a status and a fixed Problem. The codes are the contract's
   * ({@code ArtifactRefusalCode} and {@code WorkPackageDetailRefusalCode}); no body names a path, a file, a Mission directory, an
   * operating-system message or an enum name.
   */
  public static ResponseEntity<ProblemBody> detail(DetailRefusal refusal) {
    DetailRefusal.Kind kind = refusal.kind();
    return switch (kind) {
      case NOT_FOUND -> detail(kind, 404, "The resource was not found.", "No Mission, work package or eligible artifact matches the request.");
      case INVALID_ARTIFACT_PATH -> detail(kind, 400, "The artifact path was refused.", "The path is not a relative path of forward-slash segments.");
      case ARTIFACT_TOO_LARGE -> detail(kind, 413, "The artifact is too large.", "The file is larger than 262144 bytes.");
      case ARTIFACT_NOT_TEXT -> detail(kind, 415, "The artifact is not text.", "The file holds a NUL byte or is not valid UTF-8.");
      case ARTIFACT_SECRET -> detail(kind, 422, "The artifact holds a credential.", "The file holds a credential, so its content is not served.");
      case ARTIFACT_UNREADABLE -> detail(kind, 500, "The artifact could not be read.", "The file could not be read.");
      case ARTIFACT_LISTING_UNREADABLE -> detail(kind, 500, "The artifacts could not be listed.", "The Mission directory could not be listed.");
      case SOURCE_UNREADABLE -> detail(kind, 500, "A source of the work package could not be read.", "A file the detail is built from could not be read.");
    };
  }

  /**
   * A refusal of an artifact route, with the exact Problem of the contract's {@code ArtifactRefusal} examples and of the Python goldens:
   * the route's own {@code not_found} text, no trailing full stop, and {@code "type": "about:blank"}. This is the named edit of
   * {@code ProblemMapper} that the artifact goldens force (D-P8-4); {@link #detail(DetailRefusal)} is unchanged and stays the text of
   * the routes whose goldens do not force one. A kind that is not an artifact refusal gets the generic text.
   */
  public static ResponseEntity<ProblemBody> artifact(DetailRefusal refusal) {
    DetailRefusal.Kind kind = refusal.kind();
    return switch (kind) {
      case NOT_FOUND -> artifact(kind, 404, "The artifact was not found", "No eligible artifact has this path in the Mission.");
      case INVALID_ARTIFACT_PATH -> artifact(kind, 400, "The artifact path was refused", "The path is not a relative path of forward-slash segments.");
      case ARTIFACT_TOO_LARGE -> artifact(kind, 413, "The artifact is too large", "The file is larger than 262144 bytes.");
      case ARTIFACT_NOT_TEXT -> artifact(kind, 415, "The artifact is not text", "The file holds a NUL byte or is not valid UTF-8.");
      case ARTIFACT_SECRET -> artifact(kind, 422, "The artifact holds a credential", "The file holds a credential, so its content is not served.");
      case ARTIFACT_UNREADABLE -> artifact(kind, 500, "The artifact could not be read", "The file could not be read.");
      case ARTIFACT_LISTING_UNREADABLE -> artifact(kind, 500, "The artifacts could not be listed", "The Mission directory could not be listed.");
      case SOURCE_UNREADABLE -> detail(refusal);
    };
  }

  private static ResponseEntity<ProblemBody> artifact(DetailRefusal.Kind kind, int status, String title, String detail) {
    return respond(new ProblemBody(kind.wire(), detail, status, title, "about:blank"));
  }

  private static ResponseEntity<ProblemBody> detail(DetailRefusal.Kind kind, int status, String title, String detail) {
    return respond(new ProblemBody(kind.wire(), detail, status, title));
  }

  /** A request parameter with a value the service does not accept (for example {@code includePrompt=yes}): 400 {@code invalid_parameter}, naming no value. */
  public static ResponseEntity<ProblemBody> invalidParameter() {
    return respond(new ProblemBody(INVALID_PARAMETER, "A request parameter has a value the service does not accept.", 400, "The request parameter was refused."));
  }

  /** Any other failure with a status: the status text and no code. */
  public static ResponseEntity<ProblemBody> status(HttpStatus status) {
    return respond(new ProblemBody(null, null, status.value(), status.getReasonPhrase()));
  }

  /** An unexpected failure: a generic 500 that says nothing about the cause. */
  public static ResponseEntity<ProblemBody> unexpected() {
    return respond(new ProblemBody("internal_error", null, 500, HttpStatus.INTERNAL_SERVER_ERROR.getReasonPhrase()));
  }

  /** The status the contract fixes for each refusal kind. */
  private static int statusOf(StreamRefused.Kind kind) {
    return switch (kind) {
      case NEGATIVE, MISALIGNED, CURSOR_WITHOUT_MISSION -> 400;
      case OUT_OF_RANGE, CONTENT_MISMATCH -> 409;
      case UNKNOWN_MISSION -> 404;
    };
  }

  /**
   * A refusal of the Work Package detail route, with the exact Problem of the contract's {@code WorkPackageDetailRefusal} examples and of the
   * Python goldens: the route's own texts, no trailing full stop, and {@code "type": "about:blank"}. This is the named edit of
   * {@code ProblemMapper} that the golden of {@code getWorkPackageDetail} forces (D-P8-4); {@link #detail(DetailRefusal)} is unchanged and
   * stays the text of the routes whose goldens do not force one. Only the two kinds of the route are answered here: a kind the route cannot
   * throw gets the generic text.
   */
  public static ResponseEntity<ProblemBody> workPackageDetail(DetailRefusal refusal) {
    return switch (refusal.kind()) {
      case NOT_FOUND -> workPackageDetail(refusal.kind(), 404, "The work package was not found", "No work package with this identifier exists in the Mission.");
      case SOURCE_UNREADABLE -> workPackageDetail(refusal.kind(), 500, "A source of the work package could not be read", "A file the detail is built from could not be read.");
      default -> detail(refusal);
    };
  }

  private static ResponseEntity<ProblemBody> workPackageDetail(DetailRefusal.Kind kind, int status, String title, String detail) {
    return respond(new ProblemBody(kind.wire(), detail, status, title, "about:blank"));
  }

  private static String detailOf(StreamRefused.Kind kind) {
    return switch (kind) {
      case NEGATIVE -> "The stream cursor offset is below zero.";
      case MISALIGNED -> "The stream cursor offset is not at the start of a line.";
      case CURSOR_WITHOUT_MISSION -> "A stream cursor needs a missionId.";
      case OUT_OF_RANGE -> "The stream cursor offset is beyond the end of the log.";
      case CONTENT_MISMATCH -> "The stream cursor digest does not match the log at that offset.";
      case UNKNOWN_MISSION -> "No Mission has that missionId.";
    };
  }

  private static ResponseEntity<ProblemBody> respond(ProblemBody body) {
    return ResponseEntity.status(body.status()).contentType(PROBLEM_JSON).body(body);
  }
}
