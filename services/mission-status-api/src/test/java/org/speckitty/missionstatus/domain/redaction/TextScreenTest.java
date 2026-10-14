package org.speckitty.missionstatus.domain.redaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Predicate;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.redaction.TextScreen.Screened;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/**
 * FR-008, AC-5.6, AC-5.7, AC-8.1 and AC-8.2: one function for every route. Every credential fixture is assembled at test time from two
 * fragments and is never committed whole (C-006, D-48).
 */
class TextScreenTest {

  private final LeakClasses leaks = LeakPatternsFile.load();
  private final TextScreen screen = new TextScreen(leaks);

  // ---- the corpus -----------------------------------------------------------------------------------------------------------

  /** Each credential pattern at its minimum length, assembled from two fragments. */
  private static List<String> credentials() {
    List<String> found = new ArrayList<>();
    for (String kind : List.of("p", "o", "u", "s", "r")) {
      found.add("gh" + kind + "_" + "A1b2".repeat(9));
    }
    found.add("github" + "_pat_" + "Ab_9".repeat(10));
    found.add("AK" + "IA" + "0123456789ABCDEF");
    found.add("AS" + "IA" + "0123456789ABCDEF");
    found.add("-----BEGIN " + "RSA PRIVATE KEY-----");
    found.add("-----BEGIN " + "PRIVATE KEY-----");
    found.add("-----BEGIN " + "OPENSSH PRIVATE KEY-----");
    return found;
  }

  /** The near misses: one short of each minimum, and a bare prefix. */
  private static List<String> nearMisses() {
    return List.of(
        "gh" + "p_" + "A".repeat(35),
        "github" + "_pat_" + "A".repeat(39),
        "AK" + "IA" + "A".repeat(15),
        "AS" + "IA" + "A".repeat(15),
        "gh" + "p_",
        "github" + "_pat_",
        "AK" + "IA",
        "-----BEGIN " + "PUBLIC KEY-----",
        "ghx_" + "A".repeat(40));
  }

  @Test
  void eachCredentialPatternAtItsMinimumLengthIsFoundAndCarriesNoText() {
    for (String credential : credentials()) {
      assertThat(screen.screen(credential)).as(credential.substring(0, 6)).isInstanceOf(Screened.SecretFound.class);
      assertThat(screen.screen("see " + credential + " now")).isInstanceOf(Screened.SecretFound.class);
      assertThat(screen.screen("line one\n" + credential + "\nline three")).isInstanceOf(Screened.SecretFound.class);
    }
  }

  @Test
  void theNearMissesAreCleanAndUnchanged() {
    for (String text : nearMisses()) {
      Screened screened = screen.screen(text);
      assertThat(screened).as(text).isInstanceOf(Screened.Clean.class);
      assertThat(((Screened.Clean) screened).text()).isEqualTo(text);
      assertThat(((Screened.Clean) screened).redacted()).isFalse();
    }
  }

  @Test
  void aSecretFoundDecisionHasNoTextAccessorAtAll() {
    assertThat(Screened.SecretFound.class.getRecordComponents()).isEmpty();
    assertThat(new Screened.SecretFound().toString()).doesNotContain("gh");
  }

  @Test
  void aHostPathBecomesPathTogetherWithTheFollowingNonSpaceCharacters() {
    Screened.Clean clean = (Screened.Clean) screen.screen("open /home/alice/project/notes.md for details");
    assertThat(clean.text()).isEqualTo("open [path] for details");
    assertThat(clean.redacted()).isTrue();
    assertThat(((Screened.Clean) screen.screen("at /Users/bob/x,y done")).text()).isEqualTo("at [path] done");
    assertThat(((Screened.Clean) screen.screen("tmp /tmp/work/out.txt end")).text()).isEqualTo("tmp [path] end");
    assertThat(((Screened.Clean) screen.screen("win C:\\Users\\bob\\Documents\\x.txt end")).text()).isEqualTo("win [path] end");
    assertThat(((Screened.Clean) screen.screen("/root/.ssh/id")).text()).isEqualTo("[path]");
  }

  @Test
  void anAddressBecomesEmail() {
    Screened.Clean clean = (Screened.Clean) screen.screen("write to jane.doe@example.org please");
    assertThat(clean.text()).isEqualTo("write to [email] please");
    assertThat(clean.redacted()).isTrue();
  }

  @Test
  void aPathAndAnAddressTogetherAreBothSubstituted() {
    Screened.Clean clean = (Screened.Clean) screen.screen("/home/a/b and a@b.org");
    assertThat(clean.text()).isEqualTo("[path] and [email]");
    assertThat(clean.redacted()).isTrue();
  }

  @Test
  void aCleanTextIsUnchangedAndNotRedactedAndAnEmptyTextIsClean() {
    for (String text : List.of("plain prose", "# Heading\n\n- item one\n- item two\n", "relative/path/to/file.md", "caf\u00e9 \u20ac", "")) {
      Screened.Clean clean = (Screened.Clean) screen.screen(text);
      assertThat(clean.text()).isEqualTo(text);
      assertThat(clean.redacted()).isFalse();
    }
  }

  @Test
  void redactedIsTrueExactlyWhenTheTextChanged() {
    for (String text : List.of("x /home/a/b y", "mail me@x.org", "plain", "~/notes", "a/home/b")) {
      Screened.Clean clean = (Screened.Clean) screen.screen(text);
      assertThat(clean.redacted()).as(text).isEqualTo(!clean.text().equals(text));
    }
  }

  @Test
  void aCleanRecordRefusesNullText() {
    assertThatThrownBy(() -> new Screened.Clean(null, false)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> screen.screen(null)).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new TextScreen(null)).isInstanceOf(NullPointerException.class);
  }

  // ---- AC-8.1: one function, two call sites --------------------------------------------------------------------------------

  @Test
  void theHumanFieldEntryOfTheProjectorGivesTheSameSubstitutionAndTheSameCredentialDecision() {
    List<String> substituted = List.of("plain", "open /home/alice/notes.md now", "mail jane@example.org", "/Users/bob/a and c@d.net", "win C:\\Users\\bob\\x ok", "/tmp/x/y");
    for (String text : substituted) {
      String viaProjector = new Projector(leaks).human(text, "field");
      assertThat(((Screened.Clean) screen.screen(text)).text()).as(text).isEqualTo(viaProjector);
    }
    for (String credential : credentials()) {
      assertThat(screen.screen("note " + credential)).isInstanceOf(Screened.SecretFound.class);
      assertThatThrownBy(() -> new Projector(leaks).human("note " + credential, "field")).isInstanceOf(ProjectionError.class);
    }
  }

  @Test
  void theCredentialPredicateIsTheOneThePatternsOfTheProjectorUse() {
    for (String credential : credentials()) {
      assertThat(leaks.credential(credential)).isTrue();
      assertThat(leaks.humanLeak(credential)).isTrue();
    }
    for (String text : nearMisses()) {
      assertThat(leaks.credential(text)).isFalse();
    }
    assertThat(leaks.credential("")).isFalse();
    assertThat(leaks.credential("/home/alice/x and a@b.org")).as("a path or an address is not a credential").isFalse();
  }

  // ---- AC-8.2: mutation in the suite ---------------------------------------------------------------------------------------

  /** How many credential corpus cases a credential decision gets wrong. */
  private int credentialFailures(Predicate<String> credential) {
    int failures = 0;
    for (String text : credentials()) {
      failures += credential.test(text) ? 0 : 1;
    }
    for (String text : nearMisses()) {
      failures += credential.test(text) ? 1 : 0;
    }
    return failures;
  }

  /** The AC-5.7 expectations, with the inputs. */
  private static final List<String[]> SUBSTITUTIONS =
      List.of(
          new String[] {"open /home/alice/project/notes.md for details", "open [path] for details"},
          new String[] {"at /Users/bob/x,y done", "at [path] done"},
          new String[] {"tmp /tmp/work/out.txt end", "tmp [path] end"},
          new String[] {"win C:\\Users\\bob\\Documents\\x.txt end", "win [path] end"},
          new String[] {"write to jane.doe@example.org please", "write to [email] please"});

  /** The same substitution without the {@code \S*} widening: each host-path pattern replaces only its own match. */
  private String withoutWidening(String text) {
    String current = text;
    for (Pattern pattern : leaks.humanHostPaths()) {
      current = pattern.matcher(current).replaceAll("[path]");
    }
    return leaks.redactEmails(current, "[email]").text();
  }

  @Test
  void aCredentialPredicateThatAlwaysAnswersNoneFailsTheCorpusAndTheRealOneDoesNot() {
    assertThat(credentialFailures(text -> false)).as("the always-none mutant").isGreaterThanOrEqualTo(credentials().size());
    assertThat(credentialFailures(leaks::credential)).as("the real function").isZero();
  }

  @Test
  void aSubstitutionWithoutTheWideningFailsTheCorpusAndTheRealOneDoesNot() {
    int mutantFailures = 0;
    int realFailures = 0;
    for (String[] row : SUBSTITUTIONS) {
      mutantFailures += withoutWidening(row[0]).equals(row[1]) ? 0 : 1;
      realFailures += ((Screened.Clean) screen.screen(row[0])).text().equals(row[1]) ? 0 : 1;
    }
    assertThat(mutantFailures).as("the no-widening mutant").isGreaterThanOrEqualTo(1);
    assertThat(realFailures).as("the real function").isZero();
  }
}
