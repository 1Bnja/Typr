"""Input errors that interrupt the text processing chain."""


class TextValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class TextDatabaseError(RuntimeError):
    """Database operation failed; driver details remain in the exception cause."""

    def __init__(self, operation: str) -> None:
        super().__init__(f"Text database {operation} failed.")
        self.code = "database_error"
        self.operation = operation
