package org.speckitty.missionstatus.adapter.in.http;

/**
 * The one status of every Host and Origin refusal the filter itself makes (plan section 8, Q-5). It does not govern the container's own
 * 400 for the closed list of Host values it rejects before the filter, nor any contract status (400 {@code invalid_page_cursor}, the
 * stream rows, the 500 whole-read rows): only {@link HostOriginFilter} names it.
 */
public final class HostOriginRefusal {

  public static final int STATUS = 403;

  /** The Problem {@code code} of the refusal. */
  public static final String CODE = "request_refused";

  /** The Problem {@code title} of the refusal. */
  public static final String TITLE = "Request refused";

  private HostOriginRefusal() {}
}
