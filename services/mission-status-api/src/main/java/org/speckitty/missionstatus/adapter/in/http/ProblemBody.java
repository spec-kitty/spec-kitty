package org.speckitty.missionstatus.adapter.in.http;

import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * The shared Problem of the contract ({@code _shared/schemas/Problem.yaml}) as written: only the members that are set appear, because
 * the schema types every optional member as text, so a null would not validate. The generated {@code Problem} model writes nulls
 * (required-nullable members elsewhere need that), so the error side uses this class. {@code type} is written only by the artifact
 * routes, whose contract examples and goldens carry {@code "about:blank"} (WP16 named edit).
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ProblemBody(String code, String detail, int status, String title, String type) {

  /** A Problem with no {@code type} member (the schema reads an absent one as {@code about:blank}). */
  public ProblemBody(String code, String detail, int status, String title) {
    this(code, detail, status, title, null);
  }
}
