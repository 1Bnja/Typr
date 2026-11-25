Feature: Room integrity on migrated PostgreSQL

  @RI-06
  Scenario: One player requests admission to two rooms concurrently
    Given two waiting rooms with different hosts
    When one new player requests admission to both rooms concurrently
    Then one admission succeeds and PostgreSQL stores only one membership for that player

  @RI-07
  Scenario: PostgreSQL enforces unique room codes
    Given two waiting rooms with different hosts
    Then PostgreSQL rejects changing one room code to the other room's code

  @RI-07
  Scenario: Concurrent admissions compete for the last seat
    Given a waiting room with nine members
    When two new players request admission to the room concurrently
    Then one admission succeeds and the room has exactly ten members

  @RI-07
  Scenario: A new player cannot enter a live race
    Given a live race with two signed-in members
    Then a new player's admission is refused and the live roster is unchanged

  @RI-08
  Scenario: A member cannot close the room and the host can leave
    Given a room with two signed-in members
    When the member requests to close the room
    Then the request is forbidden and the waiting room is unchanged
    And PostgreSQL cascades a room deletion to its memberships
    When the host leaves the room
    Then the room and its memberships are gone
