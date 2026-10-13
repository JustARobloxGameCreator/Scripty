"""AST nodes: the tree the parser builds and later stages walk.

Statements: Let, Show, Echo, CallStatement, Give, If, Function.
Expressions: Number, Text, Name, BinaryOp, Negate, Call.  A Compare (such
as x > 5) is a condition: it only appears in an if or elif line.  Every node remembers the `line` it came from, so the checker and
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


@dataclass
class Call:
    """A function call, e.g. Add(1, 2). Works as a value or as a statement."""

    name: str
    args: list["Expression"]
    line: int


@dataclass
class Compare:
    """A condition such as x > 5. op is one of == != >= <= > <."""

    op: str
    left: "Expression"
    right: "Expression"
    line: int


Expression = Number | Text | Name | BinaryOp | Negate | Call


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


@dataclass
class CallStatement:
    """A call used as a whole line, e.g. Greet("Ana"). The result is dropped."""

    call: Call
    line: int


@dataclass
class Give:
    """give expr: hand a value back from a function (Python: return)."""

    value: Expression
    line: int


@dataclass
class Branch:
    """One `if` or `elif` part: a condition and the lines inside it."""

    condition: Compare
    body: list["Statement"]
    line: int


@dataclass
class If:
    """An if, any number of elif parts, and an optional else part."""

    branches: list[Branch]  # first is the `if`, the rest are `elif`
    else_body: list["Statement"] | None
    else_line: int
    line: int


@dataclass
class Function:
    name: str
    params: list[str]
    body: list["Statement"]
    line: int


Statement = Let | Show | Echo | CallStatement | Give | If | Function


@dataclass
class Program:
    statements: list[Statement]
