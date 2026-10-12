import unittest

from ast_nodes import (BinaryOp, Echo, Let, Name, Negate, Number, Program,
                       Show, Text)
from errors import ScriptyError
from lexer import tokenize
from parser import parse


def parse_source(source: str) -> Program:
    return parse(tokenize(source))


def n(value, line=1):
    return Number(value, line)


class ValidProgramTests(unittest.TestCase):
    def test_empty_program(self):
        self.assertEqual(parse_source(""), Program([]))
        self.assertEqual(parse_source("# only a comment\n\n"), Program([]))

    def test_let_number(self):
        self.assertEqual(parse_source("let x = 5"),
                         Program([Let("x", n(5), 1)]))

    def test_let_text_and_float(self):
        program = parse_source('let a = "hi"\nlet b = 3.5')
        self.assertEqual(program.statements, [
            Let("a", Text("hi", 1), 1), Let("b", n(3.5, 2), 2)])

    def test_show_and_echo(self):
        program = parse_source('show x\necho("Hello world!")')
        self.assertEqual(program.statements, [
            Show(Name("x", 1), 1), Echo(Text("Hello world!", 2), 2)])

    def test_hello_program(self):
        program = parse_source("let x = 5\nlet y = x + 3\nshow y")
        self.assertEqual(program.statements, [
            Let("x", n(5), 1),
            Let("y", BinaryOp("+", Name("x", 2), n(3, 2), 2), 2),
            Show(Name("y", 3), 3)])

    def test_line_numbers_skip_blank_lines(self):
        program = parse_source("\n\nshow 1")
        self.assertEqual(program.statements[0].line, 3)


class ExpressionTests(unittest.TestCase):
    def value(self, source):
        return parse_source("show " + source).statements[0].value

    def test_multiplication_binds_tighter(self):
        self.assertEqual(self.value("1 + 2 * 3"), BinaryOp(
            "+", n(1), BinaryOp("*", n(2), n(3), 1), 1))
        self.assertEqual(self.value("1 * 2 + 3"), BinaryOp(
            "+", BinaryOp("*", n(1), n(2), 1), n(3), 1))

    def test_left_associative(self):
        self.assertEqual(self.value("8 - 3 - 2"), BinaryOp(
            "-", BinaryOp("-", n(8), n(3), 1), n(2), 1))
        self.assertEqual(self.value("8 / 4 / 2"), BinaryOp(
            "/", BinaryOp("/", n(8), n(4), 1), n(2), 1))

    def test_parentheses_override_precedence(self):
        self.assertEqual(self.value("(1 + 2) * 3"), BinaryOp(
            "*", BinaryOp("+", n(1), n(2), 1), n(3), 1))

    def test_nested_parentheses(self):
        self.assertEqual(self.value("((4))"), n(4))

    def test_unary_minus(self):
        self.assertEqual(self.value("-5"), Negate(n(5), 1))
        self.assertEqual(self.value("3 * -x"), BinaryOp(
            "*", n(3), Negate(Name("x", 1), 1), 1))
        self.assertEqual(self.value("-2 * 3"), BinaryOp(
            "*", Negate(n(2), 1), n(3), 1))

    def test_echo_with_arithmetic(self):
        program = parse_source("echo((1 + 2) * 3)")
        self.assertIsInstance(program.statements[0].value, BinaryOp)


class SyntaxErrorTests(unittest.TestCase):
    def assertError(self, source, line, *words):
        with self.assertRaises(ScriptyError) as caught:
            parse_source(source)
        error = caught.exception
        self.assertEqual(error.line, line)
        self.assertTrue(str(error).startswith(f"Error on line {line}:"))
        for word in words:
            self.assertIn(word, error.message)

    def test_let_without_name(self):
        self.assertError("let = 5", 1, "name", "let x = 5")

    def test_let_missing_value(self):
        self.assertError("let x =", 1, "no value", "let x = 5")

    def test_let_missing_equals(self):
        self.assertError("let x 5", 1, '"="', "let x = 5")

    def test_let_alone(self):
        self.assertError("let", 1, "name")

    def test_show_with_nothing(self):
        self.assertError("show", 1, "show needs something")

    def test_echo_without_parentheses(self):
        self.assertError('echo "hi"', 1, "parentheses")

    def test_echo_empty(self):
        self.assertError("echo()", 1, "I did not expect", '")"')

    def test_stray_tokens_after_statement(self):
        self.assertError("let x = 5 5", 1, "did not expect", "5")
        self.assertError("show x y", 1, '"y"')

    def test_line_starting_with_name(self):
        self.assertError("x = 5", 1, "must start with")

    def test_error_reports_correct_line(self):
        self.assertError("let x = 1\nshow x\nlet = 2", 3)

    def test_unclosed_parenthesis(self):
        self.assertError("show (1 + 2", 1, '"("', "no matching")

    def test_unclosed_echo(self):
        self.assertError('echo("hi"', 1, '")"')

    def test_extra_closing_parenthesis(self):
        self.assertError("show 1 + 2)", 1, '")"', "no matching")

    def test_operator_where_value_expected(self):
        self.assertError("let x = * 3", 1, '"*"', "value")
        self.assertError("show 1 + * 2", 1, '"*"')

    def test_operator_missing_right_side(self):
        self.assertError("show 1 +", 1, 'nothing after "+"')

    def test_keyword_in_expression(self):
        self.assertError("let x = show", 1, '"show"')

    def test_two_values_in_a_row(self):
        self.assertError('show 1 "a"', 1, '"a"')


if __name__ == "__main__":
    unittest.main()
