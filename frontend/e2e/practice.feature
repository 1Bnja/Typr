@HU-02 @practice
Feature: Individual practice test gives live feedback and a final result

  Background:
    Given I register a new account in the browser
    And I start an individual practice test

  Scenario Outline: Typing a character marks it and updates the live metrics
    When I type a <typed> character at the current position
    Then that character is marked <state>
    And the live speed and accuracy reflect the <typed> input

    Examples:
      | typed     | state     |
      | correct   | correct   |
      | incorrect | incorrect |

  Scenario: Typing the last character finishes and saves the test
    When I type the whole practice text correctly
    Then the results show speed, accuracy and score
    And the match is saved in my history
