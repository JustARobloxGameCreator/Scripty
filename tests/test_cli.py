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


if __name__ == "__main__":
    unittest.main()
