@TC-FUNC-06
Feature: Starting a multiplayer race

  Scenario: Both players count down three seconds before receiving the same text
    Given I register a new account in the browser
    And two players are ready to start a race in separate browser contexts
    When the host starts the race
    Then both players see a three-second countdown followed by the same race text
