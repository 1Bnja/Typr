@auth @sessions @RI-14
Feature: Practice activity renews a live HTTP session

  Scenario: Confirmed activity renews idle, but polling and repeated notices do not
    Given a logged-in fixture with a "valid" credential
    When a practice notice arrives 14 minutes after login
    Then its confirmed idle deadline is 29 minutes after login
    And a new notice 30 seconds later does not extend it
    And repeating the original notice two minutes later does not extend it
    And polling before that deadline succeeds but activity at it is rejected

  Scenario: A notice near absolute expiry cannot extend beyond it
    Given a logged-in fixture with a "valid" credential
    When practice activity continues until one minute before absolute expiry
    Then the confirmed deadline is capped and a notice at absolute expiry is rejected

  Scenario: Delayed activity can renew only when received before idle expiry
    Given a logged-in fixture with a "valid" credential
    Then a delayed notice received before expiry uses the server receipt time
    And a newer notice at the minute boundary extends idle once
    And content is not accepted in an activity notice

  Scenario Outline: Invalid sessions cannot be renewed
    Given a logged-in fixture with a "<credential>" credential
    Then a practice notice is rejected

    Examples:
      | credential       |
      | absent           |
      | expired JWT      |
      | revoked          |
      | idle-expired     |
      | mismatched user  |
