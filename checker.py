"""Checker: finds meaning errors in a parsed program.

The parser only knows whether the code has the right shape. The checker
knows whether it makes sense. It catches:

- using a variable that was never declared (`show z` with no `let z = ...`)
- declaring the same variable twice (use `name = value` to change it)
- giving a variable a new value (`x = 5`) before it exists, or one of a
  different kind than it had
- using a built-in name (max, min, len, sort) as a variable or function
- using the built-in functions wrongly (wrong number of inputs, not a list)
- mixing lists with numbers or text in a calculation
- mixing text and numbers in a calculation (`"a" + 1`, `"a" * "b"`)
- comparing text with a number using > < >= <=
- calling a function that does not exist, or with the wrong number of inputs
- declaring a function twice, or a function and a variable with one name

Scope rules (simple on purpose):

- A name can only be declared once with `let`. A `let` can never silently
  reuse a name that is already visible, so there is no shadowing. To change
  a variable that already exists, write `name = value` (no `let`).
- Reassignment `name = value` needs a name that is visible from the place
  of the line, so inside an if / for block at the top level you can change
  an outer variable, and a variable made inside the block can only be
  changed inside it. A function can only change its own inputs and its own
  variables (it still cannot see the variables outside it). The new value
  must have the same kind as the old one (number, text or list) whenever
  both are known; the kind of a function input stays unknown.
- The top of the program is the "global" scope.
- A function has its OWN scope. Its inputs (parameters) are declared in it,
  and so is every `let` inside it. A function can NOT see variables from
  outside: pass them in as inputs. Because the scopes are separate, a
  `let x` inside a function does not clash with a `let x` outside.
- The lines inside an if / elif / else branch form a small scope of their
  own: variables made there disappear after the branch ends. They can see
  everything around them, and cannot reuse a name that is already visible.
- A `for` loop has a scope of its own too: the loop variable and every
  `let` inside the loop disappear after it. Like in an if branch, the loop
  variable cannot reuse a name that is already visible (no shadowing).
  Going through a text gives a text (one character) at each step; going
  through a list gives a value of unknown kind. A `for` can only go
  through text or a list: a number is an error when its kind is known, and
  a run-time error otherwise (function inputs and call results).
- Function names live in one list for the whole program. A function is
  visible everywhere; a call at the top of the program must come after the
  `function` lines (it would fail at run time otherwise). Functions may
  call themselves and each other.
- A function name cannot also be a variable or input name.

Type rules (simple, no guessing): every value is a number, text or a list.
A list holds numbers or text (mixed is allowed; sorting a mixed list fails
at run time with a friendly error). Lists inside lists are not supported.
`list + list` joins them into one new list; any other calculation with a
list is an error, and `<  >  <=  >=` do not work on lists (`==` and `!=`
do). Built-in functions: max(list), min(list), len(list or text) and
sort(list). `sort` changes the list itself, so it is only allowed as a
line on its own, with a variable as input. max and min give an answer of
unknown kind, len gives a number.
 The
checker tracks the kind of each variable from its `let`. Numbers work with
all of + - * /. Text can only be joined with another text using `+`. Any
other mix is an error. Function inputs and the results of calls have an
UNKNOWN kind: the checker accepts them anywhere and the run-time check
catches mistakes. Conditions: `==` and `!=` may compare anything (different
kinds are simply never equal); `> < >= <=` need two numbers or two texts
(texts compare alphabetically).

A function that has a `give` (also one inside an if or a for) must give on
every path (its last line must be a `give`, or an if/else where every
branch gives), so that a call never produces "nothing". A `for` never counts
as giving, because it may run zero times (an empty text): put a `give`
after the loop. A function without any `give` can only be called as a
line on its own, not used as a value.

The checker walks the tree top to bottom. It never changes the tree.
"""

from ast_nodes import (Assign, BinaryOp, Call, CallStatement, Compare, Echo,
                       Expression, For, Function, Give, If, Let, ListLiteral,
                       Name, Negate, Number, Program, Show, Text)
from errors import ScriptyError

NUMBER_KIND = "number"
TEXT_KIND = "text"
LIST_KIND = "list"
UNKNOWN_KIND = "unknown"  # function inputs and call results

# Names that belong to Scripty itself (no variable or function may use them).
BUILTINS = ("max", "min", "len", "sort")

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
        if function.name in BUILTINS:
            raise ScriptyError(_builtin_name_message(function.name),
                               function.line)
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
        elif isinstance(statement, Assign):
            self.check_assign(statement, scope)
        elif isinstance(statement, (Show, Echo, Give)):
            self.check_expression(statement.value, scope)
        elif isinstance(statement, CallStatement):
            self.check_call(statement.call, scope, as_value=False)
        elif isinstance(statement, If):
            self.check_if(statement, scope)
        elif isinstance(statement, For):
            self.check_for(statement, scope)
        elif isinstance(statement, Function):
            self.check_function(statement)

    def check_assign(self, statement: Assign, scope: _Scope) -> None:
        name = statement.name
        if name in BUILTINS:
            raise ScriptyError(_builtin_name_message(name), statement.line)
        found = scope.find(name)
        if found is None:
            # Same friendly errors as using an unknown name.
            self.check_name(Name(name, statement.line), scope)
            return  # (check_name always raises here)
        kind = self.check_expression(statement.value, scope)
        old_line, old_kind = found
        if UNKNOWN_KIND not in (old_kind, kind) and old_kind != kind:
            raise ScriptyError(
                f'"{name}" holds {_with_article(old_kind)} (made on line '
                f"{old_line}), so it can't be changed to "
                f"{_with_article(kind)}. A variable keeps the same kind of "
                "value: use a new name with let instead.", statement.line)

    def check_if(self, node: If, scope: _Scope) -> None:
        for branch in node.branches:
            self.check_condition(branch.condition, scope)
            self.check_block(branch.body, scope)
        if node.else_body is not None:
            self.check_block(node.else_body, scope)

    def check_for(self, node: For, scope: _Scope) -> None:
        kind = self.check_expression(node.iterable, scope)
        if kind == NUMBER_KIND:
            raise ScriptyError(
                "You can only go through text or a list with for, but "
                f"{_describe_number(node.iterable)} is a number.", node.line)
        inner = _Scope(parent=scope)
        # Going through a text gives text; a list may hold numbers or text.
        step_kind = TEXT_KIND if kind == TEXT_KIND else UNKNOWN_KIND
        self.declare(inner, node.name, node.line, step_kind)
        for statement in node.body:
            self.check_statement(statement, inner)

    def check_block(self, body: list, scope: _Scope) -> None:
        inner = _Scope(parent=scope)
        for statement in body:
            self.check_statement(statement, inner)

    def declare(self, scope: _Scope, name: str, line: int, kind: str) -> None:
        if name in BUILTINS:
            raise ScriptyError(_builtin_name_message(name), line)
        if name in self.functions:
            raise ScriptyError(
                f'"{name}" is already the name of a function (line '
                f"{self.functions[name].line}). Pick a different name.",
                line)
        existing = scope.find(name)
        if existing is not None:
            raise ScriptyError(
                f'"{name}" is already declared on line {existing[0]}. '
                "A name can only be declared once with let. To change its "
                f"value, write: {name} = ... (without let). Or pick a "
                "different name.", line)
        scope.variables[name] = (line, kind)

    # -- conditions --------------------------------------------------------

    def check_condition(self, condition: Compare, scope: _Scope) -> None:
        left = self.check_expression(condition.left, scope)
        right = self.check_expression(condition.right, scope)
        if condition.op in _ORDERING and LIST_KIND in (left, right):
            raise ScriptyError(
                f'You can\'t use "{condition.op}" with a list. Lists can '
                'only be compared with "==" or "!=".', condition.line)
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
            if kind in (TEXT_KIND, LIST_KIND):
                raise ScriptyError(
                    f"You can't put a minus sign in front of "
                    f"{_with_article(kind)}. "
                    "A minus sign only works with numbers.", expression.line)
            return NUMBER_KIND
        if isinstance(expression, ListLiteral):
            return self.check_list(expression, scope)
        if isinstance(expression, Call):
            return self.check_call(expression, scope, as_value=True)
        if isinstance(expression, Text):
            return TEXT_KIND
        return NUMBER_KIND  # Number

    def check_list(self, expression: ListLiteral, scope: _Scope) -> str:
        for item in expression.items:
            if self.check_expression(item, scope) == LIST_KIND:
                raise ScriptyError(
                    "A list can't hold another list yet. Put only numbers "
                    "or text between the [ ].", expression.line)
        return LIST_KIND

    def check_name(self, name: Name, scope: _Scope) -> str:
        found = scope.find(name.name)
        if found is not None:
            return found[1]
        if name.name in BUILTINS:
            raise ScriptyError(
                f'"{name.name}" is a built-in function. To use it, call it '
                f"with its input, like: {name.name}(a)", name.line)
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

    def check_builtin(self, call: Call, scope: _Scope, as_value: bool) -> str:
        """Check max / min / len / sort and return the kind of the answer."""
        name = call.name
        if name == "sort" and as_value:
            raise ScriptyError(
                "sort changes the list itself and gives nothing back, so "
                "it can't be used as a value. Write it on its own line: "
                "sort(a), and then use a.", call.line)
        if not as_value and name != "sort":
            raise ScriptyError(
                f"{name}(...) gives an answer, but nothing is done with "
                f"it here. Try: show {name}(a)", call.line)
        if len(call.args) != 1:
            raise ScriptyError(
                f'The built-in function "{name}" needs 1 input (a list), '
                f"but you gave {len(call.args)}. Try: {name}(a)", call.line)
        argument = call.args[0]
        if name == "sort" and not isinstance(argument, Name):
            raise ScriptyError(
                "sort changes the list itself, so give it the name of a "
                "variable that holds a list. Try: sort(a)", call.line)
        kind = self.check_expression(argument, scope)
        allowed = (LIST_KIND, TEXT_KIND) if name == "len" else (LIST_KIND,)
        if kind not in allowed and kind != UNKNOWN_KIND:
            wanted = "a list or text" if name == "len" else "a list"
            raise ScriptyError(
                f'"{name}" needs {wanted}, but this is '
                f"{_with_article(kind)}. Try: {name}([1, 2, 3])", call.line)
        return NUMBER_KIND if name == "len" else UNKNOWN_KIND

    def check_call(self, call: Call, scope: _Scope, as_value: bool) -> str:
        if call.name in BUILTINS:
            return self.check_builtin(call, scope, as_value)
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


def _describe_number(expression: Expression) -> str:
    """Name a number for the error message: 5, "n" or "this value"."""
    if isinstance(expression, Number):
        return str(expression.value)
    if isinstance(expression, Name):
        return f'"{expression.name}"'
    return "this value"


def _with_article(kind: str) -> str:
    """"a number", "a list", "text": for error messages."""
    return "text" if kind == TEXT_KIND else f"a {kind}"


def _builtin_name_message(name: str) -> str:
    return (f'"{name}" is a built-in Scripty function, so it can\'t be used '
            "as a variable or function name. Pick another name.")


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
        elif isinstance(statement, For) and _contains_give(statement.body):
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
    return False  # a for loop may run zero times, so it never counts


def _check_operation(expression: BinaryOp, left: str, right: str) -> str:
    op = expression.op
    if LIST_KIND in (left, right):
        if op == "+" and {left, right} <= {LIST_KIND, UNKNOWN_KIND}:
            return LIST_KIND  # joining two lists
        raise ScriptyError(
            f"You can't use \"{op}\" with a list like that. The only "
            'calculation for lists is "+" to join two lists, like: '
            "[1, 2] + [3]", expression.line)
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
