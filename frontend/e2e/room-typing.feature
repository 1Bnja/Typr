@TC-FUNC-07 @room_typing
Feature: Typing mistakes in a multiplayer race

  Scenario: A mistake blocks the cursor and both progress displays until corrected
    Given I register a new account in the browser
    And I start a race with a rival in a separate browser context
    When I type a wrong character
    Then the wrong character is highlighted without moving my caret or increasing either progress display
    When I try the expected character before Backspace
    Then the same mistake still blocks typing and progress
    When I erase the mistake without typing a valid character
    Then the block clears without increasing progress
    When I type the next valid character
    Then both progress displays advance and my cursor advances only for valid input
