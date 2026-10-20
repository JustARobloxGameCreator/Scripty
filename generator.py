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
    a[1]               ->   get_at(a, 1)
    a[1] = 9           ->   set_at(a, 1, 9)
    class Dog:         ->   class Dog:
    class Puppy(Dog):  ->   class Puppy(Dog):
    function init(self, name):  ->   def __init__(self, name):   (in a class)
    d.name             ->   d.name
    d.name = "Max"     ->   d.name = 'Max'
    d.speak(1)         ->   d.speak(1)
    super.init(1)      ->   super().__init__(1)
    Dog("Rex", 3)      ->   Dog('Rex', 3)

Blocks are indented with 4 spaces, like in Scripty.

Design choices (true division, repr text, `_scy` renames, how a dot is
written): see docs/architecture.md, section "Generator".

`generate` returns the Python source and a line map: a dict from each
Python line number to the Scripty line it came from. The runner uses it to
report runtime errors on the right Scripty line.
"""

import keyword

from ast_nodes import (LIST_METHODS, Assign, AssignAttribute, AssignIndex,
                       Attribute, BinaryOp, Call, CallStatement, ClassDef,
                       Compare, Echo, Expression, For, Function, Give, If,
                       Index, Let, ListLiteral, MethodCall, MethodStatement,
                       Name, Negate, Number, Program, Show, Statement, Text)

# Names that cannot be used as-is in the generated Python.
_RESERVED = {"print", "remove_all", "pop_at", "get_at", "set_at",
             "call_action", "get_attr"}


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
    for index, statement in enumerate(statements):
        if isinstance(statement, ClassDef):
            _class(statement, level, lines, line_map)
            if index < len(statements) - 1:
                lines.append("")  # a blank line after the class
        elif isinstance(statement, Function):
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


def _class(cls: ClassDef, level: int, lines: list[str],
           line_map: dict[int, int]) -> None:
    header = f"class {python_name(cls.name)}"
    if cls.parent is not None:
        header += f"({python_name(cls.parent)})"
    _add(header + ":", level, cls.line, lines, line_map)
    for index, method in enumerate(cls.methods):
        if index > 0:
            lines.append("")  # a blank line between actions
        params = ", ".join(python_name(p) for p in method.params)
        _add(f"def {_action_name(method.name)}({params}):", level + 1,
             method.line, lines, line_map)
        _block(method.body, level + 2, lines, line_map)


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


def display_name(python: str) -> str:
    """The Scripty name for a Python name (undoes python_name)."""
    plain = python.removesuffix("_scy")
    if plain != python and python_name(plain) == python:
        return plain
    return python


def _action_name(name: str) -> str:
    """The Python name of an action: `init` is Python's `__init__`."""
    return "__init__" if name == "init" else python_name(name)


def _statement(statement: Statement) -> str:
    if isinstance(statement, Let):
        return f"{python_name(statement.name)} = {_expression(statement.value)}"
    if isinstance(statement, Assign):
        return f"{python_name(statement.name)} = {_expression(statement.value)}"
    if isinstance(statement, AssignAttribute):
        return (f"{_expression(statement.target)}."
                f"{python_name(statement.name)} = "
                f"{_expression(statement.value)}")
    if isinstance(statement, AssignIndex):
        return (f"set_at({python_name(statement.target.name)}, "
                f"{_expression(statement.index)}, "
                f"{_expression(statement.value)})")
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
        return _method_call(statement.call, as_value=False)
    raise TypeError(f"Cannot generate code for {statement!r}")  # internal


def _method_call(call: MethodCall, as_value: bool) -> str:
    """Write a.pop(1), d.speak(1), super.init(1)... see the module notes."""
    target = _expression(call.target)
    args = ", ".join(_expression(arg) for arg in call.args)
    if call.target_kind == "super":
        return f"super().{_action_name(call.method)}({args})"
    if call.target_kind == "object":
        return f"{target}.{_action_name(call.method)}({args})"
    if (call.method in LIST_METHODS and len(call.args) == 1
            and (call.target_kind == "list" or not as_value)):
        argument = _expression(call.args[0])
        if call.method == "remove":
            return f"remove_all({target}, {argument}, {call.line})"
        return f"pop_at({target}, {argument})"
    text = (f"call_action({target}, {call.method!r}, [{args}], "
            f"{call.line}")
    return text + (", True)" if as_value else ")")


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
    if isinstance(expression, Attribute):
        target = _expression(expression.target)
        if expression.target_kind == "object":
            return f"{target}.{python_name(expression.name)}"
        return f"get_attr({target}, {expression.name!r})"
    if isinstance(expression, MethodCall):
        return _method_call(expression, as_value=True)
    if isinstance(expression, Index):
        return (f"get_at({_expression(expression.target)}, "
                f"{_expression(expression.index)})")
    if isinstance(expression, Negate):
        return "-" + _expression(expression.operand, nested=True)
    if isinstance(expression, BinaryOp):
        left = _expression(expression.left, nested=True)
        right = _expression(expression.right, nested=True)
        text = f"{left} {expression.op} {right}"
        return f"({text})" if nested else text
    raise TypeError(f"Cannot generate code for {expression!r}")  # internal
