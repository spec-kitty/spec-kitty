# A comment before the Feature line.
@promise:PR-FIX-001 @smoke
Feature: A valid feature that exercises every supported construct
  Free-form description line one.
  Free-form description line two.

  Background:
    Given a thing named "background"

  Scenario: Plain scenario with And, But and star steps
    Given a thing named "a"
    And a thing named 'single quoted'
    But a thing named ""
    * a thing named "star"
    When I count 3 things
    Then the word done is shown

  @manual @defect:123 @qa:QA-7.a
  Scenario: Manual scenario with a doc string and a data table
    Given a thing named "doc"
      """
      this line is not a step
      Given neither is this
      """
    And a thing named "ticks"
      ```
      also not a step
      ```
    Then a table is accepted
      | name | value |
      | a    | 1     |

  Rule: A rule groups scenarios
    @promise:PR-FIX-002
    Scenario Outline: Outline expands per examples row
      Given a thing named "<who>"
      When I count <n> things
      Then the word <w> is shown

      Examples: first block
        | who   | n  | w    |
        | alice | 1  | ok   |
        | bob   | -2 | fine |

      Examples:
        | who | n | w |
        | cy  | 3 | yes |

  Scenario: Escaped quotes and literal punctuation
    Given a quote "inside" a step
    And a literal (with parens) and a dot.
