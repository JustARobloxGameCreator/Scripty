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

- Kinds: `KEYWORD` (`let`, `show`, `echo`, `function`, `if`, `elif`, `else`, `give`, `for`, `in`, `class`), `NAME`, `NUMBER` (value is an `int` or `float`), `TEXT` (double quotes, one line, value without the quotes), `OPERATOR` (`+ - * / =` and the comparisons `== != >= <= > <`), `LPAREN`, `RPAREN`, `LBRACKET`, `RBRACKET` (`[` and `]`), `COMMA`, `COLON`, `DOT`, `NEWLINE`, `INDENT`, `DEDENT`.
- A `.` is its own `DOT` token. Numbers are matched first, so `1.5` is still one `NUMBER`; a `.` is only valid after the name of a list or an object (`a.remove("Dog")`, `d.name`, `d.speak()`), and the parser reports it anywhere else (`.5`, `5.`). `self` and `super` are ordinary names to the lexer.
- Each non-blank line ends with a `NEWLINE` token so the parser knows where a statement ends. Blank lines and whitespace produce no tokens.
- Comments: `//` (the style in `docs/to-do.md`) or `#` ignores the rest of the line. Both work; `//` or `#` inside quoted text is just text. Scripty has no integer division, so `//` is free to be a comment.
- Indentation: a block is indented by exactly **4 spaces** per level. A line one level deeper than the previous code line gets an `INDENT` token first; going back out gives one `DEDENT` per level (all remaining ones at the end of the file). Blank and comment-only lines do not affect indentation. A tab at the start of a line, an indent that is not a multiple of 4, or an indent that jumps more than one level are friendly errors. A lone `!` is an error that suggests `!=`.
- Errors raise `ScriptyError(message, line)` from `errors.py`, which prints as `Error on line N: ...`. Every stage reuses this class.
- Run the tests with `python -m unittest discover -s tests -t .`

### 4. Parser (tokens -> AST)
Checks that tokens follow the grammar and builds the syntax tree. Catches syntax errors such as `let = 5` or a missing value.

Implemented in `parser.py` as `parse(tokens) -> Program`. The tree nodes are simple dataclasses in `ast_nodes.py`: statements `Let(name, value, line)`, `Assign(name, value, line)` (a new value for an existing variable), `AssignIndex(target, index, value, line)` (`a[1] = 9`; `target` is a `Name`), `Show(value, line)`, `Echo(value, line)`, `CallStatement(call, line)`, `MethodStatement(call, line)`, `Give(value, line)`, `If(branches, else_body, else_line, line)` (each `Branch(condition, body, line)` is an `if` or `elif` part), `For(name, iterable, body, line)`, `Function(name, params, body, line)`, `AssignAttribute(target, name, value, line)` (`d.name = 1`) and `ClassDef(name, parent, methods, line)` (`methods` is a list of `Function` nodes); expressions `Number`, `Text`, `Name`, `BinaryOp(op, left, right, line)`, `Negate(operand, line)`, `Call(name, args, line)`, `ListLiteral(items, line)`, `Index(target, index, line)` (`a[1]`, `"hello"[0]`; `target` is any expression) and `Attribute(target, name, line)` (`d.name`, `self.pet.name`) and `MethodCall(target, method, args, line)` (a list action such as `a.pop(1)`, an action of an object such as `d.speak()`, or `super.init(1)`; `target` is a `Name` or an `Attribute`). `Attribute` and `MethodCall` also carry a `target_kind` that the checker fills in for the generator (see below). A `Compare(op, left, right, line)` is a condition and only appears in `if`/`elif`. A `Program` holds the list of statements. Every node keeps its line number.

Grammar (recursive descent, one function per rule):

```
statement  = "let" NAME "=" expression | NAME "=" expression
           | NAME "[" expression "]" "=" expression
           | "show" expression | "echo" "(" expression ")"
           | call | member | member "=" expression | "give" expression
           | "function" NAME "(" [ NAME { "," NAME } ] ")" block
           | "class" NAME [ "(" NAME ")" ] ":" NEWLINE INDENT { function } DEDENT
           | "if" condition block { "elif" condition block } [ "else" block ]
           | "for" NAME "in" expression block
block      = ":" NEWLINE INDENT { statement } DEDENT
condition  = expression COMPARE expression | "(" condition ")"
expression = term { ("+" | "-") term }
term       = factor { ("*" | "/") factor }
factor     = "-" factor | primary { "[" expression "]" }
primary    = NUMBER | TEXT | call | member | NAME | list | "(" expression ")"
list       = "[" [ expression { "," expression } ] "]"
call       = NAME "(" [ expression { "," expression } ] ")"
member     = NAME { "." NAME } [ "." NAME "(" [ expression { "," expression } ] ")" ]
```

- `*` and `/` bind tighter than `+` and `-`; same-level operators group left to right; parentheses override.
- Unary minus is supported (`-5`, `3 * -x`) and binds tighter than `*` and `/`.
- `echo` needs parentheses, `show` does not.
- A condition is one comparison (`==`, `!=`, `>=`, `<=`, `>`, `<`). The parentheses around it are optional (`if (x > 5):` and `if x > 5:` are the same). `=` is only for `let`; `if x = 5:` gets an error that suggests `==`. No `and`/`or` yet, and comparisons are not values (`let a = 1 > 2` is an error).
- `function` is only allowed at the top level (not inside another function or an `if`). `give` is only allowed inside a function. `elif`/`else` need an `if` above them, and `else if` is rejected with a hint to write `elif`.
- A list is `[1, 2, 3]` or `[]`; the items can be any expressions. A trailing comma (`[1, 2,]`) is a friendly error, and so is a missing `]` or comma.
- `name = value` (no `let`) is a statement of its own and gives an existing variable a new value. The parser only checks the shape; the checker checks that the name exists. `x = 5` used to be a syntax error and is now valid.
- `for NAME in VALUE:` runs its indented body once per character of a text or once per item of a list. It is allowed at the top level, inside functions and inside `if` branches, and loops, `if`s and `give` may be nested inside a loop. A `function` cannot be written inside a loop.
- A dot comes after a name. `a.remove(value)` and `a.pop(index)` are list actions (whole lines), `d.speak(1)` runs an action of an object and `d.name` reads what an object remembers; chains through things work (`self.pet.name`, `self.pet.speak()`). The parser only checks the shape: any name (even a keyword such as `class`) may follow a dot, and whether `a` is a list or an object, and which actions exist, is the checker's job (the list-action error `I don't know what "add" does to a list...` therefore comes from the checker now, same words). A call ends the chain: `d.speak().x` and `Dog("a", 1).speak()` are friendly errors (put the answer in a variable first). A `.` after a number, text or `(a)` gets `A "." only works right after the name of a list ... or of an object`. A line that is only `d.name` is an error that says how to show or change it. `remove` and `pop` are not reserved words: they are still valid variable names.
- `class Name:` or `class Child(Parent):` has a 4-space indented body of `function` lines only (the actions), at the top level only (a class inside a function, a class, an `if` or a `for` is an error). A function directly inside a class is allowed one block deep; a function inside an action is not. `give` works inside actions. `d.name = value` is a line of its own (`AssignAttribute`); `self.x` reads and writes work anywhere an expression or statement does.
- **Indexing.** `[ ]` right after a value picks one item: `a[1]`, `a[-1]`, `a[i + 1]`, `"hello"[1]`, `F(1)[0]`, `(a + b)[2]`, and chained like `words[0][1]`. The parser lets it follow any value and leaves the meaning to the checker. It binds tighter than everything else, so `-a[0]` is `-(a[0])` and `a[0] + b[1] * 2` takes both items first. Spaces do not matter: `a [1]` is the same as `a[1]`. `let x = [1, 2]` is still a list, because a list starts a value while indexing follows one. A line that starts with `name[` must be an assignment `a[1] = 9`; only a plain name can be on the left (`a[0][1] = 9` is an error), and a line that is only `a[1]` is an error that says how to show or change the item. `a[]` and a missing `]` are friendly errors.
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
- **List actions.** `name.remove(value)` and `name.pop(index)` are checked like `sort(a)`: only as a line on their own (`let x = a.pop(1)` is an error saying the action changes the list and gives nothing back), the name must be a visible variable or input (the usual unknown-name and function-scope errors apply, so a function can only touch its own lists), a known number or text is an error (`remove only works on lists, but "n" is a number.`), and exactly one input is required. For `pop`, a known text or list, a decimal literal such as `1.5` and a negative literal such as `-1` are errors too. Unknown kinds (function inputs, call results, calculations) are accepted and checked by the runner.
- **Indexing.** `a[1]` works on a list or a text anywhere a value can be used; a known number is an error (`You can only use [ ] on a list or a text, but "n" is a number.`), and undeclared names and function scopes behave as usual. The position must be a whole number: a known text or list, or a decimal written in the program (`a[1.5]`, `a[-1.5]`), is an error; a position worked out while running (`4 / 2` is `2.0`) is accepted and checked by the runner. The kind of `a[i]` is text for a known text and *unknown* for everything else (a list's items may be mixed), so `a[1] + 1` and `show a[1]` never give false errors. `a[1] = 9` needs a visible name; a known number is an error, text is an error (`Text can't be changed one character at a time ...`), and the new value can be anything except a list (lists inside lists are not supported); its kind is not compared with the old item.
- **Classes.** See "v0.5 language scope" below for the rules; in short: class names are declared once in the same name list as functions and variables, a parent must be a class on an earlier line, every action starts with `self`, `self` and `super` are reserved, `Dog(...)` is checked against `init` (own or inherited, none = no inputs), `d.speak(...)` against the actions of the class and its parents, and `d.name` against every `x.name = ...` found in the program (an attribute that is never assigned is an error). Objects get the kind `object Dog`: they can be reassigned to the same class or a child class, compared with `==`/`!=` only, and `for`, `[ ]`, `len`, calculations and `< >` on them are errors.
- **Method calls resolve by what the target is.** A known list gets the list-action rules (`remove`, `pop`, as before, value use is an error); a known object gets the actions of its class; a known number or text is an error (`A number has no action called speak.`, and for the list actions the old `remove only works on lists, but "n" is a number.`); an unknown kind (a function input or a call result) is accepted and the runner decides while the program runs. For the generator the checker writes `target_kind` ("list", "object", "super" or "unknown") on each `MethodCall` and `Attribute` node; it is the only change the checker makes to the tree.
- **Types.** Every value is a number, text, a list or an object; the checker remembers the kind of each variable from its `let`. Numbers work with `+ - * /`. Text can only be joined with other text using `+` (concatenation, `"a" + "b"` is `ab`). Everything else is an error with the operator's line: `"a" + 1`, `"a" * "b"`, `-"a"`, e.g. `You can't use "+" to mix text and a number. ...`. The checker is the primary defence; the runner's TypeError translation is the safety net.

### 6. Generator (AST -> Python text)
Walks the tree and writes equivalent Python. Each Scripty construct maps to one Python construct (`let` -> assignment, `show` and `echo` -> `print`). Keep the mapping simple.

Implemented in `generator.py` as `generate(program) -> (python_source, line_map)`.

- One Python line per statement or block header (`def`, `if`, `elif`, `else`, `for`), indented 4 spaces per level. `function F(a):` becomes `def F(a):`, `if (c):` becomes `if c:`, `for c in "hi":` becomes `for c in 'hi':`, `give x` becomes `return x`; calls and comparisons are written as they are. `line_map` is a dict from Python line number to Scripty line number (blank lines and comments in Scripty do not exist in the Python, so the numbers differ).
- Text is written with `repr`, so quotes and backslashes are always safe.
- The tree is preserved exactly: every operation nested in another gets parentheses (`1 + 2 * 3` -> `1 + (2 * 3)`).
- A list is a Python list: `[1, 2]` -> `[1, 2]`. `max(a)`, `min(a)` and `len(a)` keep their names, and `sort(a)` becomes `a.sort()`, which sorts the list itself. `a.remove("Dog")` becomes `remove_all(a, 'Dog', 3)` (3 is the Scripty line, needed for the warning) and `a.pop(3)` becomes `pop_at(a, 3)`; names that clash with these helpers get the `_scy` suffix. `name = value` -> `name = value`. `a[1]` becomes `get_at(a, 1)` and `a[1] = 9` becomes `set_at(a, 1, 9)` (helpers, so the runner can give friendly errors that include the length). `show a` is still `print(a)` (the runner prints lists in the Scripty way).
- Division is **true division** (Python `/`): `7 / 2` is `3.5`, `4 / 2` is `2.0`.
- A variable, function, class, input, attribute or action named like a Python keyword (`def`, `None`) or `print` is renamed with a `_scy` suffix in the generated code (`class` itself can no longer be a variable name, but `d.class` still works as an attribute and becomes `d.class_scy`). Every generated code line, including `elif` and `else:`, has an entry in the line map.
- **Classes.** `class Dog:` -> `class Dog:`, `class Puppy(Dog):` -> `class Puppy(Dog):`, an action `function speak(self):` -> `def speak(self):` (so `give` is `return`), and `init` -> `__init__`. There is a blank line between actions and after a class (blank lines have no line map entry). `super.init(a)` -> `super().__init__(a)` and `super.speak()` -> `super().speak()`. `Dog("Rex", 3)` is an ordinary call. A known object gives plain Python: `d.speak()`, `d.name`, `d.name = 'Max'`. When the checker could not tell what the target is (a function input, or something read from a thing an object remembers, such as `self.pet.name`), the generator writes `get_attr(x, 'name')` and `call_action(x, 'speak', [args], LINE)` (with `, True` when the result is used as a value); an unknown `x.pop(i)` / `x.remove(v)` as a line stays `pop_at(x, i)` / `remove_all(x, v, LINE)`, which also pass the call on to an object. `call_action` and `get_attr` are reserved helper names (`_scy` for user names).

### 7. Run
Executes the generated Python. Output appears in the terminal.

Implemented in `runner.py` as `run_python(source, line_map)`. The code is compiled with the fixed filename `<scripty>` and run with `exec()`. The program gets its own `print`, so `show` writes a list the Scripty way (`[1, 2, 3]`, and text items in double quotes: `["Ana", "Bo"]`); numbers and text print exactly as before. (`scripty build` shows plain `print(a)`; run on its own with Python, that would print Python's single quotes.) If it raises, the traceback entry for `<scripty>` gives the Python line, the line map gives the Scripty line, and a `ScriptyError` is raised with a friendly message:

- `ZeroDivisionError`: `You tried to divide by zero. Dividing by zero has no answer.`
- `TypeError` from a `for` over a number ("... is not iterable"): `You can only go through text or a list with for, but this value is a number.` (for `max`/`min`/`sort` of a number the message says they need a list). Comparing or sorting text with a number: `You tried to compare (or sort or find the max of) text with a number. ...`. `len` of a number, `sort` of a non-list, and `max`/`min` of an empty list (`max needs at least one item, but the list is empty.`) are friendly too. Any other `TypeError`: mixing text and numbers.
- `remove_all` / `pop_at` (helpers the runner puts in the program's globals, next to the custom `print`): `remove_all(items, value, line)` removes every item equal to `value` in place, and if nothing matched it prints `Warning on line N: "Dog" is not in the list, so nothing was removed.` to **stderr** and carries on (exit code 0, stdout untouched; the value is shown the Scripty way, text in double quotes). `pop_at(items, index)` removes `items[index]` in place. Both raise a `ListActionError` (a friendly message, shown with the Scripty line from the line map) when the value is not a list; `pop_at` also reports a position that is not a whole number (`1.5`; `2.0` is accepted), is negative (`Positions start at 0 and can't be negative...`) or is too big (`The list has 3 items (positions 0 to 2), so there is no item at position 3.`, or `The list is empty, ...`).
- `get_at` / `set_at` (helpers too): `get_at(items, index)` is `a[index]` and `set_at(items, index, value)` is `a[index] = value`. Python rules: the first position is 0 and a negative position counts from the end (`-1` is the last item). They accept a list (or a text for `get_at`), and a position that is a whole number (`2.0` is fine). Friendly errors, all shown with the Scripty line: too big or too negative (`The list has 3 items (positions 0 to 2, or -1 to -3 from the end), so there is no item at position 3.`; one item: `(only position 0, or -1 from the end)`; for text `The text has 5 characters ...  no character at position 9.`), an empty list or text (`The list is empty, so there is no item at position 0.`), a decimal or non-number position, a number instead of a list or text, and `set_at` on a text. Note: `a.pop(index)` still rejects negative positions; only `[ ]` counts from the end.
- Classes (all shown with the Scripty line, also when the error happens inside an action, because every generated line is in the line map): `show d` prints `<Dog object>` (the class name between `<` and ` object>`, also inside a list: `[<Dog object>, <Cat object>]`, from the custom print). A thing an object does not have: `This Dog has nothing called "colour". Did you forget to give it one with: self.colour = ...` (an `AttributeError` on a Scripty class); a number, text or list instead of an object: `A number has nothing called "name". Only objects made from a class remember things like that.`; actions: `A number has no action called speak.`, `Text has no action called speak.`, `A list has no action called speak.`, `This Dog has no action called "fly".`, `The action "speak" of class "Dog" needs 0 inputs, but you gave 1.`, and an action that gave nothing used as a value. Calculations, `< >`, `for` and `len` on an object get friendly messages instead of the number-or-text ones. `is_object` is "the class was made by the program" (its module name is `__scripty__`).
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
a.remove(4)
a.pop(0)
show a        // [2, 3, 6]
show a[0]     // 2
a[0] = 9
show a        // [9, 3, 6]
```

See `examples/lists.scy` and `examples/list_methods.scy`. Notes:

- `name = value` changes a variable that already exists. Re-declaring with `let` is still an error.
- Lists are shared, like in Python: after `let b = a`, `sort(a)` also changes what `b` shows, and a function that sorts its input sorts the caller's list. Use `let b = a + []` to make a separate copy.
- `show` of a list: numbers as `[1, 2.5]`, text in double quotes as `["a", "b"]`, empty as `[]`.
- `a.remove(value)` removes every item equal to `value`; if there is none, a warning goes to stderr and the program keeps running. `a.pop(index)` removes the item at that position (the first is 0). Both change the list itself, so they are lines on their own and give nothing back.
- `a[1]` gives the item at a position and `a[1] = 9` replaces it (the first position is 0, negative positions count from the end, like Python). It also works on text: `"hello"[1]` is `e`. See `examples/indexing.scy`.
- Not supported yet: lists inside lists, adding items one at a time, slices such as `a[1:3]`.

## v0.5 language scope (classes)

```
class Dog:
    function init(self, name, age):
        self.name = name
        self.age = age
    function speak(self):
        give self.name + " says woof"
    function birthday(self):
        self.age = self.age + 1

class Puppy(Dog):
    function speak(self):
        give self.name + " says yip"

let d = Dog("Rex", 3)
show d.speak()        // Rex says woof
d.birthday()
show d.age            // 4
d.name = "Max"
let p = Puppy("Bit", 1)
show p.speak()        // Bit says yip
```

See `examples/classes.scy`. Python-shaped, but in Scripty's words. The decisions:

- **Syntax.** `class Name:` with an indented body that holds only `function` lines (the actions). `class Child(Parent):` has one parent (single inheritance); actions are inherited and can be overridden. The parent must be a class written on an earlier line (otherwise a friendly error). Classes are top level only, like functions. `class` is a reserved word (a variable called `class` is an error); `self` and `super` are reserved everywhere (not only inside actions): they cannot be a variable, input, loop variable, function or class name, and `self` cannot be reassigned. Attribute and action names are not reserved words (`d.class`, `self.show` work), but names that start with two underscores are reserved.
- **Names.** Class, function and variable names share one list (no clashes, in either order). A class may be used inside an action or function even if it is written lower down, as long as the class exists when the call runs; a call at the top of the program must come after the class.
- **init.** The constructor is an action called `init` (Scripty's word, Python's `__init__` in the generated code). `Dog("Rex", 3)` makes an object and runs `init` with the inputs after `self`. No `init` means the class takes no inputs; the checker counts the inputs (an inherited `init` counts) and reports a wrong number. `init` cannot `give` a value. `d.init(...)` is an error: use `super.init(...)` in a child.
- **self.** The first input of every action must be named `self` (friendly error otherwise, explaining it is the object the action works on). It is not passed when calling: `d.speak()`.
- **Attributes.** An object remembers things: `self.name = name` (or `d.name = "Max"`, a line of its own) creates or changes one, and `d.name` / `self.name` reads one (an expression). They are created by assigning, in `init` or anywhere else. The checker rejects a read of a name that is never assigned anywhere in the program (`x.name = ...` on any object, or `self.name = ...` in the class, its parents or its children); otherwise a missing attribute is a friendly run-time error. An attribute may not have the name of an action of its class.
- **Actions as calls.** `d.speak()` is an expression (where the action `give`s) and a line on its own (for actions that give nothing back). The same `give` rules as functions apply: give on every path, and no value from an action that never gives. `self.other()` works inside actions (checked against the class the action is written in, so an action written only in a child class cannot be called on `self` from the parent). `d.speak().x` is not supported (use a variable).
- **super.** `super.init(args)` (a line, no `self` passed) runs the parent's `init`; more generally `super.name(args)` runs the parent's action `name`, as a line or as a value. It only works inside actions of a class that has a parent. If the parent has no `init`, `super.init()` takes no inputs.
- **Scope.** An action sees only its own inputs (including `self`) and its own `let`s, like a function (no global variables). Functions are visible everywhere, as before.
- **Kinds.** `let d = Dog(...)` gives `d` the kind "object of class Dog". A variable that holds an object can later hold an object of the same class or a child class, not a number, text or list (and not a parent class: `d = Animal(...)` after `let d = Dog(...)` is an error). Function inputs, call results and list items have an unknown kind, so no false errors happen; the runner checks. `==` and `!=` on objects mean "the very same object" (Python identity); `+ - * /`, `< > <= >=`, `-d`, `for x in d`, `d[0]` and `len(d)` are friendly errors. Objects can be put in lists, passed to functions and stored in other objects; they are shared, not copied, like lists.
- **List actions are unchanged.** `a.remove(...)`, `a.pop(...)` and `sort(a)` work exactly as before. A method call resolves by what the target is: a known list gets the list rules, a known object gets its class, a known number or text is an error, and an unknown kind is decided while the program runs by small helpers in the runner (`call_action`, `get_attr`, and `remove_all` / `pop_at`, which pass the call on to an object that has an action with that name, so a user class may have its own `pop` or `remove`).
- **Not supported (yet).** Several parents, calling a method on the result of a call or an attribute call result (`d.speak().x`, `Dog("a", 1).speak()`), class-level values (only functions inside a class), `self.x()` for an action that only a child class has, properties or privacy, and a customised text for `show d` (like `__str__`).

## Growing the language

Later versions add the AI features. Each is added as new tokens, tree nodes, and generator rules. **The pipeline stays the same.**

## Design principles

- Clarity and beginner-friendly error messages are the edge over Python.
- Prefer simple, readable code over clever or fast code.
- Test each stage with small examples before connecting them.
