Feature: Referential integrity on deletion

  @RI-13
  Scenario: Deleting a record holder cascades to owned rows and resets their records
    Given a record holder hosts a room and has played a match with another user
    When PostgreSQL deletes the record holder
    Then the holder's participation, hosted room, and its memberships are gone
    And all the holder's texts have no record and use the default ideal time
    And the other user's record and the holderless text are unchanged

  @RI-13
  Scenario: A match prevents deletion of its text
    Given a record holder hosts a room and has played a match with another user
    When PostgreSQL attempts to delete the text within a savepoint
    Then the text and its match retain their original state after rollback
