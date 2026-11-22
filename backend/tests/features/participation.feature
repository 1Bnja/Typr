Feature: Completed matches preserve participation integrity

  @RI-03 @RI-04
  Scenario: Practice is recorded only for the signed-in player and without a room
    Given two signed-in practice players
    When the first player submits practice with the second player's user ID
    Then the client-supplied owner is rejected without recording a match
    When the first player submits the same practice without an owner field
    Then one solo participation exists for the signed-in player and has no room

  @RI-04 @RI-05
  Scenario: A completed race stores exactly one participation per player
    Given a live race with two signed-in members
    When both members complete the race
    Then the game is linked to the live room and has one participation per player
    And PostgreSQL rejects a duplicate game and user pair without adding a row
