"""Runner: executes generated Python and translates runtime errors.

`run_python(source, line_map)` compiles the code under a known filename and
runs it with exec(). If anything goes wrong, the traceback is used to find
which line of the generated Python failed, the line map turns that into a
Scripty line, and a friendly ScriptyError is raised. The user never sees a
Python traceback.

The program runs with its own `print`, so `show` writes a list the Scripty
way: [1, 2, 3] for numbers and ["a", "b"] for text (Python would write
single quotes). Numbers and text are printed exactly as Python prints them.

Objects made from a class are shown as `<Dog object>` (the class name between
the brackets), also inside a list: [<Dog object>, <Dog object>].

It also gets helpers for the list actions `a.remove(value)` and
`a.pop(index)`: `remove_all` (prints a warning to stderr and goes on when
nothing matches) and `pop_at` (raises a friendly error for a bad position).
`get_at(a, i)` and `set_at(a, i, value)` are what `a[i]` and `a[i] = value`
become: they work like Python's, but give friendly errors (a position that is
too big or too negative, a position that is not a whole number, ...).

For classes it gets `call_action(x, "speak", [args], line)` and
`get_attr(x, "name")`. The generator only writes them when it does not know
what `x` is (a function input): they look at the real value and either run
the action, or give a friendly error such as "A number has no action called
speak." (also: remove_all and pop_at pass the call on to an object that has
an action with that name).
"""

import inspect
import re
import sys
import traceback

from errors import ScriptyError
from generator import display_name, python_name

# The filename the generated code is compiled under. Traceback entries with
# this filename belong to the user's program (not to Scripty itself).
GENERATED_FILENAME = "<scripty>"


def is_object(value: object) -> bool:
    """True for an object made from a Scripty class."""
    # The program runs with __name__ == "__scripty__", so its classes
    # (and only they) carry that module name.
    return type(value).__module__ == "__scripty__"


def _class_label(value: object) -> str:
    return display_name(type(value).__name__)


def format_value(value: object) -> str:
    """Write a value the way `show` prints it."""
    if is_object(value):
        return f"<{_class_label(value)} object>"
    if isinstance(value, list):
        return "[" + ", ".join(_format_item(item) for item in value) + "]"
    return str(value)


def _format_item(item: object) -> str:
    if isinstance(item, str):
        return '"' + item + '"'
    return format_value(item)


def _scripty_print(*values: object) -> None:
    print(*(format_value(value) for value in values))


class ListActionError(Exception):
    """A friendly problem with a list or text action (shown as is)."""


def _describe_kind(value: object) -> str:
    if isinstance(value, list):
        return "a list"
    return "text" if isinstance(value, str) else "a number"


def _sentence(kind: str) -> str:
    return kind[0].upper() + kind[1:]


def _plural(count: int) -> str:
    return f"{count} input" + ("" if count == 1 else "s")


def _object_action(target: object, name: str, args: tuple | list) -> object:
    """Run an action of an object, with friendly errors."""
    method = getattr(target, python_name(name), None)
    if not callable(method):
        raise ListActionError(
            f'This {_class_label(target)} has no action called "{name}".')
    try:
        inspect.signature(method).bind(*args)
    except TypeError:
        wanted = len(inspect.signature(method).parameters)
        raise ListActionError(
            f'The action "{name}" of class "{_class_label(target)}" needs '
            f"{_plural(wanted)}, but you gave {len(args)}.") from None
    return method(*args)


def call_action(target: object, name: str, args: list, line: int,
                as_value: bool = False) -> object:
    """target.name(args) when the generator could not tell what target is."""
    if is_object(target):
        if name == "init":
            raise ListActionError(
                "init runs by itself when you make an object, like "
                "Dog(...). To run the parent's init from a child's init, "
                "write: super.init(...)")
        result = _object_action(target, name, args)
        if as_value and result is None:
            raise ListActionError(
                f'The action "{name}" never gives anything back, so its '
                "result can't be used as a value.")
        return result
    if isinstance(target, list) and name in ("remove", "pop"):
        if as_value:
            raise ListActionError(
                f"{name} changes the list itself and gives nothing back, "
                "so it can't be used as a value.")
        if len(args) != 1:
            raise ListActionError(
                f"{name} needs exactly 1 input, but you gave {len(args)}.")
        if name == "remove":
            return remove_all(target, args[0], line)
        return pop_at(target, args[0])
    if name in ("remove", "pop"):
        raise ListActionError(
            f"{name} only works on lists, but this value is "
            f"{_describe_kind(target)}.")
    raise ListActionError(
        f"{_sentence(_describe_kind(target))} has no action called {name}.")


def get_attr(target: object, name: str) -> object:
    """target.name when the generator could not tell what target is."""
    if not is_object(target):
        raise ListActionError(
            f'{_sentence(_describe_kind(target))} has nothing called '
            f'"{name}". Only objects made from a class remember things '
            "like that.")
    value = getattr(target, python_name(name))  # AttributeError: see below
    if callable(value):
        raise ListActionError(
            f'"{name}" is an action of {_class_label(target)}, not '
            "something it remembers. To run it, call it with brackets, "
            f"like: {name}(...)")
    return value


def remove_all(items: object, value: object, line: int) -> object:
    """a.remove(value): remove every item equal to value, or warn."""
    if is_object(items):  # an object with its own action called remove
        return _object_action(items, "remove", [value])
    if not isinstance(items, list):
        raise ListActionError(
            "remove only works on lists, but this value is "
            f"{_describe_kind(items)}.")
    kept = [item for item in items if item != value]
    if len(kept) == len(items):
        print(f"Warning on line {line}: {_format_item(value)} is not in the "
              "list, so nothing was removed.", file=sys.stderr)
        return
    items[:] = kept  # change the list itself, so other names see it too


def pop_at(items: object, index: object) -> object:
    """a.pop(index): remove the item at that position (counting from 0)."""
    if is_object(items):  # an object with its own action called pop
        return _object_action(items, "pop", [index])
    if not isinstance(items, list):
        raise ListActionError(
            "pop only works on lists, but this value is "
            f"{_describe_kind(items)}.")
    if isinstance(index, (str, list)):
        raise ListActionError(
            "pop needs a position, which is a whole number, but this is "
            f"{_describe_kind(index)}.")
    if index != int(index):
        raise ListActionError(
            f"A position must be a whole number, but {index} has a decimal "
            "part.")
    position = int(index)
    if position < 0:
        raise ListActionError(
            "Positions start at 0 and can't be negative, so "
            f"{position} is not a position.")
    if not items:
        raise ListActionError(
            f"The list is empty, so there is no item at position {position}.")
    if position >= len(items):
        count = len(items)
        places = ("only position 0" if count == 1
                  else f"positions 0 to {count - 1}")
        raise ListActionError(
            f"The list has {count} item{'' if count == 1 else 's'} "
            f"({places}), so there is no item at position {position}.")
    del items[position]


def _position(items: object, index: object) -> int:
    """The position a[index] means, checked, as a whole number.

    Negative positions count from the end, so -1 is the last item.
    """
    if isinstance(index, (str, list)):
        raise ListActionError(
            "A position must be a whole number, but this is "
            f"{_describe_kind(index)}.")
    if index != int(index):
        raise ListActionError(
            f"A position must be a whole number, but {index} has a decimal "
            "part.")
    position = int(index)
    count = len(items)  # type: ignore[arg-type]
    if -count <= position < count:
        return position
    what, unit = ("list", "item") if isinstance(items, list) else (
        "text", "character")
    if count == 0:
        raise ListActionError(
            f"The {what} is empty, so there is no {unit} at position "
            f"{position}.")
    places = ("only position 0, or -1 from the end" if count == 1 else
              f"positions 0 to {count - 1}, or -1 to -{count} from the end")
    raise ListActionError(
        f"The {what} has {count} {unit}{'' if count == 1 else 's'} "
        f"({places}), so there is no {unit} at position {position}.")


def get_at(items: object, index: object) -> object:
    """a[index]: one item of a list, or one character of a text."""
    if not isinstance(items, (list, str)):
        raise ListActionError(
            "You can only use [ ] on a list or a text, but this value is "
            f"{_describe_kind(items)}.")
    return items[_position(items, index)]


def set_at(items: object, index: object, value: object) -> None:
    """a[index] = value: replace one item of a list."""
    if isinstance(items, str):
        raise ListActionError(
            "Text can't be changed one character at a time. Give the whole "
            "variable a new value instead.")
    if not isinstance(items, list):
        raise ListActionError(
            "You can only use [ ] on a list or a text, but this value is "
            f"{_describe_kind(items)}.")
    if isinstance(value, list):
        raise ListActionError(
            "A list can't hold another list yet. Put only numbers or text "
            "in the item.")
    items[_position(items, index)] = value


def run_python(source: str, line_map: dict[int, int]) -> None:
    """Run generated Python. Raises ScriptyError if the program fails."""
    code = compile(source, GENERATED_FILENAME, "exec")
    try:
        exec(code, {"__name__": "__scripty__", "print": _scripty_print,
                   "remove_all": remove_all, "pop_at": pop_at,
                   "get_at": get_at, "set_at": set_at,
                   "call_action": call_action, "get_attr": get_attr})
    except Exception as error:
        line = _scripty_line(error, line_map)
        failed = _python_line_text(error, source)
        raise ScriptyError(_friendly_message(error, failed), line) from None


def _python_line(error: Exception) -> int | None:
    """The line of the generated Python where the error happened."""
    python_line = None
    for frame in traceback.extract_tb(error.__traceback__):
        if frame.filename == GENERATED_FILENAME:
            python_line = frame.lineno  # keep the innermost generated frame
    return python_line


def _python_line_text(error: Exception, source: str) -> str:
    """The text of the generated Python line that failed ("" if unknown)."""
    python_line = _python_line(error)
    lines = source.splitlines()
    if python_line is not None and 1 <= python_line <= len(lines):
        return lines[python_line - 1].strip()
    return ""


def _scripty_line(error: Exception, line_map: dict[int, int]) -> int:
    """Find the Scripty line where the error happened."""
    python_line = _python_line(error)
    if python_line in line_map:
        return line_map[python_line]
    return max(line_map.values(), default=1)  # should not happen


_PLAIN_TYPES = {"int", "float", "str", "list", "NoneType", "bool"}


def _mentions_object(message: str) -> bool:
    """Does a Python error message talk about a Scripty class?"""
    names = re.findall(r"'(\w+)'", message)
    return any(name not in _PLAIN_TYPES for name in names)


def _attribute_message(error: AttributeError) -> str:
    """Friendly words for a thing an object does not remember."""
    # Python names the type in the message ('int' object has no attribute
    # 'x'), even when it does not fill in error.obj (assigning to a number).
    match = re.match(r"'(\w+)' object has no attribute '(\w+)'", str(error))
    name = display_name(getattr(error, "name", None)
                        or (match.group(2) if match else "that"))
    target = getattr(error, "obj", None)
    if target is None and match:
        target = {"int": 0, "float": 0.0, "str": "", "list": []}.get(
            match.group(1))
    if is_object(target):
        return (f'This {_class_label(target)} has nothing called "{name}". '
                f"Did you forget to give it one with: self.{name} = ...")
    if isinstance(target, (int, float, str, list)):
        return (f'{_sentence(_describe_kind(target))} has nothing called '
                f'"{name}". Only objects made from a class remember '
                "things like that.")
    return f'This value has nothing called "{name}".'


def _friendly_message(error: Exception, failed_line: str = "") -> str:
    if isinstance(error, ListActionError):
        return str(error)
    if isinstance(error, ZeroDivisionError):
        return "You tried to divide by zero. Dividing by zero has no answer."
    if isinstance(error, ValueError) and "empty" in str(error):
        for word in ("max", "min"):
            if str(error).startswith(word + "("):
                return (f"{word} needs at least one item, but the list "
                        "is empty.")
    mentions_object = _mentions_object(str(error))
    if isinstance(error, TypeError) and "not iterable" in str(error):
        what = "an object" if mentions_object else "a number"
        if not failed_line.startswith("for "):  # max(...), min(...), sort
            return f"max, min and sort need a list, but this value is {what}."
        return ("You can only go through text or a list with for, but "
                f"this value is {what}.")
    if isinstance(error, TypeError) and "has no len" in str(error):
        what = "an object" if mentions_object else "a number"
        return f"len needs a list or text, but this value is {what}."
    if isinstance(error, AttributeError) and "'sort'" in str(error):
        return "sort needs a list, but this value is not a list."
    if isinstance(error, AttributeError):
        return _attribute_message(error)
    if isinstance(error, TypeError) and mentions_object:
        return ("You can't calculate with objects, or use < > <= >= on "
                "them. Objects can only be compared with == and !=.")
    if isinstance(error, TypeError) and "not supported between" in str(error):
        return ("You tried to compare (or sort or find the max of) text "
                "with a number. Everything must be numbers, or everything "
                "must be text.")
    if isinstance(error, TypeError) and "positional argument" in str(error):
        return "This call has the wrong number of inputs."
    if isinstance(error, TypeError):
        return ("You tried to mix text and numbers in a calculation. "
                "Both sides of an operation must be the same kind.")
    if isinstance(error, NameError):
        name = getattr(error, "name", None) or "that name"
        return (f'I don\'t know what "{name}" is. '
                f"Did you forget to write: let {name} = ...")
    if isinstance(error, RecursionError):
        return ("A function kept calling itself and never stopped. "
                "Make sure it can reach a give that does not call itself.")
    if isinstance(error, OverflowError):
        return "This number is too big for Scripty to work with."
    return "Something went wrong while running this line."
