package org.speckitty.missionstatus.domain.redaction;

import java.util.Objects;

/**
 * The redaction function of every route that serves free text (FR-008, plan 7.1 row 7): does the text hold a credential, and what is it
 * with host paths and addresses substituted. It is the same function the {@link Projector} applies to a human field, asked once for a
 * whole text. A credential is decided on the text as read, before any substitution, so a secret that sits inside a path-like run is
 * still refused.
 */
public final class TextScreen {

  private static final String PATH_TOKEN = "[path]";
  private static final String EMAIL_TOKEN = "[email]";

  /** The decision for one text. */
  public sealed interface Screened {

    /**
     * The text with each host path replaced by {@code [path]} together with the following non-space characters, and each address by
     * {@code [email]}; {@code redacted} is true exactly when the text changed.
     */
    record Clean(String text, boolean redacted) implements Screened {
      public Clean {
        Objects.requireNonNull(text, "text");
      }
    }

    /** A credential pattern matched. It carries no text, so nothing of the secret can be served. */
    record SecretFound() implements Screened {}
  }

  private final LeakClasses leaks;

  public TextScreen(LeakClasses leaks) {
    this.leaks = Objects.requireNonNull(leaks, "leaks");
  }

  /** Screens one decoded text. */
  public Screened screen(String text) {
    Objects.requireNonNull(text, "text");
    if (leaks.credential(text)) {
      return new Screened.SecretFound();
    }
    try {
      String paths = leaks.redactHumanHostPaths(text, PATH_TOKEN).text();
      String emails = leaks.redactEmails(paths, EMAIL_TOKEN).text();
      return new Screened.Clean(emails, !emails.equals(text));
    } catch (StackOverflowError overflow) {
      // A pattern overflowed the stack on hostile text: fail closed, the same outcome as a credential hit.
      return new Screened.SecretFound();
    }
  }
}
