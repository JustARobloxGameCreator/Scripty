"""Lexer: turns Scripty source text into a list of tokens.

Rules:
- Keywords: let, show, echo, function, if, elif, else, give, for, in.
- Names: letters, digits and underscores, not starting with a digit.
- Numbers: 5 or 3.14 (the value is an int or a float).
- Text: written in double quotes on a single line, e.g. "Hello".
- Operators: + - * / =  and the comparisons == != >= <= > <
- Punctuation: ( ) , :
- Comments: from // or # to the end of the line are ignored. A // or #
  inside quoted text is just text. (Scripty has no integer division, so
  // is free to be a comment.)
- Spaces inside a line are ignored. Blank and comment-only lines produce
  no tokens and do not affect indentation.
- Each non-blank line ends with a NEWLINE token, so the parser can tell
  where one statement ends and the next begins.
- Indentation: blocks are indented by exactly 4 spaces per level. When a
  line is indented one level deeper than the line before, an INDENT token
  comes first; when it goes back out, one DEDENT token per level closes
  the blocks (also at the end of the file). Tabs at the start of a line
  are rejected with a friendly error, as are indents that are not a
  multiple of 4 spaces or that jump more than one level at once.
"""

import re
from typing import NamedTuple

from errors import ScriptyError

KEYWORDS = {"let", "show", "echo", "function", "if", "elif", "else", "give",
            "for", "in"}
INDENT_SIZE = 4

# Token kinds
KEYWORD = "KEYWORD"
NAME = "NAME"
NUMBER = "NUMBER"
TEXT = "TEXT"
OPERATOR = "OPERATOR"  # + - * / =  == != >= <= > <
LPAREN = "LPAREN"
RPAREN = "RPAREN"
COMMA = "COMMA"
COLON = "COLON"
NEWLINE = "NEWLINE"
INDENT = "INDENT"
DEDENT = "DEDENT"


class Token(NamedTuple):
    kind: str
    value: object  # str for most kinds, int/float for NUMBER
    line: int


_NUMBER = re.compile(r"\d+(\.\d+)?")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_OPERATORS = "+-*/="
_TWO_CHAR_OPERATORS = ("==", "!=", ">=", "<=")
_ONE_CHAR_COMPARISONS = "<>"


def tokenize(source: str) -> list[Token]:
    """Split source text into tokens. Raises ScriptyError on bad input."""
    tokens: list[Token] = []
    level = 0  # how many blocks deep the previous line was
    last_line = 1
    for line_number, line in enumerate(source.splitlines(), start=1):
        line_tokens = _tokenize_line(line, line_number)
        if not line_tokens:
            continue  # blank or comment-only line
        new_level = _indent_level(line, level, line_number)
        if new_level > level:
            tokens.append(Token(INDENT, "", line_number))
        for _ in range(level - new_level):
            tokens.append(Token(DEDENT, "", line_number))
        level = new_level
        tokens.extend(line_tokens)
        tokens.append(Token(NEWLINE, "\n", line_number))
        last_line = line_number
    for _ in range(level):  # close blocks still open at the end of the file
        tokens.append(Token(DEDENT, "", last_line))
    return tokens


def _indent_level(line: str, previous_level: int, line_number: int) -> int:
    """How many blocks deep a line is (4 spaces = 1 level)."""
    spaces = line[: len(line) - len(line.lstrip(" \t"))]
    if "\t" in spaces:
        raise ScriptyError(
            "This line is indented with a tab. Scripty only accepts spaces "
            f"for indentation: use {INDENT_SIZE} spaces for each level.",
            line_number,
        )
    if len(spaces) % INDENT_SIZE != 0:
        raise ScriptyError(
            f"This line is indented by {len(spaces)} spaces. Indent with "
            f"{INDENT_SIZE} spaces for each level (0, {INDENT_SIZE}, "
            f"{INDENT_SIZE * 2}, ...).",
            line_number,
        )
    level = len(spaces) // INDENT_SIZE
    if level > previous_level + 1:
        raise ScriptyError(
            "This line is indented too far. Indent only one level "
            f"({INDENT_SIZE} spaces) deeper than the line above.",
            line_number,
        )
    return level


def _tokenize_line(line: str, line_number: int) -> list[Token]:
    tokens: list[Token] = []
    pos = 0
    while pos < len(line):
        char = line[pos]

        if char in " \t":
            pos += 1
        elif char == "#" or line.startswith("//", pos):
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
        elif line[pos : pos + 2] in _TWO_CHAR_OPERATORS:
            tokens.append(Token(OPERATOR, line[pos : pos + 2], line_number))
            pos += 2
        elif char in _OPERATORS or char in _ONE_CHAR_COMPARISONS:
            tokens.append(Token(OPERATOR, char, line_number))
            pos += 1
        elif char == "(":
            tokens.append(Token(LPAREN, char, line_number))
            pos += 1
        elif char == ")":
            tokens.append(Token(RPAREN, char, line_number))
            pos += 1
        elif char == ",":
            tokens.append(Token(COMMA, char, line_number))
            pos += 1
        elif char == ":":
            tokens.append(Token(COLON, char, line_number))
            pos += 1
        elif char == "!":
            raise ScriptyError(
                'A "!" on its own means nothing in Scripty. '
                'Did you mean "!=" (not equal)?',
                line_number,
            )
        else:
            raise ScriptyError(
                f'I don\'t know what "{char}" is. '
                "Scripty doesn't use that character here.",
                line_number,
            )
    return tokens
