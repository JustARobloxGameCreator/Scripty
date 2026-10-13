"""Checker: finds meaning errors in a parsed program.

The parser only knows whether the code has the right shape. The checker
knows whether it makes sense. It catches:

- using a variable that was never declared (`show z` with no `let z = ...`)
- declaring the same variable twice
- mixing text and numbers in a calculation (`"a" + 1`, `"a" * "b"`)
- comparing text with a number using > < >= <=
- calling a function that does not exist, or with the wrong number of inputs
- declaring a function twice, or a function and a variable with one name

Scope rules (simple on purpose):

- A name can only be declared once. This may be relaxed when reassignment
  is added to the language. A `let` can never silently reuse a name that
  is already visible, so there is no shadowing.
- The top of the program is the "global" scope.
- A function has its OWN scope. Its inputs (parameters) are declared in it,
  and so is every `let` inside it. A function can NOT see variables from
  outside: pass them in as inputs. Because the scopes are separate, a
  `let x` inside a function does not clash with a `let x` outside.
- The lines inside an if / elif / else branch form a small scope of their
  own: variables made there disappear after the branch ends. They can see
  everything around them, and cannot reuse a name that is already visible.
- Function names live in one list for the whole program. A function is
  visible everywhere; a call at the top of the program must come after the
  `function` lines (it would fail at run time otherwise). Functions may
  call themselves and each other.
- A function name cannot also be a variable or input name.

Type rules (simple, no guessing): every value is a number or text. The
checker tracks the kind of each variable from its `let`. Numbers work with
all of + - * /. Text can only be joined with another text using `+`. Any
other mix is an error. Function inputs and the results of calls have an
UNKNOWN kind: the checker accepts them anywhere and the run-time check
catches mistakes. Conditions: `==` and `!=` may compare anything (different
kinds are simply never equal); `> < >= <=` need two numbers or two texts
(texts compare alphabetically).

A function that has a `give` must give on every path (its last line must be
a `give`, or an if/else where every branch gives), so that a call never
produces "nothing". A function without any `give` can only be called as a
line on its own, not used as a value.

The checker walks the tree top to bottom. It never changes the tree.
"""

from ast_nodes import (BinaryOp, Call, CallStatement, Compare, Echo,
                       Expression, Function, Give, If, Let, Name, Negate,
                       Number, Program, Show, Text)
from errors import ScriptyError

NUMBER_KIND = "number"
TEXT_KIND = "text"
UNKNOWN_KIND = "unknown"  # function inputs and call results

_ORDERING = ("<", ">", "<=", ">=")


class _Scope:
    """The variables visible at one place in the program."""

    def __init__(self, parent: "_Scope | None" = None,
                 function: Function | None = None) -> None:
        self.parent = parent
        # The function this scope belongs to (None = top of the program).
        if function is None and parent is not None:
            function = parent.function
        self.function = function
        self.variables: dict[str, tuple[int, str]] = {}  # name -> (line, kind)

    def find(self, name: str) -> tuple[int, str] | None:
        scope: _Scope | None = self
        while scope is not None:
            if name in scope.variables:
                return scope.variables[name]
            scope = scope.parent
        return None


def check(program: Program) -> Program:
    """Return the program unchanged if it is fine, else raise ScriptyError."""
    _Checker(program).run()
    return program


class _Checker:
    def __init__(self, program: Program) -> None:
        self.program = program
        self.functions: dict[str, Function] = {}
        self.defined: set[str] = set()  # functions whose line was passed
        self.globals = _Scope()

    def run(self) -> None:
        for statement in self.program.statements:
            if isinstance(statement, Function):
                self.register_function(statement)
        for statement in self.program.statements:
            self.check_statement(statement, self.globals)

    # -- functions ---------------------------------------------------------

    def register_function(self, function: Function) -> None:
        if function.name in self.functions:
            raise ScriptyError(
                f'The function "{function.name}" is already defined on '
                f"line {self.functions[function.name].line}. A function "
                "name can only be used once, so pick a different name.",
                function.line)
        self.functions[function.name] = function

    def check_function(self, function: Function) -> None:
        scope = _Scope(function=function)
        for param in function.params:
            self.declare(scope, param, function.line, UNKNOWN_KIND)
        for statement in function.body:
            self.check_statement(statement, scope)
        if _contains_give(function.body) and not _always_gives(function.body):
            raise ScriptyError(
                f'The function "{function.name}" gives a value back in some '
                "cases but not in all of them. Make sure its last line is "
                "a give (or an if / else where every part gives).",
                function.line)
        self.defined.add(function.name)

    # -- statements --------------------------------------------------------

    def check_statement(self, statement, scope: _Scope) -> None:
        if isinstance(statement, Let):
            # Check the value first, so `let x = x + 1` fails when x is new.
            kind = self.check_expression(statement.value, scope)
            self.declare(scope, statement.name, statement.line, kind)
        elif isinstance(statement, (Show, Echo, Give)):
            self.check_expression(statement.value, scope)
        elif isinstance(statement, CallStatement):
            self.check_call(statement.call, scope, as_value=False)
        elif isinstance(statement, If):
            self.check_if(statement, scope)
        elif isinstance(statement, Function):
            self.check_function(statement)

    def check_if(self, node: If, scope: _Scope) -> None:
        for branch in node.branches:
            self.check_condition(branch.condition, scope)
            self.check_block(branch.body, scope)
        if node.else_body is not None:
            self.check_block(node.else_body, scope)

    def check_block(self, body: list, scope: _Scope) -> None:
        inner = _Scope(parent=scope)
        for statement in body:
            self.check_statement(statement, inner)

    def declare(self, scope: _Scope, name: str, line: int, kind: str) -> None:
        if name in self.functions:
            raise ScriptyError(
                f'"{name}" is already the name of a function (line '
                f"{self.functions[name].line}). Pick a different name.",
                line)
        existing = scope.find(name)
        if existing is not None:
            raise ScriptyError(
                f'"{name}" is already declared on line {existing[0]}. '
                "A name can only be declared once, so pick a different "
                "name.", line)
        scope.variables[name] = (line, kind)

    # -- conditions --------------------------------------------------------

    def check_condition(self, condition: Compare, scope: _Scope) -> None:
        left = self.check_expression(condition.left, scope)
        right = self.check_expression(condition.right, scope)
        if condition.op in _ORDERING and {left, right} == {NUMBER_KIND,
                                                          TEXT_KIND}:
            raise ScriptyError(
                f'You can\'t use "{condition.op}" to compare text with a '
                "number. Both sides must be numbers, or both must be text. "
                '(You can use "==" or "!=" to compare anything.)',
                condition.line)

    # -- expressions -------------------------------------------------------

    def check_expression(self, expression: Expression, scope: _Scope) -> str:
        """Check an expression and return its kind."""
        if isinstance(expression, Name):
            return self.check_name(expression, scope)
        if isinstance(expression, BinaryOp):
            left = self.check_expression(expression.left, scope)
            right = self.check_expression(expression.right, scope)
            return _check_operation(expression, left, right)
        if isinstance(expression, Negate):
            kind = self.check_expression(expression.operand, scope)
            if kind == TEXT_KIND:
                raise ScriptyError(
                    "You can't put a minus sign in front of text. "
                    "A minus sign only works with numbers.", expression.line)
            return NUMBER_KIND
        if isinstance(expression, Call):
            return self.check_call(expression, scope, as_value=True)
        if isinstance(expression, Text):
            return TEXT_KIND
        return NUMBER_KIND  # Number

    def check_name(self, name: Name, scope: _Scope) -> str:
        found = scope.find(name.name)
        if found is not None:
            return found[1]
        if name.name in self.functions:
            raise ScriptyError(
                f'"{name.name}" is a function. To use it, call it with '
                f"its inputs, like: {name.name}(...)", name.line)
        if scope.function is not None and self.globals.find(name.name):
            raise ScriptyError(
                f'I don\'t know what "{name.name}" is inside the function '
                f'"{scope.function.name}". A function can only use its own '
                "inputs and the variables made inside it. Add it as an "
                f"input: function {scope.function.name}"
                f"({', '.join(scope.function.params + [name.name])}):",
                name.line)
        raise ScriptyError(
            f"I don't know what \"{name.name}\" is. "
            f"Did you forget to write: let {name.name} = ...", name.line)

    def check_call(self, call: Call, scope: _Scope, as_value: bool) -> str:
        function = self.functions.get(call.name)
        if function is None:
            if scope.find(call.name) is not None:
                raise ScriptyError(
                    f'"{call.name}" is a variable, not a function, so it '
                    "can't be called.", call.line)
            raise ScriptyError(
                f'I don\'t know a function called "{call.name}". Did you '
                f"forget to write: function {call.name}(...):", call.line)
        if scope.function is None and call.name not in self.defined:
            raise ScriptyError(
                f'The function "{call.name}" is used here before it is '
                f"written (it starts on line {function.line}). Move the "
                "function above this line.", call.line)
        wanted, given = len(function.params), len(call.args)
        if wanted != given:
            raise ScriptyError(
                f'The function "{call.name}" needs {_plural(wanted)} '
                f"({', '.join(function.params) or 'none'}), but you gave "
                f"{given}.", call.line)
        for argument in call.args:
            self.check_expression(argument, scope)
        if as_value and not _contains_give(function.body):
            raise ScriptyError(
                f'The function "{call.name}" never gives anything back, so '
                "its result can't be used as a value. Add a give line to "
                f"it, or call it on its own line: {call.name}(...)",
                call.line)
        return UNKNOWN_KIND


def _plural(count: int) -> str:
    return f"{count} input" + ("" if count == 1 else "s")


def _contains_give(body: list) -> bool:
    for statement in body:
        if isinstance(statement, Give):
            return True
        if isinstance(statement, If):
            parts = [branch.body for branch in statement.branches]
            if statement.else_body is not None:
                parts.append(statement.else_body)
            if any(_contains_give(part) for part in parts):
                return True
    return False


def _always_gives(body: list) -> bool:
    """True if running `body` always ends in a give."""
    if not body:
        return False
    last = body[-1]
    if isinstance(last, Give):
        return True
    if isinstance(last, If) and last.else_body is not None:
        parts = [branch.body for branch in last.branches] + [last.else_body]
        return all(_always_gives(part) for part in parts)
    return False


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
    if UNKNOWN_KIND in (left, right):
        # One side is unknown (a function input or a call result): accept
        # it, and work out what we can. Only + works on text, so anything
        # else is a number; a known side tells us the other must match.
        known = right if left == UNKNOWN_KIND else left
        if op != "+":
            if known == TEXT_KIND:
                raise ScriptyError(
                    f"You can't use \"{op}\" with text. Text can only be "
                    'joined with "+", like: "Hello " + "world"',
                    expression.line)
            return NUMBER_KIND
        return known
    raise ScriptyError(
        f"You can't use \"{op}\" to mix text and a number. Both sides must "
        "be numbers, or (with +) both must be text.", expression.line)
