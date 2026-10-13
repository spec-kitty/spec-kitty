package org.speckitty.missionstatus.domain.redaction;

import java.util.ArrayList;
import java.util.List;

/**
 * Leak probes with the verdict of the REAL Python patterns of {@code contracts/tools/leak_patterns.py} (run under CPython 3.11): each text is
 * a character that sits on the edge between {@code java.util.regex}'s Unicode classes and Python's {@code re} ({@code \w} and {@code \s}),
 * placed where a pattern looks at it. Generated once from the run; written with escapes only, so no control character is in this file.
 */
final class LeakProbeCases {

  /** One probe: the text and what Python gave for it. */
  record Probe(String name, String text, boolean strictLeak, boolean humanLeak, String pathsRedacted, int pathCount, String emailsRedacted, int emailCount) {}

  private LeakProbeCases() {}

  static List<Probe> all() {
    List<Probe> probes = new ArrayList<>();
    part0(probes);
    part1(probes);
    part2(probes);
    part3(probes);
    part4(probes);
    return probes;
  }

  private static void part0(List<Probe> probes) {
    probes.add(new Probe("U+0301 before-path", "a\u0301/home/x", false, true, "a\u0301[path]", 1, "a\u0301/home/x", 0));
    probes.add(new Probe("U+0301 bare-before-path", "\u0301/home/x", false, true, "\u0301[path]", 1, "\u0301/home/x", 0));
    probes.add(new Probe("U+0301 before-dotless-email", "x\u0301user@localhost", true, true, "x\u0301user@localhost", 0, "x\u0301[email]", 1));
    probes.add(new Probe("U+0301 before-email", "x\u0301user@example.org", true, true, "x\u0301user@example.org", 0, "x\u0301[email]", 1));
    probes.add(new Probe("U+0301 inside-path-segment", "/home/al\u0301ice/x tail", true, true, "[path] tail", 1, "/home/al\u0301ice/x tail", 0));
    probes.add(new Probe("U+0301 after-path", "/home/alice\u0301tail more", true, true, "[path] more", 1, "/home/alice\u0301tail more", 0));
    probes.add(new Probe("U+0301 strict-segment", "home/al\u0301ice/x", true, false, "home/al\u0301ice/x", 0, "home/al\u0301ice/x", 0));
    probes.add(new Probe("U+0301 after-dotless-host", "user@localhost\u0301z", true, true, "user@localhost\u0301z", 0, "[email]\u0301z", 1));
    probes.add(new Probe("U+0301 windows-user", "C:\\Users\\al\u0301ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u0301ice rest", 0));
    probes.add(new Probe("U+200D before-path", "a\u200d/home/x", false, true, "a\u200d[path]", 1, "a\u200d/home/x", 0));
    probes.add(new Probe("U+200D bare-before-path", "\u200d/home/x", false, true, "\u200d[path]", 1, "\u200d/home/x", 0));
    probes.add(new Probe("U+200D before-dotless-email", "x\u200duser@localhost", true, true, "x\u200duser@localhost", 0, "x\u200d[email]", 1));
    probes.add(new Probe("U+200D before-email", "x\u200duser@example.org", true, true, "x\u200duser@example.org", 0, "x\u200d[email]", 1));
    probes.add(new Probe("U+200D inside-path-segment", "/home/al\u200dice/x tail", true, true, "[path] tail", 1, "/home/al\u200dice/x tail", 0));
    probes.add(new Probe("U+200D after-path", "/home/alice\u200dtail more", true, true, "[path] more", 1, "/home/alice\u200dtail more", 0));
    probes.add(new Probe("U+200D strict-segment", "home/al\u200dice/x", true, false, "home/al\u200dice/x", 0, "home/al\u200dice/x", 0));
    probes.add(new Probe("U+200D after-dotless-host", "user@localhost\u200dz", true, true, "user@localhost\u200dz", 0, "[email]\u200dz", 1));
    probes.add(new Probe("U+200D windows-user", "C:\\Users\\al\u200dice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u200dice rest", 0));
    probes.add(new Probe("U+203F before-path", "a\u203f/home/x", false, true, "a\u203f[path]", 1, "a\u203f/home/x", 0));
    probes.add(new Probe("U+203F bare-before-path", "\u203f/home/x", false, true, "\u203f[path]", 1, "\u203f/home/x", 0));
    probes.add(new Probe("U+203F before-dotless-email", "x\u203fuser@localhost", true, true, "x\u203fuser@localhost", 0, "x\u203f[email]", 1));
    probes.add(new Probe("U+203F before-email", "x\u203fuser@example.org", true, true, "x\u203fuser@example.org", 0, "x\u203f[email]", 1));
    probes.add(new Probe("U+203F inside-path-segment", "/home/al\u203fice/x tail", true, true, "[path] tail", 1, "/home/al\u203fice/x tail", 0));
    probes.add(new Probe("U+203F after-path", "/home/alice\u203ftail more", true, true, "[path] more", 1, "/home/alice\u203ftail more", 0));
    probes.add(new Probe("U+203F strict-segment", "home/al\u203fice/x", true, false, "home/al\u203fice/x", 0, "home/al\u203fice/x", 0));
    probes.add(new Probe("U+203F after-dotless-host", "user@localhost\u203fz", true, true, "user@localhost\u203fz", 0, "[email]\u203fz", 1));
    probes.add(new Probe("U+203F windows-user", "C:\\Users\\al\u203fice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u203fice rest", 0));
    probes.add(new Probe("U+001C before-path", "a\u001c/home/x", false, true, "a\u001c[path]", 1, "a\u001c/home/x", 0));
    probes.add(new Probe("U+001C bare-before-path", "\u001c/home/x", false, true, "\u001c[path]", 1, "\u001c/home/x", 0));
    probes.add(new Probe("U+001C before-dotless-email", "x\u001cuser@localhost", true, true, "x\u001cuser@localhost", 0, "x\u001c[email]", 1));
    probes.add(new Probe("U+001C before-email", "x\u001cuser@example.org", true, true, "x\u001cuser@example.org", 0, "x\u001c[email]", 1));
    probes.add(new Probe("U+001C inside-path-segment", "/home/al\u001cice/x tail", true, true, "[path]\u001cice/x tail", 1, "/home/al\u001cice/x tail", 0));
    probes.add(new Probe("U+001C after-path", "/home/alice\u001ctail more", true, true, "[path]\u001ctail more", 1, "/home/alice\u001ctail more", 0));
    probes.add(new Probe("U+001C strict-segment", "home/al\u001cice/x", false, false, "home/al\u001cice/x", 0, "home/al\u001cice/x", 0));
    probes.add(new Probe("U+001C after-dotless-host", "user@localhost\u001cz", true, true, "user@localhost\u001cz", 0, "[email]\u001cz", 1));
    probes.add(new Probe("U+001C windows-user", "C:\\Users\\al\u001cice rest", true, true, "[path]\u001cice rest", 1, "C:\\Users\\al\u001cice rest", 0));
    probes.add(new Probe("U+001D before-path", "a\u001d/home/x", false, true, "a\u001d[path]", 1, "a\u001d/home/x", 0));
    probes.add(new Probe("U+001D bare-before-path", "\u001d/home/x", false, true, "\u001d[path]", 1, "\u001d/home/x", 0));
    probes.add(new Probe("U+001D before-dotless-email", "x\u001duser@localhost", true, true, "x\u001duser@localhost", 0, "x\u001d[email]", 1));
    probes.add(new Probe("U+001D before-email", "x\u001duser@example.org", true, true, "x\u001duser@example.org", 0, "x\u001d[email]", 1));
    probes.add(new Probe("U+001D inside-path-segment", "/home/al\u001dice/x tail", true, true, "[path]\u001dice/x tail", 1, "/home/al\u001dice/x tail", 0));
    probes.add(new Probe("U+001D after-path", "/home/alice\u001dtail more", true, true, "[path]\u001dtail more", 1, "/home/alice\u001dtail more", 0));
    probes.add(new Probe("U+001D strict-segment", "home/al\u001dice/x", false, false, "home/al\u001dice/x", 0, "home/al\u001dice/x", 0));
    probes.add(new Probe("U+001D after-dotless-host", "user@localhost\u001dz", true, true, "user@localhost\u001dz", 0, "[email]\u001dz", 1));
    probes.add(new Probe("U+001D windows-user", "C:\\Users\\al\u001dice rest", true, true, "[path]\u001dice rest", 1, "C:\\Users\\al\u001dice rest", 0));
    probes.add(new Probe("U+001E before-path", "a\u001e/home/x", false, true, "a\u001e[path]", 1, "a\u001e/home/x", 0));
    probes.add(new Probe("U+001E bare-before-path", "\u001e/home/x", false, true, "\u001e[path]", 1, "\u001e/home/x", 0));
    probes.add(new Probe("U+001E before-dotless-email", "x\u001euser@localhost", true, true, "x\u001euser@localhost", 0, "x\u001e[email]", 1));
    probes.add(new Probe("U+001E before-email", "x\u001euser@example.org", true, true, "x\u001euser@example.org", 0, "x\u001e[email]", 1));
    probes.add(new Probe("U+001E inside-path-segment", "/home/al\u001eice/x tail", true, true, "[path]\u001eice/x tail", 1, "/home/al\u001eice/x tail", 0));
    probes.add(new Probe("U+001E after-path", "/home/alice\u001etail more", true, true, "[path]\u001etail more", 1, "/home/alice\u001etail more", 0));
    probes.add(new Probe("U+001E strict-segment", "home/al\u001eice/x", false, false, "home/al\u001eice/x", 0, "home/al\u001eice/x", 0));
    probes.add(new Probe("U+001E after-dotless-host", "user@localhost\u001ez", true, true, "user@localhost\u001ez", 0, "[email]\u001ez", 1));
    probes.add(new Probe("U+001E windows-user", "C:\\Users\\al\u001eice rest", true, true, "[path]\u001eice rest", 1, "C:\\Users\\al\u001eice rest", 0));
    probes.add(new Probe("U+001F before-path", "a\u001f/home/x", false, true, "a\u001f[path]", 1, "a\u001f/home/x", 0));
    probes.add(new Probe("U+001F bare-before-path", "\u001f/home/x", false, true, "\u001f[path]", 1, "\u001f/home/x", 0));
    probes.add(new Probe("U+001F before-dotless-email", "x\u001fuser@localhost", true, true, "x\u001fuser@localhost", 0, "x\u001f[email]", 1));
    probes.add(new Probe("U+001F before-email", "x\u001fuser@example.org", true, true, "x\u001fuser@example.org", 0, "x\u001f[email]", 1));
    probes.add(new Probe("U+001F inside-path-segment", "/home/al\u001fice/x tail", true, true, "[path]\u001fice/x tail", 1, "/home/al\u001fice/x tail", 0));
    probes.add(new Probe("U+001F after-path", "/home/alice\u001ftail more", true, true, "[path]\u001ftail more", 1, "/home/alice\u001ftail more", 0));
  }

  private static void part1(List<Probe> probes) {
    probes.add(new Probe("U+001F strict-segment", "home/al\u001fice/x", false, false, "home/al\u001fice/x", 0, "home/al\u001fice/x", 0));
    probes.add(new Probe("U+001F after-dotless-host", "user@localhost\u001fz", true, true, "user@localhost\u001fz", 0, "[email]\u001fz", 1));
    probes.add(new Probe("U+001F windows-user", "C:\\Users\\al\u001fice rest", true, true, "[path]\u001fice rest", 1, "C:\\Users\\al\u001fice rest", 0));
    probes.add(new Probe("U+0085 before-path", "a\u0085/home/x", false, true, "a\u0085[path]", 1, "a\u0085/home/x", 0));
    probes.add(new Probe("U+0085 bare-before-path", "\u0085/home/x", false, true, "\u0085[path]", 1, "\u0085/home/x", 0));
    probes.add(new Probe("U+0085 before-dotless-email", "x\u0085user@localhost", true, true, "x\u0085user@localhost", 0, "x\u0085[email]", 1));
    probes.add(new Probe("U+0085 before-email", "x\u0085user@example.org", true, true, "x\u0085user@example.org", 0, "x\u0085[email]", 1));
    probes.add(new Probe("U+0085 inside-path-segment", "/home/al\u0085ice/x tail", true, true, "[path]\u0085ice/x tail", 1, "/home/al\u0085ice/x tail", 0));
    probes.add(new Probe("U+0085 after-path", "/home/alice\u0085tail more", true, true, "[path]\u0085tail more", 1, "/home/alice\u0085tail more", 0));
    probes.add(new Probe("U+0085 strict-segment", "home/al\u0085ice/x", false, false, "home/al\u0085ice/x", 0, "home/al\u0085ice/x", 0));
    probes.add(new Probe("U+0085 after-dotless-host", "user@localhost\u0085z", true, true, "user@localhost\u0085z", 0, "[email]\u0085z", 1));
    probes.add(new Probe("U+0085 windows-user", "C:\\Users\\al\u0085ice rest", true, true, "[path]\u0085ice rest", 1, "C:\\Users\\al\u0085ice rest", 0));
    probes.add(new Probe("U+00A0 before-path", "a\u00a0/home/x", false, true, "a\u00a0[path]", 1, "a\u00a0/home/x", 0));
    probes.add(new Probe("U+00A0 bare-before-path", "\u00a0/home/x", false, true, "\u00a0[path]", 1, "\u00a0/home/x", 0));
    probes.add(new Probe("U+00A0 before-dotless-email", "x\u00a0user@localhost", true, true, "x\u00a0user@localhost", 0, "x\u00a0[email]", 1));
    probes.add(new Probe("U+00A0 before-email", "x\u00a0user@example.org", true, true, "x\u00a0user@example.org", 0, "x\u00a0[email]", 1));
    probes.add(new Probe("U+00A0 inside-path-segment", "/home/al\u00a0ice/x tail", true, true, "[path]\u00a0ice/x tail", 1, "/home/al\u00a0ice/x tail", 0));
    probes.add(new Probe("U+00A0 after-path", "/home/alice\u00a0tail more", true, true, "[path]\u00a0tail more", 1, "/home/alice\u00a0tail more", 0));
    probes.add(new Probe("U+00A0 strict-segment", "home/al\u00a0ice/x", false, false, "home/al\u00a0ice/x", 0, "home/al\u00a0ice/x", 0));
    probes.add(new Probe("U+00A0 after-dotless-host", "user@localhost\u00a0z", true, true, "user@localhost\u00a0z", 0, "[email]\u00a0z", 1));
    probes.add(new Probe("U+00A0 windows-user", "C:\\Users\\al\u00a0ice rest", true, true, "[path]\u00a0ice rest", 1, "C:\\Users\\al\u00a0ice rest", 0));
    probes.add(new Probe("U+2028 before-path", "a\u2028/home/x", false, true, "a\u2028[path]", 1, "a\u2028/home/x", 0));
    probes.add(new Probe("U+2028 bare-before-path", "\u2028/home/x", false, true, "\u2028[path]", 1, "\u2028/home/x", 0));
    probes.add(new Probe("U+2028 before-dotless-email", "x\u2028user@localhost", true, true, "x\u2028user@localhost", 0, "x\u2028[email]", 1));
    probes.add(new Probe("U+2028 before-email", "x\u2028user@example.org", true, true, "x\u2028user@example.org", 0, "x\u2028[email]", 1));
    probes.add(new Probe("U+2028 inside-path-segment", "/home/al\u2028ice/x tail", true, true, "[path]\u2028ice/x tail", 1, "/home/al\u2028ice/x tail", 0));
    probes.add(new Probe("U+2028 after-path", "/home/alice\u2028tail more", true, true, "[path]\u2028tail more", 1, "/home/alice\u2028tail more", 0));
    probes.add(new Probe("U+2028 strict-segment", "home/al\u2028ice/x", false, false, "home/al\u2028ice/x", 0, "home/al\u2028ice/x", 0));
    probes.add(new Probe("U+2028 after-dotless-host", "user@localhost\u2028z", true, true, "user@localhost\u2028z", 0, "[email]\u2028z", 1));
    probes.add(new Probe("U+2028 windows-user", "C:\\Users\\al\u2028ice rest", true, true, "[path]\u2028ice rest", 1, "C:\\Users\\al\u2028ice rest", 0));
    probes.add(new Probe("U+2029 before-path", "a\u2029/home/x", false, true, "a\u2029[path]", 1, "a\u2029/home/x", 0));
    probes.add(new Probe("U+2029 bare-before-path", "\u2029/home/x", false, true, "\u2029[path]", 1, "\u2029/home/x", 0));
    probes.add(new Probe("U+2029 before-dotless-email", "x\u2029user@localhost", true, true, "x\u2029user@localhost", 0, "x\u2029[email]", 1));
    probes.add(new Probe("U+2029 before-email", "x\u2029user@example.org", true, true, "x\u2029user@example.org", 0, "x\u2029[email]", 1));
    probes.add(new Probe("U+2029 inside-path-segment", "/home/al\u2029ice/x tail", true, true, "[path]\u2029ice/x tail", 1, "/home/al\u2029ice/x tail", 0));
    probes.add(new Probe("U+2029 after-path", "/home/alice\u2029tail more", true, true, "[path]\u2029tail more", 1, "/home/alice\u2029tail more", 0));
    probes.add(new Probe("U+2029 strict-segment", "home/al\u2029ice/x", false, false, "home/al\u2029ice/x", 0, "home/al\u2029ice/x", 0));
    probes.add(new Probe("U+2029 after-dotless-host", "user@localhost\u2029z", true, true, "user@localhost\u2029z", 0, "[email]\u2029z", 1));
    probes.add(new Probe("U+2029 windows-user", "C:\\Users\\al\u2029ice rest", true, true, "[path]\u2029ice rest", 1, "C:\\Users\\al\u2029ice rest", 0));
    probes.add(new Probe("U+200B before-path", "a\u200b/home/x", false, true, "a\u200b[path]", 1, "a\u200b/home/x", 0));
    probes.add(new Probe("U+200B bare-before-path", "\u200b/home/x", false, true, "\u200b[path]", 1, "\u200b/home/x", 0));
    probes.add(new Probe("U+200B before-dotless-email", "x\u200buser@localhost", true, true, "x\u200buser@localhost", 0, "x\u200b[email]", 1));
    probes.add(new Probe("U+200B before-email", "x\u200buser@example.org", true, true, "x\u200buser@example.org", 0, "x\u200b[email]", 1));
    probes.add(new Probe("U+200B inside-path-segment", "/home/al\u200bice/x tail", true, true, "[path] tail", 1, "/home/al\u200bice/x tail", 0));
    probes.add(new Probe("U+200B after-path", "/home/alice\u200btail more", true, true, "[path] more", 1, "/home/alice\u200btail more", 0));
    probes.add(new Probe("U+200B strict-segment", "home/al\u200bice/x", true, false, "home/al\u200bice/x", 0, "home/al\u200bice/x", 0));
    probes.add(new Probe("U+200B after-dotless-host", "user@localhost\u200bz", true, true, "user@localhost\u200bz", 0, "[email]\u200bz", 1));
    probes.add(new Probe("U+200B windows-user", "C:\\Users\\al\u200bice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u200bice rest", 0));
    probes.add(new Probe("U+FEFF before-path", "a\ufeff/home/x", false, true, "a\ufeff[path]", 1, "a\ufeff/home/x", 0));
    probes.add(new Probe("U+FEFF bare-before-path", "\ufeff/home/x", false, true, "\ufeff[path]", 1, "\ufeff/home/x", 0));
    probes.add(new Probe("U+FEFF before-dotless-email", "x\ufeffuser@localhost", true, true, "x\ufeffuser@localhost", 0, "x\ufeff[email]", 1));
    probes.add(new Probe("U+FEFF before-email", "x\ufeffuser@example.org", true, true, "x\ufeffuser@example.org", 0, "x\ufeff[email]", 1));
    probes.add(new Probe("U+FEFF inside-path-segment", "/home/al\ufeffice/x tail", true, true, "[path] tail", 1, "/home/al\ufeffice/x tail", 0));
    probes.add(new Probe("U+FEFF after-path", "/home/alice\ufefftail more", true, true, "[path] more", 1, "/home/alice\ufefftail more", 0));
    probes.add(new Probe("U+FEFF strict-segment", "home/al\ufeffice/x", true, false, "home/al\ufeffice/x", 0, "home/al\ufeffice/x", 0));
    probes.add(new Probe("U+FEFF after-dotless-host", "user@localhost\ufeffz", true, true, "user@localhost\ufeffz", 0, "[email]\ufeffz", 1));
    probes.add(new Probe("U+FEFF windows-user", "C:\\Users\\al\ufeffice rest", true, true, "[path] rest", 1, "C:\\Users\\al\ufeffice rest", 0));
    probes.add(new Probe("U+0300 before-path", "a\u0300/home/x", false, true, "a\u0300[path]", 1, "a\u0300/home/x", 0));
    probes.add(new Probe("U+0300 bare-before-path", "\u0300/home/x", false, true, "\u0300[path]", 1, "\u0300/home/x", 0));
    probes.add(new Probe("U+0300 before-dotless-email", "x\u0300user@localhost", true, true, "x\u0300user@localhost", 0, "x\u0300[email]", 1));
  }

  private static void part2(List<Probe> probes) {
    probes.add(new Probe("U+0300 before-email", "x\u0300user@example.org", true, true, "x\u0300user@example.org", 0, "x\u0300[email]", 1));
    probes.add(new Probe("U+0300 inside-path-segment", "/home/al\u0300ice/x tail", true, true, "[path] tail", 1, "/home/al\u0300ice/x tail", 0));
    probes.add(new Probe("U+0300 after-path", "/home/alice\u0300tail more", true, true, "[path] more", 1, "/home/alice\u0300tail more", 0));
    probes.add(new Probe("U+0300 strict-segment", "home/al\u0300ice/x", true, false, "home/al\u0300ice/x", 0, "home/al\u0300ice/x", 0));
    probes.add(new Probe("U+0300 after-dotless-host", "user@localhost\u0300z", true, true, "user@localhost\u0300z", 0, "[email]\u0300z", 1));
    probes.add(new Probe("U+0300 windows-user", "C:\\Users\\al\u0300ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u0300ice rest", 0));
    probes.add(new Probe("U+0345 before-path", "a\u0345/home/x", false, true, "a\u0345[path]", 1, "a\u0345/home/x", 0));
    probes.add(new Probe("U+0345 bare-before-path", "\u0345/home/x", false, true, "\u0345[path]", 1, "\u0345/home/x", 0));
    probes.add(new Probe("U+0345 before-dotless-email", "x\u0345user@localhost", true, true, "x\u0345user@localhost", 0, "x\u0345[email]", 1));
    probes.add(new Probe("U+0345 before-email", "x\u0345user@example.org", true, true, "x\u0345user@example.org", 0, "x\u0345[email]", 1));
    probes.add(new Probe("U+0345 inside-path-segment", "/home/al\u0345ice/x tail", true, true, "[path] tail", 1, "/home/al\u0345ice/x tail", 0));
    probes.add(new Probe("U+0345 after-path", "/home/alice\u0345tail more", true, true, "[path] more", 1, "/home/alice\u0345tail more", 0));
    probes.add(new Probe("U+0345 strict-segment", "home/al\u0345ice/x", true, false, "home/al\u0345ice/x", 0, "home/al\u0345ice/x", 0));
    probes.add(new Probe("U+0345 after-dotless-host", "user@localhost\u0345z", true, true, "user@localhost\u0345z", 0, "[email]\u0345z", 1));
    probes.add(new Probe("U+0345 windows-user", "C:\\Users\\al\u0345ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u0345ice rest", 0));
    probes.add(new Probe("U+0903 before-path", "a\u0903/home/x", false, true, "a\u0903[path]", 1, "a\u0903/home/x", 0));
    probes.add(new Probe("U+0903 bare-before-path", "\u0903/home/x", false, true, "\u0903[path]", 1, "\u0903/home/x", 0));
    probes.add(new Probe("U+0903 before-dotless-email", "x\u0903user@localhost", true, true, "x\u0903user@localhost", 0, "x\u0903[email]", 1));
    probes.add(new Probe("U+0903 before-email", "x\u0903user@example.org", true, true, "x\u0903user@example.org", 0, "x\u0903[email]", 1));
    probes.add(new Probe("U+0903 inside-path-segment", "/home/al\u0903ice/x tail", true, true, "[path] tail", 1, "/home/al\u0903ice/x tail", 0));
    probes.add(new Probe("U+0903 after-path", "/home/alice\u0903tail more", true, true, "[path] more", 1, "/home/alice\u0903tail more", 0));
    probes.add(new Probe("U+0903 strict-segment", "home/al\u0903ice/x", true, false, "home/al\u0903ice/x", 0, "home/al\u0903ice/x", 0));
    probes.add(new Probe("U+0903 after-dotless-host", "user@localhost\u0903z", true, true, "user@localhost\u0903z", 0, "[email]\u0903z", 1));
    probes.add(new Probe("U+0903 windows-user", "C:\\Users\\al\u0903ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u0903ice rest", 0));
    probes.add(new Probe("U+20DD before-path", "a\u20dd/home/x", false, true, "a\u20dd[path]", 1, "a\u20dd/home/x", 0));
    probes.add(new Probe("U+20DD bare-before-path", "\u20dd/home/x", false, true, "\u20dd[path]", 1, "\u20dd/home/x", 0));
    probes.add(new Probe("U+20DD before-dotless-email", "x\u20dduser@localhost", true, true, "x\u20dduser@localhost", 0, "x\u20dd[email]", 1));
    probes.add(new Probe("U+20DD before-email", "x\u20dduser@example.org", true, true, "x\u20dduser@example.org", 0, "x\u20dd[email]", 1));
    probes.add(new Probe("U+20DD inside-path-segment", "/home/al\u20ddice/x tail", true, true, "[path] tail", 1, "/home/al\u20ddice/x tail", 0));
    probes.add(new Probe("U+20DD after-path", "/home/alice\u20ddtail more", true, true, "[path] more", 1, "/home/alice\u20ddtail more", 0));
    probes.add(new Probe("U+20DD strict-segment", "home/al\u20ddice/x", true, false, "home/al\u20ddice/x", 0, "home/al\u20ddice/x", 0));
    probes.add(new Probe("U+20DD after-dotless-host", "user@localhost\u20ddz", true, true, "user@localhost\u20ddz", 0, "[email]\u20ddz", 1));
    probes.add(new Probe("U+20DD windows-user", "C:\\Users\\al\u20ddice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u20ddice rest", 0));
    probes.add(new Probe("U+2040 before-path", "a\u2040/home/x", false, true, "a\u2040[path]", 1, "a\u2040/home/x", 0));
    probes.add(new Probe("U+2040 bare-before-path", "\u2040/home/x", false, true, "\u2040[path]", 1, "\u2040/home/x", 0));
    probes.add(new Probe("U+2040 before-dotless-email", "x\u2040user@localhost", true, true, "x\u2040user@localhost", 0, "x\u2040[email]", 1));
    probes.add(new Probe("U+2040 before-email", "x\u2040user@example.org", true, true, "x\u2040user@example.org", 0, "x\u2040[email]", 1));
    probes.add(new Probe("U+2040 inside-path-segment", "/home/al\u2040ice/x tail", true, true, "[path] tail", 1, "/home/al\u2040ice/x tail", 0));
    probes.add(new Probe("U+2040 after-path", "/home/alice\u2040tail more", true, true, "[path] more", 1, "/home/alice\u2040tail more", 0));
    probes.add(new Probe("U+2040 strict-segment", "home/al\u2040ice/x", true, false, "home/al\u2040ice/x", 0, "home/al\u2040ice/x", 0));
    probes.add(new Probe("U+2040 after-dotless-host", "user@localhost\u2040z", true, true, "user@localhost\u2040z", 0, "[email]\u2040z", 1));
    probes.add(new Probe("U+2040 windows-user", "C:\\Users\\al\u2040ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u2040ice rest", 0));
    probes.add(new Probe("U+FE33 before-path", "a\ufe33/home/x", false, true, "a\ufe33[path]", 1, "a\ufe33/home/x", 0));
    probes.add(new Probe("U+FE33 bare-before-path", "\ufe33/home/x", false, true, "\ufe33[path]", 1, "\ufe33/home/x", 0));
    probes.add(new Probe("U+FE33 before-dotless-email", "x\ufe33user@localhost", true, true, "x\ufe33user@localhost", 0, "x\ufe33[email]", 1));
    probes.add(new Probe("U+FE33 before-email", "x\ufe33user@example.org", true, true, "x\ufe33user@example.org", 0, "x\ufe33[email]", 1));
    probes.add(new Probe("U+FE33 inside-path-segment", "/home/al\ufe33ice/x tail", true, true, "[path] tail", 1, "/home/al\ufe33ice/x tail", 0));
    probes.add(new Probe("U+FE33 after-path", "/home/alice\ufe33tail more", true, true, "[path] more", 1, "/home/alice\ufe33tail more", 0));
    probes.add(new Probe("U+FE33 strict-segment", "home/al\ufe33ice/x", true, false, "home/al\ufe33ice/x", 0, "home/al\ufe33ice/x", 0));
    probes.add(new Probe("U+FE33 after-dotless-host", "user@localhost\ufe33z", true, true, "user@localhost\ufe33z", 0, "[email]\ufe33z", 1));
    probes.add(new Probe("U+FE33 windows-user", "C:\\Users\\al\ufe33ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\ufe33ice rest", 0));
    probes.add(new Probe("U+180E before-path", "a\u180e/home/x", false, true, "a\u180e[path]", 1, "a\u180e/home/x", 0));
    probes.add(new Probe("U+180E bare-before-path", "\u180e/home/x", false, true, "\u180e[path]", 1, "\u180e/home/x", 0));
    probes.add(new Probe("U+180E before-dotless-email", "x\u180euser@localhost", true, true, "x\u180euser@localhost", 0, "x\u180e[email]", 1));
    probes.add(new Probe("U+180E before-email", "x\u180euser@example.org", true, true, "x\u180euser@example.org", 0, "x\u180e[email]", 1));
    probes.add(new Probe("U+180E inside-path-segment", "/home/al\u180eice/x tail", true, true, "[path] tail", 1, "/home/al\u180eice/x tail", 0));
    probes.add(new Probe("U+180E after-path", "/home/alice\u180etail more", true, true, "[path] more", 1, "/home/alice\u180etail more", 0));
    probes.add(new Probe("U+180E strict-segment", "home/al\u180eice/x", true, false, "home/al\u180eice/x", 0, "home/al\u180eice/x", 0));
    probes.add(new Probe("U+180E after-dotless-host", "user@localhost\u180ez", true, true, "user@localhost\u180ez", 0, "[email]\u180ez", 1));
    probes.add(new Probe("U+180E windows-user", "C:\\Users\\al\u180eice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u180eice rest", 0));
  }

  private static void part3(List<Probe> probes) {
    probes.add(new Probe("U+1680 before-path", "a\u1680/home/x", false, true, "a\u1680[path]", 1, "a\u1680/home/x", 0));
    probes.add(new Probe("U+1680 bare-before-path", "\u1680/home/x", false, true, "\u1680[path]", 1, "\u1680/home/x", 0));
    probes.add(new Probe("U+1680 before-dotless-email", "x\u1680user@localhost", true, true, "x\u1680user@localhost", 0, "x\u1680[email]", 1));
    probes.add(new Probe("U+1680 before-email", "x\u1680user@example.org", true, true, "x\u1680user@example.org", 0, "x\u1680[email]", 1));
    probes.add(new Probe("U+1680 inside-path-segment", "/home/al\u1680ice/x tail", true, true, "[path]\u1680ice/x tail", 1, "/home/al\u1680ice/x tail", 0));
    probes.add(new Probe("U+1680 after-path", "/home/alice\u1680tail more", true, true, "[path]\u1680tail more", 1, "/home/alice\u1680tail more", 0));
    probes.add(new Probe("U+1680 strict-segment", "home/al\u1680ice/x", false, false, "home/al\u1680ice/x", 0, "home/al\u1680ice/x", 0));
    probes.add(new Probe("U+1680 after-dotless-host", "user@localhost\u1680z", true, true, "user@localhost\u1680z", 0, "[email]\u1680z", 1));
    probes.add(new Probe("U+1680 windows-user", "C:\\Users\\al\u1680ice rest", true, true, "[path]\u1680ice rest", 1, "C:\\Users\\al\u1680ice rest", 0));
    probes.add(new Probe("U+3000 before-path", "a\u3000/home/x", false, true, "a\u3000[path]", 1, "a\u3000/home/x", 0));
    probes.add(new Probe("U+3000 bare-before-path", "\u3000/home/x", false, true, "\u3000[path]", 1, "\u3000/home/x", 0));
    probes.add(new Probe("U+3000 before-dotless-email", "x\u3000user@localhost", true, true, "x\u3000user@localhost", 0, "x\u3000[email]", 1));
    probes.add(new Probe("U+3000 before-email", "x\u3000user@example.org", true, true, "x\u3000user@example.org", 0, "x\u3000[email]", 1));
    probes.add(new Probe("U+3000 inside-path-segment", "/home/al\u3000ice/x tail", true, true, "[path]\u3000ice/x tail", 1, "/home/al\u3000ice/x tail", 0));
    probes.add(new Probe("U+3000 after-path", "/home/alice\u3000tail more", true, true, "[path]\u3000tail more", 1, "/home/alice\u3000tail more", 0));
    probes.add(new Probe("U+3000 strict-segment", "home/al\u3000ice/x", false, false, "home/al\u3000ice/x", 0, "home/al\u3000ice/x", 0));
    probes.add(new Probe("U+3000 after-dotless-host", "user@localhost\u3000z", true, true, "user@localhost\u3000z", 0, "[email]\u3000z", 1));
    probes.add(new Probe("U+3000 windows-user", "C:\\Users\\al\u3000ice rest", true, true, "[path]\u3000ice rest", 1, "C:\\Users\\al\u3000ice rest", 0));
    probes.add(new Probe("U+00B2 before-path", "a\u00b2/home/x", false, false, "a\u00b2/home/x", 0, "a\u00b2/home/x", 0));
    probes.add(new Probe("U+00B2 bare-before-path", "\u00b2/home/x", false, false, "\u00b2/home/x", 0, "\u00b2/home/x", 0));
    probes.add(new Probe("U+00B2 before-dotless-email", "x\u00b2user@localhost", false, false, "x\u00b2user@localhost", 0, "x\u00b2user@localhost", 0));
    probes.add(new Probe("U+00B2 before-email", "x\u00b2user@example.org", true, true, "x\u00b2user@example.org", 0, "x\u00b2[email]", 1));
    probes.add(new Probe("U+00B2 inside-path-segment", "/home/al\u00b2ice/x tail", true, true, "[path] tail", 1, "/home/al\u00b2ice/x tail", 0));
    probes.add(new Probe("U+00B2 after-path", "/home/alice\u00b2tail more", true, true, "[path] more", 1, "/home/alice\u00b2tail more", 0));
    probes.add(new Probe("U+00B2 strict-segment", "home/al\u00b2ice/x", true, false, "home/al\u00b2ice/x", 0, "home/al\u00b2ice/x", 0));
    probes.add(new Probe("U+00B2 after-dotless-host", "user@localhost\u00b2z", false, false, "user@localhost\u00b2z", 0, "user@localhost\u00b2z", 0));
    probes.add(new Probe("U+00B2 windows-user", "C:\\Users\\al\u00b2ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u00b2ice rest", 0));
    probes.add(new Probe("U+2160 before-path", "a\u2160/home/x", false, false, "a\u2160/home/x", 0, "a\u2160/home/x", 0));
    probes.add(new Probe("U+2160 bare-before-path", "\u2160/home/x", false, false, "\u2160/home/x", 0, "\u2160/home/x", 0));
    probes.add(new Probe("U+2160 before-dotless-email", "x\u2160user@localhost", false, false, "x\u2160user@localhost", 0, "x\u2160user@localhost", 0));
    probes.add(new Probe("U+2160 before-email", "x\u2160user@example.org", true, true, "x\u2160user@example.org", 0, "x\u2160[email]", 1));
    probes.add(new Probe("U+2160 inside-path-segment", "/home/al\u2160ice/x tail", true, true, "[path] tail", 1, "/home/al\u2160ice/x tail", 0));
    probes.add(new Probe("U+2160 after-path", "/home/alice\u2160tail more", true, true, "[path] more", 1, "/home/alice\u2160tail more", 0));
    probes.add(new Probe("U+2160 strict-segment", "home/al\u2160ice/x", true, false, "home/al\u2160ice/x", 0, "home/al\u2160ice/x", 0));
    probes.add(new Probe("U+2160 after-dotless-host", "user@localhost\u2160z", false, false, "user@localhost\u2160z", 0, "user@localhost\u2160z", 0));
    probes.add(new Probe("U+2160 windows-user", "C:\\Users\\al\u2160ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u2160ice rest", 0));
    probes.add(new Probe("U+0660 before-path", "a\u0660/home/x", false, false, "a\u0660/home/x", 0, "a\u0660/home/x", 0));
    probes.add(new Probe("U+0660 bare-before-path", "\u0660/home/x", false, false, "\u0660/home/x", 0, "\u0660/home/x", 0));
    probes.add(new Probe("U+0660 before-dotless-email", "x\u0660user@localhost", false, false, "x\u0660user@localhost", 0, "x\u0660user@localhost", 0));
    probes.add(new Probe("U+0660 before-email", "x\u0660user@example.org", true, true, "x\u0660user@example.org", 0, "x\u0660[email]", 1));
    probes.add(new Probe("U+0660 inside-path-segment", "/home/al\u0660ice/x tail", true, true, "[path] tail", 1, "/home/al\u0660ice/x tail", 0));
    probes.add(new Probe("U+0660 after-path", "/home/alice\u0660tail more", true, true, "[path] more", 1, "/home/alice\u0660tail more", 0));
    probes.add(new Probe("U+0660 strict-segment", "home/al\u0660ice/x", true, false, "home/al\u0660ice/x", 0, "home/al\u0660ice/x", 0));
    probes.add(new Probe("U+0660 after-dotless-host", "user@localhost\u0660z", false, false, "user@localhost\u0660z", 0, "user@localhost\u0660z", 0));
    probes.add(new Probe("U+0660 windows-user", "C:\\Users\\al\u0660ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u0660ice rest", 0));
    probes.add(new Probe("U+1D7CE before-path", "a\ud835\udfce/home/x", false, false, "a\ud835\udfce/home/x", 0, "a\ud835\udfce/home/x", 0));
    probes.add(new Probe("U+1D7CE bare-before-path", "\ud835\udfce/home/x", false, false, "\ud835\udfce/home/x", 0, "\ud835\udfce/home/x", 0));
    probes.add(new Probe("U+1D7CE before-dotless-email", "x\ud835\udfceuser@localhost", false, false, "x\ud835\udfceuser@localhost", 0, "x\ud835\udfceuser@localhost", 0));
    probes.add(new Probe("U+1D7CE before-email", "x\ud835\udfceuser@example.org", true, true, "x\ud835\udfceuser@example.org", 0, "x\ud835\udfce[email]", 1));
    probes.add(new Probe("U+1D7CE inside-path-segment", "/home/al\ud835\udfceice/x tail", true, true, "[path] tail", 1, "/home/al\ud835\udfceice/x tail", 0));
    probes.add(new Probe("U+1D7CE after-path", "/home/alice\ud835\udfcetail more", true, true, "[path] more", 1, "/home/alice\ud835\udfcetail more", 0));
    probes.add(new Probe("U+1D7CE strict-segment", "home/al\ud835\udfceice/x", true, false, "home/al\ud835\udfceice/x", 0, "home/al\ud835\udfceice/x", 0));
    probes.add(new Probe("U+1D7CE after-dotless-host", "user@localhost\ud835\udfcez", false, false, "user@localhost\ud835\udfcez", 0, "user@localhost\ud835\udfcez", 0));
    probes.add(new Probe("U+1D7CE windows-user", "C:\\Users\\al\ud835\udfceice rest", true, true, "[path] rest", 1, "C:\\Users\\al\ud835\udfceice rest", 0));
    probes.add(new Probe("U+E0100 before-path", "a\udb40\udd00/home/x", false, true, "a\udb40\udd00[path]", 1, "a\udb40\udd00/home/x", 0));
    probes.add(new Probe("U+E0100 bare-before-path", "\udb40\udd00/home/x", false, true, "\udb40\udd00[path]", 1, "\udb40\udd00/home/x", 0));
    probes.add(new Probe("U+E0100 before-dotless-email", "x\udb40\udd00user@localhost", true, true, "x\udb40\udd00user@localhost", 0, "x\udb40\udd00[email]", 1));
    probes.add(new Probe("U+E0100 before-email", "x\udb40\udd00user@example.org", true, true, "x\udb40\udd00user@example.org", 0, "x\udb40\udd00[email]", 1));
    probes.add(new Probe("U+E0100 inside-path-segment", "/home/al\udb40\udd00ice/x tail", true, true, "[path] tail", 1, "/home/al\udb40\udd00ice/x tail", 0));
    probes.add(new Probe("U+E0100 after-path", "/home/alice\udb40\udd00tail more", true, true, "[path] more", 1, "/home/alice\udb40\udd00tail more", 0));
  }

  private static void part4(List<Probe> probes) {
    probes.add(new Probe("U+E0100 strict-segment", "home/al\udb40\udd00ice/x", true, false, "home/al\udb40\udd00ice/x", 0, "home/al\udb40\udd00ice/x", 0));
    probes.add(new Probe("U+E0100 after-dotless-host", "user@localhost\udb40\udd00z", true, true, "user@localhost\udb40\udd00z", 0, "[email]\udb40\udd00z", 1));
    probes.add(new Probe("U+E0100 windows-user", "C:\\Users\\al\udb40\udd00ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\udb40\udd00ice rest", 0));
    probes.add(new Probe("U+10FFFF before-path", "a\udbff\udfff/home/x", false, true, "a\udbff\udfff[path]", 1, "a\udbff\udfff/home/x", 0));
    probes.add(new Probe("U+10FFFF bare-before-path", "\udbff\udfff/home/x", false, true, "\udbff\udfff[path]", 1, "\udbff\udfff/home/x", 0));
    probes.add(new Probe("U+10FFFF before-dotless-email", "x\udbff\udfffuser@localhost", true, true, "x\udbff\udfffuser@localhost", 0, "x\udbff\udfff[email]", 1));
    probes.add(new Probe("U+10FFFF before-email", "x\udbff\udfffuser@example.org", true, true, "x\udbff\udfffuser@example.org", 0, "x\udbff\udfff[email]", 1));
    probes.add(new Probe("U+10FFFF inside-path-segment", "/home/al\udbff\udfffice/x tail", true, true, "[path] tail", 1, "/home/al\udbff\udfffice/x tail", 0));
    probes.add(new Probe("U+10FFFF after-path", "/home/alice\udbff\udffftail more", true, true, "[path] more", 1, "/home/alice\udbff\udffftail more", 0));
    probes.add(new Probe("U+10FFFF strict-segment", "home/al\udbff\udfffice/x", true, false, "home/al\udbff\udfffice/x", 0, "home/al\udbff\udfffice/x", 0));
    probes.add(new Probe("U+10FFFF after-dotless-host", "user@localhost\udbff\udfffz", true, true, "user@localhost\udbff\udfffz", 0, "[email]\udbff\udfffz", 1));
    probes.add(new Probe("U+10FFFF windows-user", "C:\\Users\\al\udbff\udfffice rest", true, true, "[path] rest", 1, "C:\\Users\\al\udbff\udfffice rest", 0));
    probes.add(new Probe("U+00E9 before-path", "a\u00e9/home/x", false, false, "a\u00e9/home/x", 0, "a\u00e9/home/x", 0));
    probes.add(new Probe("U+00E9 bare-before-path", "\u00e9/home/x", false, false, "\u00e9/home/x", 0, "\u00e9/home/x", 0));
    probes.add(new Probe("U+00E9 before-dotless-email", "x\u00e9user@localhost", false, false, "x\u00e9user@localhost", 0, "x\u00e9user@localhost", 0));
    probes.add(new Probe("U+00E9 before-email", "x\u00e9user@example.org", true, true, "x\u00e9user@example.org", 0, "x\u00e9[email]", 1));
    probes.add(new Probe("U+00E9 inside-path-segment", "/home/al\u00e9ice/x tail", true, true, "[path] tail", 1, "/home/al\u00e9ice/x tail", 0));
    probes.add(new Probe("U+00E9 after-path", "/home/alice\u00e9tail more", true, true, "[path] more", 1, "/home/alice\u00e9tail more", 0));
    probes.add(new Probe("U+00E9 strict-segment", "home/al\u00e9ice/x", true, false, "home/al\u00e9ice/x", 0, "home/al\u00e9ice/x", 0));
    probes.add(new Probe("U+00E9 after-dotless-host", "user@localhost\u00e9z", false, false, "user@localhost\u00e9z", 0, "user@localhost\u00e9z", 0));
    probes.add(new Probe("U+00E9 windows-user", "C:\\Users\\al\u00e9ice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u00e9ice rest", 0));
    probes.add(new Probe("U+00DF before-path", "a\u00df/home/x", false, false, "a\u00df/home/x", 0, "a\u00df/home/x", 0));
    probes.add(new Probe("U+00DF bare-before-path", "\u00df/home/x", false, false, "\u00df/home/x", 0, "\u00df/home/x", 0));
    probes.add(new Probe("U+00DF before-dotless-email", "x\u00dfuser@localhost", false, false, "x\u00dfuser@localhost", 0, "x\u00dfuser@localhost", 0));
    probes.add(new Probe("U+00DF before-email", "x\u00dfuser@example.org", true, true, "x\u00dfuser@example.org", 0, "x\u00df[email]", 1));
    probes.add(new Probe("U+00DF inside-path-segment", "/home/al\u00dfice/x tail", true, true, "[path] tail", 1, "/home/al\u00dfice/x tail", 0));
    probes.add(new Probe("U+00DF after-path", "/home/alice\u00dftail more", true, true, "[path] more", 1, "/home/alice\u00dftail more", 0));
    probes.add(new Probe("U+00DF strict-segment", "home/al\u00dfice/x", true, false, "home/al\u00dfice/x", 0, "home/al\u00dfice/x", 0));
    probes.add(new Probe("U+00DF after-dotless-host", "user@localhost\u00dfz", false, false, "user@localhost\u00dfz", 0, "user@localhost\u00dfz", 0));
    probes.add(new Probe("U+00DF windows-user", "C:\\Users\\al\u00dfice rest", true, true, "[path] rest", 1, "C:\\Users\\al\u00dfice rest", 0));
    probes.add(new Probe("U+000B before-path", "a\u000b/home/x", false, true, "a\u000b[path]", 1, "a\u000b/home/x", 0));
    probes.add(new Probe("U+000B bare-before-path", "\u000b/home/x", false, true, "\u000b[path]", 1, "\u000b/home/x", 0));
    probes.add(new Probe("U+000B before-dotless-email", "x\u000buser@localhost", true, true, "x\u000buser@localhost", 0, "x\u000b[email]", 1));
    probes.add(new Probe("U+000B before-email", "x\u000buser@example.org", true, true, "x\u000buser@example.org", 0, "x\u000b[email]", 1));
    probes.add(new Probe("U+000B inside-path-segment", "/home/al\u000bice/x tail", true, true, "[path]\u000bice/x tail", 1, "/home/al\u000bice/x tail", 0));
    probes.add(new Probe("U+000B after-path", "/home/alice\u000btail more", true, true, "[path]\u000btail more", 1, "/home/alice\u000btail more", 0));
    probes.add(new Probe("U+000B strict-segment", "home/al\u000bice/x", false, false, "home/al\u000bice/x", 0, "home/al\u000bice/x", 0));
    probes.add(new Probe("U+000B after-dotless-host", "user@localhost\u000bz", true, true, "user@localhost\u000bz", 0, "[email]\u000bz", 1));
    probes.add(new Probe("U+000B windows-user", "C:\\Users\\al\u000bice rest", true, true, "[path]\u000bice rest", 1, "C:\\Users\\al\u000bice rest", 0));
    probes.add(new Probe("U+000C before-path", "a\u000c/home/x", false, true, "a\u000c[path]", 1, "a\u000c/home/x", 0));
    probes.add(new Probe("U+000C bare-before-path", "\u000c/home/x", false, true, "\u000c[path]", 1, "\u000c/home/x", 0));
    probes.add(new Probe("U+000C before-dotless-email", "x\u000cuser@localhost", true, true, "x\u000cuser@localhost", 0, "x\u000c[email]", 1));
    probes.add(new Probe("U+000C before-email", "x\u000cuser@example.org", true, true, "x\u000cuser@example.org", 0, "x\u000c[email]", 1));
    probes.add(new Probe("U+000C inside-path-segment", "/home/al\u000cice/x tail", true, true, "[path]\u000cice/x tail", 1, "/home/al\u000cice/x tail", 0));
    probes.add(new Probe("U+000C after-path", "/home/alice\u000ctail more", true, true, "[path]\u000ctail more", 1, "/home/alice\u000ctail more", 0));
    probes.add(new Probe("U+000C strict-segment", "home/al\u000cice/x", false, false, "home/al\u000cice/x", 0, "home/al\u000cice/x", 0));
    probes.add(new Probe("U+000C after-dotless-host", "user@localhost\u000cz", true, true, "user@localhost\u000cz", 0, "[email]\u000cz", 1));
    probes.add(new Probe("U+000C windows-user", "C:\\Users\\al\u000cice rest", true, true, "[path]\u000cice rest", 1, "C:\\Users\\al\u000cice rest", 0));
  }

}
