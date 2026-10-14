package org.speckitty.missionstatus.adapter.in.http;

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
