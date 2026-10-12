"""Parser: turns tokens into an AST (see ast_nodes.py).

Grammar (v0.1):

    program    = { statement NEWLINE }
    statement  = "let" NAME "=" expression
               | "show" expression
               | "echo" "(" expression ")"
    expression = term { ("+" | "-") term }
    term       = factor { ("*" | "/") factor }
    factor     = "-" factor | NUMBER | TEXT | NAME | "(" expression ")"

Design choice: unary minus IS supported (`-5`, `-x`, `3 * -2`). It binds
tighter than * and /, so `-2 * 3` means `(-2) * 3`.

`*` and `/` are handled one level deeper than `+` and `-`, which is what
gives them higher precedence. Errors raise ScriptyError with a line number.
"""

from ast_nodes import (BinaryOp, Echo, Expression, Let, Name, Negate, Number,
                       Program, Show, Statement, Text)
from errors import ScriptyError
from lexer import (KEYWORD, LPAREN, NAME, NEWLINE, NUMBER, OPERATOR, RPAREN,
                   TEXT, Token)


def parse(tokens: list[Token]) -> Program:
    """Build a Program from tokens. Raises ScriptyError on bad syntax."""
    return _Parser(tokens).parse_program()


def _describe(token: Token) -> str:
    """Show a token the way the user wrote it, for error messages."""
    if token.kind == NEWLINE:
        return "the end of the line"
    return f'"{token.value}"'


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.last_line = tokens[-1].line if tokens else 1

    # -- helpers -----------------------------------------------------------

    def peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(NEWLINE, "\n", self.last_line)  # safety net

    def advance(self) -> Token:
        token = self.peek()
        self.pos += 1
        return token

    def is_operator(self, *symbols: str) -> bool:
        token = self.peek()
        return token.kind == OPERATOR and token.value in symbols

    # -- statements --------------------------------------------------------

    def parse_program(self) -> Program:
        statements: list[Statement] = []
        while self.pos < len(self.tokens):
            statements.append(self.parse_statement())
        return Program(statements)

    def parse_statement(self) -> Statement:
        token = self.peek()
        if token.kind == KEYWORD and token.value == "let":
            statement = self.parse_let()
        elif token.kind == KEYWORD and token.value == "show":
            statement = self.parse_show()
        elif token.kind == KEYWORD and token.value == "echo":
            statement = self.parse_echo()
        else:
            raise ScriptyError(
                f"I don't understand a line that starts with "
                f"{_describe(token)}. A line must start with let, show "
                "or echo.",
                token.line,
            )
        self.expect_end_of_line()
        return statement

    def parse_let(self) -> Let:
        keyword = self.advance()
        name = self.peek()
        if name.kind != NAME:
            raise ScriptyError(
                "You wrote let but forgot the name of the variable. "
                "Try: let x = 5",
                keyword.line,
            )
        self.advance()
        if not self.is_operator("="):
            raise ScriptyError(
                f'I expected "=" after "{name.value}". '
                f"Try: let {name.value} = 5",
                keyword.line,
            )
        self.advance()
        if self.peek().kind == NEWLINE:
            raise ScriptyError(
                f'"{name.value}" has no value. Write a value after the "=". '
                f"Try: let {name.value} = 5",
                keyword.line,
            )
        return Let(name.value, self.parse_expression(), keyword.line)

    def parse_show(self) -> Show:
        keyword = self.advance()
        if self.peek().kind == NEWLINE:
            raise ScriptyError(
                "show needs something to show. Try: show x", keyword.line
            )
        return Show(self.parse_expression(), keyword.line)

    def parse_echo(self) -> Echo:
        keyword = self.advance()
        if self.peek().kind != LPAREN:
            raise ScriptyError(
                'echo needs parentheses. Try: echo("Hello world!")',
                keyword.line,
            )
        self.advance()
        value = self.parse_expression()
        if self.peek().kind != RPAREN:
            raise ScriptyError(
                'echo is missing its closing ")". '
                'Try: echo("Hello world!")',
                keyword.line,
            )
        self.advance()
        return Echo(value, keyword.line)

    def expect_end_of_line(self) -> None:
        token = self.peek()
        if token.kind == NEWLINE:
            self.advance()
        elif token.kind == RPAREN:
            raise ScriptyError(
                'This ")" has no matching "(". '
                "Did you add one ) too many?",
                token.line,
            )
        else:
            raise ScriptyError(
                f"I did not expect {_describe(token)} here. "
                "Each line holds one statement, and this one was already "
                "complete before it.",
                token.line,
            )

    # -- expressions -------------------------------------------------------

    def parse_expression(self) -> Expression:
        left = self.parse_term()
        while self.is_operator("+", "-"):
            op = self.advance()
            right = self.parse_term()
            left = BinaryOp(op.value, left, right, op.line)
        return left

    def parse_term(self) -> Expression:
        left = self.parse_factor()
        while self.is_operator("*", "/"):
            op = self.advance()
            right = self.parse_factor()
            left = BinaryOp(op.value, left, right, op.line)
        return left

    def parse_factor(self) -> Expression:
        token = self.peek()
        if token.kind == NUMBER:
            self.advance()
            return Number(token.value, token.line)
        if token.kind == TEXT:
            self.advance()
            return Text(token.value, token.line)
        if token.kind == NAME:
            self.advance()
            return Name(token.value, token.line)
        if self.is_operator("-"):
            self.advance()
            return Negate(self.parse_factor(), token.line)
        if token.kind == LPAREN:
            return self.parse_parentheses()
        raise self.missing_value_error(token)

    def parse_parentheses(self) -> Expression:
        opening = self.advance()
        value = self.parse_expression()
        if self.peek().kind != RPAREN:
            raise ScriptyError(
                'This "(" has no matching ")". Did you forget to close it?',
                opening.line,
            )
        self.advance()
        return value

    def missing_value_error(self, token: Token) -> ScriptyError:
        """Explain why a value (number, text or name) was expected."""
        if token.kind == NEWLINE:
            previous = self.tokens[self.pos - 1] if self.pos else None
            if previous and previous.kind == OPERATOR:
                return ScriptyError(
                    f'There is nothing after "{previous.value}". '
                    f"Write a value after it, like: 5 {previous.value} 2",
                    token.line,
                )
            return ScriptyError(
                "I expected a value (a number, text or name) here, "
                "but the line ended.",
                token.line,
            )
        return ScriptyError(
            f"I did not expect {_describe(token)} here. "
            "I expected a value (a number, text or name).",
            token.line,
        )
