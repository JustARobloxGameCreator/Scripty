import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def scripty(*args: str) -> subprocess.CompletedProcess:
    """Run `python scripty.py ARGS` from the repo root, capturing output."""
    return subprocess.run(
        [sys.executable, "scripty.py", *args], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8")


class ProgramFileTestCase(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def write(self, source: str, name: str = "test.scy") -> str:
        path = os.path.join(self.folder.name, name)
        with open(path, "w", encoding="utf-8") as file:
            file.write(source)
        return path

    def run_source(self, source: str) -> subprocess.CompletedProcess:
        return scripty("run", self.write(source))

    def assertFriendlyError(self, result, expected: str):
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn(expected, result.stderr)
        self.assertNotIn("Traceback", result.stdout + result.stderr)


class RunTests(ProgramFileTestCase):
    def test_hello_prints_8(self):
        result = scripty("run", "hello.scy")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "8")
        self.assertEqual(result.stderr, "")

    def test_example_with_text(self):
        result = scripty("run", os.path.join("examples", "text.scy"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(),
                         ["Hello world!", "Hello, Scripty", "2.5"])

    def test_text_with_special_characters(self):
        result = self.run_source('echo("café it\'s")')
        self.assertEqual(result.stdout.strip(), "café it's")

    def test_output_before_a_runtime_error_is_kept(self):
        result = self.run_source("show 1\nshow 1 / 0")
        self.assertEqual(result.stdout.strip(), "1")
        self.assertIn("Error on line 2", result.stderr)

    def test_module_entry_point_cli_py(self):
        result = subprocess.run(
            [sys.executable, "cli.py", "run", "hello.scy"], cwd=ROOT,
            capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "8")


class BuildTests(ProgramFileTestCase):
    def test_build_prints_python_only(self):
        result = scripty("build", "hello.scy")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "x = 5\ny = x + 3\nprint(y)\n")


class FileErrorTests(ProgramFileTestCase):
    def test_missing_file(self):
        result = scripty("run", "nope.scy")
        self.assertFriendlyError(result, 'I can\'t find the file "nope.scy".')

    def test_wrong_extension(self):
        path = self.write("show 1", "x.txt")
        result = scripty("run", path)
        self.assertFriendlyError(
            result, f'Scripty files end in .scy, but "{path}" does not.')

    def test_build_checks_the_file_too(self):
        self.assertFriendlyError(scripty("build", "nope.scy"),
                                 "I can't find the file")

    def test_no_arguments_shows_usage(self):
        self.assertFriendlyError(scripty(), "Usage:")

    def test_unknown_command(self):
        self.assertFriendlyError(scripty("fly", "hello.scy"), "Usage:")


class ScriptyErrorTests(ProgramFileTestCase):
    def test_undeclared_variable(self):
        result = self.run_source("let x = 5\nshow z")
        self.assertFriendlyError(
            result, 'Error on line 2: I don\'t know what "z" is. '
                    "Did you forget to write: let z = ...")

    def test_syntax_error(self):
        result = self.run_source("let = 5")
        self.assertFriendlyError(result, "Error on line 1:")

    def test_lexer_error(self):
        result = self.run_source("show 1\nshow @")
        self.assertFriendlyError(result, "Error on line 2:")

    def test_mixed_types(self):
        result = self.run_source('let a = "a"\nshow a + 1')
        self.assertFriendlyError(result, "Error on line 2:")
        self.assertIn("mix text and a number", result.stderr)

    def test_text_times_text(self):
        result = self.run_source('show "a" * "b"')
        self.assertFriendlyError(result, "Error on line 1:")

    def test_division_by_zero(self):
        result = self.run_source("let a = 1\n\n# note\nshow a / 0")
        self.assertFriendlyError(
            result, "Error on line 4: You tried to divide by zero.")

    def test_error_is_printed_only_once_and_nothing_runs_on_check_error(self):
        result = self.run_source('show 1\nshow "a" - 1')
        self.assertEqual(result.stdout, "")



TODO_PROGRAM = """function Name(item1, item2):
    if (item1 > item2): // This is a comment
        give item1 // Same as return
    elif (item1 == item2):
        give 0
    else:
        give item2

show Name(5, 2)
show Name(3, 3)
show Name(1, 9)
"""


class FunctionAndIfRunTests(ProgramFileTestCase):
    def test_todo_example_runs(self):
        result = self.run_source(TODO_PROGRAM)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["5", "0", "9"])
        self.assertEqual(result.stderr, "")

    def test_functions_example_file(self):
        result = scripty("run", os.path.join("examples", "functions.scy"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "7", "Hello, Scripty!", "bigger", "equal", "smaller", "120"])

    def test_conditions_example_file(self):
        result = scripty("run", os.path.join("examples", "conditions.scy"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(),
                         ["You can enter", "B", "not 5"])

    def test_if_without_function(self):
        result = self.run_source(
            'let age = 20\nif (age >= 18):\n    echo("adult")\n'
            'else:\n    echo("child")')
        self.assertEqual(result.stdout.strip(), "adult")

    def test_function_statement_call_prints(self):
        result = self.run_source(
            'function Greet(name):\n    show "Hi " + name\nGreet("Ana")')
        self.assertEqual(result.stdout.strip(), "Hi Ana")

    def test_slash_slash_in_text_is_not_a_comment(self):
        result = self.run_source('show "http://x.y" // really a comment')
        self.assertEqual(result.stdout.strip(), "http://x.y")

    def test_build_shows_python(self):
        result = scripty("build", self.write(TODO_PROGRAM))
        self.assertIn("def Name(item1, item2):", result.stdout)
        self.assertIn("    elif item1 == item2:", result.stdout)

    # -- runtime errors keep the Scripty line, never a traceback ----------

    def test_divide_by_zero_inside_function(self):
        result = self.run_source(
            "function Half(n, d):\n    give n / d\n\nshow Half(4, 0)")
        self.assertFriendlyError(result, "Error on line 2: You tried to divide "
                                         "by zero")

    def test_divide_by_zero_inside_if_branch(self):
        result = self.run_source(
            "let d = 0\nif d == 0:\n    show 1 / d\nelse:\n    show 2")
        self.assertFriendlyError(result, "Error on line 3: You tried to divide")

    def test_divide_by_zero_inside_else_branch(self):
        result = self.run_source(
            "function F(d):\n    if d > 0:\n        give 1\n"
            "    else:\n        give 1 / d\nshow F(0)")
        self.assertFriendlyError(result, "Error on line 5:")

    def test_type_error_at_runtime_inside_function(self):
        result = self.run_source(
            'function Add(a, b):\n    give a + b\nshow Add("x", 1)')
        self.assertFriendlyError(result, "Error on line 2:")

    def test_comparing_text_to_number_at_runtime(self):
        result = self.run_source(
            'function Big(a):\n    if a > 3:\n        give 1\n    give 0\n'
            'show Big("x")')
        self.assertFriendlyError(result, "Error on line 2:")

    def test_endless_recursion_is_friendly(self):
        result = self.run_source(
            "function Loop(n):\n    give Loop(n + 1)\nshow Loop(1)")
        self.assertFriendlyError(result, "Error on line 2:")
        self.assertIn("kept calling itself", result.stderr)

    # -- friendly syntax and meaning errors through the whole pipeline ----

    def test_missing_colon(self):
        result = self.run_source("if 1 < 2\n    show 1")
        self.assertFriendlyError(result, "Error on line 1:")

    def test_tab_indentation(self):
        result = self.run_source("if 1 < 2:\n\tshow 1")
        self.assertFriendlyError(result, "Error on line 2: This line is "
                                         "indented with a tab")

    def test_wrong_argument_count(self):
        result = self.run_source("function F(a):\n    give a\nshow F(1, 2)")
        self.assertFriendlyError(result, "Error on line 3:")
        self.assertIn("needs 1 input", result.stderr)

    def test_give_outside_function(self):
        result = self.run_source("give 1")
        self.assertFriendlyError(result, "Error on line 1: give only works")

if __name__ == "__main__":
    unittest.main()
