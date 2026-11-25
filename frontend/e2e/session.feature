@TC-AUTO-01 @RI-14
Feature: Browser session lifecycle
  Background:
    Given I register a new account in the browser

  @profile_routes
  Scenario: Root and the legacy dashboard resolve to the canonical profile
    Then the profile routes respect session state and replace redirect history

  @TC-FUNC-01
  Scenario: Reload, sign out, go Back and sign in again
    When I reload the profile and the API validates my session
    When I sign out with another tab open and a separate session for my account
    Then only the browser session is revoked
    And the other tab detects the revocation on a protected request and on reload
    Then I can go Back without seeing private data and sign in with a new session

  Scenario: Local sign-out does not wait for revocation
    When my logout request loses connectivity
    Then local sign-out finishes first and warns if revocation cannot be confirmed

  Scenario Outline: Reload validation is temporarily unavailable
    When I reload with a <failure> validation failure
    Then my credentials are retained and the profile stays hidden until retry succeeds

    Examples:
      | failure |
      | network |
      | 503     |

  @invalid_session_reload
  Scenario Outline: Reload rejects an invalid session without exposing private data
    Given my browser session has "<credential>"
    When I reload the profile with the rejected credentials
    Then the API rejects the session and the browser signs out without displaying private data

    Examples:
      | credential                 |
      | an invalid token signature |
      | a deleted account          |
