import contextlib
import io
import unittest

from errors import ScriptyError
from runner import run_python


def run(source: str, line_map: dict[int, int]) -> str:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        run_python(source, line_map)
    return output.getvalue()


def error_for(source: str, line_map: dict[int, int]) -> ScriptyError:
    with unittest.TestCase().assertRaises(ScriptyError) as caught:
        run(source, line_map)
    return caught.exception


class RunPythonTests(unittest.TestCase):
    def test_runs_code(self):
        self.assertEqual(run("print(1 + 2)\n", {1: 1}), "3\n")

    def test_division_by_zero_uses_line_map(self):
        error = error_for("x = 1\nprint(x / 0)\n", {1: 3, 2: 7})
        self.assertEqual(str(error),
                         "Error on line 7: You tried to divide by zero. "
                         "Dividing by zero has no answer.")

    def test_type_error(self):
        error = error_for("print('a' + 1)\n", {1: 4})
        self.assertEqual(error.line, 4)
        self.assertIn("mix text and numbers", error.message)

    def test_name_error(self):
        error = error_for("print(z)\n", {1: 2})
        self.assertEqual(error.line, 2)
        self.assertIn('"z"', error.message)

    def test_other_errors_are_friendly_too(self):
        error = error_for("print(1)\nraise ValueError('boom')\n", {1: 1, 2: 5})
        self.assertEqual(error.line, 5)
        self.assertNotIn("boom", error.message)

    def test_overflow(self):
        error = error_for("print(10 ** 400 / 1)\n", {1: 1})
        self.assertIn("too big", error.message)


class ForLoopRuntimeTests(unittest.TestCase):
    def test_loop_over_number_is_friendly(self):
        error = error_for("for i in 5:\n    print(i)\n", {1: 3, 2: 4})
        self.assertEqual(error.line, 3)
        self.assertEqual(error.message, "You can only go through text with "
                                        "for, but this value is a number.")

    def test_loop_over_float_is_friendly(self):
        error = error_for("for i in 2.5:\n    pass\n", {1: 1, 2: 2})
        self.assertIn("only go through text", error.message)

    def test_other_type_errors_are_not_mistaken_for_loops(self):
        error = error_for("for i in 'ab':\n    print(i + 1)\n", {1: 1, 2: 2})
        self.assertEqual(error.line, 2)
        self.assertIn("mix text and numbers", error.message)

    def test_error_inside_loop_body_uses_body_line(self):
        error = error_for("for i in 'ab':\n    print(1 / 0)\n", {1: 5, 2: 6})
        self.assertEqual(error.line, 6)
        self.assertIn("divide by zero", error.message)


if __name__ == "__main__":
    unittest.main()
