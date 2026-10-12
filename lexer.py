"""Lexer: turns Scripty source text into a list of tokens.

Rules (v0.1):
- Keywords: let, show, echo.
- Names: letters, digits and underscores, not starting with a digit.
- Numbers: 5 or 3.14 (the value is an int or a float).
- Text: written in double quotes on a single line, e.g. "Hello".
- Operators: + - * / =   Parentheses: ( )
- Comments: from # to the end of the line are ignored.
- Spaces and tabs are ignored. Blank lines produce no tokens.
- Each non-blank line ends with a NEWLINE token, so the parser can tell
  where one statement ends and the next begins.
"""

import re
from typing import NamedTuple

from errors import ScriptyError

KEYWORDS = {"let", "show", "echo"}

# Token kinds
KEYWORD = "KEYWORD"
NAME = "NAME"
NUMBER = "NUMBER"
TEXT = "TEXT"
OPERATOR = "OPERATOR"  # + - * / =
LPAREN = "LPAREN"
RPAREN = "RPAREN"
NEWLINE = "NEWLINE"


class Token(NamedTuple):
    kind: str
    value: object  # str for most kinds, int/float for NUMBER
    line: int


_NUMBER = re.compile(r"\d+(\.\d+)?")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPERATORS = "+-*/="


def tokenize(source: str) -> list[Token]:
    """Split source text into tokens. Raises ScriptyError on bad input."""
    tokens: list[Token] = []
    for line_number, line in enumerate(source.splitlines(), start=1):
        line_tokens = _tokenize_line(line, line_number)
        if line_tokens:
            tokens.extend(line_tokens)
            tokens.append(Token(NEWLINE, "\n", line_number))
    return tokens


def _tokenize_line(line: str, line_number: int) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(line):
        char = line[pos]

        if char in " \t":
            pos += 1
        elif char == "#":
            break  # comment: ignore the rest of the line
        elif char == '"':
            end = line.find('"', pos + 1)
            if end == -1:
                raise ScriptyError(
                    'This text starts with a " but never ends. '
                    'Did you forget the closing " ?',
                    line_number,
                )
            tokens.append(Token(TEXT, line[pos + 1 : end], line_number))
            pos = end + 1
        elif match := _NUMBER.match(line, pos):
            text = match.group()
            value = float(text) if match.group(1) else int(text)
            tokens.append(Token(NUMBER, value, line_number))
            pos = match.end()
        elif match := _NAME.match(line, pos):
            word = match.group()
            kind = KEYWORD if word in KEYWORDS else NAME
            tokens.append(Token(kind, word, line_number))
            pos = match.end()
        elif char in _OPERATORS:
            tokens.append(Token(OPERATOR, char, line_number))
            pos += 1
        elif char == "(":
            tokens.append(Token(LPAREN, char, line_number))
            pos += 1
        elif char == ")":
            tokens.append(Token(RPAREN, char, line_number))
            pos += 1
        else:
            raise ScriptyError(
                f'I don\'t know what "{char}" is. '
                "Scripty doesn't use that character here.",
                line_number,
            )
    return tokens
