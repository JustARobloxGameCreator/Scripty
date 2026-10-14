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

- Kinds: `KEYWORD` (`let`, `show`, `echo`, `function`, `if`, `elif`, `else`, `give`, `for`, `in`), `NAME`, `NUMBER` (value is an `int` or `float`), `TEXT` (double quotes, one line, value without the quotes), `OPERATOR` (`+ - * / =` and the comparisons `== != >= <= > <`), `LPAREN`, `RPAREN`, `LBRACKET`, `RBRACKET` (`[` and `]`), `COMMA`, `COLON`, `NEWLINE`, `INDENT`, `DEDENT`.
- Each non-blank line ends with a `NEWLINE` token so the parser knows where a statement ends. Blank lines and whitespace produce no tokens.
- Comments: `//` (the style in `docs/to-do.md`) or `#` ignores the rest of the line. Both work; `//` or `#` inside quoted text is just text. Scripty has no integer division, so `//` is free to be a comment.
- Indentation: a block is indented by exactly **4 spaces** per level. A line one level deeper than the previous code line gets an `INDENT` token first; going back out gives one `DEDENT` per level (all remaining ones at the end of the file). Blank and comment-only lines do not affect indentation. A tab at the start of a line, an indent that is not a multiple of 4, or an indent that jumps more than one level are friendly errors. A lone `!` is an error that suggests `!=`.
- Errors raise `ScriptyError(message, line)` from `errors.py`, which prints as `Error on line N: ...`. Every stage reuses this class.
- Run the tests with `python -m unittest discover -s tests -t .`

### 4. Parser (tokens -> AST)
Checks that tokens follow the grammar and builds the syntax tree. Catches syntax errors such as `let = 5` or a missing value.

Implemented in `parser.py` as `parse(tokens) -> Program`. The tree nodes are simple dataclasses in `ast_nodes.py`: statements `Let(name, value, line)`, `Assign(name, value, line)` (a new value for an existing variable), `Show(value, line)`, `Echo(value, line)`, `CallStatement(call, line)`, `Give(value, line)`, `If(branches, else_body, else_line, line)` (each `Branch(condition, body, line)` is an `if` or `elif` part), `For(name, iterable, body, line)` and `Function(name, params, body, line)`; expressions `Number`, `Text`, `Name`, `BinaryOp(op, left, right, line)`, `Negate(operand, line)`, `Call(name, args, line)` and `ListLiteral(items, line)`. A `Compare(op, left, right, line)` is a condition and only appears in `if`/`elif`. A `Program` holds the list of statements. Every node keeps its line number.

Grammar (recursive descent, one function per rule):

```
statement  = "let" NAME "=" expression | NAME "=" expression
           | "show" expression | "echo" "(" expression ")"
           | call | "give" expression
           | "function" NAME "(" [ NAME { "," NAME } ] ")" block
           | "if" condition block { "elif" condition block } [ "else" block ]
           | "for" NAME "in" expression block
block      = ":" NEWLINE INDENT { statement } DEDENT
condition  = expression COMPARE expression | "(" condition ")"
expression = term { ("+" | "-") term }
term       = factor { ("*" | "/") factor }
factor     = "-" factor | NUMBER | TEXT | call | NAME | list | "(" expression ")"
list       = "[" [ expression { "," expression } ] "]"
call       = NAME "(" [ expression { "," expression } ] ")"
```

- `*` and `/` bind tighter than `+` and `-`; same-level operators group left to right; parentheses override.
- Unary minus is supported (`-5`, `3 * -x`) and binds tighter than `*` and `/`.
- `echo` needs parentheses, `show` does not.
- A condition is one comparison (`==`, `!=`, `>=`, `<=`, `>`, `<`). The parentheses around it are optional (`if (x > 5):` and `if x > 5:` are the same). `=` is only for `let`; `if x = 5:` gets an error that suggests `==`. No `and`/`or` yet, and comparisons are not values (`let a = 1 > 2` is an error).
- `function` is only allowed at the top level (not inside another function or an `if`). `give` is only allowed inside a function. `elif`/`else` need an `if` above them, and `else if` is rejected with a hint to write `elif`.
- A list is `[1, 2, 3]` or `[]`; the items can be any expressions. A trailing comma (`[1, 2,]`) is a friendly error, and so is a missing `]` or comma.
- `name = value` (no `let`) is a statement of its own and gives an existing variable a new value. The parser only checks the shape; the checker checks that the name exists. `x = 5` used to be a syntax error and is now valid.
- `for NAME in VALUE:` runs its indented body once per character of a text or once per item of a list. It is allowed at the top level, inside functions and inside `if` branches, and loops, `if`s and `give` may be nested inside a loop. A `function` cannot be written inside a loop.
- A call can be a value (`let r = Add(1, 2)`, `show Add(1, 2)`) or a whole line (`Greet("Ana")`).
- Friendly `for` errors: missing loop name, missing `in`, missing value, missing colon, missing body, wrong indentation, a keyword used as the loop name, `in` outside a `for`.
- Friendly errors: missing colon, missing or empty body, text after the colon on the same line, unexpected indent, missing function name/parentheses/commas, `give` outside a function, missing condition or comparison.
- Syntax errors raise `ScriptyError` with a friendly message and line: missing name (`let = 5`), missing `=`, missing value, `show` with nothing, stray tokens, unbalanced parentheses, an operator where a value was expected.

### 5. Checker (AST -> AST or error)
A light pass for meaning errors. Its main job is **clear, beginner-friendly messages**.

Implemented in `checker.py` as `check(program) -> Program`. It returns the same tree unchanged if everything is fine, otherwise raises `ScriptyError`. It walks every statement and expression in order, remembering declared names and the line each was declared on.

- Undeclared variable: `Error on line 2: I don't know what "z" is. Did you forget to write: let z = ...`
- A `let` value is checked **before** its name is declared, so `let x = x + 1` is an error when `x` is new.
- Declaring the same name twice with `let` is an error (`"x" is already declared on line 1 ... To change its value, write: x = ... (without let). Or pick a different name.`). There is still no shadowing.
- The first error found stops the check.
- **Scopes.** The top of the program is the global scope. A function has its **own** scope: its inputs and every `let` inside it are local, and it **cannot see** global variables (pass them in as inputs; the error says so, e.g. `function F(g)`). So a `let x` inside a function never clashes with a `let x` outside. The lines inside an `if`/`elif`/`else` branch form a small scope: variables made there disappear after the branch; a branch can see what is around it but cannot redeclare a name that is already visible (no silent shadowing, so "declared twice" still applies).
- **Loops.** `for NAME in VALUE:` has a scope of its own: the loop variable and every `let` inside the loop disappear after it, so the name can be used again afterwards. Like in an `if` branch, the loop variable may **not** reuse a name that is already visible (no shadowing), and a `let` inside the loop cannot reuse the loop variable. The loop sees everything around it; a function's loop sees only that function's names. Going through a text gives text (one character) at each step; going through a list (or something of unknown kind) gives a value of unknown kind, because a list may hold numbers or text. If the value is known to be a number (`for i in 5:` or a number variable) the checker raises `You can only go through text or a list with for, but 5 is a number.`; function inputs and call results have an unknown kind, so that mistake is caught at run time by the runner with the same wording.
- **Functions.** Names are declared once (`The function "F" is already defined on line N`), cannot also be a variable or input name, and are visible everywhere. A call at the top of the program must come after the function's lines; functions may call themselves and each other. Calling an unknown function, calling a variable, using a function name without `(...)`, or passing the wrong number of inputs are friendly errors with the call's line. A function with a `give` (also one inside an `if` or a `for`) must give on every path (its last line is a `give`, or an if/else where every branch gives). A `for` never counts as giving, because the text may be empty and the loop may run zero times, so put a `give` after the loop (a `give` inside a loop is fine, as long as the function ends with one that always runs); a function with no `give` can only be called as a line on its own, not used as a value.
- **Conditions.** `==` and `!=` may compare any two values (text and number are just never equal). `>`, `<`, `>=`, `<=` need two numbers or two texts (texts compare alphabetically); mixing text and number there is an error. Function inputs and call results have an *unknown* kind: the checker accepts them and the runner catches real mistakes.
- **Reassignment.** `name = value` needs a name that is visible at that line, otherwise the usual `I don't know what "x" is. Did you forget to write: let x = ...` error appears. A variable made inside an `if`/`for` block can only be changed inside that block; an outer variable can be changed from inside a top-level `if`/`for`. A function can change its own inputs and its own variables, but (like reading) it cannot reach variables outside it. The new value must have the same kind (number, text or list) as the old one when both kinds are known, otherwise `"a" holds a list (made on line 1), so it can't be changed to a number.`. Function inputs and call results have an unknown kind, so they can be given anything and the kind of a variable stays what it was.
- **Lists.** A list holds numbers or text; mixing them is allowed (sorting or `max` of a mixed list is a friendly run-time error). A list inside a list is rejected (`A list can't hold another list yet.`). `list + list` joins two lists into a new list; every other calculation with a list (`* - /`, list + number, minus sign) is an error, and `> < >= <=` do not work on lists, while `==` and `!=` do.
- **Built-in functions.** `max(list)`, `min(list)`, `len(list or text)` and `sort(list)`. Their names are reserved: using `max`, `min`, `len` or `sort` as a variable, input, loop variable or function name is an error (so existing programs that used `min` or `len` as names must rename them). They need exactly 1 input, and a known number or text (a list for `max`/`min`/`sort`) is an error; unknown kinds are accepted. `sort(a)` sorts the list itself (in place), gives nothing back, and is only allowed as a line on its own with a variable (`sort(a)`); `let b = sort(a)` is an error that explains this. `max(a)`, `min(a)` and `len(a)` give answers, so they cannot stand alone on a line (`show max(a)`). `max`/`min` results have an unknown kind; `len` gives a number.
- **Types.** Every value is a number, text or a list; the checker remembers the kind of each variable from its `let`. Numbers work with `+ - * /`. Text can only be joined with other text using `+` (concatenation, `"a" + "b"` is `ab`). Everything else is an error with the operator's line: `"a" + 1`, `"a" * "b"`, `-"a"`, e.g. `You can't use "+" to mix text and a number. ...`. The checker is the primary defence; the runner's TypeError translation is the safety net.

### 6. Generator (AST -> Python text)
Walks the tree and writes equivalent Python. Each Scripty construct maps to one Python construct (`let` -> assignment, `show` and `echo` -> `print`). Keep the mapping simple.

Implemented in `generator.py` as `generate(program) -> (python_source, line_map)`.

- One Python line per statement or block header (`def`, `if`, `elif`, `else`, `for`), indented 4 spaces per level. `function F(a):` becomes `def F(a):`, `if (c):` becomes `if c:`, `for c in "hi":` becomes `for c in 'hi':`, `give x` becomes `return x`; calls and comparisons are written as they are. `line_map` is a dict from Python line number to Scripty line number (blank lines and comments in Scripty do not exist in the Python, so the numbers differ).
- Text is written with `repr`, so quotes and backslashes are always safe.
- The tree is preserved exactly: every operation nested in another gets parentheses (`1 + 2 * 3` -> `1 + (2 * 3)`).
- A list is a Python list: `[1, 2]` -> `[1, 2]`. `max(a)`, `min(a)` and `len(a)` keep their names, and `sort(a)` becomes `a.sort()`, which sorts the list itself. `name = value` -> `name = value`. `show a` is still `print(a)` (the runner prints lists in the Scripty way).
- Division is **true division** (Python `/`): `7 / 2` is `3.5`, `4 / 2` is `2.0`.
- A variable, function or input named like a Python keyword (`class`) or `print` is renamed with a `_scy` suffix in the generated code. Every generated line, including `elif` and `else:`, has an entry in the line map.

### 7. Run
Executes the generated Python. Output appears in the terminal.

Implemented in `runner.py` as `run_python(source, line_map)`. The code is compiled with the fixed filename `<scripty>` and run with `exec()`. The program gets its own `print`, so `show` writes a list the Scripty way (`[1, 2, 3]`, and text items in double quotes: `["Ana", "Bo"]`); numbers and text print exactly as before. (`scripty build` shows plain `print(a)`; run on its own with Python, that would print Python's single quotes.) If it raises, the traceback entry for `<scripty>` gives the Python line, the line map gives the Scripty line, and a `ScriptyError` is raised with a friendly message:

- `ZeroDivisionError`: `You tried to divide by zero. Dividing by zero has no answer.`
- `TypeError` from a `for` over a number ("... is not iterable"): `You can only go through text or a list with for, but this value is a number.` (for `max`/`min`/`sort` of a number the message says they need a list). Comparing or sorting text with a number: `You tried to compare (or sort or find the max of) text with a number. ...`. `len` of a number, `sort` of a non-list, and `max`/`min` of an empty list (`max needs at least one item, but the list is empty.`) are friendly too. Any other `TypeError`: mixing text and numbers.
- `NameError`: `I don't know what "z" is. ...`
- `RecursionError`: a function kept calling itself and never stopped.
- `OverflowError`: the number is too big.

Because functions, branches and loops are real Python lines in the line map, errors raised inside them report the Scripty line inside the function, branch or loop.
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

See `examples/functions.scy` and `examples/conditions.scy`.

## v0.3 language scope (loops)

```
for i in "hello world!":
    show i
```

prints one character per line (the space prints as a blank-looking line). See `examples/loops.scy`. From v0.4 a list can be looped over too; the AI features are not implemented yet.

## v0.4 language scope (lists)

```
let a = [0, 1, 3]
show max(a)   // 3
a = [0, 4, 2, 6, 3]
sort(a)
show a        // [0, 2, 3, 4, 6]
```

See `examples/lists.scy`. Notes:

- `name = value` changes a variable that already exists. Re-declaring with `let` is still an error.
- Lists are shared, like in Python: after `let b = a`, `sort(a)` also changes what `b` shows, and a function that sorts its input sorts the caller's list. Use `let b = a + []` to make a separate copy.
- `show` of a list: numbers as `[1, 2.5]`, text in double quotes as `["a", "b"]`, empty as `[]`.
- Not supported yet: lists inside lists, getting one item by position, adding items one at a time.

## Growing the language

Later versions add the AI features. Each is added as new tokens, tree nodes, and generator rules. **The pipeline stays the same.**

## Design principles

- Clarity and beginner-friendly error messages are the edge over Python.
- Prefer simple, readable code over clever or fast code.
- Test each stage with small examples before connecting them.
