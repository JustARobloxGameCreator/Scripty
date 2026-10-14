"""AST nodes: the tree the parser builds and later stages walk.

Statements: Let, Assign, Show, Echo, CallStatement, MethodStatement, Give,
If, For, Function, AssignIndex, AssignAttribute, ClassDef.
Expressions: Number, Text, Name, BinaryOp, Negate, Call, ListLiteral, Index,
Attribute (d.name), MethodCall (a list action such as a.pop(1), or an
action of an object such as d.speak()).  A
Compare (such as x > 5) is a condition: it only appears in an if or elif
line.  Every node remembers the `line` it came from, so the checker and
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
class ListLiteral:
    """A list written in square brackets, e.g. [1, 2, 3] or []."""

    items: list["Expression"]
    line: int


@dataclass
class Compare:
    """A condition such as x > 5. op is one of == != >= <= > <."""

    op: str
    left: "Expression"
    right: "Expression"
    line: int


@dataclass
class MethodCall:
    """A call after a dot: a list action or an action of an object.

    `a.remove("Dog")` and `a.pop(3)` are list actions: they change the list
    and give nothing back, so the checker only allows them as a whole line
    (MethodStatement). `d.speak()` runs an action (a function written inside
    a class) of an object, and `super.init(1)` runs the parent's action.

    `target` is a Name (a variable, `self` or `super`) or an Attribute
    (`self.pet.speak()`). The checker fills in `target_kind` ("list",
    "object", "super" or "unknown") so the generator knows how to write it.
    """

    target: "Expression"
    method: str
    args: list["Expression"]
    line: int
    target_kind: str = "unknown"


@dataclass
class Attribute:
    """A thing an object remembers, read as a value: d.name or self.age.

    The checker sets `target_kind` to "object" when it knows the target is
    an object (the generator then writes plain `d.name`).
    """

    target: "Expression"
    name: str
    line: int
    target_kind: str = "unknown"


@dataclass
class Index:
    """One item of a list, or one character of a text: a[1], "hello"[0].

    `target` is any expression and `index` is the position (counting from 0;
    negative positions count from the end).
    """

    target: "Expression"
    index: "Expression"
    line: int


# The actions that can be written after a dot.
LIST_METHODS = ("remove", "pop")

Expression = (Number | Text | Name | BinaryOp | Negate | Call | ListLiteral
              | Index | MethodCall | Attribute)


@dataclass
class Let:
    name: str
    value: Expression
    line: int


@dataclass
class Assign:
    """name = value: give an existing variable a new value (no `let`)."""

    name: str
    value: Expression
    line: int


@dataclass
class AssignIndex:
    """name[index] = value: replace one item of an existing list."""

    target: Name
    index: Expression
    value: Expression
    line: int


@dataclass
class AssignAttribute:
    """d.name = value: give an object a thing to remember (or change it)."""

    target: Expression
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
class MethodStatement:
    """A list action used as a whole line, e.g. a.remove("Dog")."""

    call: MethodCall
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
class For:
    """for name in value: ... - run the body once per character or list item."""

    name: str
    iterable: Expression
    body: list["Statement"]
    line: int


@dataclass
class Function:
    name: str
    params: list[str]
    body: list["Statement"]
    line: int


@dataclass
class ClassDef:
    """class Name: or class Name(Parent): with its functions (the actions)."""

    name: str
    parent: str | None
    methods: list[Function]
    line: int


Statement = (Let | Assign | AssignIndex | AssignAttribute | Show | Echo
             | CallStatement | MethodStatement | Give | If | For | Function
             | ClassDef)


@dataclass
class Program:
    statements: list[Statement]
