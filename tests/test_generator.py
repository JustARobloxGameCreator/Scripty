import contextlib
import io
import unittest

from checker import check
from generator import generate
from lexer import tokenize
from parser import parse


def gen(source: str):
    return generate(check(parse(tokenize(source))))


class StatementTests(unittest.TestCase):
    def test_let_show(self):
        source, _ = gen("let x = 5\nlet y = x + 3\nshow y")
        self.assertEqual(source, "x = 5\ny = x + 3\nprint(y)\n")

    def test_echo_becomes_print(self):
        source, _ = gen('echo("Hello world!")')
        self.assertEqual(source, "print('Hello world!')\n")

    def test_empty_program(self):
        self.assertEqual(gen(""), ("", {}))

    def test_floats(self):
        source, _ = gen("show 3.14")
        self.assertEqual(source, "print(3.14)\n")

    def test_generated_code_runs(self):
        source, _ = gen("let x = 5\nshow x * 2")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(compile(source, "<test>", "exec"), {})
        self.assertEqual(output.getvalue(), "10" + chr(10))


class TextTests(unittest.TestCase):
    def test_backslash_and_single_quote_are_safe(self):
        text = "it's a " + chr(92) + " test"
        source, _ = gen('show "' + text + '"')
        namespace: dict = {}
        exec(compile("result = " + source[len("print("):-2], "<t>", "exec"),
             namespace)
        self.assertEqual(namespace["result"], text)

    def test_text_concatenation(self):
        source, _ = gen('show "a" + "b"')
        self.assertEqual(source, "print('a' + 'b')\n")


class ExpressionTests(unittest.TestCase):
    def test_precedence_is_kept_with_parentheses(self):
        source, _ = gen("show 1 + 2 * 3")
        self.assertEqual(source, "print(1 + (2 * 3))\n")

    def test_left_grouping(self):
        source, _ = gen("show 10 - 4 - 3")
        self.assertEqual(source, "print((10 - 4) - 3)\n")

    def test_explicit_parentheses(self):
        source, _ = gen("show (1 + 2) * 3")
        self.assertEqual(source, "print((1 + 2) * 3)\n")

    def test_right_nested(self):
        source, _ = gen("show 10 - (4 - 3)")
        self.assertEqual(source, "print(10 - (4 - 3))\n")

    def test_negation(self):
        self.assertEqual(gen("show -5")[0], "print(-5)\n")
        self.assertEqual(gen("show -(1 + 2)")[0], "print(-(1 + 2))\n")
        self.assertEqual(gen("show 3 * -2")[0], "print(3 * -2)\n")

    def test_true_division(self):
        source, _ = gen("show 7 / 2")
        self.assertEqual(source, "print(7 / 2)\n")


class NameTests(unittest.TestCase):
    def test_python_keyword_is_renamed(self):
        source, _ = gen("let class = 1\nshow class")
        self.assertEqual(source, "class_scy = 1\nprint(class_scy)\n")

    def test_print_variable_does_not_break_print(self):
        source, _ = gen("let print = 1\nshow print")
        self.assertEqual(source, "print_scy = 1\nprint(print_scy)\n")


class LineMapTests(unittest.TestCase):
    def test_one_python_line_per_statement(self):
        _, line_map = gen("let x = 1\nshow x")
        self.assertEqual(line_map, {1: 1, 2: 2})

    def test_blank_lines_and_comments_are_skipped(self):
        source = "# start\n\nlet x = 1\n\n# note\nshow x\n\necho(\"hi\")"
        _, line_map = gen(source)
        self.assertEqual(line_map, {1: 3, 2: 6, 3: 8})


if __name__ == "__main__":
    unittest.main()
