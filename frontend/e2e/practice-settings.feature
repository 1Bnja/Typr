Feature: Change solo practice settings without losing progress silently

  Scenario Outline: Only an in-progress attempt requires confirmation
    Given a fresh solo practice session at <width> by <height>
    Then changing solo practice settings protects only the in-progress attempt

    Examples:
      | width | height |
      | 1280  | 800    |
      | 375   | 667    |
