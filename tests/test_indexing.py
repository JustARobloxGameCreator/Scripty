"""Tests for indexing: a[1], a[-1], "hello"[1] and the line a[1] = 9."""

import contextlib
import io
import os
import subprocess
import sys
import unittest

from ast_nodes import AssignIndex, Index, Let, Name, Negate, Number, Show, Text
from checker import check
from errors import ScriptyError
from generator import generate
from lexer import LBRACKET, NAME, NUMBER, RBRACKET, tokenize
from parser import parse
from runner import get_at, run_python, set_at

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = "let a = [10, 20, 30]\n"


def parse_source(source):
    return parse(tokenize(source))


def run_source(source):
    """Run in-process. Returns the printed text."""
    python, line_map = generate(check(parse_source(source)))
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        run_python(python, line_map)
    return out.getvalue()


def lines_of(source):
    return run_source(source).splitlines()


def error_in(stage, source):
    with unittest.TestCase().assertRaises(ScriptyError) as caught:
        if stage == "parse":
            parse_source(source)
        elif stage == "check":
            check(parse_source(source))
        else:
            run_source(source)
    return caught.exception


class LexerTests(unittest.TestCase):
    def test_brackets_after_a_name(self):
        kinds = [t.kind for t in tokenize("a[1]")]
        self.assertEqual(kinds[:4], [NAME, LBRACKET, NUMBER, RBRACKET])


class ParserTests(unittest.TestCase):
    def test_index_in_show(self):
        statement = parse_source("show a[1]").statements[0]
        self.assertEqual(statement, Show(Index(Name("a", 1), Number(1, 1), 1), 1))

    def test_negative_index(self):
        node = parse_source("show a[-1]").statements[0].value
        self.assertEqual(node.index, Negate(Number(1, 1), 1))

    def test_index_with_a_calculation(self):
        node = parse_source("show a[i + 1]").statements[0].value
        self.assertEqual(node.index.op, "+")

    def test_text_literal_index(self):
        node = parse_source('show "hello"[1]').statements[0].value
        self.assertEqual(node, Index(Text("hello", 1), Number(1, 1), 1))

    def test_function_result_index(self):
        node = parse_source("show F(1)[0]").statements[0].value
        self.assertEqual(node.target.name, "F")

    def test_chained_index(self):
        node = parse_source("show a[0][1]").statements[0].value
        self.assertIsInstance(node.target, Index)

    def test_space_before_bracket_is_the_same(self):
        self.assertEqual(parse_source("show a [1]"), parse_source("show a[1]"))

    def test_minus_applies_to_the_item(self):
        node = parse_source("show -a[0]").statements[0].value
        self.assertIsInstance(node, Negate)
        self.assertIsInstance(node.operand, Index)

    def test_index_binds_tighter_than_arithmetic(self):
        node = parse_source("show a[0] + b[1] * 2").statements[0].value
        self.assertIsInstance(node.left, Index)
        self.assertIsInstance(node.right.left, Index)

    def test_list_literal_still_a_list(self):
        statement = parse_source("let x = [1, 2]").statements[0]
        self.assertIsInstance(statement, Let)
        self.assertEqual(len(statement.value.items), 2)

    def test_index_inside_a_list_literal(self):
        node = parse_source("let x = [a[0], 2]").statements[0].value
        self.assertIsInstance(node.items[0], Index)

    def test_assignment_statement(self):
        statement = parse_source("a[1] = 9").statements[0]
        self.assertEqual(statement, AssignIndex(
            Name("a", 1), Number(1, 1), Number(9, 1), 1))

    def test_empty_brackets(self):
        error = error_in("parse", "show a[]")
        self.assertEqual(error.line, 1)
        self.assertIn("Put a position between the [ ]", str(error))

    def test_missing_closing_bracket(self):
        error = error_in("parse", "show a[1")
        self.assertIn('no matching "]"', str(error))

    def test_missing_closing_bracket_in_assignment(self):
        self.assertIn('no matching "]"', str(error_in("parse", "a[1 = 2")))

    def test_line_with_only_an_item(self):
        self.assertIn("A line can't be only a[...]", str(error_in("parse", "a[1]")))

    def test_assignment_without_value(self):
        self.assertIn("has no new value", str(error_in("parse", "a[1] =")))

    def test_assignment_to_a_chained_item(self):
        error = error_in("parse", "a[0][1] = 5")
        self.assertIn("Only one item of a list can be changed", str(error))

    def test_comparison_after_item_is_an_error(self):
        self.assertIn("can't be only", str(error_in("parse", "a[1] == 2")))


class CheckerTests(unittest.TestCase):
    def test_list_item_is_fine_in_calculations(self):
        check(parse_source(LIST + "show a[1] + 1\nshow a[0] + a[1]\n"
                           "show a[1] * 2\n"))

    def test_item_of_mixed_list_is_unknown(self):
        check(parse_source('let a = [1, "x"]\nshow a[0] + 1\nshow a[1] + "y"\n'))

    def test_text_item_is_text(self):
        error = error_in("check", 'let w = "hi"\nshow w[0] + 1')
        self.assertIn("mix text and a number", str(error))

    def test_text_literal_is_fine(self):
        check(parse_source('show "hello"[1]'))

    def test_item_in_condition_and_loop(self):
        check(parse_source(LIST + "if (a[0] > 5):\n    show a[0]\n"
                           "for c in a[0]:\n    show c\n"))

    def test_item_as_argument_and_in_list(self):
        check(parse_source(LIST + "show max([a[0], a[1]])\nshow len(a[0])\n"
                           "a.pop(a[0])\na.remove(a[1])\n"))

    def test_computed_index(self):
        check(parse_source(LIST + "let i = 1\nshow a[i + 1]\n"
                           "show a[len(a) - 1]\nshow a[4 / 2]\n"))

    def test_index_a_number(self):
        error = error_in("check", "let n = 5\nshow n[0]")
        self.assertEqual(error.line, 2)
        self.assertEqual(str(error), 'Error on line 2: You can only use [ ] on '
                         'a list or a text, but "n" is a number.')

    def test_index_a_number_literal(self):
        self.assertIn("but 5 is a number", str(error_in("check", "show 5[0]")))

    def test_decimal_literal_index(self):
        error = error_in("check", LIST + "show a[1.5]")
        self.assertIn("1.5 has a decimal part", str(error))

    def test_negative_decimal_literal_index(self):
        error = error_in("check", LIST + "show a[-1.5]")
        self.assertIn("-1.5 has a decimal part", str(error))

    def test_text_index(self):
        error = error_in("check", LIST + 'show a["x"]')
        self.assertIn("must be a whole number, but this is text", str(error))

    def test_list_index(self):
        error = error_in("check", LIST + "show a[[1]]")
        self.assertIn("but this is a list", str(error))

    def test_undeclared_name(self):
        error = error_in("check", "show z[0]")
        self.assertEqual(str(error), 'Error on line 1: I don\'t know what "z" '
                         "is. Did you forget to write: let z = ...")

    def test_undeclared_in_assignment(self):
        error = error_in("check", "z[0] = 1")
        self.assertIn('I don\'t know what "z" is', str(error))

    def test_function_cannot_see_outside_list(self):
        source = LIST + "function F():\n    give a[0]\n"
        self.assertIn("inside the function", str(error_in("check", source)))

    def test_function_input_is_unknown(self):
        check(parse_source("function F(x):\n    give x[0] + 1\n"))

    def test_assignment_is_fine(self):
        check(parse_source(LIST + 'a[0] = 1\na[1] = "x"\na[2] = a[0] + 1\n'))

    def test_assignment_to_text(self):
        error = error_in("check", 'let w = "hi"\nw[0] = "j"')
        self.assertEqual(error.line, 2)
        self.assertIn("Text can't be changed one character at a time",
                      str(error))

    def test_assignment_to_number(self):
        error = error_in("check", "let n = 5\nn[0] = 1")
        self.assertIn('but "n" is a number', str(error))

    def test_assignment_decimal_position(self):
        self.assertIn("decimal part", str(error_in("check", LIST + "a[0.5] = 1")))

    def test_assignment_list_value(self):
        error = error_in("check", LIST + "a[0] = [1]")
        self.assertIn("can't hold another list", str(error))

    def test_assignment_value_is_checked(self):
        self.assertIn("I don't know what", str(error_in("check", LIST + "a[0] = z")))

    def test_assignment_in_a_block_sees_outer_list(self):
        check(parse_source(LIST + "if (a[0] == 10):\n    a[0] = 1\n"))

    def test_helper_names_are_not_clashing(self):
        source = "let get_at = 1\nlet set_at = 2\nshow get_at + set_at\n"
        self.assertEqual(lines_of(source), ["3"])


class GeneratorTests(unittest.TestCase):
    def python(self, source):
        return generate(check(parse_source(source)))[0]

    def test_read(self):
        self.assertEqual(self.python(LIST + "show a[1]"),
                         "a = [10, 20, 30]\nprint(get_at(a, 1))\n")

    def test_negative_and_computed(self):
        text = self.python(LIST + "show a[-1]\nshow a[len(a) - 1]\n")
        self.assertIn("get_at(a, -1)", text)
        self.assertIn("get_at(a, len(a) - 1)", text)

    def test_text(self):
        self.assertIn("get_at('hello', 1)", self.python('show "hello"[1]'))

    def test_assignment(self):
        self.assertIn("set_at(a, 1, 9)", self.python(LIST + "a[1] = 9"))

    def test_line_map(self):
        _, line_map = generate(check(parse_source(LIST + "show a[0]\na[1] = 2\n")))
        self.assertEqual(line_map, {1: 1, 2: 2, 3: 3})


class RunTests(unittest.TestCase):
    def test_first_last_and_negative(self):
        self.assertEqual(
            lines_of(LIST + "show a[0]\nshow a[2]\nshow a[-1]\nshow a[-3]\n"),
            ["10", "30", "30", "10"])

    def test_computed_index(self):
        source = (LIST + "let i = 1\nshow a[i + 1]\nshow a[len(a) - 1]\n"
                  "show a[4 / 2]\nshow a[a[0] / 10]\n")
        self.assertEqual(lines_of(source), ["30", "30", "30", "20"])

    def test_text_indexing(self):
        source = ('let word = "hello"\nshow word[0]\nshow word[-1]\n'
                  'show "hello"[1]\nshow len(word[0])\n')
        self.assertEqual(lines_of(source), ["h", "o", "e", "1"])

    def test_item_of_text_list(self):
        source = 'let words = ["cat", "dog"]\nshow words[0][1]\nshow words[-1][-1]\n'
        self.assertEqual(lines_of(source), ["a", "g"])

    def test_function_call_result(self):
        source = "function F():\n    give [5, 6]\nshow F()[1]\n"
        self.assertEqual(lines_of(source), ["6"])

    def test_in_arithmetic_and_conditions(self):
        source = (LIST + "show a[0] + a[2] * 2\nshow -a[0]\n"
                  "if (a[1] > 15):\n    show \"big\"\nelse:\n    show \"small\"\n")
        self.assertEqual(lines_of(source), ["70", "-10", "big"])

    def test_in_loop(self):
        source = (LIST + "let i = 0\nfor n in a:\n    show a[i] + n\n"
                  "    i = i + 1\nfor c in \"hey\"[0]:\n    show c\n")
        self.assertEqual(lines_of(source), ["20", "40", "60", "h"])

    def test_in_function(self):
        source = ("function Last(items):\n    give items[-1]\n"
                  "show Last([1, 2, 3])\nshow Last(\"abc\")\n")
        self.assertEqual(lines_of(source), ["3", "c"])

    def test_as_function_argument_and_list_item(self):
        source = LIST + "show max([a[0], a[1]])\nshow [a[0], a[1]]\n"
        self.assertEqual(lines_of(source), ["20", "[10, 20]"])

    def test_pop_with_an_item(self):
        source = "let a = [1, 0, 5]\na.pop(a[1])\nshow a\n"
        self.assertEqual(lines_of(source), ["[0, 5]"])

    def test_assignment(self):
        source = LIST + "a[1] = 99\nshow a\na[-1] = a[0] + 1\nshow a\n"
        self.assertEqual(lines_of(source), ["[10, 99, 30]", "[10, 99, 11]"])

    def test_assignment_mixed_kinds(self):
        source = LIST + 'a[0] = "x"\nshow a\n'
        self.assertEqual(lines_of(source), ['["x", 20, 30]'])

    def test_assignment_shared_list(self):
        source = "let a = [1, 2]\nlet b = a\nb[0] = 7\nshow a\n"
        self.assertEqual(lines_of(source), ["[7, 2]"])

    def test_assignment_in_a_function(self):
        source = "function Zero(items):\n    items[0] = 0\nlet a = [5, 6]\nZero(a)\nshow a\n"
        self.assertEqual(lines_of(source), ["[0, 6]"])

    def test_pop_still_rejects_negative(self):
        error = error_in("run", LIST + "let i = -1\na.pop(i)")
        self.assertIn("can't be negative", str(error))


class RuntimeErrorTests(unittest.TestCase):
    def test_too_big(self):
        error = error_in("run", "let a = [1, 2, 3]\nshow 1\nshow a[3]")
        self.assertEqual(
            str(error),
            "Error on line 3: The list has 3 items (positions 0 to 2, or -1 "
            "to -3 from the end), so there is no item at position 3.")

    def test_too_negative(self):
        error = error_in("run", LIST + "show a[-4]")
        self.assertIn("there is no item at position -4", str(error))
        self.assertEqual(error.line, 2)

    def test_one_item(self):
        error = error_in("run", "let a = [1]\nshow a[1]")
        self.assertIn("The list has 1 item (only position 0, or -1 from the "
                      "end), so there is no item at position 1.", str(error))

    def test_empty_list(self):
        error = error_in("run", "let a = []\nshow a[0]")
        self.assertIn("The list is empty, so there is no item at position 0.",
                      str(error))

    def test_text_too_big(self):
        error = error_in("run", 'let w = "hi"\nshow w[5]')
        self.assertIn("The text has 2 characters (positions 0 to 1, or -1 to "
                      "-2 from the end), so there is no character at position "
                      "5.", str(error))

    def test_empty_text(self):
        error = error_in("run", 'show ""[0]')
        self.assertIn("The text is empty", str(error))

    def test_computed_index_out_of_range_inside_function(self):
        source = "function F(a):\n    give a[len(a)]\nshow F([1])\n"
        error = error_in("run", source)
        self.assertEqual(error.line, 2)
        self.assertIn("no item at position 1", str(error))

    def test_computed_decimal_index(self):
        error = error_in("run", LIST + "show a[3 / 2]")
        self.assertIn("1.5 has a decimal part", str(error))

    def test_non_number_index_at_run_time(self):
        source = "function F(a, i):\n    give a[i]\nshow F([1], \"x\")\n"
        self.assertIn("but this is text", str(error_in("run", source)))

    def test_index_a_number_at_run_time(self):
        source = "function F(a):\n    give a[0]\nshow F(5)\n"
        error = error_in("run", source)
        self.assertEqual(error.line, 2)
        self.assertIn("but this value is a number", str(error))

    def test_assignment_out_of_range(self):
        error = error_in("run", LIST + "a[3] = 1")
        self.assertEqual(error.line, 2)
        self.assertIn("The list has 3 items", str(error))

    def test_assignment_empty_list(self):
        error = error_in("run", "let a = []\na[0] = 1")
        self.assertIn("The list is empty", str(error))

    def test_assignment_to_text_at_run_time(self):
        source = "function F(a):\n    a[0] = 1\nF(\"hi\")\n"
        self.assertIn("Text can't be changed", str(error_in("run", source)))

    def test_assignment_to_number_at_run_time(self):
        source = "function F(a):\n    a[0] = 1\nF(5)\n"
        self.assertIn("but this value is a number", str(error_in("run", source)))

    def test_assignment_list_value_at_run_time(self):
        source = "function F(a, b):\n    a[0] = b\nF([1], [2])\n"
        self.assertIn("can't hold another list", str(error_in("run", source)))

    def test_helpers_directly(self):
        self.assertEqual(get_at([1, 2], -2), 1)
        self.assertEqual(get_at("abc", 2.0), "c")
        items = [1, 2]
        set_at(items, 0, 5)
        self.assertEqual(items, [5, 2])


class CommandLineTests(unittest.TestCase):
    def scripty(self, command, path):
        return subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripty.py"), command, path],
            capture_output=True, text=True, encoding="utf-8", cwd=ROOT)

    def test_example_runs(self):
        result = self.scripty("run", os.path.join("examples", "indexing.scy"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[10, 99, 30]", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_build_output_is_readable(self):
        result = self.scripty("build", os.path.join("examples", "indexing.scy"))
        self.assertEqual(result.returncode, 0)
        self.assertIn("print(get_at(numbers, -1))", result.stdout)
        self.assertIn("set_at(numbers, 1, 99)", result.stdout)

    def test_friendly_error_from_the_command_line(self):
        path = os.path.join(ROOT, "tests", "_tmp_indexing.scy")
        with open(path, "w", encoding="utf-8") as file:
            file.write("let a = [1, 2, 3]\nshow a[3]\n")
        try:
            result = self.scripty("run", path)
        finally:
            os.remove(path)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.startswith("Error on line 2: The list has 3"))
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
