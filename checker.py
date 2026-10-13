"""Checker: finds meaning errors in a parsed program.

The parser only knows whether the code has the right shape. The checker
knows whether it makes sense. It catches:

- using a variable that was never declared (`show z` with no `let z = ...`)
- declaring the same variable twice
- mixing text and numbers in a calculation (`"a" + 1`, `"a" * "b"`)

Rule for v0.1: a name can only be declared once. This may be relaxed when
reassignment is added to the language.

Type rules (simple, no guessing): every value is a number or text. The
checker tracks the kind of each variable from its `let`. Numbers work with
all of + - * /. Text can only be joined with another text using `+`. Any
other mix is an error. (Runtime errors still catch anything missed.)

The checker walks the tree top to bottom and remembers which names are
declared so far (and on which line). It never changes the tree.
"""

from ast_nodes import (BinaryOp, Echo, Expression, Let, Name, Negate, Number,
                       Program, Show, Text)
from errors import ScriptyError

NUMBER_KIND = "number"
TEXT_KIND = "text"


def check(program: Program) -> Program:
    """Return the program unchanged if it is fine, else raise ScriptyError."""
    declared: dict[str, int] = {}  # variable name -> line it was declared on
    kinds: dict[str, str] = {}  # variable name -> NUMBER_KIND or TEXT_KIND
    for statement in program.statements:
        _check_statement(statement, declared, kinds)
    return program


def _check_statement(statement, declared: dict[str, int],
                     kinds: dict[str, str]) -> None:
    if isinstance(statement, Let):
        # Check the value first, so `let x = x + 1` fails when x is new.
        kind = _check_expression(statement.value, declared, kinds)
        if statement.name in declared:
            raise ScriptyError(
                f'"{statement.name}" is already declared on line '
                f"{declared[statement.name]}. A name can only be declared "
                "once, so pick a different name.",
                statement.line)
        declared[statement.name] = statement.line
        kinds[statement.name] = kind
    elif isinstance(statement, (Show, Echo)):
        _check_expression(statement.value, declared, kinds)


def _check_expression(expression: Expression, declared: dict[str, int],
                      kinds: dict[str, str]) -> str:
    """Check an expression and return its kind (number or text)."""
    if isinstance(expression, Name):
        if expression.name not in declared:
            raise ScriptyError(
                f"I don't know what \"{expression.name}\" is. "
                f"Did you forget to write: let {expression.name} = ...",
                expression.line)
        return kinds[expression.name]
    if isinstance(expression, BinaryOp):
        left = _check_expression(expression.left, declared, kinds)
        right = _check_expression(expression.right, declared, kinds)
        return _check_operation(expression, left, right)
    if isinstance(expression, Negate):
        kind = _check_expression(expression.operand, declared, kinds)
        if kind == TEXT_KIND:
            raise ScriptyError(
                "You can't put a minus sign in front of text. "
                "A minus sign only works with numbers.", expression.line)
        return NUMBER_KIND
    if isinstance(expression, Text):
        return TEXT_KIND
    return NUMBER_KIND  # Number


def _check_operation(expression: BinaryOp, left: str, right: str) -> str:
    op = expression.op
    if left == right == NUMBER_KIND:
        return NUMBER_KIND
    if left == right == TEXT_KIND:
        if op == "+":
            return TEXT_KIND  # joining two texts
        raise ScriptyError(
            f"You can't use \"{op}\" with text. Text can only be joined "
            'with "+", like: "Hello " + "world"', expression.line)
    raise ScriptyError(
        f"You can't use \"{op}\" to mix text and a number. Both sides must "
        "be numbers, or (with +) both must be text.", expression.line)
