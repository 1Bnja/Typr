@auth @room_sessions @RI-14
Feature: Room sockets follow the server session lifecycle

  Scenario Outline: A room member cannot connect with an ended session
    Given a room with two signed-in members
    When the host session ends by <reason> before connecting
    Then the room handshake closes as unauthorized

    Examples:
      | reason          |
      | logout          |
      | idle expiry     |
      | absolute expiry |

  Scenario: Polls and pings do not save a silent host socket from idle expiry
    Given a room with two signed-in members
    And both members are connected
    When the host polls and sends a ping just before idle expiry
    And the host reaches idle expiry while silent
    Then only the host socket closes as unauthorized
    And the peer can still change readiness

  Scenario: Logging out closes an already connected silent socket
    Given a room with two signed-in members
    And both members are connected
    When the host logs out without sending another frame
    Then only the host socket closes as unauthorized
    And the peer can still change readiness

  Scenario: Only advancing race progress renews within the established cadence
    Given a live race with two signed-in members
    When the host advances near idle expiry
    Then its idle deadline moves by fifteen minutes from receipt
    And further advances respect the one-minute cadence
    And repeated progress does not renew

  Scenario: Advancing race progress cannot extend the absolute deadline
    Given a live race with a sixteen-minute host session
    When the host advances near idle expiry
    Then its renewal is capped by absolute expiry
    And its socket closes at absolute expiry while the peer stays connected
    And the peer can finish the race after the host disconnects
