# Scripty Architecture

Scripty is a beginner-friendly programming language, built in Python, that is **compiled to Python**. When you run a program, Scripty translates it to Python and executes the result. The user never has to see the Python.

The long-term goal is to make building an AI easy and understandable. For now, the focus is a clear, simple back-end language with beginner-friendly error messages.

## The pipeline

```
hello.scy -> Read -> Lex -> Parse -> Check -> Generate Python -> Run -> Output
```

Each stage is its own Python file so it can be tested alone:

| Stage | File | Input | Output | Typical errors |
|---|---|---|---|---|
| CLI | `cli.py` | command | file path | file not found, wrong extension |
| Read | (in `cli.py`) | file path | source text | unreadable file |
| Lexer | `lexer.py` | text | tokens (with line numbers) | bad character, unclosed string |
| Parser | `parser.py` | tokens | AST | syntax error (`let = 5`) |
| Checker | `checker.py` | AST | AST or error | undeclared variable, duplicate declaration |
| Generator | `generator.py` | AST | Python text (+ line map) | rare, internal |
| Run | (in `cli.py`) | Python text | program output | runtime errors (e.g. divide by zero) |

### 1. CLI
Receives the file path, checks that the file exists and ends in `.scy`, otherwise prints a friendly error and stops. Commands:

- `scripty run hello.scy` runs the program.
- `scripty build hello.scy` only prints the generated Python (for debugging and teaching).

### 2. Read
Loads the source as plain text. Nothing is interpreted yet.

### 3. Lexer (text -> tokens)
Splits the text into tokens (keyword, name, number, string, operator). Every token carries its **line number**. Catches unknown characters and unclosed strings.

Implemented in `lexer.py` as `tokenize(source) -> list[Token]`. A `Token` has `kind`, `value` and `line`.

- Kinds: `KEYWORD` (`let`, `show`, `echo`), `NAME`, `NUMBER` (value is an `int` or `float`), `TEXT` (double quotes, one line, value without the quotes), `OPERATOR` (`+ - * / =`), `LPAREN`, `RPAREN`, `NEWLINE`.
- Each non-blank line ends with a `NEWLINE` token so the parser knows where a statement ends. Blank lines and whitespace produce no tokens.
- Comments: `#` ignores the rest of the line (a `#` inside text is kept).
- Errors raise `ScriptyError(message, line)` from `errors.py`, which prints as `Error on line N: ...`. Every stage reuses this class.
- Run the tests with `python -m unittest discover -s tests -t .`

### 4. Parser (tokens -> AST)
Checks that tokens follow the grammar and builds the syntax tree. Catches syntax errors such as `let = 5` or a missing value.

Implemented in `parser.py` as `parse(tokens) -> Program`. The tree nodes are simple dataclasses in `ast_nodes.py`: statements `Let(name, value, line)`, `Show(value, line)`, `Echo(value, line)`; expressions `Number`, `Text`, `Name`, `BinaryOp(op, left, right, line)` and `Negate(operand, line)`. A `Program` holds the list of statements. Every node keeps its line number.

Grammar (recursive descent, one function per rule):

```
statement  = "let" NAME "=" expression | "show" expression | "echo" "(" expression ")"
expression = term { ("+" | "-") term }
term       = factor { ("*" | "/") factor }
factor     = "-" factor | NUMBER | TEXT | NAME | "(" expression ")"
```

- `*` and `/` bind tighter than `+` and `-`; same-level operators group left to right; parentheses override.
- Unary minus is supported (`-5`, `3 * -x`) and binds tighter than `*` and `/`.
- `echo` needs parentheses, `show` does not.
- Syntax errors raise `ScriptyError` with a friendly message and line: missing name (`let = 5`), missing `=`, missing value, `show` with nothing, stray tokens, unbalanced parentheses, an operator where a value was expected.

### 5. Checker (AST -> AST or error)
A light pass for meaning errors: using a variable before declaring it, or declaring one twice (if disallowed). Its main job is **clear, beginner-friendly messages**.

### 6. Generator (AST -> Python text)
Walks the tree and writes equivalent Python. Each Scripty construct maps to one Python construct (`let` -> assignment, `show` -> `print`). Keep the mapping simple. The generator also records a **line map** from Python lines back to Scripty lines.

### 7. Run
Executes the generated Python (via `exec()` or a temporary `.py` file). Output appears in the terminal.

## Error handling

If any stage fails, **stop immediately** and show an error in Scripty terms, **never a Python traceback**:

```
Error on line 2: I don't know what "z" is. Did you forget to write: let z = ...
```

Runtime errors from Python (such as division by zero) are caught and translated the same way, using the line map to report the Scripty line number.

## v0.1 language scope

- Variables: `let x = 5`
- Arithmetic: `+ - * /`
- Output: `show x`
- `echo("Hello world!")`
- Numbers and text values
- Friendly, line-numbered errors

Example:

```
let x = 5
let y = x + 3
show y
```

`scripty run hello.scy` prints `8`.

## Growing the language

Later versions add conditions, loops, functions, and then the AI features. Each is added as new tokens, tree nodes, and generator rules. **The pipeline stays the same.**

## Design principles

- Clarity and beginner-friendly error messages are the edge over Python.
- Prefer simple, readable code over clever or fast code.
- Test each stage with small examples before connecting them.
