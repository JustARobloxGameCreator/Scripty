"""Runner: executes generated Python and translates runtime errors.

`run_python(source, line_map)` compiles the code under a known filename and
runs it with exec(). If anything goes wrong, the traceback is used to find
which line of the generated Python failed, the line map turns that into a
Scripty line, and a friendly ScriptyError is raised. The user never sees a
Python traceback.

The program runs with its own `print`, so `show` writes a list the Scripty
way: [1, 2, 3] for numbers and ["a", "b"] for text (Python would write
single quotes). Numbers and text are printed exactly as Python prints them.

It also gets two helpers for the list actions `a.remove(value)` and
`a.pop(index)`: `remove_all` (prints a warning to stderr and goes on when
nothing matches) and `pop_at` (raises a friendly error for a bad position).
"""

import sys
import traceback

from errors import ScriptyError

# The filename the generated code is compiled under. Traceback entries with
# this filename belong to the user's program (not to Scripty itself).
GENERATED_FILENAME = "<scripty>"


def format_value(value: object) -> str:
    """Write a value the way `show` prints it."""
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
    """A friendly problem with a list action (the message is shown as is)."""


def _describe_kind(value: object) -> str:
    if isinstance(value, list):
        return "a list"
    return "text" if isinstance(value, str) else "a number"


def remove_all(items: object, value: object, line: int) -> None:
    """a.remove(value): remove every item equal to value, or warn."""
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


def pop_at(items: object, index: object) -> None:
    """a.pop(index): remove the item at that position (counting from 0)."""
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


def run_python(source: str, line_map: dict[int, int]) -> None:
    """Run generated Python. Raises ScriptyError if the program fails."""
    code = compile(source, GENERATED_FILENAME, "exec")
    try:
        exec(code, {"__name__": "__scripty__", "print": _scripty_print,
                   "remove_all": remove_all, "pop_at": pop_at})
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
    if isinstance(error, TypeError) and "not iterable" in str(error):
        if not failed_line.startswith("for "):  # max(...), min(...), sort
            return "max, min and sort need a list, but this value is a number."
        return ("You can only go through text or a list with for, but "
                "this value is a number.")
    if isinstance(error, TypeError) and "has no len" in str(error):
        return "len needs a list or text, but this value is a number."
    if isinstance(error, TypeError) and "not supported between" in str(error):
        return ("You tried to compare (or sort or find the max of) text "
                "with a number. Everything must be numbers, or everything "
                "must be text.")
    if isinstance(error, AttributeError) and "'sort'" in str(error):
        return "sort needs a list, but this value is not a list."
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
