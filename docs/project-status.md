# Project Status

_Last updated: 2026-10-12_

## How to run and test

From the repo folder (Python 3.10 or newer, no other dependencies):

```
python scripty.py run hello.scy      # prints 8
python scripty.py build hello.scy    # prints the generated Python
scripty run hello.scy                # Windows only, uses scripty.bat
python -m unittest discover -s tests -t . -v   # run all tests
```

Examples live in `hello.scy` and `examples/`. Errors are shown as `Error on line N: ...`, never as a Python traceback.

## What are the project milestones?

1. **Basic features (v0.1):** variable declaration, arithmetic, `show`, `echo`, numbers and text, friendly line-numbered errors. A basic language to be improved over time.
2. **More features:** conditions, loops, functions, and then the AI features. Plan and implement them in that order.
3. **Public release:** release Scripty, then add or fix features based on user feedback.

## What's been accomplished?

- Repository created, with the `development` branch tracking the remote.
- Project plan written in `CLAUDE.md`: goals, pipeline design, error-handling rules, v0.1 scope.
- Documentation set up in `docs/` (architecture, changelog, this status file).
- Lexer done (`lexer.py`, `errors.py`) with unit tests in `tests/`.
- Parser done (`parser.py`, `ast_nodes.py`) with unit tests: `let`, `show`, `echo`, arithmetic, parentheses, friendly syntax errors.
- Checker done (`checker.py`) with unit tests: undeclared variables and duplicate declarations.
- Generator done (`generator.py`) with unit tests: Python output plus line map.
- CLI done (`cli.py`, `runner.py`, `scripty.py`, `scripty.bat`): `run` and `build`, runtime errors translated to Scripty lines, number/text type checks, `hello.scy` prints 8.

## What's next?

Milestone 1 (v0.1), in this order, testing each stage alone before connecting them:

1. `checker.py`: undeclared and duplicate variable errors (done).
2. `generator.py`: Python output plus the line map (done).
3. `cli.py`: `scripty run` and `scripty build`, with runtime errors translated to Scripty terms (done).
4. An example `hello.scy` and tests (done).

Milestone 1 (v0.1) is complete. Next is milestone 2: conditions, loops, functions, then the AI features.
