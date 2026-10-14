package org.speckitty.missionstatus.adapter.in.http;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.List;
import org.apache.tomcat.util.http.InvalidParameterException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.speckitty.missionstatus.application.query.port.in.exceptions.MissionStatusUnavailable;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamCursorText;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.readmodel.cursor.InvalidPageCursor;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.beans.TypeMismatchException;
import org.springframework.web.ErrorResponse;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.async.AsyncRequestNotUsableException;

/** Turns every exception of the HTTP adapter into the shared Problem; the unexpected ones are logged without a path or a message. */
@RestControllerAdvice
class ProblemAdvice {

  private static final Logger LOG = LoggerFactory.getLogger(ProblemAdvice.class);
  private static final String MISSIONS_PATH = "/api/v1/missions";
  private static final String EVENTS_PATH = "/api/v1/events";
  private static final String MALFORMED_QUERY_DETAIL = "The request query string is malformed.";

  @ExceptionHandler(MissionStatusUnavailable.class)
  ResponseEntity<ProblemBody> unavailable(MissionStatusUnavailable refusal) {
    return ProblemMapper.unavailable(refusal);
  }

  @ExceptionHandler(InvalidPageCursor.class)
  ResponseEntity<ProblemBody> pageCursor(InvalidPageCursor refusal) {
    return ProblemMapper.pageCursor(refusal);
  }

  @ExceptionHandler(StreamRefused.class)
  ResponseEntity<ProblemBody> stream(StreamRefused refusal) {
    return ProblemMapper.stream(refusal);
  }

  @ExceptionHandler(EventsController.UnparseableCursor.class)
  ResponseEntity<ProblemBody> unparseableCursor(EventsController.UnparseableCursor refusal) {
    return ProblemMapper.stream(new StreamRefused(StreamRefused.Kind.MISALIGNED), StreamCursorText.UNPARSEABLE_DETAIL);
  }

  @ExceptionHandler(EventsController.StreamCapacityReached.class)
  ResponseEntity<ProblemBody> streamCapacity(EventsController.StreamCapacityReached refusal) {
    return ProblemMapper.streamCapacity();
  }

  @ExceptionHandler(TypeMismatchException.class)
  ResponseEntity<ProblemBody> typeMismatch(TypeMismatchException mismatch) {
    return ProblemMapper.status(HttpStatus.BAD_REQUEST);
  }

  /**
   * A malformed percent-encoding in the query string (pre-merge fold F4, landing fold A2): a client error, answered with the 400 the route
   * declares, so the body is valid against the contract: {@code invalid_page_cursor} on the Mission listing, {@code misaligned} with a fixed
   * detail on the event stream. The route is read from the path only (the query is the part that cannot be parsed), and nothing of the
   * request is echoed. Any other path has no declared 400 and gets the plain shared Problem.
   */
  @ExceptionHandler(InvalidParameterException.class)
  ResponseEntity<ProblemBody> malformedQuery(InvalidParameterException refusal, HttpServletRequest request) {
    String path = request.getRequestURI();
    if (MISSIONS_PATH.equals(path)) {
      return ProblemMapper.pageCursor(new InvalidPageCursor(InvalidPageCursor.Reason.NOT_BASE64));
    }
    if (EVENTS_PATH.equals(path)) {
      return ProblemMapper.stream(new StreamRefused(StreamRefused.Kind.MISALIGNED), MALFORMED_QUERY_DETAIL);
    }
    return ProblemMapper.status(HttpStatus.BAD_REQUEST);
  }

  /**
   * The client closed an event stream (landing fold R-5): the container reports the write it could no longer make. That is not a fault of
   * the service, so nothing is logged and nothing is written: the response is an event stream that has gone, and a Problem cannot be
   * written into it.
   */
  @ExceptionHandler(AsyncRequestNotUsableException.class)
  void clientGone(AsyncRequestNotUsableException gone, HttpServletResponse response) {
    // handled: the HttpServletResponse parameter marks the request as handled and no body is written
  }

  @ExceptionHandler(Exception.class)
  ResponseEntity<ProblemBody> unexpected(Exception failure) {
    if (failure instanceof ErrorResponse refusal) {
      // The framework's own refusals (404 for an unknown path, 405, 415, 400 for a missing parameter): the status, no detail.
      HttpStatus status = HttpStatus.resolve(refusal.getStatusCode().value());
      ResponseEntity<ProblemBody> problem = ProblemMapper.status(status == null ? HttpStatus.INTERNAL_SERVER_ERROR : status);
      List<HttpMethod> allowed = List.copyOf(refusal.getHeaders().getAllow());
      if (allowed.isEmpty()) {
        return problem;
      }
      // a 405 names the methods the route takes
      return ResponseEntity.status(problem.getStatusCode()).headers(problem.getHeaders()).allow(allowed.toArray(HttpMethod[]::new)).body(problem.getBody());
    }
    // One line, no path, no message, no stack trace: the exception class only.
    LOG.error("unexpected failure class={}", failure.getClass().getSimpleName());
    return ProblemMapper.unexpected();
  }
}
