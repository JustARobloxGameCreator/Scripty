"""AST nodes: the tree the parser builds and later stages walk.

Statements: Let, Show, Echo.  Expressions: Number, Text, Name, BinaryOp,
Negate.  Every node remembers the `line` it came from, so the checker and
the generator can report friendly, line-numbered errors.
"""

from dataclasses import dataclass


@dataclass
class Number:
    value: int | float
    line: int


@dataclass
class Text:
    value: str
    line: int


@dataclass
class Name:
    name: str
    line: int


@dataclass
class BinaryOp:
    op: str  # one of + - * /
    left: "Expression"
    right: "Expression"
    line: int


@dataclass
class Negate:
    """Unary minus, e.g. -x or -(1 + 2)."""

    operand: "Expression"
    line: int


Expression = Number | Text | Name | BinaryOp | Negate


@dataclass
class Let:
    name: str
    value: Expression
    line: int


@dataclass
class Show:
    value: Expression
    line: int


@dataclass
class Echo:
    value: Expression
    line: int


Statement = Let | Show | Echo


@dataclass
class Program:
    statements: list[Statement]
