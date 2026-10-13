# Changelog

All notable changes to Scripty are recorded here, newest first.

## [Unreleased]

### Added (conditions and functions, issues #12 and #14)
- Conditions: `if`, `elif`, `else` with the comparisons `== != >= <= > <`. Parentheses around the condition are optional.
- Functions: `function Name(a, b):`, `give` (Python `return`), and calls as values (`let r = Name(1, 2)`) or as a line on their own (`Greet("Ana")`). Recursion works.
- Blocks are indented with exactly 4 spaces; the lexer now produces `INDENT`/`DEDENT` tokens. Tabs, odd indents and over-indents are friendly errors.
- `//` comments (as in `docs/to-do.md`); `#` comments still work. `//` or `#` inside text is not a comment.
- Checker: function scopes (functions cannot see outside variables), branch scopes, function name rules, unknown function / wrong number of inputs errors, text-vs-number ordering comparison error, "give on every path" rule.
- Generator: `def`, `if`/`elif`/`else`, `return`, with a correct line map for every line.
- Runner: friendly message for endless recursion.
- `examples/functions.scy`, `examples/conditions.scy`, `docs/to-do.md`, and tests for every stage (246 tests in total).

### Changed (conditions and functions)
- A line that is indented without a block above it is now an error (before, leading spaces were ignored). Indents must be multiples of 4 spaces.
- `Name(` is now a function call; before it was a syntax error.
- The error for a line starting with a name now also lists `give`, `if`, `function` and calls (the text "must start with" is unchanged).
- Not done yet: loops (#13) and the AI features.

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
