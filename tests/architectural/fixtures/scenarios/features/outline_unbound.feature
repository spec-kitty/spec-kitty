Feature: Outline whose expansion is unbound
  Scenario Outline: Only the second row is unbound
    When I count <n> things
    Examples:
      | n   |
      | 1   |
      | two |
