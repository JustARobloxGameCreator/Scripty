"""Checker: finds meaning errors in a parsed program.

The parser only knows whether the code has the right shape. The checker
knows whether it makes sense. It catches:

- using a variable that was never declared (`show z` with no `let z = ...`)
- declaring the same variable twice

Rule for v0.1: a name can only be declared once. This may be relaxed when
reassignment is added to the language.

The checker walks the tree top to bottom and remembers which names are
declared so far (and on which line). It never changes the tree.
"""

from ast_nodes import (BinaryOp, Echo, Expression, Let, Name, Negate, Number,
                       Program, Show, Text)
from errors import ScriptyError


def check(program: Program) -> Program:
    """Return the program unchanged if it is fine, else raise ScriptyError."""
    declared: dict[str, int] = {}  # variable name -> line it was declared on
    for statement in program.statements:
        _check_statement(statement, declared)
    return program


def _check_statement(statement, declared: dict[str, int]) -> None:
    if isinstance(statement, Let):
        # Check the value first, so `let x = x + 1` fails when x is new.
        _check_expression(statement.value, declared)
        if statement.name in declared:
            raise ScriptyError(
                f'"{statement.name}" is already declared on line '
                f"{declared[statement.name]}. A name can only be declared "
                "once, so pick a different name.",
                statement.line)
        declared[statement.name] = statement.line
    elif isinstance(statement, (Show, Echo)):
        _check_expression(statement.value, declared)


def _check_expression(expression: Expression, declared: dict[str, int]) -> None:
    if isinstance(expression, Name):
        if expression.name not in declared:
            raise ScriptyError(
                f'I don\'t know what "{expression.name}" is. '
                f"Did you forget to write: let {expression.name} = ...",
                expression.line)
    elif isinstance(expression, BinaryOp):
        _check_expression(expression.left, declared)
        _check_expression(expression.right, declared)
    elif isinstance(expression, Negate):
        _check_expression(expression.operand, declared)
    # Number and Text are always fine.
