package org.speckitty.missionstatus.adapter.in.http;

import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * The shared Problem of the contract ({@code _shared/schemas/Problem.yaml}) as written: only the members that are set appear, because
 * the schema types every optional member as text, so a null would not validate. The generated {@code Problem} model writes nulls
 * (required-nullable members elsewhere need that), so the error side uses this class. Only the artifact refusals set {@code type}, as
 * the reference reader writes them; every other body leaves it out.
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ProblemBody(String code, String detail, int status, String title, String type) {

  /** The problem type of a body that names one explicitly: RFC 9457's default, which the artifact refusals write out. */
  public static final String ABOUT_BLANK = "about:blank";

  /** A body with no explicit {@code type} member (absent means {@code about:blank}). */
  public ProblemBody(String code, String detail, int status, String title) {
    this(code, detail, status, title, null);
  }
}
