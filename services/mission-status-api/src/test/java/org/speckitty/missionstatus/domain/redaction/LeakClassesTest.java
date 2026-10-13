package org.speckitty.missionstatus.domain.redaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.function.Predicate;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;

/** The leak-class value: patterns handed to the constructor, compiled with the Unicode flag, answering the questions of AC-9g. */
class LeakClassesTest {

  private final LeakClasses leaks = InlineLeakClasses.python();

  @Test
  void compileReadsTheWordClassLikePythonDoesNotLikeTheUnicodeFlag() {
    assertThat(LeakClasses.compile("\\w").matcher("\u00e9").matches()).isTrue();
    assertThat(LeakClasses.compile("\\w").matcher("\u0301").matches()).isFalse();
    assertThat(LeakClasses.compile("\\s").matcher("\u001c").matches()).isTrue();
    assertThat(LeakClasses.compile("\\w").flags() & Pattern.UNICODE_CHARACTER_CLASS).isZero();
  }

  @Test
  void aStrictHostPathIsAnyAbsolutePathATildePathAHomeSegmentOrAWindowsProfile() {
    Predicate<String> hostPath = leaks::strictHostPath;
    for (String value : List.of("/abs", "~/x", "C:\\x", "C:/x", "a/home/bob/x", "home/bob/x", "/Users/bob/", "C:\\Users\\bob\\")) {
      assertThat(hostPath.test(value)).as(value).isTrue();
    }
    for (String value : List.of("main", "feature/x", "release/1.0", "home", "home/bob", "")) {
      assertThat(hostPath.test(value)).as(value).isFalse();
    }
  }

  @Test
  void strictLeaksIncludeEmailsAndSecretsButHumanHostPathsDoNotApplyToStrictFields() {
    assertThat(leaks.strictLeak("/abs")).isTrue();
    assertThat(leaks.strictLeak("x@y.org")).isTrue();
    assertThat(leaks.strictLeak(InlineLeakClasses.fakeGithubToken())).isTrue();
    assertThat(leaks.strictLeak("/tmp/x")).isTrue();
    assertThat(leaks.strictLeak("fine")).isFalse();
  }

  @Test
  void humanLeaksUseTheHumanHostPathsSoABareTildeIsNotOne() {
    assertThat(leaks.humanLeak("see ~/notes")).isFalse();
    assertThat(leaks.humanLeak("/home/alice/x")).isTrue();
    assertThat(leaks.humanLeak("mail a@b.org")).isTrue();
    assertThat(leaks.humanLeak(InlineLeakClasses.fakeAwsKeyId())).isTrue();
    assertThat(leaks.humanLeak("/tmp/x")).isTrue();
    assertThat(leaks.humanLeak("plain")).isFalse();
  }

  @Test
  void redactEmailsReplacesEachSpanAndCountsThem() {
    LeakClasses.Replaced replaced = leaks.redactEmails("a@b.org and c@d.net", "[email]");
    assertThat(replaced.text()).isEqualTo("[email] and [email]");
    assertThat(replaced.count()).isEqualTo(2);
    LeakClasses.Replaced none = leaks.redactEmails("nothing here", "[email]");
    assertThat(none.text()).isEqualTo("nothing here");
    assertThat(none.count()).isZero();
  }

  @Test
  void anAddressGluedOntoAMatchIsFoundByTheAnchoredPatternAtTheEndOfTheLastOne() {
    // Python's email_matches: after 'a@b.comc' the anchored form is tried at the position where the previous match ended.
    LeakClasses.Replaced replaced = leaks.redactEmails("a@b.comc@d.org x@y.io", "[email]");
    assertThat(replaced.text()).isEqualTo("[email]@d.org [email]");
    assertThat(replaced.count()).isEqualTo(2);
    LeakClasses.Replaced glued = leaks.redactEmails("a@b.org%c@d.net", "[email]");
    assertThat(glued.text()).isEqualTo("[email][email]");
    assertThat(glued.count()).isEqualTo(2);
    LeakClasses.Replaced plus = leaks.redactEmails("a@b.org+c@d.net x@y.io", "[email]");
    assertThat(plus.text()).isEqualTo("[email][email] [email]");
    assertThat(plus.count()).isEqualTo(3);
  }

  @Test
  void redactHumanHostPathsReplacesThePathAndTheRestOfItsToken() {
    assertThat(leaks.redactHumanHostPaths("go /home/alice/dev/x, ok", "[path]").text()).isEqualTo("go [path] ok");
    assertThat(leaks.redactHumanHostPaths("go /home/alice/dev/x, ok", "[path]").count()).isEqualTo(1);
    assertThat(leaks.redactHumanHostPaths("no path", "[path]").count()).isZero();
  }

  @Test
  void theValueCopiesItsListsAndRequiresEveryPart() {
    List<Pattern> mutable = new java.util.ArrayList<>(List.of(LeakClasses.compile("a")));
    LeakClasses copy = new LeakClasses(mutable, List.of(), LeakClasses.compile("b"), LeakClasses.compile("c"), List.of());
    mutable.clear();
    assertThat(copy.strictHostPaths()).hasSize(1);
    assertThatThrownBy(() -> new LeakClasses(null, List.of(), LeakClasses.compile("b"), LeakClasses.compile("c"), List.of())).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new LeakClasses(List.of(), List.of(), null, LeakClasses.compile("c"), List.of())).isInstanceOf(NullPointerException.class);
  }
}
