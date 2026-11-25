Feature: Personal statistics

  Background:
    Given I register a new account in the browser

  @TC-FUNC-13
  Scenario: The speed chart shows the latest 30 matches in chronological order
    Given my stats fixture contains 35 finished matches
    When I open my personal statistics
    Then the speed chart shows only the latest 30 matches, oldest to newest

  @TC-FUNC-14
  Scenario: The history shows practice and multiplayer match details
    Given my stats fixture contains 2 finished matches
    When I open my personal statistics
    Then the API and match history show the expected details for both modes

  @TC-FUNC-15
  Scenario: A new account without matches sees the empty stats view
    When I open my personal statistics
    Then I see the first-match guidance instead of a chart or history
