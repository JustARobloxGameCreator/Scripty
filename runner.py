"""Runner: executes generated Python and translates runtime errors.

`run_python(source, line_map)` compiles the code under a known filename and
runs it with exec(). If anything goes wrong, the traceback is used to find
which line of the generated Python failed, the line map turns that into a
Scripty line, and a friendly ScriptyError is raised. The user never sees a
Python traceback.
"""

import traceback

from errors import ScriptyError

# The filename the generated code is compiled under. Traceback entries with
# this filename belong to the user's program (not to Scripty itself).
GENERATED_FILENAME = "<scripty>"


def run_python(source: str, line_map: dict[int, int]) -> None:
    """Run generated Python. Raises ScriptyError if the program fails."""
    code = compile(source, GENERATED_FILENAME, "exec")
    try:
        exec(code, {"__name__": "__scripty__"})
    except Exception as error:
        line = _scripty_line(error, line_map)
        raise ScriptyError(_friendly_message(error), line) from None


def _scripty_line(error: Exception, line_map: dict[int, int]) -> int:
    """Find the Scripty line where the error happened."""
    python_line = None
    for frame in traceback.extract_tb(error.__traceback__):
        if frame.filename == GENERATED_FILENAME:
            python_line = frame.lineno  # keep the innermost generated frame
    if python_line in line_map:
        return line_map[python_line]
    return max(line_map.values(), default=1)  # should not happen


def _friendly_message(error: Exception) -> str:
    if isinstance(error, ZeroDivisionError):
        return "You tried to divide by zero. Dividing by zero has no answer."
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
