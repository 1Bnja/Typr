@RI-14 @practice-activity
Feature: Practice typing sends minimal session activity

  Scenario: Only real typing sends a notice, at most once a minute
    Given I register a new account in the browser
    When I start a practice test with a controlled clock
    Then advancing the clock without typing sends nothing
    And real typing sends a content-free notice and respects the minute boundary
