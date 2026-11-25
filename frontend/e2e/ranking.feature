Feature: Monthly ranking filters

  @TC-FUNC-10
  Scenario: Changing difficulty and language replaces the ranking in the same document
    Given distinct practice results for Easy Spanish, Medium Spanish and Medium English
    And I register a new account in the browser
    When I open the monthly ranking for the seeded month
    Then only "rank_easy_es" appears in the ranking
    When I select the "Medium" ranking difficulty
    Then only "rank_medium_es" appears in the ranking
    When I select the "English" ranking language
    Then only "rank_medium_en" appears in the ranking
    And the ranking remains in the original document without a navigation request

  @TC-FUNC-12
  Scenario: A valid empty category displays the required empty message
    Given a completed Hard Spanish result but no Hard English result
    And I register a new account in the browser
    When I open the monthly ranking for the seeded month
    And I select the "Hard" ranking difficulty
    Then only "rank_hard_es" appears in the ranking
    When I select the "English" ranking language
    Then the successful ranking response is empty and no table or error is displayed
    And the empty ranking message is exactly "Aún no hay partidas para esta categoría"
