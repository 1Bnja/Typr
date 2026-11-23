Feature: Registration
  @TC-FUNC-02
  Scenario: Successful registration signs me in and opens the profile
    Given I open the registration form with valid new account data
    When I submit the registration form
    Then the account is created
    And I land on the profile with an authenticated session

  @TC-FUNC-02
  Scenario Outline: Email conflicts are reported at the email field
    Given an account exists and I open the registration form
    When I submit registration with a <conflict> conflict
    Then the email field reports "Este correo ya está en uso"
    And registration keeps all my entered values

    Examples:
      | conflict |
      | email    |
      | dual     |

  @TC-FUNC-02
  Scenario: A username-only conflict keeps the existing form error
    Given an account exists and I open the registration form
    When I submit registration with a username conflict
    Then the form reports "El usuario ya existe bro" without marking email invalid
    And registration keeps all my entered values

  @TC-FUNC-01 @registration_boundaries
  Scenario Outline: Registration accepts a <field> of <length> characters
    Given I open the registration form
    When I enter a <field> of <length> characters and submit valid remaining fields
    Then registration creates an account and opens the profile

    Examples:
      | field    | length |
      | username | 3      |
      | username | 20     |
      | password | 8      |

  @TC-FUNC-01 @registration_boundaries
  Scenario Outline: Registration rejects a <field> of <length> characters at the field
    Given I open the registration form
    When I enter a <field> of <length> characters and submit valid remaining fields
    Then the <field> field displays a length message mentioning <limit> characters
    And registration keeps all my entered values

    Examples:
      | field    | length | limit |
      | username | 2      | 3     |
      | username | 21     | 20    |
      | password | 7      | 8     |
