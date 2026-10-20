"""Checker: finds meaning errors in a parsed program (names, kinds, scopes,
function and class rules). The parser only knows the shape; this knows the
sense. It returns the tree unchanged, except that it fills in `target_kind`
on MethodCall and Attribute nodes for the generator. The full rules are in
docs/architecture.md (section "Checker").
"""

from ast_nodes import (LIST_METHODS, Assign, AssignAttribute, AssignIndex, Attribute,
                       BinaryOp, Call, CallStatement, ClassDef, Compare, Echo,
                       Expression, For, Function, Give, If, Index, Let,
                       ListLiteral, MethodCall, MethodStatement, Name, Negate,
                       Number, Program, Show, Text)
from errors import ScriptyError

NUMBER_KIND = "number"
TEXT_KIND = "text"
LIST_KIND = "list"
UNKNOWN_KIND = "unknown"  # function inputs and call results
OBJECT_PREFIX = "object "  # the kind of a Dog object is "object Dog"

# Names only the class machinery may use.
RESERVED = ("self", "super")

# Names that belong to Scripty itself (no variable or function may use them).
BUILTINS = ("max", "min", "len", "sort")

_ORDERING = ("<", ">", "<=", ">=")


class _Scope:
    """The variables visible at one place in the program."""

    def __init__(self, parent: "_Scope | None" = None,
                 function: Function | None = None,
                 cls: ClassDef | None = None) -> None:
        self.parent = parent
        # The function this scope belongs to (None = top of the program).
        if function is None and parent is not None:
            function = parent.function
        self.function = function
        # The class this scope is inside (only set inside its actions).
        if cls is None and parent is not None:
            cls = parent.cls
        self.cls = cls
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
        self.classes: dict[str, ClassDef] = {}
        # Functions and classes whose line was passed.
        self.defined: set[str] = set()
        # Things objects remember, by class: names assigned as self.name = ...
        self.attributes: dict[str, dict[str, None]] = {}
        # Names assigned on anything that is not self: d.name = ...
        self.outside_attributes: dict[str, None] = {}
        self.globals = _Scope()

    def run(self) -> None:
        for statement in self.program.statements:
            if isinstance(statement, Function):
                self.register_function(statement)
            elif isinstance(statement, ClassDef):
                self.register_class(statement)
        for cls in self.classes.values():
            self.check_parent(cls)
        for statement in self.program.statements:
            self.collect_attributes(statement, None)
        for statement in self.program.statements:
            self.check_statement(statement, self.globals)

    # -- functions ---------------------------------------------------------

    def register_function(self, function: Function) -> None:
        _check_not_taken(function.name, function.line)
        if function.name in self.classes:
            raise ScriptyError(
                f'"{function.name}" is already the name of a class (line '
                f"{self.classes[function.name].line}). A function can't "
                "have the same name, so pick a different name.",
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

    # -- classes -----------------------------------------------------------

    def register_class(self, cls: ClassDef) -> None:
        _check_not_taken(cls.name, cls.line)
        if cls.name in self.classes:
            raise ScriptyError(
                f'The class "{cls.name}" is already defined on line '
                f"{self.classes[cls.name].line}. A class name can only be "
                "used once, so pick a different name.", cls.line)
        if cls.name in self.functions:
            raise ScriptyError(
                f'"{cls.name}" is already the name of a function (line '
                f"{self.functions[cls.name].line}). A class can't have the "
                "same name, so pick a different name.", cls.line)
        self.classes[cls.name] = cls

    def check_parent(self, cls: ClassDef) -> None:
        """The parent of a class must be a class written above it."""
        if cls.parent is None:
            return
        parent = self.classes.get(cls.parent)
        if parent is None:
            if cls.parent in self.functions:
                what = "a function"
            elif cls.parent in BUILTINS:
                what = "a built-in function"
            else:
                raise ScriptyError(
                    f'I don\'t know a class called "{cls.parent}", so '
                    f'"{cls.name}" can\'t be built on it. Did you forget to '
                    f"write: class {cls.parent}:", cls.line)
            raise ScriptyError(
                f'"{cls.parent}" is {what}, not a class, so "{cls.name}" '
                "can't be built on it. The name in brackets after a class "
                f"must be a class, like: class {cls.name}(Animal):",
                cls.line)
        if parent.line >= cls.line:
            raise ScriptyError(
                f'The parent class "{parent.name}" is written below '
                f'"{cls.name}" (it starts on line {parent.line}). Move '
                f'"{parent.name}" above this line.', cls.line)

    def chain(self, name: str) -> list[ClassDef]:
        """The class and its parents, the class itself first."""
        classes: list[ClassDef] = []
        cls = self.classes.get(name)
        while cls is not None and cls not in classes:
            classes.append(cls)
            cls = self.classes.get(cls.parent) if cls.parent else None
        return classes

    def find_method(self, class_name: str, method: str) -> tuple[ClassDef, Function] | None:
        """The action a class has under this name (its own or inherited)."""
        for cls in self.chain(class_name):
            for function in cls.methods:
                if function.name == method:
                    return cls, function
        return None

    def method_names(self, class_name: str) -> list[str]:
        names: list[str] = []
        for cls in self.chain(class_name):
            for function in cls.methods:
                if function.name not in names and function.name != "init":
                    names.append(function.name)
        return names

    def is_subclass(self, child: str, parent: str) -> bool:
        return any(cls.name == parent for cls in self.chain(child))

    def collect_attributes(self, statement, cls: ClassDef | None) -> None:
        """Find every `x.name = value` so reads can be checked later."""
        if isinstance(statement, ClassDef):
            self.attributes.setdefault(statement.name, {})
            for method in statement.methods:
                for inner in method.body:
                    self.collect_attributes(inner, statement)
        elif isinstance(statement, Function):
            for inner in statement.body:
                self.collect_attributes(inner, None)
        elif isinstance(statement, If):
            parts = [branch.body for branch in statement.branches]
            parts.append(statement.else_body or [])
            for part in parts:
                for inner in part:
                    self.collect_attributes(inner, cls)
        elif isinstance(statement, For):
            for inner in statement.body:
                self.collect_attributes(inner, cls)
        elif isinstance(statement, AssignAttribute):
            target = statement.target
            if (cls is not None and isinstance(target, Name)
                    and target.name == "self"):
                self.attributes[cls.name][statement.name] = None
            else:
                self.outside_attributes[statement.name] = None

    def known_attributes(self, class_name: str) -> list[str]:
        """Everything an object of this class might remember."""
        names: dict[str, None] = {}
        for cls in self.classes.values():
            related = (self.is_subclass(class_name, cls.name)
                       or self.is_subclass(cls.name, class_name))
            if related:
                names.update(self.attributes.get(cls.name, {}))
        names.update(self.outside_attributes)
        return list(names)

    def check_class(self, cls: ClassDef) -> None:
        seen: dict[str, Function] = {}
        for method in cls.methods:
            _check_member_name(method.name, method.line)
            if method.name in seen:
                raise ScriptyError(
                    f'The class "{cls.name}" already has an action called '
                    f'"{method.name}" (line {seen[method.name].line}). Each '
                    "function in a class needs its own name.", method.line)
            seen[method.name] = method
        for method in cls.methods:
            self.check_method_definition(cls, method)
        self.defined.add(cls.name)

    def check_method_definition(self, cls: ClassDef, method: Function) -> None:
        if not method.params or method.params[0] != "self":
            inputs = ", ".join(["self"] + [p for p in method.params if p != "self"])
            raise ScriptyError(
                f'The first input of "{method.name}" in class "{cls.name}" '
                "must be self. self is the object the function works on "
                "(you don't write it when you call the function: "
                f"d.{method.name}(...)). Try: function {method.name}({inputs}):",
                method.line)
        scope = _Scope(function=method, cls=cls)
        self.declare(scope, "self", method.line, _object_kind(cls.name),
                     allow_reserved=True)
        for param in method.params[1:]:
            self.declare(scope, param, method.line, UNKNOWN_KIND)
        for statement in method.body:
            self.check_statement(statement, scope)
        label = f'The action "{method.name}" in class "{cls.name}"'
        if method.name == "init" and _contains_give(method.body):
            raise ScriptyError(
                f'{label} can\'t give a value back. init only sets the '
                "object up; Dog(...) always gives you the new object.",
                method.line)
        if _contains_give(method.body) and not _always_gives(method.body):
            raise ScriptyError(
                f"{label} gives a value back in some cases but not in all "
                "of them. Make sure its last line is a give (or an if / "
                "else where every part gives).", method.line)

    # -- statements --------------------------------------------------------

    def check_statement(self, statement, scope: _Scope) -> None:
        if isinstance(statement, Let):
            # Check the value first, so `let x = x + 1` fails when x is new.
            kind = self.check_expression(statement.value, scope)
            self.declare(scope, statement.name, statement.line, kind)
        elif isinstance(statement, Assign):
            self.check_assign(statement, scope)
        elif isinstance(statement, AssignIndex):
            self.check_assign_index(statement, scope)
        elif isinstance(statement, AssignAttribute):
            self.check_assign_attribute(statement, scope)
        elif isinstance(statement, (Show, Echo, Give)):
            self.check_expression(statement.value, scope)
        elif isinstance(statement, CallStatement):
            self.check_call(statement.call, scope, as_value=False)
        elif isinstance(statement, MethodStatement):
            self.check_method(statement.call, scope, as_value=False)
        elif isinstance(statement, If):
            self.check_if(statement, scope)
        elif isinstance(statement, For):
            self.check_for(statement, scope)
        elif isinstance(statement, Function):
            self.check_function(statement)
        elif isinstance(statement, ClassDef):
            self.check_class(statement)

    def check_assign(self, statement: Assign, scope: _Scope) -> None:
        name = statement.name
        if name in BUILTINS:
            raise ScriptyError(_builtin_name_message(name), statement.line)
        if name in RESERVED:
            raise ScriptyError(
                f'"{name}" can\'t be given a new value. It is reserved for '
                "classes.", statement.line)
        found = scope.find(name)
        if found is None:
            # Same friendly errors as using an unknown name.
            self.check_name(Name(name, statement.line), scope)
            return  # (check_name always raises here)
        kind = self.check_expression(statement.value, scope)
        old_line, old_kind = found
        if not self.same_kind(old_kind, kind):
            raise ScriptyError(
                f'"{name}" holds {_with_article(old_kind)} (made on line '
                f"{old_line}), so it can't be changed to "
                f"{_with_article(kind)}. A variable keeps the same kind of "
                "value: use a new name with let instead.", statement.line)

    def same_kind(self, old_kind: str, new_kind: str) -> bool:
        """Can a variable holding old_kind be given a value of new_kind?"""
        if UNKNOWN_KIND in (old_kind, new_kind):
            return True
        if _is_object(old_kind) and _is_object(new_kind):
            return self.is_subclass(_class_name(new_kind),
                                    _class_name(old_kind))
        return old_kind == new_kind

    def check_assign_attribute(self, statement: AssignAttribute,
                               scope: _Scope) -> None:
        """d.name = value: an object remembers (or changes) a thing."""
        kind = self.check_expression(statement.target, scope)
        _check_member_name(statement.name, statement.line)
        if kind in (NUMBER_KIND, TEXT_KIND, LIST_KIND):
            raise ScriptyError(
                f"{_sentence(kind)} can't remember things, so "
                f"{_describe_target(statement.target)}.{statement.name} = "
                "... doesn't work. Only an object made from a class can.",
                statement.line)
        if _is_object(kind):
            action = self.find_method(_class_name(kind), statement.name)
            if action is not None:
                raise ScriptyError(
                    f'"{statement.name}" is already an action of class '
                    f'"{action[0].name}", so an object can\'t also remember '
                    "something with that name. Pick another name.",
                    statement.line)
        self.check_expression(statement.value, scope)

    def check_assign_index(self, statement: AssignIndex,
                           scope: _Scope) -> None:
        """a[1] = value: change one item of an existing list."""
        target = statement.target
        kind = self.check_name(target, scope)
        if kind == NUMBER_KIND or _is_object(kind):
            raise ScriptyError(_index_number_message(target, kind),
                               statement.line)
        if kind == TEXT_KIND:
            raise ScriptyError(
                "Text can't be changed one character at a time, so "
                f"{target.name}[...] = ... is not allowed. Give the whole "
                f'variable a new value instead, like: {target.name} = "new text"',
                statement.line)
        self.check_position(statement.index, scope,
                            f"{target.name}[1] = 9", statement.line)
        if self.check_expression(statement.value, scope) == LIST_KIND:
            raise ScriptyError(
                "A list can't hold another list yet. Put only numbers "
                "or text in the item.", statement.line)

    def check_position(self, index: Expression, scope: _Scope, example: str,
                       line: int) -> None:
        """The position inside [ ] must be a whole number (when known)."""
        kind = self.check_expression(index, scope)
        if kind in (TEXT_KIND, LIST_KIND) or _is_object(kind):
            raise ScriptyError(
                "A position must be a whole number, but this is "
                f"{_with_article(kind)}. Try: {example}", line)
        decimal = _decimal_literal(index)
        if decimal is not None:
            raise ScriptyError(
                f"A position must be a whole number, but {decimal} has a "
                f"decimal part. Try: {example}", line)

    def check_index(self, expression: Index, scope: _Scope) -> str:
        """a[1]: one item of a list, or one character of a text."""
        kind = self.check_expression(expression.target, scope)
        if kind == NUMBER_KIND or _is_object(kind):
            raise ScriptyError(
                _index_number_message(expression.target, kind),
                expression.line)
        self.check_position(expression.index, scope, "a[1]", expression.line)
        return TEXT_KIND if kind == TEXT_KIND else UNKNOWN_KIND

    def check_if(self, node: If, scope: _Scope) -> None:
        for branch in node.branches:
            self.check_condition(branch.condition, scope)
            self.check_block(branch.body, scope)
        if node.else_body is not None:
            self.check_block(node.else_body, scope)

    def check_for(self, node: For, scope: _Scope) -> None:
        kind = self.check_expression(node.iterable, scope)
        if _is_object(kind):
            raise ScriptyError(
                "You can only go through text or a list with for, but "
                f"this is {_with_article(kind)}.", node.line)
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

    def declare(self, scope: _Scope, name: str, line: int, kind: str,
                allow_reserved: bool = False) -> None:
        _check_not_taken(name, line, allow_reserved)
        if name in self.functions:
            raise ScriptyError(
                f'"{name}" is already the name of a function (line '
                f"{self.functions[name].line}). Pick a different name.",
                line)
        if name in self.classes:
            raise ScriptyError(
                f'"{name}" is already the name of a class (line '
                f"{self.classes[name].line}). Pick a different name.",
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
        if condition.op in _ORDERING and (_is_object(left)
                                          or _is_object(right)):
            raise ScriptyError(
                f'You can\'t use "{condition.op}" with an object. Objects '
                'can only be compared with "==" or "!=" (which asks if '
                "they are the very same object).", condition.line)
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
            if kind in (TEXT_KIND, LIST_KIND) or _is_object(kind):
                raise ScriptyError(
                    f"You can't put a minus sign in front of "
                    f"{_with_article(kind)}. "
                    "A minus sign only works with numbers.", expression.line)
            return NUMBER_KIND
        if isinstance(expression, ListLiteral):
            return self.check_list(expression, scope)
        if isinstance(expression, Index):
            return self.check_index(expression, scope)
        if isinstance(expression, Call):
            return self.check_call(expression, scope, as_value=True)
        if isinstance(expression, MethodCall):
            return self.check_method(expression, scope, as_value=True)
        if isinstance(expression, Attribute):
            return self.check_attribute(expression, scope)
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
        if name.name in self.classes:
            raise ScriptyError(
                f'"{name.name}" is a class. To make an object, call it '
                f"with its inputs, like: let d = {name.name}(...)",
                name.line)
        if name.name == "self":
            raise ScriptyError(
                '"self" only works inside a function written in a class. '
                "It is the object that the function works on.", name.line)
        if name.name == "super":
            raise ScriptyError(
                '"super" only works as super.init(...) (or super.name(...)) '
                "inside a function of a class that has a parent, like: "
                "class Puppy(Dog):", name.line)
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

    def check_attribute(self, expression: Attribute, scope: _Scope) -> str:
        """d.name: something an object remembers."""
        target, name = expression.target, expression.name
        kind = self.check_expression(target, scope)
        _check_member_name(name, expression.line)
        if kind in (NUMBER_KIND, TEXT_KIND, LIST_KIND):
            if kind == LIST_KIND and name in LIST_METHODS:
                raise ScriptyError(
                    f"{name} needs parentheses with a value inside. Try: "
                    f"{_describe_target(target)}.{name}("
                    f"{_METHOD_EXAMPLES[name]})", expression.line)
            raise ScriptyError(
                f'{_sentence(kind)} has nothing called "{name}". Only '
                "objects made from a class remember things like that.",
                expression.line)
        if _is_object(kind):
            class_name = _class_name(kind)
            if self.find_method(class_name, name) is not None:
                raise ScriptyError(
                    f'"{name}" is an action of {class_name}, not something '
                    "it remembers. To run it, call it with brackets, like: "
                    f"{_describe_target(target)}.{name}(...)", expression.line)
            known = self.known_attributes(class_name)
            if name not in known:
                raise ScriptyError(
                    f'This {class_name} has nothing called "{name}", and '
                    f"nothing in the program ever sets it. Did you forget "
                    f"to write: self.{name} = ... (for example inside "
                    f"init)?" + _things_message(known), expression.line)
            expression.target_kind = "object"
        return UNKNOWN_KIND

    def check_method(self, call: MethodCall, scope: _Scope,
                     as_value: bool) -> str:
        """Check a.remove(v) / a.pop(i) / d.speak() / super.init()."""
        method, target = call.method, call.target
        _check_member_name(method, call.line)
        if isinstance(target, Name) and target.name == "super":
            return self.check_super_call(call, scope, as_value)
        kind = self.check_expression(target, scope)
        if kind == LIST_KIND:
            call.target_kind = "list"
            return self.check_list_action(call, scope, as_value)
        if _is_object(kind):
            call.target_kind = "object"
            return self.check_object_action(call, _class_name(kind), scope,
                                            as_value)
        if kind in (NUMBER_KIND, TEXT_KIND):
            if method in LIST_METHODS:
                raise ScriptyError(
                    f"{method} only works on lists, but "
                    f"{_describe_target(target, quoted=True)} is "
                    f"{_with_article(kind)}.", call.line)
            raise ScriptyError(f"{_sentence(kind)} has no action called "
                               f"{method}.", call.line)
        # Unknown kind (a function input or a call result): the runner
        # decides what the target is while the program runs.
        call.target_kind = "unknown"
        if method == "init":
            raise ScriptyError(_init_message(), call.line)
        for argument in call.args:
            self.check_expression(argument, scope)
        return UNKNOWN_KIND

    def check_list_action(self, call: MethodCall, scope: _Scope,
                          as_value: bool) -> str:
        """a.remove(value) / a.pop(index) on a list. It never gives a value."""
        method, target = call.method, call.target
        name = _describe_target(target)
        if method not in LIST_METHODS:
            raise ScriptyError(
                f"I don't know what \"{method}\" does to a list. The list "
                f"actions are: {', '.join(LIST_METHODS)}. "
                f'Try: {name}.remove("Dog") or {name}.pop(1)', call.line)
        example = f"{name}.{method}({_METHOD_EXAMPLES[method]})"
        if as_value:
            raise ScriptyError(
                f"{method} changes the list itself and gives nothing back, "
                f"so it can't be used as a value. Write it on its own "
                f"line: {example}, and then use {name}.", call.line)
        if len(call.args) != 1:
            wanted = ("a value to remove" if method == "remove"
                      else "a position (a whole number)")
            raise ScriptyError(
                f"{method} needs exactly 1 input, {wanted}, but you gave "
                f"{len(call.args)}. Try: {example}", call.line)
        argument = call.args[0]
        argument_kind = self.check_expression(argument, scope)
        if method == "pop":
            _check_position(argument, argument_kind, example, call.line)
        return UNKNOWN_KIND

    def check_object_action(self, call: MethodCall, class_name: str,
                            scope: _Scope, as_value: bool) -> str:
        """d.speak(...) on an object whose class is known."""
        method = call.method
        if method == "init":
            raise ScriptyError(_init_message(), call.line)
        found = self.find_method(class_name, method)
        if found is None:
            names = self.method_names(class_name)
            known = (f" Its actions are: {', '.join(names)}." if names
                     else " It has no actions yet.")
            raise ScriptyError(
                f'A {class_name} object has no action called "{method}".'
                + known, call.line)
        owner, function = found
        label = f'The action "{method}" of class "{owner.name}"'
        return self.check_action_call(call, function, label, scope,
                                      as_value)

    def check_super_call(self, call: MethodCall, scope: _Scope,
                         as_value: bool) -> str:
        """super.init(...) / super.speak(): run the parent's version."""
        cls = scope.cls
        if cls is None or cls.parent is None:
            raise ScriptyError(
                '"super" only works inside a function of a class that has '
                "a parent, like: class Puppy(Dog):", call.line)
        call.target_kind = "super"
        found = self.find_method(cls.parent, call.method)
        if found is None:
            if call.method == "init":  # the parent has no init: takes none
                if call.args:
                    raise ScriptyError(
                        f'The parent class "{cls.parent}" has no init '
                        "function, so super.init() takes no inputs, but "
                        f"you gave {len(call.args)}.", call.line)
                if as_value:
                    raise ScriptyError(_init_value_message(), call.line)
                return UNKNOWN_KIND
            raise ScriptyError(
                f'The parent class "{cls.parent}" has no action called '
                f'"{call.method}".', call.line)
        owner, function = found
        label = f'The action "{call.method}" of class "{owner.name}"'
        return self.check_action_call(call, function, label, scope,
                                      as_value)

    def check_action_call(self, call: MethodCall, function: Function,
                          label: str, scope: _Scope, as_value: bool) -> str:
        """Inputs and value rules shared by d.speak() and super.speak()."""
        wanted, given = len(function.params) - 1, len(call.args)  # no self
        if wanted != given:
            raise ScriptyError(
                f"{label} needs {_plural(wanted)} "
                f"({', '.join(function.params[1:]) or 'none'}), but you "
                f"gave {given}.", call.line)
        for argument in call.args:
            self.check_expression(argument, scope)
        if as_value and not _contains_give(function.body):
            raise ScriptyError(
                f"{label} never gives anything back, so its result can't "
                "be used as a value. Add a give line to it, or call it on "
                "its own line.", call.line)
        return UNKNOWN_KIND

    def check_constructor(self, call: Call, scope: _Scope) -> str:
        """Dog(...): make an object. Its inputs are the ones of init."""
        name = call.name
        if scope.function is None and name not in self.defined:
            raise ScriptyError(
                f'The class "{name}" is used here before it is written '
                f"(it starts on line {self.classes[name].line}). Move the "
                "class above this line.", call.line)
        found = self.find_method(name, "init")
        wanted = len(found[1].params) - 1 if found else 0
        given = len(call.args)
        if wanted != given:
            if found is None:
                raise ScriptyError(
                    f'The class "{name}" takes no inputs (it has no init '
                    f"function), but you gave {given}. To give it inputs, "
                    "add a function init(self, ...) to the class.",
                    call.line)
            raise ScriptyError(
                f'The class "{name}" needs {_plural(wanted)} '
                f"({', '.join(found[1].params[1:]) or 'none'}) to make an "
                f"object, but you gave {given}.", call.line)
        for argument in call.args:
            self.check_expression(argument, scope)
        return _object_kind(name)

    def check_call(self, call: Call, scope: _Scope, as_value: bool) -> str:
        if call.name in BUILTINS:
            return self.check_builtin(call, scope, as_value)
        if call.name in self.classes:
            return self.check_constructor(call, scope)
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


_METHOD_EXAMPLES = {"remove": '"Dog"', "pop": "3"}


def _is_object(kind: str) -> bool:
    return kind.startswith(OBJECT_PREFIX)


def _object_kind(class_name: str) -> str:
    return OBJECT_PREFIX + class_name


def _class_name(kind: str) -> str:
    return kind[len(OBJECT_PREFIX):]


def _check_member_name(name: str, line: int) -> None:
    """Names after a dot may not start with two underscores."""
    if name.startswith("__"):
        raise ScriptyError(
            f'"{name}" starts with two underscores, which Scripty keeps '
            "for itself. Pick another name.", line)


def _reserved_message(name: str) -> str:
    return (f'"{name}" is reserved for classes (self is the first input of '
            "every function written in a class, and super runs the parent's "
            "version of a function), so it can't be a variable, input, "
            "function or class name. Pick another name.")


def _init_message() -> str:
    return ("init runs by itself when you make an object, like Dog(...). "
            "To run the parent's init from a child's init, write: "
            "super.init(...)")


def _init_value_message() -> str:
    return ("init never gives anything back, so its result can't be used "
            "as a value.")


def _sentence(kind: str) -> str:
    """"A number", "Text", "A list" or "A Dog object": starts a sentence."""
    text = _with_article(kind)
    return text[0].upper() + text[1:]


def _describe_target(target: Expression, quoted: bool = False) -> str:
    """Name the thing before a dot for a message: d, self.pet or "d"."""
    if isinstance(target, Name):
        text = target.name
    elif isinstance(target, Attribute):
        text = f"{_describe_target(target.target)}.{target.name}"
    else:
        text = "this value"
    return f'"{text}"' if quoted and text != "this value" else text


def _things_message(known: list[str]) -> str:
    if not known:
        return ""
    return f" The things set somewhere in the program are: {', '.join(known)}."


def _check_position(argument: Expression, kind: str, example: str,
                    line: int) -> None:
    """pop(index): a position must be a whole number, 0 or more."""
    if kind in (TEXT_KIND, LIST_KIND) or _is_object(kind):
        raise ScriptyError(
            f"pop needs a position, which is a whole number, but this is "
            f"{_with_article(kind)}. Try: {example}", line)
    if isinstance(argument, Number) and argument.value != int(argument.value):
        raise ScriptyError(
            f"A position must be a whole number, but {argument.value} has "
            f"a decimal part. Try: {example}", line)
    if isinstance(argument, Negate) and isinstance(argument.operand, Number):
        raise ScriptyError(
            f"Positions start at 0 and can't be negative, so "
            f"-{argument.operand.value} is not a position. Try: {example}",
            line)


def _decimal_literal(expression: Expression) -> float | None:
    """The value of a decimal written in the program (1.5, -1.5), else None."""
    if isinstance(expression, Negate):
        value = _decimal_literal(expression.operand)
        return None if value is None else -value
    if isinstance(expression, Number) and expression.value != int(expression.value):
        return expression.value
    return None


def _index_number_message(target: Expression, kind: str = NUMBER_KIND) -> str:
    return ("You can only use [ ] on a list or a text, but "
            f"{_describe_number(target)} is {_with_article(kind)}.")


def _describe_number(expression: Expression) -> str:
    """Name a number for the error message: 5, "n" or "this value"."""
    if isinstance(expression, Number):
        return str(expression.value)
    if isinstance(expression, Name):
        return f'"{expression.name}"'
    return "this value"


def _with_article(kind: str) -> str:
    """"a number", "a list", "text", "a Dog object": for error messages."""
    if _is_object(kind):
        name = _class_name(kind)
        article = "an" if name[0].lower() in "aeiou" else "a"
        return f"{article} {name} object"
    return "text" if kind == TEXT_KIND else f"a {kind}"


def _check_not_taken(name: str, line: int, allow_reserved: bool = False) -> None:
    """A name may not be a built-in or (unless allowed) self / super."""
    if name in BUILTINS:
        raise ScriptyError(_builtin_name_message(name), line)
    if name in RESERVED and not allow_reserved:
        raise ScriptyError(_reserved_message(name), line)


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
    if _is_object(left) or _is_object(right):
        raise ScriptyError(
            f"You can't use \"{op}\" with an object. Objects only work "
            "with each other in a comparison (== or !=); to calculate, use "
            "the numbers or text they remember.", expression.line)
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
