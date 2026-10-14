"""Generator: turns a checked Scripty program into Python source text.

Each Scripty construct maps to exactly one Python construct, and each
statement (or header line such as `if`, `elif`, `else`, `for`, `function`)
becomes exactly one Python line:

    let x = 5          ->   x = 5
    x = 6              ->   x = 6
    show x             ->   print(x)
    echo("Hello")      ->   print('Hello')
    function F(a):     ->   def F(a):
    if (a > 1):        ->   if a > 1:
    elif (a == 1):     ->   elif a == 1:
    else:              ->   else:
    for c in "hi":     ->   for c in 'hi':
    give a             ->   return a
    F(1, 2)            ->   F(1, 2)
    [1, 2]             ->   [1, 2]
    max(a)             ->   max(a)      (also min and len)
    sort(a)            ->   a.sort()    (sorts the list itself)
    a.remove("Dog")    ->   remove_all(a, 'Dog', 3)   (3 = the Scripty line)
    a.pop(2)           ->   pop_at(a, 2)

Blocks are indented with 4 spaces, like in Scripty.

Design choices:

- Division is TRUE division: `7 / 2` is 3.5 and `4 / 2` is 2.0 (Python's `/`).
- Text is written with `repr`, so quotes and special characters are safe.
- The tree structure is kept exactly: every operation nested inside another
  one gets its own parentheses, e.g. `1 + 2 * 3` becomes `1 + (2 * 3)`.
- Lists are Python lists. `show a` is still `print(a)`: the runner prints
  lists in the Scripty way (see runner.py), so the generator needs no
  type information.
- `remove_all` and `pop_at` are small helpers that the runner gives to the
  program (see runner.py). `remove_all` needs the Scripty line number to
  write its warning, so the generator passes it as the last input.
- A Scripty variable, function or input name that would clash with Python
  (a Python keyword such as `class`, or `print`) gets `_scy` added to its
  name in the generated code.

`generate` returns the Python source and a line map: a dict from each
Python line number to the Scripty line it came from. The runner uses it to
report runtime errors on the right Scripty line.
"""

import keyword

from ast_nodes import (Assign, BinaryOp, Call, CallStatement, Compare, Echo,
                       Expression, For, Function, Give, If, Let, ListLiteral,
                       MethodStatement, Name, Negate, Number, Program, Show,
                       Statement, Text)

# Names that cannot be used as-is in the generated Python.
_RESERVED = {"print", "remove_all", "pop_at"}


def generate(program: Program) -> tuple[str, dict[int, int]]:
    """Return (python_source, line_map) for a program."""
    lines: list[str] = []
    line_map: dict[int, int] = {}
    _block(program.statements, 0, lines, line_map)
    source = "\n".join(lines) + "\n" if lines else ""
    return source, line_map


def _add(text: str, level: int, scripty_line: int, lines: list[str],
         line_map: dict[int, int]) -> None:
    """Append one Python line and remember which Scripty line it is from."""
    lines.append("    " * level + text)
    line_map[len(lines)] = scripty_line  # Python lines start at 1


def _block(statements: list[Statement], level: int, lines: list[str],
           line_map: dict[int, int]) -> None:
    for statement in statements:
        if isinstance(statement, Function):
            params = ", ".join(python_name(p) for p in statement.params)
            header = f"def {python_name(statement.name)}({params}):"
            _add(header, level, statement.line, lines, line_map)
            _block(statement.body, level + 1, lines, line_map)
        elif isinstance(statement, If):
            _if(statement, level, lines, line_map)
        elif isinstance(statement, For):
            header = (f"for {python_name(statement.name)} in "
                      f"{_expression(statement.iterable)}:")
            _add(header, level, statement.line, lines, line_map)
            _block(statement.body, level + 1, lines, line_map)
        else:
            _add(_statement(statement), level, statement.line, lines,
                 line_map)


def _if(node: If, level: int, lines: list[str],
        line_map: dict[int, int]) -> None:
    for index, branch in enumerate(node.branches):
        word = "if" if index == 0 else "elif"
        condition = _condition(branch.condition)
        _add(f"{word} {condition}:", level, branch.line, lines, line_map)
        _block(branch.body, level + 1, lines, line_map)
    if node.else_body is not None:
        _add("else:", level, node.else_line, lines, line_map)
        _block(node.else_body, level + 1, lines, line_map)


def _condition(condition: Compare) -> str:
    left = _expression(condition.left)
    right = _expression(condition.right)
    return f"{left} {condition.op} {right}"


def python_name(name: str) -> str:
    """The Python variable name used for a Scripty variable name."""
    if keyword.iskeyword(name) or name in _RESERVED:
        return name + "_scy"
    return name


def _statement(statement: Statement) -> str:
    if isinstance(statement, Let):
        return f"{python_name(statement.name)} = {_expression(statement.value)}"
    if isinstance(statement, Assign):
        return f"{python_name(statement.name)} = {_expression(statement.value)}"
    if isinstance(statement, (Show, Echo)):
        return f"print({_expression(statement.value)})"
    if isinstance(statement, Give):
        return f"return {_expression(statement.value)}"
    if isinstance(statement, CallStatement):
        call = statement.call
        if call.name == "sort":  # sort(a) sorts the list itself
            return f"{_expression(call.args[0])}.sort()"
        return _expression(call)
    if isinstance(statement, MethodStatement):
        call = statement.call
        target = python_name(call.target.name)
        argument = _expression(call.args[0])
        if call.method == "remove":
            return f"remove_all({target}, {argument}, {statement.line})"
        return f"pop_at({target}, {argument})"
    raise TypeError(f"Cannot generate code for {statement!r}")  # internal


def _expression(expression: Expression, nested: bool = False) -> str:
    if isinstance(expression, Number):
        return repr(expression.value)
    if isinstance(expression, Text):
        return repr(expression.value)
    if isinstance(expression, Name):
        return python_name(expression.name)
    if isinstance(expression, ListLiteral):
        items = ", ".join(_expression(item) for item in expression.items)
        return f"[{items}]"
    if isinstance(expression, Call):
        args = ", ".join(_expression(arg) for arg in expression.args)
        return f"{python_name(expression.name)}({args})"
    if isinstance(expression, Negate):
        return "-" + _expression(expression.operand, nested=True)
    if isinstance(expression, BinaryOp):
        left = _expression(expression.left, nested=True)
        right = _expression(expression.right, nested=True)
        text = f"{left} {expression.op} {right}"
        return f"({text})" if nested else text
    raise TypeError(f"Cannot generate code for {expression!r}")  # internal
