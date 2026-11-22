@ranking @HU-04 @TC-FUNC-11
Feature: The monthly ranking leaves out matches below 75% accuracy

  Scenario Outline: A saved practice match is ranked only when its accuracy is at least 75%
    Given a registered player with a practice text
    When the player finishes the practice text with <mistakes> mistakes
    Then the match appears in the player's practice history
    And the ranking <outcome> the player

    Examples:
      | mistakes | accuracy | outcome       |
      | 1        | 96.7%    | lists         |
      | 12       | 70.7%    | does not list |
