"""CLI: the command line front door of Scripty.

    scripty run hello.scy     run the program
    scripty build hello.scy   only print the generated Python

Pipeline: read -> tokenize -> parse -> check -> generate -> run.
Any ScriptyError stops the pipeline, is printed in friendly form (never a
Python traceback) and makes the exit code 1.
"""

import os
import sys

from checker import check
from errors import ScriptyError
from generator import generate
from lexer import tokenize
from parser import parse
from runner import run_python

USAGE = """Usage:
  scripty run FILE.scy     run a Scripty program
  scripty build FILE.scy   show the Python that Scripty writes for it"""


class CliError(Exception):
    """A friendly problem with the command or the file (not a code line)."""


def main(argv: list[str] | None = None) -> int:
    """Run the command line. Returns the exit code (0 = ok, 1 = error)."""
    args = sys.argv[1:] if argv is None else argv
    _use_utf8_output()
    try:
        if len(args) != 2 or args[0] not in ("run", "build"):
            raise CliError("I need a command and a file.\n" + USAGE)
        command, path = args
        source = read_source(path)
        python_source, line_map = compile_scripty(source)
        if command == "build":
            print(python_source, end="")
        else:
            run_python(python_source, line_map)
    except CliError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except ScriptyError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


def read_source(path: str) -> str:
    """Check the file name and load the file as text."""
    if not path.lower().endswith(".scy"):
        raise CliError(
            f'Scripty files end in .scy, but "{path}" does not.')
    if not os.path.isfile(path):
        raise CliError(f'I can\'t find the file "{path}".')
    try:
        with open(path, encoding="utf-8") as file:
            return file.read()
    except (OSError, UnicodeDecodeError):
        raise CliError(
            f'I can\'t read the file "{path}". '
            "Is it a text file saved as UTF-8?") from None


def compile_scripty(source: str) -> tuple[str, dict[int, int]]:
    """Scripty text -> (Python text, line map). Raises ScriptyError."""
    program = check(parse(tokenize(source)))
    return generate(program)


def _use_utf8_output() -> None:
    """Make printing text like "café" work on any terminal."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
