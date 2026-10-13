import unittest

from ast_nodes import (BinaryOp, Branch, Call, CallStatement, Compare, Echo,
                       For, Function, Give, If, Let, Name, Negate, Number, Program,
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



TODO_EXAMPLE = """function Name(item1, item2):
    if (item1 > item2): // This is a comment
        give item1 // Same as return
    elif (item1 == item2):
        give 0
    else:
        give item2
"""


class FunctionAndIfTests(unittest.TestCase):
    def test_todo_example(self):
        program = parse_source(TODO_EXAMPLE)
        self.assertEqual(program, Program([Function("Name", ["item1", "item2"], [
            If([
                Branch(Compare(">", Name("item1", 2), Name("item2", 2), 2),
                       [Give(Name("item1", 3), 3)], 2),
                Branch(Compare("==", Name("item1", 4), Name("item2", 4), 4),
                       [Give(n(0, 5), 5)], 4),
            ], [Give(Name("item2", 7), 7)], 6, 2)], 1)]))

    def test_function_without_parameters(self):
        program = parse_source("function Hi():\n    show 1")
        self.assertEqual(program.statements,
                         [Function("Hi", [], [Show(n(1, 2), 2)], 1)])

    def test_parentheses_around_condition_are_optional(self):
        with_parens = parse_source("if (1 < 2):\n    show 1")
        without = parse_source("if 1 < 2:\n    show 1")
        self.assertEqual(with_parens, without)

    def test_parenthesised_expression_inside_condition(self):
        program = parse_source("if (1 + 2) * 3 > 4:\n    show 1")
        condition = program.statements[0].branches[0].condition
        self.assertEqual(condition.op, ">")
        self.assertIsInstance(condition.left, BinaryOp)

    def test_double_parentheses(self):
        parse_source("if ((1 + 2) > 2):\n    show 1")

    def test_if_without_else(self):
        node = parse_source("if 1 == 1:\n    show 1").statements[0]
        self.assertIsNone(node.else_body)

    def test_nested_if_and_dedent(self):
        source = ("if 1 < 2:\n    if 2 < 3:\n        show 1\n"
                  "    show 2\nshow 3")
        program = parse_source(source)
        outer = program.statements[0]
        self.assertEqual(len(outer.branches[0].body), 2)
        self.assertEqual(len(program.statements), 2)

    def test_calls_as_value_and_statement(self):
        program = parse_source(
            'let r = Add(1, 2 * 3)\nshow Add(r, 1)\nGreet("Ana")\nNone()')
        self.assertEqual(program.statements[0].value,
                         Call("Add", [n(1), BinaryOp("*", n(2), n(3), 1)], 1))
        self.assertIsInstance(program.statements[1].value, Call)
        self.assertEqual(program.statements[2],
                         CallStatement(Call("Greet", [Text("Ana", 3)], 3), 3))
        self.assertEqual(program.statements[3].call.args, [])

    def test_call_inside_expression(self):
        value = parse_source("show 1 + F(2)").statements[0].value
        self.assertIsInstance(value.right, Call)

    def test_give_inside_if_inside_function(self):
        parse_source("function F(a):\n    if a > 1:\n        give a\n    give 0")


class FunctionAndIfErrorTests(SyntaxErrorTests):
    def test_missing_colon_function(self):
        self.assertError("function F(a)\n    give a", 1, "missing", '":"')

    def test_missing_colon_if(self):
        self.assertError("if 1 < 2\n    show 1", 1, "if", '":"')

    def test_missing_colon_else(self):
        self.assertError("if 1 < 2:\n    show 1\nelse\n    show 2", 3, '":"')

    def test_missing_body(self):
        self.assertError("function F(a):\nshow 1", 1, "nothing inside")

    def test_missing_body_at_end_of_file(self):
        self.assertError("if 1 < 2:", 1, "nothing inside")

    def test_statement_on_same_line_as_colon(self):
        self.assertError("if 1 < 2: show 1", 1, "next lines")

    def test_elif_without_if(self):
        self.assertError("elif 1 < 2:\n    show 1", 1, "elif", "if above")

    def test_else_without_if(self):
        self.assertError("show 1\nelse:\n    show 2", 2, "else", "if above")

    def test_elif_after_else(self):
        self.assertError(
            "if 1 < 2:\n    show 1\nelse:\n    show 2\nelif 1 < 3:\n    show 3",
            5, "elif")

    def test_else_if(self):
        self.assertError("if 1 < 2:\n    show 1\nelse if 1 < 3:\n    show 3",
                         3, "elif")

    def test_give_outside_function(self):
        self.assertError("give 5", 1, "inside a function")

    def test_give_in_if_outside_function(self):
        self.assertError("if 1 < 2:\n    give 5", 2, "inside a function")

    def test_give_without_value(self):
        self.assertError("function F():\n    give", 2, "needs a value")

    def test_unexpected_indent(self):
        self.assertError("show 1\n    show 2", 2, "indented")

    def test_function_inside_function(self):
        self.assertError("function A():\n    function B():\n        show 1",
                         2, "can't be written inside")

    def test_function_inside_if(self):
        self.assertError("if 1 < 2:\n    function B():\n        show 1",
                         2, "can't be written inside")

    def test_function_without_name(self):
        self.assertError("function (a):\n    show 1", 1, "forgot its name")

    def test_function_name_is_keyword(self):
        self.assertError("function show(a):\n    show 1", 1, "keyword")

    def test_function_without_parentheses(self):
        self.assertError("function F:\n    show 1", 1, "parentheses")

    def test_function_bad_parameter(self):
        self.assertError("function F(1):\n    show 1", 1, "input name")

    def test_function_trailing_comma(self):
        self.assertError("function F(a,):\n    show 1", 1, "input name")

    def test_function_missing_comma(self):
        self.assertError("function F(a b):\n    show 1", 1, "comma")

    def test_function_unclosed_parameters(self):
        self.assertError("function F(a", 1, "comma")

    def test_if_without_condition(self):
        self.assertError("if:\n    show 1", 1, "needs a condition")

    def test_condition_without_comparison(self):
        self.assertError("if 5:\n    show 1", 1, "needs a comparison")

    def test_single_equals_in_condition(self):
        self.assertError("if x = 5:\n    show 1", 1, '"=="')

    def test_chained_comparison(self):
        self.assertError("if 1 < 2 < 3:\n    show 1", 1, "two values")

    def test_comparison_outside_if(self):
        self.assertError("let x = 1 > 2", 1, "after if or elif")

    def test_call_missing_closing_parenthesis(self):
        self.assertError("show F(1, 2", 1, "closing")

    def test_call_missing_comma(self):
        self.assertError("show F(1 2)", 1, "comma")

    def test_assignment_without_let(self):
        self.assertError("x = 5", 1, "must start with", "let x = ...")


TODO_FOR = 'for i in "hello world!":\n    show i'


class ForLoopTests(unittest.TestCase):
    def test_todo_example(self):
        program = parse_source(TODO_FOR)
        self.assertEqual(program, Program([
            For("i", Text("hello world!", 1), [Show(Name("i", 2), 2)], 1)]))

    def test_iterable_can_be_a_variable_call_or_expression(self):
        source = ('for a in word:\n    show a\n'
                  'for b in F(1):\n    show b\n'
                  'for c in "x" + "y":\n    show c')
        values = [s.iterable for s in parse_source(source).statements]
        self.assertEqual(values[0], Name("word", 1))
        self.assertEqual(values[1], Call("F", [n(1, 3)], 3))
        self.assertIsInstance(values[2], BinaryOp)

    def test_statements_after_the_loop_are_outside_it(self):
        program = parse_source('for i in "ab":\n    show i\nshow 1')
        self.assertEqual(len(program.statements), 2)
        self.assertEqual(len(program.statements[0].body), 1)

    def test_nested_loops_ifs_and_give(self):
        source = ('function F(t):\n'
                  '    for a in t:\n'
                  '        for b in t:\n'
                  '            if a == b:\n'
                  '                give a\n'
                  '    give "none"')
        function = parse_source(source).statements[0]
        outer = function.body[0]
        self.assertIsInstance(outer, For)
        self.assertIsInstance(outer.body[0], For)
        self.assertIsInstance(outer.body[0].body[0], If)

    def test_loop_inside_if_branch(self):
        program = parse_source('if 1 < 2:\n    for i in "a":\n        show i')
        self.assertIsInstance(program.statements[0].branches[0].body[0], For)


class ForLoopErrorTests(SyntaxErrorTests):
    def test_missing_name(self):
        self.assertError('for in "hi":\n    show 1', 1, "forgot the name",
                         "for letter in")

    def test_missing_name_and_everything(self):
        self.assertError("for", 1, "forgot the name")

    def test_number_as_name(self):
        self.assertError('for 5 in "hi":\n    show 1', 1, "forgot the name")

    def test_keyword_as_name(self):
        self.assertError('for let in "hi":\n    show 1', 1, '"let"',
                         "keyword")

    def test_missing_in(self):
        self.assertError('for i "hi":\n    show i', 1, 'expected "in"',
                         '"i"')

    def test_missing_in_at_end_of_line(self):
        self.assertError("for i\n    show i", 1, 'expected "in"')

    def test_wrong_word_instead_of_in(self):
        self.assertError('for i of "hi":\n    show i', 1, 'expected "in"')

    def test_missing_value_before_colon(self):
        self.assertError("for i in:\n    show i", 1, "needs a text",
                         "for i in")

    def test_missing_value_at_end_of_line(self):
        self.assertError("for i in", 1, "needs a text")

    def test_missing_colon(self):
        self.assertError('for i in "hi"\n    show i', 1, '":"', "for loop")

    def test_junk_instead_of_colon(self):
        self.assertError('for i in "hi" 5:\n    show i', 1, '":"')

    def test_missing_body(self):
        self.assertError('for i in "hi":\nshow 1', 1, "nothing inside",
                         "4 spaces")

    def test_missing_body_at_end_of_file(self):
        self.assertError('for i in "hi":', 1, "nothing inside")

    def test_statement_on_same_line(self):
        self.assertError('for i in "hi": show i', 1, "next lines")

    def test_wrong_indentation_in_body(self):
        self.assertError('for i in "hi":\n  show i', 2, "4 spaces")

    def test_body_indented_too_far(self):
        self.assertError('for i in "hi":\n        show i', 2, "too far")

    def test_in_outside_for(self):
        self.assertError("in 5", 1, "in only works", "for")

    def test_function_inside_for(self):
        self.assertError('for i in "hi":\n    function F():\n        show 1',
                         2, "can't be written inside")

    def test_give_in_loop_outside_function(self):
        self.assertError('for i in "hi":\n    give i', 2,
                         "inside a function")

    def test_indented_line_without_colon_mentions_for(self):
        self.assertError("show 1\n    show 2", 2, "a for")


if __name__ == "__main__":
    unittest.main()
