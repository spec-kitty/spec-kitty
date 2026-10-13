package org.speckitty.missionstatus.adapter.in.http;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.web.filter.OncePerRequestFilter;
import tools.jackson.databind.json.JsonMapper;

/**
 * The Host and Origin guard (FR-009, plan section 8): a servlet filter at the highest precedence, so it runs before MVC dispatch, before
 * the async dispatch of the event stream and before any Mission read, on every path (unknown paths, error paths, the contract document).
 *
 * <ul>
 *   <li>The RAW {@code Host} header is compared, never {@code getServerName()} or {@code getServerPort()}, which Tomcat derives from it
 *       (or, for an HTTP/1.0 absolute-form target, from the target). The comparison is exact and case-sensitive against
 *       {@code 127.0.0.1:<own port>} and {@code localhost:<own port>}; an absent or empty header is refused.
 *   <li>{@code Forwarded} and {@code X-Forwarded-Host}, present with any value, are refused.
 *   <li>{@code Origin}, when present, must be {@code http://} plus one of the two accepted host forms; {@code null} and anything else is
 *       refused. There is no allowed-origin configuration.
 * </ul>
 *
 * Every refusal is {@link HostOriginRefusal#STATUS} with the shared Problem {@code request_refused}; the body names no check and carries
 * no request value.
 */
public class HostOriginFilter extends OncePerRequestFilter {

  private final OwnPortSource ownPort;
  private final byte[] refusalBody;

  public HostOriginFilter(OwnPortSource ownPort, JsonMapper mapper) {
    this.ownPort = ownPort;
    // the canonical form of the adapter's documents: compact members, then exactly one newline
    this.refusalBody = (mapper.writeValueAsString(new ProblemBody(HostOriginRefusal.CODE, null, HostOriginRefusal.STATUS, HostOriginRefusal.TITLE)) + "\n").getBytes(StandardCharsets.UTF_8);
  }

  @Override
  protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain) throws ServletException, IOException {
    if (accepted(request)) {
      chain.doFilter(request, response);
      return;
    }
    response.setStatus(HostOriginRefusal.STATUS);
    response.setContentType(MediaType.APPLICATION_PROBLEM_JSON_VALUE);
    response.setContentLength(refusalBody.length);
    response.getOutputStream().write(refusalBody);
    response.flushBuffer();
  }

  private boolean accepted(HttpServletRequest request) {
    int port = ownPort.port();
    if (port < 0) {
      return false; // no server is bound yet: nothing is accepted
    }
    String loopback = "127.0.0.1:" + port;
    String named = "localhost:" + port;
    String host = request.getHeader("Host");
    if (host == null || !(host.equals(loopback) || host.equals(named))) {
      return false;
    }
    if (request.getHeader("Forwarded") != null || request.getHeader("X-Forwarded-Host") != null) {
      return false;
    }
    List<String> origins = Collections.list(request.getHeaders("Origin"));
    for (String origin : origins) {
      if (!(origin.equals("http://" + loopback) || origin.equals("http://" + named))) {
        return false;
      }
    }
    return true;
  }

  /**
   * The guard covers error paths (FR-009): a request the container answers with its own {@code sendError} (a method it refuses, for
   * example) reaches the error page through an ERROR dispatch that never passed the REQUEST dispatch of this filter. A request that did
   * pass is checked again with the same headers and passes again.
   */
  @Override
  protected boolean shouldNotFilterErrorDispatch() {
    return false;
  }
}
