@TC-FUNC-02
Feature: Registration
  Scenario: Successful registration signs me in and opens the dashboard
    Given I open the registration form with valid new account data
    When I submit the registration form
    Then the account is created
    And I land on the dashboard with an authenticated session

  Scenario Outline: Email conflicts are reported at the email field
    Given an account exists and I open the registration form
    When I submit registration with a <conflict> conflict
    Then the email field reports "Este correo ya está en uso"
    And registration keeps all my entered values

    Examples:
      | conflict |
      | email    |
      | dual     |

  Scenario: A username-only conflict keeps the existing form error
    Given an account exists and I open the registration form
    When I submit registration with a username conflict
    Then the form reports "El usuario ya existe bro" without marking email invalid
    And registration keeps all my entered values
