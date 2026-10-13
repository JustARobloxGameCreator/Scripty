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

## Later

- [ ] AI features (later)
