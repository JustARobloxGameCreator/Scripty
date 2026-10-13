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



def run_source(source: str) -> str:
    python, _ = gen(source)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exec(compile(python, "<test>", "exec"), {})
    return output.getvalue()


class FunctionAndIfGenerationTests(unittest.TestCase):
    TODO = (
        "function Name(item1, item2):\n"
        "    if (item1 > item2): // This is a comment\n"
        "        give item1 // Same as return\n"
        "    elif (item1 == item2):\n"
        "        give 0\n"
        "    else:\n"
        "        give item2\n"
        "show Name(5, 2)\n")

    def test_todo_example_python(self):
        source, _ = gen(self.TODO)
        self.assertEqual(source, (
            "def Name(item1, item2):\n"
            "    if item1 > item2:\n"
            "        return item1\n"
            "    elif item1 == item2:\n"
            "        return 0\n"
            "    else:\n"
            "        return item2\n"
            "print(Name(5, 2))\n"))

    def test_todo_example_line_map(self):
        _, line_map = gen(self.TODO)
        # Python line -> Scripty line (the `else:` maps to Scripty line 6)
        self.assertEqual(line_map, {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6,
                                    7: 7, 8: 8})

    def test_line_map_skips_comments_and_blank_lines(self):
        source = ("// top\nfunction F(a):\n\n    // inside\n    give a\n\n"
                  "show F(1)")
        python, line_map = gen(source)
        self.assertEqual(line_map, {1: 2, 2: 5, 3: 7})
        self.assertEqual(python.count("\n"), 3)

    def test_all_comparisons(self):
        for op in ("==", "!=", ">=", "<=", ">", "<"):
            source, _ = gen(f"if 1 {op} 2:\n    show 1")
            self.assertEqual(source, f"if 1 {op} 2:\n    print(1)\n")

    def test_nested_blocks_are_indented(self):
        source, _ = gen(
            "function F(a):\n    if a > 1:\n        if a > 2:\n"
            "            give 3\n        give 2\n    give 1")
        self.assertEqual(source, (
            "def F(a):\n    if a > 1:\n        if a > 2:\n"
            "            return 3\n        return 2\n    return 1\n"))

    def test_code_after_a_block_is_dedented(self):
        source, _ = gen("if 1 < 2:\n    show 1\nshow 2")
        self.assertEqual(source, "if 1 < 2:\n    print(1)\nprint(2)\n")

    def test_call_statement(self):
        source, _ = gen("function Hi(n):\n    show n\nHi(1 + 2)")
        self.assertEqual(source, "def Hi(n):\n    print(n)\nHi(1 + 2)\n")

    def test_python_keyword_names_get_suffix(self):
        source, _ = gen(
            "function class(lambda):\n    give lambda\nshow class(1)")
        self.assertEqual(source, (
            "def class_scy(lambda_scy):\n    return lambda_scy\n"
            "print(class_scy(1))\n"))

    def test_function_named_print(self):
        source, _ = gen("function print(a):\n    give a\nshow print(2)")
        self.assertIn("def print_scy(a):", source)
        self.assertEqual(run_source("function print(a):\n    give a\n"
                                    "show print(2)"), "2\n")

    def test_generated_code_runs(self):
        self.assertEqual(run_source(self.TODO), "5\n")

    def test_recursion(self):
        source = ("function Fact(n):\n    if n <= 1:\n        give 1\n"
                  "    else:\n        give n * Fact(n - 1)\nshow Fact(5)")
        self.assertEqual(run_source(source), "120\n")

    def test_text_comparison_runs(self):
        self.assertEqual(run_source(
            'if "a" < "b":\n    echo("yes")\nelse:\n    echo("no")'), "yes\n")

if __name__ == "__main__":
    unittest.main()
