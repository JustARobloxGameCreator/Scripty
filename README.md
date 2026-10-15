# Scripty

Scripty is a small, friendly programming language. It is built to be **clear and
straightforward**, with error messages written for beginners, so that anyone can
learn it, and so that, later on, anyone can use it to build an AI.

Scripty is written in Python. When you run a Scripty program, it is translated to
Python and executed for you. You never have to see the Python.

> Scripty is young (version 0.1 and growing). Features and wording may change
> while we listen to feedback.

## What you need

- **Python 3.10 or newer.** Check with `python --version` (or `python3 --version`
  on macOS and Linux). Get it from <https://www.python.org/downloads/> if needed.
- **Git**, to download Scripty (or use the "Download ZIP" button on GitHub).

Scripty has no other dependencies. There is nothing to install with `pip`.

## Get Scripty

```
git clone https://github.com/JustARobloxGameCreator/Scripty.git
cd Scripty
```

## Run a Scripty program

Scripty files end in `.scy`. The repository comes with one, `hello.scy`. From the
`Scripty` folder, run it with:

```
python scripty.py run hello.scy
```

You should see:

```
8
```

On macOS and Linux, use `python3` if `python` is not found:

```
python3 scripty.py run hello.scy
```

On Windows you can also use the short launcher included in the folder:

```
.\scripty run hello.scy
```

(In Command Prompt you can leave out the `.\`.)

### Run your own file

1. Create a text file ending in `.scy`, for example `mine.scy`.
2. Write your Scripty program in it and save it.
3. Run it:

```
python scripty.py run mine.scy
```

The path can point anywhere on your computer, for example
`python scripty.py run C:\Users\you\Documents\mine.scy`. Put the path in quotes
if it contains spaces.

### More programs to try

The `examples/` folder has ready-made programs. Run any of them the same way:

```
python scripty.py run examples/text.scy
python scripty.py run examples/conditions.scy
python scripty.py run examples/functions.scy
python scripty.py run examples/loops.scy
python scripty.py run examples/lists.scy
python scripty.py run examples/list_methods.scy
python scripty.py run examples/indexing.scy
python scripty.py run examples/classes.scy
```

## See the Python that Scripty makes

`build` prints the generated Python instead of running the program. It is handy
for debugging and for seeing what your program turns into:

```
python scripty.py build hello.scy
```

## When something goes wrong

Scripty stops at the first problem and tells you what happened in plain words,
with the line number of **your** Scripty file, never a Python traceback:

```
Error on line 2: I don't know what "z" is. Did you forget to write: let z = ...
```

Problems with the file itself are explained too:

```
Error: I can't find the file "nope.scy".
Error: Scripty files end in .scy, but "notes.txt" does not.
```

If a command is wrong or missing, Scripty prints a short reminder of how to call it.

## Run the tests

If you want to check that everything works on your computer:

```
python -m unittest discover -s tests -t .
```

You should see `OK` at the end.

## Feedback

Found a bug, a confusing error message, or have an idea? Please
[open an issue](https://github.com/JustARobloxGameCreator/Scripty/issues). Feedback
from real users is what shapes the next versions.

## License

Scripty is released under the [MIT License](LICENSE).
