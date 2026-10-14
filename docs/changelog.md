# Changelog

All notable changes to Scripty are recorded here, newest first.

## [Unreleased]

### Added (classes)
- Classes, "just like in Python" but in Scripty's words: `class Dog:` with indented `function` lines inside (the actions), and `class Puppy(Dog):` for one parent (single inheritance; actions are inherited and can be replaced). The to-do example runs as written (output `Rex says woof`, `4`, `Bit says yip`). Everything is described in `docs/architecture.md` ("v0.5 language scope").
- Objects: `Dog("Rex", 3)` makes an object and runs its `init` action (Scripty's name for `__init__`). No `init` means no inputs. The first input of every action must be `self` (the object); it is not passed when calling. Attributes: `self.name = name` / `d.name = "Max"` (a line of its own) and reading `d.name` / `self.age` anywhere a value goes. Actions: `d.speak()` as a value and `d.birthday()` as a line. `super.init(name, 0)` runs the parent's `init` (and `super.speak()` the parent's other actions). `show d` prints `<Dog object>`. `==` / `!=` on objects mean "the very same object". Objects work in lists, functions and other objects.
- New keyword `class`; new tree nodes `ClassDef`, `Attribute` and `AssignAttribute`. `MethodCall` now accepts any name and any dotted target (`self.pet.speak()`), and the checker fills in a `target_kind` on `MethodCall` and `Attribute` for the generator.
- Checker: class names share one list with functions and variables; the parent must be a class on an earlier line; the first input of every action must be `self`; `Dog(...)`, `d.speak(...)` and `super.x(...)` input counts; unknown actions (`A Dog object has no action called "fly". Its actions are: speak, birthday.`) and attributes that nothing sets (`This Dog has nothing called "colour", and nothing in the program ever sets it. Did you forget to write: self.colour = ...`); `init` cannot give and cannot be called on an object; `self` and `super` outside an action, in the wrong place or used as names; the same give rules as functions for actions; object kinds in the type rules (no calculations, `< >`, `for`, `[ ]`, `len` on objects; reassignment needs the same class or a child class).
- Generator: Python classes with `init` -> `__init__`, `super.init(...)` -> `super().__init__(...)`, names that clash with Python (`def`, `None`, `print`, even attributes such as `d.class`) get `_scy`, one line map entry per code line, blank lines between actions. When the kind of a value is unknown (a function input) it writes `call_action(...)` / `get_attr(...)`, helpers provided by the runner.
- Runner: friendly messages for a missing attribute (`This Dog has nothing called "colour". Did you forget to give it one with: self.colour = ...`), an action a number, text or list does not have (`A number has no action called speak.`), wrong input counts found while running, objects in calculations, `for` and `len`, division by zero inside an action (on the line in the action). `show` of an object is `<Dog object>`.
- `examples/classes.scy` (also in the README commands) and 154 new tests in `tests/test_classes.py` (710 in total).

### Changed (classes)
- `class` is now a reserved word. A variable, input, function or loop variable called `class` is an error (`"class" is a Scripty keyword ...`). The old generator tests that used `class` as a variable name (to show the `_scy` suffix) now use `def`.
- `self` and `super` are reserved names everywhere: they can no longer be variables, inputs, loop variables, functions or classes.
- A dot after a name is now parsed for any action name. Because of that the list error `I don't know what "add" does to a list. The list actions are: remove, pop.` now comes from the checker instead of the parser (same words, plus a `Try:` hint), and `a.pop.pop(1)` is now `pop needs parentheses with a value inside` from the checker (a bare `a.pop` line is still a parser error). Two tests changed for that (`test_unknown_method_name_now_parses`, `test_chained_method_is_an_error`).
- A function input of unknown kind used with `x.pop(...)` / `x.remove(...)` is no longer checked for the number of inputs while writing (an object may have its own `pop`); it is checked when the program runs, with the same friendly words. A list action is still always a line on its own for a known list.
- The "." error now also mentions objects (`A "." only works right after the name of a list, like: ... or of an object, like: d.speak() or d.name ...`), and `Dog("a", 1).speak()` / `d.speak().x` get a specific message about keeping the answer in a variable.
- All other existing tests pass unchanged (556 before, 710 now).

### Added (indexing)
- `name[index]` gives one item of a list or one character of a text, like Python: `show a[1]`, `show a[-1]`, `show "hello"[1]`. Positions start at 0 and a negative position counts from the end (`a[-1]` is the last item). The position can be any expression (`a[i + 1]`, `a[len(a) - 1]`, `a[4 / 2]`). It is an expression, so it works anywhere a value does: `show`, `let`, calculations, conditions, function inputs, inside list literals, as the value of a `for`, and as the input of `remove` or `pop`. `words[0][1]` (a character of the first text item) works too.
- `a[1] = 9` replaces one item of an existing list (a line on its own). The new value may be any number or text (items can be mixed). Text can't be changed this way (friendly error); only a plain name can be on the left (`a[0][1] = 9` is an error).
- Friendly errors with the Scripty line: a position that is too big or too negative (`The list has 3 items (positions 0 to 2, or -1 to -3 from the end), so there is no item at position 3.`), an empty list or text, a decimal or text position (checked in the program when written, while running when worked out), indexing a number (`You can only use [ ] on a list or a text, but "n" is a number.`), assigning into text, an undeclared name, `a[]`, a missing `]`, and a line that is only `a[1]`.
- New tree nodes `Index` and `AssignIndex`. The checker gives `a[i]` the kind text for a known text and unknown for a list (items may be mixed), so `a[1] + 1` has no false errors.
- Generator: `a[1]` becomes `get_at(a, 1)` and `a[1] = 9` becomes `set_at(a, 1, 9)`; the runner provides both helpers (next to `remove_all` and `pop_at`), so out-of-range errors report the real numbers on the Scripty line. A variable named `get_at` or `set_at` gets the `_scy` suffix in the generated code.
- `examples/indexing.scy` (also in the README commands) and 84 new tests in `tests/test_indexing.py` (556 in total).

### Changed (indexing)
- A line that starts with `name[` (such as `a[1]`) used to be `I don't understand a line that starts with "a"`. It is now either an assignment (`a[1] = 9`) or a friendlier error. The "I don't understand a line" error text also mentions list items now.
- `a [1]` (with a space) means the same as `a[1]`.
- `pop` is unchanged: `a.pop(-1)` is still an error, while `a[-1]` counts from the end.
- All 472 existing tests pass unchanged.

### Added (list actions: remove and pop)
- `name.remove(value)` removes EVERY item equal to `value` from the list (the value can be text, a number, a variable or any expression). If nothing matches, Scripty prints `Warning on line N: "Dog" is not in the list, so nothing was removed.` to **stderr** (so the program's normal output stays clean) and keeps running; the exit code stays 0. Text and numbers never match each other (`"1"` does not remove `1`), with no error.
- `name.pop(index)` removes the item at that position. Positions start at 0, like `listName[3]` in the to-do. A position that is too big (`Error on line 3: The list has 3 items (positions 0 to 2), so there is no item at position 3.`), an empty list, a negative position, a decimal such as `1.5` and a non-number are friendly errors. A whole number that is the result of a division (`4 / 2` is `2.0`) is accepted.
- Both are lines on their own, like `sort(a)`. Using one as a value (`let x = a.pop(1)`) is a friendly error saying it changes the list and gives nothing back. Lists are shared like before: `let b = a` followed by `a.remove(1)` also changes `b`.
- New `.` token and `MethodCall` / `MethodStatement` tree nodes. Decimal numbers such as `1.5` still lex as one number. A `.` anywhere else (`.5`, `5.`, `5.pop(1)`, `a.remove(1).pop(2)`) is a friendly error, and an unknown action (`a.add(1)`) lists the available ones (remove, pop).
- Checker: the name must be a visible list or function input (an unknown name gives the usual `I don't know what "z" is` error, a known number or text gives `remove only works on lists, but "n" is a number.`), exactly one input is required, and scope rules are unchanged (a function can only touch its own inputs and lets). Inputs of unknown kind are checked while the program runs, with friendly messages.
- Generator: `a.remove("Dog")` becomes `remove_all(a, 'Dog', 3)` (the last input is the Scripty line, used for the warning) and `a.pop(3)` becomes `pop_at(a, 3)`. `sort(a)` is unchanged (`a.sort()`).
- Runner: `remove_all` and `pop_at` are small helpers given to the program, like the custom `print`. `scripty build` shows the calls but not the helpers.
- `examples/list_methods.scy` (also in the README commands) and 60 new tests in `tests/test_list_methods.py` (472 in total).

### Changed (list actions: remove and pop)
- `remove` and `pop` are NOT reserved: they are still fine as variable names (the action name comes after the dot).
- In the generated Python, a variable, input or function named `remove_all` or `pop_at` now gets the `_scy` suffix (like `print`), so it cannot clash with the helpers.
- The "I don't understand a line that starts with" error now also mentions list actions like `a.pop(1)`.
- A `.` used to be an `I don't know what "."` lexer error; it is now a token, and a "." in the wrong place gets a parser error instead (still a friendly error, but from a different stage and with different words).
- All 412 existing tests pass unchanged.

### Added (lists, built-in functions and reassignment)
- List literals: `[1, 2, 3]`, `["a", "b"]`, `[]`, with any expressions inside. Lists hold numbers or text (mixed is allowed). A trailing comma, a missing `]` and a list inside a list are friendly errors. New `[` and `]` tokens and a `ListLiteral` tree node.
- Built-in functions: `max(list)` (alphabetical for text), `min(list)`, `len(list or text)` and `sort(list)`. `sort(a)` sorts the list itself and is used as a line on its own (`let b = sort(a)` is a friendly error). An empty list in `max`/`min` is a friendly run-time error (`max needs at least one item, but the list is empty.`); sorting a list that mixes numbers and text is a friendly run-time error too. Wrong number of inputs or a known non-list is a checker error.
- Reassignment: `name = value` (no `let`) gives an existing variable a new value, with an `Assign` tree node. The name must be visible there, and the new value must be the same kind (number, text, list) when both are known. Function inputs may be reassigned.
- `show a` prints a list as `[0, 2, 3, 4, 6]`; text items are shown in double quotes (`["Ana", "Bo"]`). Numbers and text print exactly as before.
- `list + list` joins two lists; `==` and `!=` work on lists. Other calculations and `> < >= <=` with lists are friendly errors.
- `for item in list:` goes through the items of a list.
- `examples/lists.scy` and 72 new tests in `tests/test_lists.py` covering every stage and the to-do program (412 in total).

### Changed (lists, built-in functions and reassignment)
- `max`, `min`, `len` and `sort` are built-in names: they can no longer be used as variable, input, loop variable or function names (programs using `min` or `len` as names must rename them).
- The "already declared" error now also says how to change the value (`write: x = ... (without let)`).
- A line such as `x = 5` used to be a syntax error; it is now reassignment (an error from the checker if `x` does not exist).
- The `for` error became `You can only go through text or a list with for, but 5 is a number.` (same at run time). The loop variable over a function input is now of unknown kind instead of text, so it accepts more programs, never fewer.
- Existing tests changed only for these messages (the `for` messages, and the parser test that used `x = 5` as an example of a bad line, now `x + 5`).

### Added (public release, issue #16)
- `README.md`: what Scripty is, what you need (Python 3.10+), how to download it, and how to run `.scy` files (`run`, `build`, the Windows launcher, running your own file, the examples, errors, tests). It does not teach the language itself yet.

### Added (loops, issue #13)
- `for NAME in VALUE:` with an indented 4-space body: runs the body once per character of a text (`for i in "hello world!":` then `show i` prints 12 lines, the space as a blank-looking line). New `for` and `in` keywords and a `For` tree node.
- The value can be a text, a text variable, a function input or a call result. Loops work at the top level, inside functions and inside `if` branches, and `if`, `give` and other loops can be nested inside them.
- Checker: the loop variable is text, local to the loop, and cannot reuse a visible name (same no-shadowing rule as `if` branches). `for` over a known number is an error (`You can only go through text with for, but 5 is a number.`). A `give` inside a loop counts as a give, but a loop never counts as giving on every path (it may run zero times), so the function needs a `give` after the loop.
- Parser: friendly errors for a missing name, `in`, value, colon, body, wrong indentation, a keyword as the loop name, and `in` outside a `for`.
- Generator: Python `for` with a correct line map; names like `class` or `print` keep the `_scy` suffix.
- Runner: a `for` over a number at run time (function input) gives the same friendly message instead of a TypeError text.
- `examples/loops.scy`, `docs/to-do.md` (now with the done functions/conditions section and the loops section), and 94 new tests (340 in total; the 246 existing tests are unchanged).

### Changed (loops)
- `for` and `in` are now keywords, so they can no longer be used as variable, function or input names.
- The "indented line" and "function inside" parser errors now also mention `for`.

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
