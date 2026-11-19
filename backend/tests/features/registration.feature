@auth @postgresql
Feature: Registration preserves unique account identities and protects passwords

  Scenario Outline: Overlapping registrations collide on <identity>
    Given two new registrations that share <identity>
    When both registrations reach the database insert in separate transactions
    Then one request succeeds and the other receives "<detail>" with status 409
    And exactly one matching account is persisted
    And a new unrelated account can still register

    Examples:
      | identity | detail                      |
      | email    | Este correo ya está en uso  |
      | username | El usuario ya existe bro    |
      | both     | Este correo ya está en uso  |

  Scenario: Email conflict takes precedence even when two accounts own the fields
    Given two registered accounts with different emails and usernames
    When a new request uses the email of one and the username of the other
    Then registration returns "Este correo ya está en uso" with status 409

  Scenario: Passwords are stored as bcrypt and never exposed by account endpoints
    When a new account registers, logs in, and requests its profile
    Then its persisted password is a bcrypt hash of the submitted password
    And the register, login, and profile responses omit password material
