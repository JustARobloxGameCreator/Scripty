# Changelog

All notable changes to Scripty are recorded here, newest first.

## [Unreleased]

### Added
- CLI (`cli.py`): `run` and `build` commands, friendly errors for a missing file or wrong extension, exit code 1 on any error. Launchers `scripty.py` and `scripty.bat` (issue #5).
- Runner (`runner.py`): runs generated Python and translates runtime errors (divide by zero, type, name, anything else) into `Error on line N: ...` using the line map. No Python traceback is ever shown.
- Checker: simple number/text type tracking. Mixing text and numbers, or using `- * /` with text, is a friendly error; text + text is allowed (concatenation).
- `hello.scy` and `examples/text.scy`; tests in `tests/test_cli.py`, `tests/test_runner.py` and new checker type tests.
- Generator (`generator.py`): `generate(program)` returns Python source and a Python-line -> Scripty-line map, with tests in `tests/test_generator.py` (issue #4).
- Checker (`checker.py`): friendly errors for undeclared variables (including `let x = x + 1`) and duplicate declarations, with unit tests in `tests/test_checker.py` (issue #3).
- Parser (`parser.py`) and AST nodes (`ast_nodes.py`): `let`, `show`, `echo`, arithmetic with precedence, parentheses and unary minus, with friendly line-numbered syntax errors (issue #2).
- Parser unit tests in `tests/test_parser.py`.
- Lexer (`lexer.py`): tokens with line numbers, `#` comments, friendly errors for unknown characters and unclosed text (issue #1).
- `errors.py` with `ScriptyError`, the shared friendly error (`Error on line N: ...`).
- Lexer unit tests in `tests/test_lexer.py` (stdlib `unittest`).
- Project documentation in `docs/`: `architecture.md`, `changelog.md`, `project-status.md`.
- `CLAUDE.md` project guidance (git workflow, goals, pipeline, v0.1 scope).

### Changed
- `CLAUDE.md` now requires updating the three docs files after every major update.

## Initial commit
- Repository created with the LICENSE file.
