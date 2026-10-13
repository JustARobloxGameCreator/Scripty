import unittest

from ast_nodes import Program
from checker import check
from errors import ScriptyError
from lexer import tokenize
from parser import parse


def parse_source(source: str) -> Program:
    return parse(tokenize(source))


def error_for(source: str) -> ScriptyError:
    with_error = parse_source(source)
    with unittest.TestCase().assertRaises(ScriptyError) as caught:
        check(with_error)
    return caught.exception


class ValidProgramTests(unittest.TestCase):
    def test_returns_same_program(self):
        program = parse_source("let x = 5\nlet y = x + 3\nshow y")
        self.assertIs(check(program), program)

    def test_empty_program(self):
        check(parse_source(""))

    def test_literals_only(self):
        check(parse_source('show 1\necho("hi")\nshow -2 * 3'))

    def test_nested_use_of_declared_names(self):
        check(parse_source("let a = 1\nlet b = 2\necho(-(a + b) * (a - b))"))


class UndeclaredTests(unittest.TestCase):
    def test_exact_message_and_line(self):
        error = error_for("let x = 5\nshow z")
        self.assertEqual(
            str(error),
            'Error on line 2: I don\'t know what "z" is. '
            "Did you forget to write: let z = ...")
        self.assertEqual(error.line, 2)

    def test_use_before_declare(self):
        error = error_for("show x\nlet x = 1")
        self.assertEqual(error.line, 1)
        self.assertIn('"x"', error.message)

    def test_self_reference(self):
        error = error_for("let x = x + 1")
        self.assertEqual(str(error),
                         'Error on line 1: I don\'t know what "x" is. '
                         "Did you forget to write: let x = ...")

    def test_in_echo(self):
        self.assertEqual(error_for('let a = 1\n\necho(b)').line, 3)

    def test_nested_binary_and_negate(self):
        error = error_for("let a = 1\nlet b = a + 2 * (3 - -q)")
        self.assertEqual(error.line, 2)
        self.assertIn('"q"', error.message)

    def test_first_error_wins(self):
        self.assertIn('"p"', error_for("show p\nshow q").message)


class DuplicateTests(unittest.TestCase):
    def test_duplicate_declaration(self):
        error = error_for("let x = 1\nshow x\nlet x = 2")
        self.assertEqual(error.line, 3)
        self.assertIn('"x" is already declared on line 1', error.message)

    def test_duplicate_can_use_itself(self):
        # x exists, so the value is fine; the redeclaration is the problem.
        error = error_for("let x = 1\nlet x = x + 1")
        self.assertIn("already declared on line 1", error.message)

    def test_undeclared_in_value_reported_first(self):
        error = error_for("let x = 1\nlet x = y")
        self.assertIn('"y"', error.message)


class TypeTests(unittest.TestCase):
    def test_text_plus_text_is_allowed(self):
        check(parse_source('let a = "x"\nshow a + "y" + a'))

    def test_numbers_allow_everything(self):
        check(parse_source("show 1 + 2 * 3 - 4 / 5"))

    def test_text_plus_number(self):
        error = error_for('show "a" + 1')
        self.assertEqual(error.line, 1)
        self.assertIn("mix text and a number", error.message)

    def test_number_plus_text_variable(self):
        error = error_for('let a = "a"\nlet b = 1\nshow b + a')
        self.assertEqual(error.line, 3)

    def test_text_times_text(self):
        error = error_for('show "a" * "b"')
        self.assertIn('can\'t use "*" with text', error.message)

    def test_text_minus_text(self):
        self.assertIn('"-"', error_for('show "a" - "b"').message)

    def test_negating_text(self):
        self.assertIn("minus sign", error_for('show -"a"').message)

    def test_type_flows_through_variables(self):
        error = error_for('let a = "x" + "y"\nlet b = a * 2')
        self.assertEqual(error.line, 2)


if __name__ == "__main__":
    unittest.main()
