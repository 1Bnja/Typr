@HU-04 @ranking
Feature: The monthly ranking filters update the table without reloading the page

  Background:
    Given I register a new account in the browser
    And I start an individual practice test
    When I type the whole practice text correctly
    And I open the monthly ranking

  @TC-FUNC-10
  Scenario: Changing the language filter refreshes the table without reloading
    Given the ranking lists my result
    When I switch the language filter to English
    Then the table refreshes without reloading the page
    And my result is no longer listed

  @TC-FUNC-12
  Scenario: A category without matches shows the empty state
    When I switch the difficulty filter to Hard
    Then the ranking says the first place is still open
