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

## Progress

- [x] `function Name(item1, item2):` with an indented body (4 spaces)
- [x] `if (condition):`, `elif (condition):`, `else:`
- [x] `give result` (same as return)
- [x] `// comment` to the end of the line (`#` still works too)
- [x] Conditions: `==  !=  >=  <=  >  <`
- [x] Calling functions as values and as lines (`let r = Name(1, 2)`, `show Name(1, 2)`)
- [x] Friendly errors for all of the above
- [ ] Loops (issue #13, not part of this to-do yet)
- [ ] AI features (later)
