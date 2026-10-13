"""Generator: turns a checked Scripty program into Python source text.

Each Scripty construct maps to exactly one Python construct, and each
statement becomes exactly one Python line:

    let x = 5          ->   x = 5
    show x             ->   print(x)
    echo("Hello")      ->   print('Hello')

Design choices:

- Division is TRUE division: `7 / 2` is 3.5 and `4 / 2` is 2.0 (Python's `/`).
- Text is written with `repr`, so quotes and special characters are safe.
- The tree structure is kept exactly: every operation nested inside another
  one gets its own parentheses, e.g. `1 + 2 * 3` becomes `1 + (2 * 3)`.
- A Scripty variable that would clash with Python (a Python keyword such as
  `class`, or `print`) gets `_scy` added to its name in the generated code.

`generate` returns the Python source and a line map: a dict from each
Python line number to the Scripty line it came from. The runner uses it to
report runtime errors on the right Scripty line.
"""

import keyword

from ast_nodes import (BinaryOp, Echo, Expression, Let, Name, Negate, Number,
                       Program, Show, Statement, Text)

# Names that cannot be used as-is in the generated Python.
_RESERVED = {"print"}


def generate(program: Program) -> tuple[str, dict[int, int]]:
    """Return (python_source, line_map) for a program."""
    lines: list[str] = []
    line_map: dict[int, int] = {}
    for statement in program.statements:
        lines.append(_statement(statement))
        line_map[len(lines)] = statement.line  # Python lines start at 1
    source = "\n".join(lines) + "\n" if lines else ""
    return source, line_map


def python_name(name: str) -> str:
    """The Python variable name used for a Scripty variable name."""
    if keyword.iskeyword(name) or name in _RESERVED:
        return name + "_scy"
    return name


def _statement(statement: Statement) -> str:
    if isinstance(statement, Let):
        return f"{python_name(statement.name)} = {_expression(statement.value)}"
    if isinstance(statement, (Show, Echo)):
        return f"print({_expression(statement.value)})"
    raise TypeError(f"Cannot generate code for {statement!r}")  # internal


def _expression(expression: Expression, nested: bool = False) -> str:
    if isinstance(expression, Number):
        return repr(expression.value)
    if isinstance(expression, Text):
        return repr(expression.value)
    if isinstance(expression, Name):
        return python_name(expression.name)
    if isinstance(expression, Negate):
        return "-" + _expression(expression.operand, nested=True)
    if isinstance(expression, BinaryOp):
        left = _expression(expression.left, nested=True)
        right = _expression(expression.right, nested=True)
        text = f"{left} {expression.op} {right}"
        return f"({text})" if nested else text
    raise TypeError(f"Cannot generate code for {expression!r}")  # internal
