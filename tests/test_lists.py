"""Tests for lists, max/min/len/sort and reassignment (`x = value`)."""

import contextlib
import io
import os
import subprocess
import sys
import unittest

from ast_nodes import (Assign, BinaryOp, Call, CallStatement, Let,
                       ListLiteral, Name, Number, Show, Text)
from checker import check
from errors import ScriptyError
from generator import generate
from lexer import (COMMA, LBRACKET, NAME, NUMBER, OPERATOR, RBRACKET,
                   tokenize)
from parser import parse
from runner import run_python

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TODO_PROGRAM = (
    "let a = [0, 1, 3]\n\n"
    "show max(a) // output: 3\n\n"
    "a = [0, 4, 2, 6, 3]\n\n"
    "sort(a) // python has a function for this as long as i remember\n\n"
    "show a\n")


def parse_source(source):
    return parse(tokenize(source))


def run_source(source):
    """Run Scripty source in-process and return what it printed."""
    python, line_map = generate(check(parse_source(source)))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        run_python(python, line_map)
    return output.getvalue()


def error_in(stage, source):
    """The ScriptyError raised by `stage` (parse / check / run)."""
    with unittest.TestCase().assertRaises(ScriptyError) as caught:
        if stage == "parse":
            parse_source(source)
        elif stage == "check":
            check(parse_source(source))
        else:
            run_source(source)
    return caught.exception


class LexerTests(unittest.TestCase):
    def test_brackets_and_commas(self):
        kinds = [t.kind for t in tokenize("[1, 2]")][:5]
        self.assertEqual(kinds, [LBRACKET, NUMBER, COMMA, NUMBER, RBRACKET])

    def test_assignment_tokens(self):
        kinds = [t.kind for t in tokenize("a = 1")][:3]
        self.assertEqual(kinds, [NAME, OPERATOR, NUMBER])

    def test_comment_after_call(self):
        kinds = [t.kind for t in tokenize("max(a) // the biggest")]
        self.assertNotIn("TEXT", kinds)
        self.assertEqual(len(kinds), 5)  # max ( a ) NEWLINE


class ParserTests(unittest.TestCase):
    def test_list_literal(self):
        program = parse_source("let a = [1, 2 + 3]")
        value = program.statements[0].value
        self.assertEqual(value, ListLiteral(
            [Number(1, 1), BinaryOp("+", Number(2, 1), Number(3, 1), 1)], 1))

    def test_empty_list(self):
        self.assertEqual(parse_source("let a = []").statements[0].value,
                         ListLiteral([], 1))

    def test_list_of_text(self):
        value = parse_source('let a = ["x", "y"]').statements[0].value
        self.assertEqual(value.items, [Text("x", 1), Text("y", 1)])

    def test_assignment(self):
        self.assertEqual(parse_source("x = 5\n").statements,
                         [Assign("x", Number(5, 1), 1)])

    def test_assignment_with_expression_on_line_2(self):
        program = parse_source("let x = 1\nx = x + 1")
        self.assertEqual(program.statements[1].line, 2)
        self.assertIsInstance(program.statements[1].value, BinaryOp)

    def test_call_statement_and_value(self):
        program = parse_source("sort(a)\nshow max(a)")
        self.assertEqual(program.statements, [
            CallStatement(Call("sort", [Name("a", 1)], 1), 1),
            Show(Call("max", [Name("a", 2)], 2), 2)])

    def test_todo_program_parses(self):
        statements = parse_source(TODO_PROGRAM).statements
        self.assertEqual([type(s) for s in statements],
                         [Let, Show, Assign, CallStatement, Show])

    def test_trailing_comma_is_an_error(self):
        error = error_in("parse", "let a = [1, 2,]")
        self.assertEqual(error.line, 1)
        self.assertIn("comma right before", error.message)

    def test_missing_closing_bracket(self):
        error = error_in("parse", "let a = [1, 2")
        self.assertIn('closing "]"', error.message)

    def test_missing_comma_between_items(self):
        error = error_in("parse", "let a = [1 2]")
        self.assertIn("comma", error.message)

    def test_assignment_without_value(self):
        error = error_in("parse", "let x = 1\nx =")
        self.assertEqual(error.line, 2)
        self.assertIn("no new value", error.message)

    def test_stray_closing_bracket(self):
        error_in("parse", "show 1]")


class CheckerTests(unittest.TestCase):
    def check_ok(self, source):
        check(parse_source(source))

    def test_todo_program_is_fine(self):
        self.check_ok(TODO_PROGRAM)

    def test_reassign_unknown_name(self):
        error = error_in("check", "z = 4")
        self.assertEqual(
            str(error), 'Error on line 1: I don\'t know what "z" is. '
                        "Did you forget to write: let z = ...")

    def test_reassign_same_kinds(self):
        self.check_ok('let n = 1\nn = 2\nlet t = "a"\nt = "b"\n'
                      "let l = [1]\nl = []")

    def test_reassign_different_kind_is_an_error(self):
        error = error_in("check", 'let n = 1\nn = "a"')
        self.assertEqual(error.line, 2)
        self.assertIn("holds a number", error.message)
        self.assertIn("text", error.message)
        error = error_in("check", "let a = [1]\na = 5")
        self.assertIn("holds a list", error.message)

    def test_reassign_with_unknown_kind_is_fine(self):
        self.check_ok("function F(x):\n    x = 5\n    x = [1]\n    give x")
        self.check_ok("function F(x):\n    give x\nlet n = 1\nn = F(2)")

    def test_reassign_outer_variable_inside_blocks(self):
        self.check_ok("let n = 0\nfor c in \"ab\":\n    n = n + 1\n"
                      "if (n == 2):\n    n = 5")

    def test_block_variable_cannot_be_changed_outside(self):
        error = error_in("check", "if (1 == 1):\n    let k = 1\nk = 2")
        self.assertEqual(error.line, 3)
        self.assertIn('I don\'t know what "k" is', error.message)

    def test_function_cannot_change_outside_variable(self):
        error = error_in("check", "let n = 1\nfunction F():\n    n = 2")
        self.assertEqual(error.line, 3)
        self.assertIn('inside the function "F"', error.message)

    def test_cannot_assign_to_a_function(self):
        error = error_in("check", "function F():\n    show 1\nF = 3")
        self.assertIn("is a function", error.message)

    def test_value_is_checked_when_assigning(self):
        error = error_in("check", "let n = 1\nn = n + y")
        self.assertIn('"y"', error.message)

    def test_duplicate_let_message_mentions_assignment(self):
        error = error_in("check", "let x = 1\nlet x = 2")
        self.assertEqual(error.line, 2)
        self.assertIn('"x" is already declared on line 1', error.message)
        self.assertIn("x = ... (without let)", error.message)

    def test_builtin_names_cannot_be_used(self):
        for name in ("max", "min", "len", "sort"):
            for source in (f"let {name} = 1", f"let a = 1\n{name} = 2",
                           f"function {name}():\n    show 1",
                           f"function F({name}):\n    give 1",
                           f'for {name} in "ab":\n    show 1'):
                error = error_in("check", source)
                self.assertIn("built-in", error.message, source)

    def test_builtin_name_without_call(self):
        error = error_in("check", "let a = max")
        self.assertIn("built-in function", error.message)

    def test_max_min_len_kinds(self):
        self.check_ok("let a = [1]\nshow max(a)\nshow min(a)\nshow len(a)\n"
                      'show len("abc")\nlet n = len(a) + 1')

    def test_wrong_number_of_inputs(self):
        error = error_in("check", "let a = [1]\nshow max(a, a)")
        self.assertIn('needs 1 input', error.message)
        error = error_in("check", "show max()")
        self.assertIn("you gave 0", error.message)
        error = error_in("check", "sort()")
        self.assertIn("needs 1 input", error.message)

    def test_non_list_argument(self):
        error = error_in("check", "show max(5)")
        self.assertIn('"max" needs a list, but this is a number',
                      error.message)
        error = error_in("check", 'let t = "ab"\nshow min(t)')
        self.assertIn("but this is text", error.message)
        error = error_in("check", "show len(5)")
        self.assertIn("a list or text", error.message)
        error = error_in("check", "let n = 3\nsort(n)")
        self.assertIn("needs a list", error.message)

    def test_sort_cannot_be_a_value(self):
        error = error_in("check", "let a = [2, 1]\nlet b = sort(a)")
        self.assertEqual(error.line, 2)
        self.assertIn("changes the list itself", error.message)
        error_in("check", "let a = [2, 1]\nshow sort(a)")

    def test_sort_needs_a_variable(self):
        error = error_in("check", "sort([2, 1])")
        self.assertIn("name of a variable", error.message)

    def test_max_alone_on_a_line_is_an_error(self):
        error = error_in("check", "let a = [1]\nmax(a)")
        self.assertIn("show max(a)", error.message)

    def test_function_inputs_are_accepted(self):
        self.check_ok("function F(items):\n    sort(items)\n"
                      "    give max(items)")

    def test_list_in_list_is_an_error(self):
        error = error_in("check", "let a = [[1], 2]")
        self.assertIn("another list", error.message)

    def test_list_items_are_checked(self):
        error = error_in("check", "let a = [1, y]")
        self.assertIn('"y"', error.message)

    def test_list_concatenation_is_allowed(self):
        self.check_ok("let a = [1] + [2]\nshow a")

    def test_other_list_arithmetic_is_an_error(self):
        for source in ("let a = [1]\nshow a * 2", "let a = [1]\nshow a + 1",
                       'let a = [1]\nshow "x" + a', "let a = [1]\nshow -a",
                       "let a = [1]\nshow a - a", "let a = [1]\nshow 2 / a"):
            error_in("check", source)

    def test_list_comparisons(self):
        self.check_ok("let a = [1]\nif (a == [1]):\n    show 1\n"
                      "if (a != [2]):\n    show 2")
        error = error_in("check", "let a = [1]\nif (a > [1]):\n    show 1")
        self.assertIn("with a list", error.message)

    def test_for_over_list(self):
        self.check_ok("let a = [1, 2]\nfor n in a:\n    show n + 1")
        self.check_ok('for c in "ab":\n    show c + "x"')

    def test_for_over_number_mentions_lists(self):
        error = error_in("check", "for i in 5:\n    show i")
        self.assertEqual(error.message,
                         "You can only go through text or a list with for, "
                         "but 5 is a number.")

    def test_loop_variable_of_unknown_list_is_not_text(self):
        self.check_ok("function F(items):\n    for i in items:\n"
                      "        show i + 1\nF([1])")


class GeneratorTests(unittest.TestCase):
    def gen(self, source):
        return generate(check(parse_source(source)))

    def test_list_and_builtins(self):
        python, _ = self.gen("let a = [0, 1 + 2, \"x\"]\nshow max(a)\n"
                             "show min(a)\nshow len(a)")
        self.assertEqual(python, "a = [0, 1 + 2, 'x']\nprint(max(a))\n"
                                 "print(min(a))\nprint(len(a))\n")

    def test_sort_becomes_dot_sort(self):
        python, _ = self.gen("let a = [2, 1]\nsort(a)")
        self.assertEqual(python, "a = [2, 1]\na.sort()\n")

    def test_assignment_and_line_map(self):
        python, line_map = self.gen("let n = 1\n\nn = n + 1\nshow n")
        self.assertEqual(python, "n = 1\nn = n + 1\nprint(n)\n")
        self.assertEqual(line_map, {1: 1, 2: 3, 3: 4})

    def test_empty_list_and_concatenation(self):
        python, _ = self.gen("let a = [] + [1]")
        self.assertEqual(python, "a = [] + [1]\n")

    def test_python_keyword_name_in_assignment(self):
        python, _ = self.gen("let class = [1]\nclass = [2]\nsort(class)")
        self.assertEqual(
            python, "class_scy = [1]\nclass_scy = [2]\nclass_scy.sort()\n")

    def test_todo_program_line_map(self):
        _, line_map = self.gen(TODO_PROGRAM)
        self.assertEqual(line_map, {1: 1, 2: 3, 3: 5, 4: 7, 5: 9})


class RunnerTests(unittest.TestCase):
    def test_todo_program_output(self):
        self.assertEqual(run_source(TODO_PROGRAM), "3\n[0, 2, 3, 4, 6]\n")

    def test_text_and_numbers_print_as_before(self):
        self.assertEqual(run_source('show "hi"\nshow 2.5\nshow 4 / 2'),
                         "hi\n2.5\n2.0\n")

    def test_list_formats(self):
        self.assertEqual(run_source("show []\nshow [1, 2.5]"),
                         "[]\n[1, 2.5]\n")
        self.assertEqual(run_source('show ["b", "a"]'), '["b", "a"]\n')
        self.assertEqual(run_source('show [1, "a"]'), '[1, "a"]\n')

    def test_echo_a_list(self):
        self.assertEqual(run_source('echo([1, 2])'), "[1, 2]\n")

    def test_text_list_sorts_alphabetically(self):
        self.assertEqual(
            run_source('let w = ["pear", "apple", "fig"]\nsort(w)\n'
                       "show w\nshow max(w)\nshow min(w)"),
            '["apple", "fig", "pear"]\npear\napple\n')

    def test_len(self):
        self.assertEqual(run_source('show len([4, 5, 6])\nshow len("ab")'),
                         "3\n2\n")

    def test_concatenation_and_compare(self):
        self.assertEqual(run_source("show [1] + [2, 3]\n"
                                    "if ([1] == [1]):\n    show 7"),
                         "[1, 2, 3]\n7\n")

    def test_for_over_list(self):
        self.assertEqual(run_source("for n in [3, 1]:\n    show n * 2"),
                         "6\n2\n")

    def test_reassign_in_loop_and_function(self):
        source = ("function Total(items):\n    let sum = 0\n"
                  "    for i in items:\n        sum = sum + i\n"
                  "    give sum\nshow Total([1, 2, 3])")
        self.assertEqual(run_source(source), "6\n")

    def test_function_sorts_the_callers_list(self):
        source = ("function Order(items):\n    sort(items)\n"
                  "let a = [3, 1, 2]\nOrder(a)\nshow a")
        self.assertEqual(run_source(source), "[1, 2, 3]\n")

    def test_empty_list_max_is_friendly(self):
        error = error_in("run", "let a = []\n\nshow max(a)")
        self.assertEqual(str(error), "Error on line 3: max needs at least "
                                     "one item, but the list is empty.")

    def test_empty_list_min_is_friendly(self):
        error = error_in("run", "let a = []\nshow min(a)")
        self.assertIn("min needs at least one item", error.message)

    def test_sorting_mixed_list_is_friendly(self):
        error = error_in("run", 'let a = [1, "x"]\nsort(a)')
        self.assertEqual(error.line, 2)
        self.assertIn("compare (or sort", error.message)

    def test_max_of_mixed_list_is_friendly(self):
        error = error_in("run", 'let a = [1, "x"]\nshow max(a)')
        self.assertIn("text with a number", error.message)

    def test_max_of_number_input_is_friendly(self):
        error = error_in("run", "function F(x):\n    give max(x)\nshow F(5)")
        self.assertEqual(error.line, 2)
        self.assertIn("need a list", error.message)
        self.assertNotIn("with for", error.message)

    def test_sort_of_number_input_is_friendly(self):
        error = error_in("run", "function F(x):\n    sort(x)\nF(5)")
        self.assertIn("sort needs a list", error.message)

    def test_len_of_number_input_is_friendly(self):
        error = error_in("run", "function F(x):\n    give len(x)\nshow F(5)")
        self.assertIn("len needs a list or text", error.message)

    def test_list_plus_number_at_run_time_is_friendly(self):
        error = error_in("run", "function F(x):\n    give x + 1\nshow F([1])")
        self.assertIn("mix", error.message)

    def test_for_over_number_input_still_says_for(self):
        error = error_in("run", "function F(x):\n    for i in x:\n"
                                "        show i\nF(5)")
        self.assertIn("text or a list with for", error.message)


class EndToEndTests(unittest.TestCase):
    def scripty(self, *args):
        return subprocess.run(
            [sys.executable, "scripty.py", *args], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8")

    def run_text(self, source, tmp_name="lists_test.scy"):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, tmp_name)
            with open(path, "w", encoding="utf-8") as file:
                file.write(source)
            return self.scripty("run", path)

    def test_todo_program_through_the_cli(self):
        result = self.run_text(TODO_PROGRAM)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ["3", "[0, 2, 3, 4, 6]"])
        self.assertEqual(result.stderr, "")

    def test_example_file(self):
        result = self.scripty("run", os.path.join("examples", "lists.scy"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "3", "0", "3", "[0, 2, 3, 4, 6]", '["Ana", "Bo", "Zed"]',
            '["Ana", "Bo", "Zed", "Eve"]', "Ana", "Bo", "Zed", "9", "15"])

    def test_build_shows_python(self):
        with __import__("tempfile").TemporaryDirectory() as folder:
            path = os.path.join(folder, "b.scy")
            with open(path, "w", encoding="utf-8") as file:
                file.write("let a = [2, 1]\nsort(a)\nshow a\n")
            result = self.scripty("build", path)
        self.assertEqual(result.stdout, "a = [2, 1]\na.sort()\nprint(a)\n")

    def assertFriendly(self, source, expected):
        result = self.run_text(source)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(expected, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_friendly_errors(self):
        self.assertFriendly("let a = [1, 2,]",
                            "Error on line 1: There is a comma right before")
        self.assertFriendly("let max = 3",
                            'Error on line 1: "max" is a built-in')
        self.assertFriendly("let a = [1]\nlet b = sort(a)",
                            "Error on line 2: sort changes the list itself")
        self.assertFriendly("let a = []\nshow max(a)",
                            "Error on line 2: max needs at least one item")
        self.assertFriendly('let a = [2, "x"]\nsort(a)',
                            "Error on line 2: You tried to compare")
        self.assertFriendly("let a = [1]\na = 5",
                            'Error on line 2: "a" holds a list')


if __name__ == "__main__":
    unittest.main()
