# CLAUDE.md

Guidance for Claude when working on Scripty.

## Git workflow

- Remote repository: https://github.com/JustARobloxGameCreator/Scripty.git
- **Always work on a branch called `development`.** Do not commit directly to `main`/`master`.
- If the `development` branch does not exist (locally or on the remote), **create it** (`git checkout -b development`) and push it with upstream tracking (`git push -u origin development`).
- If the local folder is not yet a git repository, run `git init`, add the remote above, and fetch before creating or checking out `development`.
- Never force-push, and never merge into `main`/`master` unless the user explicitly asks.

## Project goal

Scripty is a programming language built to make creating an AI easy and understandable, so that anyone can build one. It must be **clear and straightforward**, because it is planned to be released to the public. The author also wants to exercise their Python skills with it.

- Security is not a concern; it is just a simple programming language.
- **Ignore the AI part for now.** First make Scripty work like any back-end programming language. The AI features come later.

## Milestones

1. Basic features: variable declaration, arithmetic, etc. (v0.1, a basic language to be improved over time).
2. Plan and implement more features (conditions, loops, functions, and then the AI features).
3. Release to the public, then add or fix features based on user feedback.

## Who it is for, and why

AI is confusing and hard to build. Scripty exists to make that experience easy to understand. Its edge over Python is **clarity and beginner-friendly error messages**.

## How Scripty runs

Scripty is a **compiled-to-Python** language, built in Python. Running a program translates it to Python and then executes the result. The user never has to see the Python. It is slower than a native language, but simple and understandable, which is the point.

```
hello.scy  ->  Read  ->  Lex  ->  Parse  ->  Check  ->  Generate Python  ->  Run  ->  Output
```

Example (`hello.scy`):

```
let x = 5
let y = x + 3
show y
```

Run with `scripty run hello.scy`. It produces `8`.

### Pipeline stages

1. **CLI**: receives the file path, checks that the file exists and ends in `.scy`. Otherwise it prints a friendly error and stops.
2. **Read**: load the source as plain text. Nothing is interpreted yet.
3. **Lexer** (text -> tokens): split the text into tokens (keyword, name, number, operator), each with its **line number**. Catches unknown characters and unclosed strings.
4. **Parser** (tokens -> AST): check that the tokens follow the grammar and build the tree. Catches syntax errors such as `let = 5` or a missing value.
5. **Checker** (AST -> AST or error): a light pass for meaning errors, such as using a variable before declaring it, or declaring one twice (if disallowed). Its main job is **clear, beginner-friendly messages**.
6. **Generator** (AST -> Python text): walk the tree and write equivalent Python. Each Scripty construct maps to one Python construct (`let` -> assignment, `show` -> `print`). Keep this mapping simple.
7. **Run**: execute the generated Python (via `exec()` or a temporary `.py` file). The output appears in the terminal.

| Stage | Input | Output | Typical errors |
|---|---|---|---|
| CLI | command | file path | file not found |
| Lexer | text | tokens | bad character |
| Parser | tokens | AST | syntax error |
| Checker | AST | AST (or error) | undeclared variable |
| Generator | AST | Python text | (rare, internal) |
| Run | Python | program output | runtime errors |

### Error handling

If any step fails, **stop immediately** and show an error in Scripty terms, **never a Python traceback**:

```
Error on line 2: I don't know what "z" is. Did you forget to write: let z = ...
```

Runtime errors from Python (such as dividing by zero) must be caught and translated the same way, using the Scripty line number. Keep a line map from Python lines back to Scripty lines.

## v0.1 scope

- Variables: `let x = 5`
- Arithmetic: `+ - * /`
- Output: `show x` instead of `return x`
- `echo("Hello world!")` instead of `print("Hello world!")`
- Numbers and text values
- Friendly, line-numbered errors

Later versions add conditions, loops, functions, and then the AI features, each as new tokens, tree nodes, and generator rules. The pipeline stays the same.

## Code organization and build tips

- Write each stage as a separate Python file (`lexer.py`, `parser.py`, `checker.py`, `generator.py`, `cli.py`) so each can be tested alone.
- Add a `scripty build hello.scy` option that only outputs the Python. It is handy for debugging and teaching.
- Test each stage with small examples before connecting them.
- Prefer simple, readable code over clever or fast code.

## Important stuff

- Edit the folder docs with files of type .md whenever you make an important change to the code.
- **Every time a major update is made, update all three files in `docs/`:** `architecture.md` (how the code is supposed to work), `changelog.md` (what changed), and `project-status.md` (milestones, what's been accomplished, what's next).
- Check the files in the docs folder.