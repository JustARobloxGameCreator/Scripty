# Changelog

All notable changes to Scripty are recorded here, newest first.

## [Unreleased]

### Added
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
