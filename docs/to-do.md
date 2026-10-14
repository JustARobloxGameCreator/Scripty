# To-do

## Done: functions and conditions (issues #12 and #14)

You have to make the language do like below:

```
function Name(item1, item2):
    if (condition): // This is a comment
        give result // Same as return
    elif (condition):
        give result
    else:
        give result
```

------

Conditions:

```
==
!=
>=
<=
>
<
```

### Progress

- [x] `function Name(item1, item2):` with an indented body (4 spaces)
- [x] `if (condition):`, `elif (condition):`, `else:`
- [x] `give result` (same as return)
- [x] `// comment` to the end of the line (`#` still works too)
- [x] Conditions: `==  !=  >=  <=  >  <`
- [x] Calling functions as values and as lines (`let r = Name(1, 2)`, `show Name(1, 2)`)
- [x] Friendly errors for all of the above

## Done: loops (issue #13)

You have to make the language do like below:

```
for i in "hello world!":
    show i

// output:
h
e
l
l
o
(blank line: the space)
w
o
r
l
d
!
```

### Progress

- [x] `for` and `in` keywords: `for NAME in VALUE:` with an indented body (4 spaces)
- [x] One step per character of a text (text, text variables, function inputs and results)
- [x] The loop variable is text, lives only inside the loop and cannot reuse a visible name
- [x] Loops at the top level, inside functions and inside if branches; loops, ifs and `give` inside loops
- [x] Friendly errors: missing name, `in`, value, colon, body, wrong indentation, and a number instead of text
- [x] Generated Python `for` with a correct line map
- [x] `examples/loops.scy` and tests for every stage

## Done: lists, max and sort (reassignment)

You have to implement the functions below:

```
let a = [0, 1, 3]

show max(a) // output: 3

a = [0, 4, 2, 6, 3]

sort(a) // python has a function for this as long as i remember

show a
```

Output: `3` then `[0, 2, 3, 4, 6]`.

### Progress

- [x] List literals `[1, 2, 3]`, `[]`, text lists, any expressions inside (no trailing comma, no list inside a list)
- [x] `max(list)`; also `min(list)` and `len(list or text)`; empty list gives a friendly error
- [x] `sort(list)` sorts the list itself, as a line on its own (`let b = sort(a)` is a friendly error)
- [x] `max`, `min`, `len`, `sort` are built-in names (friendly error if used as variable or function names)
- [x] Reassignment `name = value` without `let` (same kind of value, name must exist, scope rules documented)
- [x] `show a` prints the whole list: `[0, 2, 3, 4, 6]`
- [x] `list + list`, `==` / `!=` on lists, `for item in list:`
- [x] Friendly errors for all of the above, with the Scripty line
- [x] `examples/lists.scy` and tests for every stage and the to-do program

## Done: remove and pop

The request, as written by the owner:

```
listName.remove("Dog")  // if "Dog" is in the list, remove every item that is "Dog".
                        // If it isn't, give a warning and continue running the code.
listName.pop(3)         // remove the item listName[3] from the list
```

### Progress

- [x] `name.remove(value)`: removes EVERY item equal to the value (text, number, variable or any expression)
- [x] Nothing matches: `Warning on line N: "Dog" is not in the list, so nothing was removed.` goes to stderr, the program keeps running and exits with code 0
- [x] `name.pop(index)`: removes the item at that position (the first item is position 0)
- [x] `pop` errors: too big (`The list has 3 items (positions 0 to 2), ...`), empty list, negative, decimal, not a number
- [x] New `.` token; a `.` anywhere else (`.5`, `5.pop(1)`, `a.remove(1).pop(2)`) is a friendly error; an unknown action lists the choices (remove, pop)
- [x] Both are lines on their own (like `sort(a)`); using them as a value (`let x = a.pop(1)`) is a friendly error
- [x] Checker: the name must be a visible list (a known number or text is an error), exactly one input, scope rules unchanged
- [x] Generated Python: `remove_all(a, 'Dog', LINE)` and `pop_at(a, 3)` (helpers given to the program by the runner)
- [x] `examples/list_methods.scy` and tests for every stage (`tests/test_list_methods.py`)

## Done: indexing

The request, as written by the owner: "also add a function like listName[1] which is the same as in python."

### Progress

- [x] `name[index]` gives one item of a list or one character of a text; positions start at 0, like Python
- [x] Negative positions count from the end (`a[-1]` is the last item)
- [x] The position can be any expression (`a[i + 1]`, `a[len(a) - 1]`); a whole decimal such as `4 / 2` is accepted
- [x] Works anywhere a value does: `show`, `let`, calculations, conditions, function inputs, list literals, `for`, `remove` and `pop` inputs
- [x] Works on text too (`"hello"[1]`, `word[0]`) and on an item of a text list (`words[0][1]`)
- [x] `a[1] = 9` replaces one item of a list (text can't be changed one character at a time: friendly error)
- [x] Friendly errors: position too big or too negative (with the length and the valid positions), empty list or text, decimal or non-number position, indexing a number, undeclared name, `a[]`, missing `]`
- [x] Checker: `a[i]` has unknown kind for lists (no false errors for mixed lists) and text kind for text
- [x] Generated Python: `get_at(a, 1)` and `set_at(a, 1, 9)` (helpers given to the program by the runner)
- [x] `pop` is unchanged (it still rejects negative positions)
- [x] `examples/indexing.scy` and tests for every stage (`tests/test_indexing.py`)

## Done: classes

The request, as written by the owner: "implement classes just like in python."

The design, kept Python-shaped but in Scripty's words (the first example is
`examples/classes.scy` and is also in the tests):

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
show d.speak()
d.birthday()
show d.age
d.name = "Max"
let p = Puppy("Bit", 1)
show p.speak()
```

Output: `Rex says woof`, `4`, `Bit says yip`.

### Progress

- [x] `class Name:` with an indented body of `function` lines only (the actions); top level only
- [x] `class Child(Parent):` single inheritance; actions inherited and overridable; the parent must be a class written above
- [x] `init` is the constructor (`Dog("Rex", 3)` makes an object); no `init` means no inputs; the number of inputs is checked (inherited `init` counts)
- [x] The first input of every action must be `self` (friendly error otherwise); `self` is not passed when calling (`d.speak()`)
- [x] Attributes: read `d.name` / `self.name`, write `d.name = value` / `self.name = value`; reading one that nothing ever sets is a friendly error
- [x] Action calls as values (`show d.speak()`) and as lines (`d.birthday()`), with the same `give` rules as functions; `self.other()` works
- [x] `super.init(args)` runs the parent's `init` (and `super.name(args)` the parent's other actions)
- [x] Objects are a kind in the checker (same class or a child class on reassignment); `==` / `!=` mean the same object; calculations, `< >`, `for`, `[ ]` and `len` on objects are friendly errors; objects work in lists, functions and other objects
- [x] `show d` prints `<Dog object>`
- [x] List actions `a.remove(...)`, `a.pop(...)` and `sort(a)` work exactly as before (a method call resolves by what the target is; unknown kinds are decided while running)
- [x] Python names that clash (`def`, `None`, an attribute called `class`, ...) get the `_scy` suffix; `scripty build` shows readable Python classes
- [x] Friendly errors with the Scripty line at every stage, also for errors inside actions
- [x] `class` is a reserved word (`self` and `super` too); noted in the changelog
- [x] `examples/classes.scy` and tests for every stage (`tests/test_classes.py`)

Left out on purpose (ideas for later): several parents, a customised text for `show d`, calling an action on a call result (`Dog("a", 1).speak()`), class-level values.

## Later

- [ ] AI features (later)
