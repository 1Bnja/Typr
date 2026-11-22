Feature: Administering multiplayer rooms

  @TC-FUNC-16
  Scenario: A registered player creates and hosts a waiting room
    Given I register a new account in the browser
    And I do not belong to a room
    When I select the room type, language, difficulty, rounds, and time limit and create the room
    Then the new room is waiting and lists me as its host and member
    And its unique access code opens that room

  @TC-FUNC-18
  Scenario: The host updates the rules of a waiting room
    Given I register a new account in the browser
    And I host a waiting room
    When I change the language, difficulty, rounds, and time limit through the lobby
    Then the updated rules persist and are visible after reloading the waiting lobby

  @TC-FUNC-20
  Scenario: The host removes a player from a waiting room
    Given I register a new account in the browser
    And I host a waiting room
    And another player belongs to the room in a separate browser context
    When I remove that player through the lobby
    Then the player is removed from the host's roster
    And the removed player is disconnected and no longer belongs to the room

  @TC-FUNC-23
  Scenario: A player joins a waiting room with a valid code
    Given I register a new account in the browser
    And I host a waiting room
    And another player belongs to no room and the waiting room has fewer than 10 players
    When that player enters the valid room code and submits the join form
    Then that player joins the waiting room as a member without host permissions
    And the joining player sees the other members and the room settings

  @TC-FUNC-24
  Scenario: A player cannot join a room with an invalid code
    Given I register a new account in the browser
    And I do not belong to a room
    When I submit a code that does not match any available room
    Then the join is rejected without navigation or a membership change
    And the join form displays "That room code is not valid."

  @TC-FUNC-27
  Scenario: A member confirms readiness in a waiting room
    Given I register a new account in the browser
    And I host a waiting room
    And a not-ready member is viewing my waiting room in a separate browser context
    When the member presses the ready button
    Then the member is registered as ready
    And the host sees that member's updated ready status
