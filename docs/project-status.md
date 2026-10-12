# Project Status

_Last updated: 2026-10-12_

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

## What's next?

Milestone 1 (v0.1), in this order, testing each stage alone before connecting them:

1. `checker.py`: undeclared and duplicate variable errors (done).
2. `generator.py`: Python output plus the line map (next).
3. `cli.py`: `scripty run` and `scripty build`, with runtime errors translated to Scripty terms.
4. An example `hello.scy` and tests.
