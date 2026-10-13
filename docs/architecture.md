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
| CLI | `cli.py`, `scripty.py`, `scripty.bat` | command | file path | file not found, wrong extension |
| Read | `cli.py` (`read_source`) | file path | source text | unreadable file |
| Lexer | `lexer.py` | text | tokens (with line numbers) | bad character, unclosed string, bad indentation |
| Parser | `parser.py` | tokens | AST | syntax error (`let = 5`) |
| Checker | `checker.py` | AST | AST or error | undeclared variable, duplicate declaration, unknown function, wrong number of inputs |
| Generator | `generator.py` | AST | Python text (+ line map) | rare, internal |
| Run | `runner.py` | Python text | program output | runtime errors (e.g. divide by zero) |

### 1. CLI
Receives the file path, checks that the file exists and ends in `.scy`, otherwise prints a friendly error and stops. Commands:

- `scripty run hello.scy` runs the program.
- `scripty build hello.scy` only prints the generated Python (for debugging and teaching).

Implemented in `cli.py` as `main(argv) -> exit code`. Ways to start it from the repo folder: `python scripty.py run hello.scy`, `python cli.py run hello.scy`, or `scripty run hello.scy` on Windows (`scripty.bat`). A missing file or a wrong extension prints `Error: I can't find the file "x.scy".` or `Error: Scripty files end in .scy, but "x.txt" does not.` Any `ScriptyError` is printed to stderr as `Error on line N: ...` and the exit code is 1 (0 on success). Output is forced to UTF-8.

### 2. Read
Loads the source as plain text. Nothing is interpreted yet.

### 3. Lexer (text -> tokens)
Splits the text into tokens (keyword, name, number, string, operator). Every token carries its **line number**. Catches unknown characters and unclosed strings.

Implemented in `lexer.py` as `tokenize(source) -> list[Token]`. A `Token` has `kind`, `value` and `line`.

- Kinds: `KEYWORD` (`let`, `show`, `echo`, `function`, `if`, `elif`, `else`, `give`), `NAME`, `NUMBER` (value is an `int` or `float`), `TEXT` (double quotes, one line, value without the quotes), `OPERATOR` (`+ - * / =` and the comparisons `== != >= <= > <`), `LPAREN`, `RPAREN`, `COMMA`, `COLON`, `NEWLINE`, `INDENT`, `DEDENT`.
- Each non-blank line ends with a `NEWLINE` token so the parser knows where a statement ends. Blank lines and whitespace produce no tokens.
- Comments: `//` (the style in `docs/to-do.md`) or `#` ignores the rest of the line. Both work; `//` or `#` inside quoted text is just text. Scripty has no integer division, so `//` is free to be a comment.
- Indentation: a block is indented by exactly **4 spaces** per level. A line one level deeper than the previous code line gets an `INDENT` token first; going back out gives one `DEDENT` per level (all remaining ones at the end of the file). Blank and comment-only lines do not affect indentation. A tab at the start of a line, an indent that is not a multiple of 4, or an indent that jumps more than one level are friendly errors. A lone `!` is an error that suggests `!=`.
- Errors raise `ScriptyError(message, line)` from `errors.py`, which prints as `Error on line N: ...`. Every stage reuses this class.
- Run the tests with `python -m unittest discover -s tests -t .`

### 4. Parser (tokens -> AST)
Checks that tokens follow the grammar and builds the syntax tree. Catches syntax errors such as `let = 5` or a missing value.

Implemented in `parser.py` as `parse(tokens) -> Program`. The tree nodes are simple dataclasses in `ast_nodes.py`: statements `Let(name, value, line)`, `Show(value, line)`, `Echo(value, line)`, `CallStatement(call, line)`, `Give(value, line)`, `If(branches, else_body, else_line, line)` (each `Branch(condition, body, line)` is an `if` or `elif` part) and `Function(name, params, body, line)`; expressions `Number`, `Text`, `Name`, `BinaryOp(op, left, right, line)`, `Negate(operand, line)` and `Call(name, args, line)`. A `Compare(op, left, right, line)` is a condition and only appears in `if`/`elif`. A `Program` holds the list of statements. Every node keeps its line number.

Grammar (recursive descent, one function per rule):

```
statement  = "let" NAME "=" expression | "show" expression | "echo" "(" expression ")"
           | call | "give" expression
           | "function" NAME "(" [ NAME { "," NAME } ] ")" block
           | "if" condition block { "elif" condition block } [ "else" block ]
block      = ":" NEWLINE INDENT { statement } DEDENT
condition  = expression COMPARE expression | "(" condition ")"
expression = term { ("+" | "-") term }
term       = factor { ("*" | "/") factor }
factor     = "-" factor | NUMBER | TEXT | call | NAME | "(" expression ")"
call       = NAME "(" [ expression { "," expression } ] ")"
```

- `*` and `/` bind tighter than `+` and `-`; same-level operators group left to right; parentheses override.
- Unary minus is supported (`-5`, `3 * -x`) and binds tighter than `*` and `/`.
- `echo` needs parentheses, `show` does not.
- A condition is one comparison (`==`, `!=`, `>=`, `<=`, `>`, `<`). The parentheses around it are optional (`if (x > 5):` and `if x > 5:` are the same). `=` is only for `let`; `if x = 5:` gets an error that suggests `==`. No `and`/`or` yet, and comparisons are not values (`let a = 1 > 2` is an error).
- `function` is only allowed at the top level (not inside another function or an `if`). `give` is only allowed inside a function. `elif`/`else` need an `if` above them, and `else if` is rejected with a hint to write `elif`.
- A call can be a value (`let r = Add(1, 2)`, `show Add(1, 2)`) or a whole line (`Greet("Ana")`).
- Friendly errors: missing colon, missing or empty body, text after the colon on the same line, unexpected indent, missing function name/parentheses/commas, `give` outside a function, missing condition or comparison.
- Syntax errors raise `ScriptyError` with a friendly message and line: missing name (`let = 5`), missing `=`, missing value, `show` with nothing, stray tokens, unbalanced parentheses, an operator where a value was expected.

### 5. Checker (AST -> AST or error)
A light pass for meaning errors. Its main job is **clear, beginner-friendly messages**.

Implemented in `checker.py` as `check(program) -> Program`. It returns the same tree unchanged if everything is fine, otherwise raises `ScriptyError`. It walks every statement and expression in order, remembering declared names and the line each was declared on.

- Undeclared variable: `Error on line 2: I don't know what "z" is. Did you forget to write: let z = ...`
- A `let` value is checked **before** its name is declared, so `let x = x + 1` is an error when `x` is new.
- Declaring the same name twice is an error in v0.1 (`"x" is already declared on line 1 ...`). This rule may be relaxed when reassignment is added.
- The first error found stops the check.
- **Scopes.** The top of the program is the global scope. A function has its **own** scope: its inputs and every `let` inside it are local, and it **cannot see** global variables (pass them in as inputs; the error says so, e.g. `function F(g)`). So a `let x` inside a function never clashes with a `let x` outside. The lines inside an `if`/`elif`/`else` branch form a small scope: variables made there disappear after the branch; a branch can see what is around it but cannot redeclare a name that is already visible (no silent shadowing, so "declared twice" still applies).
- **Functions.** Names are declared once (`The function "F" is already defined on line N`), cannot also be a variable or input name, and are visible everywhere. A call at the top of the program must come after the function's lines; functions may call themselves and each other. Calling an unknown function, calling a variable, using a function name without `(...)`, or passing the wrong number of inputs are friendly errors with the call's line. A function with a `give` must give on every path (its last line is a `give`, or an if/else where every branch gives); a function with no `give` can only be called as a line on its own, not used as a value.
- **Conditions.** `==` and `!=` may compare any two values (text and number are just never equal). `>`, `<`, `>=`, `<=` need two numbers or two texts (texts compare alphabetically); mixing text and number there is an error. Function inputs and call results have an *unknown* kind: the checker accepts them and the runner catches real mistakes.
- **Types.** Every value is a number or text; the checker remembers the kind of each variable from its `let`. Numbers work with `+ - * /`. Text can only be joined with other text using `+` (concatenation, `"a" + "b"` is `ab`). Everything else is an error with the operator's line: `"a" + 1`, `"a" * "b"`, `-"a"`, e.g. `You can't use "+" to mix text and a number. ...`. The checker is the primary defence; the runner's TypeError translation is the safety net.

### 6. Generator (AST -> Python text)
Walks the tree and writes equivalent Python. Each Scripty construct maps to one Python construct (`let` -> assignment, `show` and `echo` -> `print`). Keep the mapping simple.

Implemented in `generator.py` as `generate(program) -> (python_source, line_map)`.

- One Python line per statement or block header (`def`, `if`, `elif`, `else`), indented 4 spaces per level. `function F(a):` becomes `def F(a):`, `if (c):` becomes `if c:`, `give x` becomes `return x`; calls and comparisons are written as they are. `line_map` is a dict from Python line number to Scripty line number (blank lines and comments in Scripty do not exist in the Python, so the numbers differ).
- Text is written with `repr`, so quotes and backslashes are always safe.
- The tree is preserved exactly: every operation nested in another gets parentheses (`1 + 2 * 3` -> `1 + (2 * 3)`).
- Division is **true division** (Python `/`): `7 / 2` is `3.5`, `4 / 2` is `2.0`.
- A variable, function or input named like a Python keyword (`class`) or `print` is renamed with a `_scy` suffix in the generated code. Every generated line, including `elif` and `else:`, has an entry in the line map.

### 7. Run
Executes the generated Python. Output appears in the terminal.

Implemented in `runner.py` as `run_python(source, line_map)`. The code is compiled with the fixed filename `<scripty>` and run with `exec()`. If it raises, the traceback entry for `<scripty>` gives the Python line, the line map gives the Scripty line, and a `ScriptyError` is raised with a friendly message:

- `ZeroDivisionError`: `You tried to divide by zero. Dividing by zero has no answer.`
- `TypeError`: mixing text and numbers.
- `NameError`: `I don't know what "z" is. ...`
- `RecursionError`: a function kept calling itself and never stopped.
- `OverflowError`: the number is too big.

Because functions and branches are real Python lines in the line map, errors raised inside them report the Scripty line inside the function or branch.
- any other exception: `Something went wrong while running this line.`

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

## v0.2 language scope (conditions and functions)

```
function Compare(a, b):
    if (a > b): // This is a comment
        give "bigger"
    elif (a == b):
        give "equal"
    else:
        give "smaller"

show Compare(5, 2)
```

See `examples/functions.scy` and `examples/conditions.scy`. Loops and the AI features are not implemented yet.

## Growing the language

Later versions add loops and then the AI features. Each is added as new tokens, tree nodes, and generator rules. **The pipeline stays the same.**

## Design principles

- Clarity and beginner-friendly error messages are the edge over Python.
- Prefer simple, readable code over clever or fast code.
- Test each stage with small examples before connecting them.
