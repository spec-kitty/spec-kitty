package org.speckitty.missionstatus.config;

import jakarta.servlet.RequestDispatcher;
import jakarta.servlet.http.HttpServletRequest;
import org.speckitty.missionstatus.adapter.in.http.ProblemBody;
import org.speckitty.missionstatus.adapter.in.http.ProblemMapper;
import org.springframework.boot.webmvc.error.ErrorController;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The container's error page (pre-merge fold J12). An error the CONTAINER routes to {@code /error} (an accepted-Host TRACE the container
 * refuses with 405, say) used to get Boot's default JSON, which echoes the request {@code path} and a timestamp. This controller replaces it
 * with the shared Problem: the status the container set and its reason phrase, nothing taken from the request. A foreign Host never gets
 * here: the Host/Origin filter refuses it with 403 on the original request. Lives in {@code config}, outside the {@code /api/v1} path prefix of
 * the adapter's controllers: the container dispatches to {@code /error}. A request that names {@code /error} itself has no error status and is a 404.
 */
@RestController
class ProblemErrorController implements ErrorController {

  @RequestMapping("${server.error.path:/error}")
  ResponseEntity<ProblemBody> error(HttpServletRequest request) {
    Object code = request.getAttribute(RequestDispatcher.ERROR_STATUS_CODE);
    if (code == null) {
      // Nothing routed this request here: it names the error page directly, which is an unknown path like any other (landing fold A6).
      return ProblemMapper.status(HttpStatus.NOT_FOUND);
    }
    HttpStatus status = code instanceof Integer value ? HttpStatus.resolve(value) : null;
    return ProblemMapper.status(status == null ? HttpStatus.INTERNAL_SERVER_ERROR : status);
  }
}
