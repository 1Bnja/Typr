@RI-14 @active_expiry
Feature: Absolute session expiry during active play

  Scenario: Offline practice warns and ends without saving
    Given I register a new account in the browser
    And I start an active practice attempt near absolute expiry
    When I cross the five-minute boundary offline
    Then I see an expiry warning without losing typing focus
    When the browser reaches the absolute deadline
    Then I am signed out with the notice "Tu sesión ya no es válida. Inicia sesión de nuevo. Tu prueba de práctica no se guardó."
    And no practice attempt was submitted
    And signing in again does not resume play

  Scenario Outline: A racing session ends without interrupting its peer
    Given I register a new account in the browser
    And I enter an active race with a separate peer near absolute expiry
    When I cross the five-minute boundary offline
    Then I see an expiry warning without losing typing focus
    When <ending>
    Then I am signed out with the notice "Your session expired. Sign in again to rejoin the room."
    And the peer can finish the race
    And signing in again does not resume play

    Examples:
      | ending                                    |
      | the browser reaches the absolute deadline |
      | the server revokes my racing session      |
