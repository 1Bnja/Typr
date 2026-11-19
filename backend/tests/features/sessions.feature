@auth @sessions @RI-14
Feature: Protected HTTP sessions

  Scenario Outline: Invalid session
    Given a logged-in fixture with a "<credential>" credential
    When it requests a private profile and tries to create a room
    Then both requests return only a bearer 401 and no room is created

    Examples:
      | credential       |
      | absent           |
      | invalid          |
      | tampered         |
      | expired JWT      |
      | idle-expired     |
      | absolute-expired |
      | revoked          |
      | nonexistent user |
      | legacy           |
      | unknown session  |
      | mismatched user  |

  Scenario: Reads do not renew a session
    Given a logged-in fixture with a "valid" credential
    When it reads its profile just before the idle deadline
    Then it is rejected at the original deadline and a fresh login works
