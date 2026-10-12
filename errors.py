"""Errors shared by every Scripty stage (lexer, parser, checker, ...)."""


class ScriptyError(Exception):
    """A beginner-friendly error that points at a line of Scripty code."""

    def __init__(self, message: str, line: int) -> None:
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        return f"Error on line {self.line}: {self.message}"
