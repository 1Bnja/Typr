@practice @HU-02 @TC-FUNC-03
Feature: Individual practice results are saved to the player's own history

  Scenario: Finishing a practice test returns the final metrics
    Given a registered player with a practice text
    When the player finishes the practice text with 1 mistake
    Then the response reports the speed, accuracy and score
    And the match appears in the player's practice history

  Scenario: A finished practice test belongs only to the authenticated player
    Given a registered player with a practice text
    And another registered player
    When the player finishes the practice text with 0 mistakes
    Then the match is stored as an individual game without a room
    And it is linked only to the authenticated player
    And it does not appear in the other player's history
