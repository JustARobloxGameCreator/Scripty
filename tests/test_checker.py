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



ADD = "function Add(a, b):\n    give a + b\n"


class ConditionTests(unittest.TestCase):
    def test_valid_if_elif_else(self):
        check(parse_source(
            "let x = 5\nif x > 3:\n    show 1\nelif x == 3:\n    show 2\n"
            "else:\n    show 3"))

    def test_undeclared_name_in_condition(self):
        error = error_for("if z > 3:\n    show 1")
        self.assertEqual(error.line, 1)
        self.assertIn('"z"', error.message)

    def test_ordering_text_with_number_is_error(self):
        error = error_for('let t = "a"\nif t > 3:\n    show 1')
        self.assertEqual(error.line, 2)
        self.assertIn("compare text with a number", error.message)
        self.assertIn("==", error.message)

    def test_ordering_text_with_text_is_fine(self):
        check(parse_source('if "a" < "b":\n    show 1'))

    def test_equality_between_different_kinds_is_allowed(self):
        check(parse_source('if "5" == 5:\n    show 1\nelif 5 != "5":\n    show 2'))

    def test_error_inside_branch_has_its_own_line(self):
        error = error_for("if 1 < 2:\n    show 1\nelse:\n    show nope")
        self.assertEqual(error.line, 4)

    def test_branch_variable_is_gone_after_the_if(self):
        error = error_for("if 1 < 2:\n    let a = 1\nshow a")
        self.assertEqual(error.line, 3)

    def test_same_name_in_two_branches_is_fine(self):
        check(parse_source(
            "if 1 < 2:\n    let a = 1\n    show a\nelse:\n    let a = 2\n"
            "    show a"))

    def test_branch_cannot_redeclare_outer_variable(self):
        error = error_for("let a = 1\nif 1 < 2:\n    let a = 2")
        self.assertEqual(error.line, 3)
        self.assertIn("already declared on line 1", error.message)

    def test_branch_can_use_outer_variable(self):
        check(parse_source("let a = 1\nif a < 2:\n    show a + 1"))

    def test_type_error_in_branch(self):
        error = error_for('if 1 < 2:\n    show "a" + 1')
        self.assertEqual(error.line, 2)


class FunctionTests(unittest.TestCase):
    def test_valid_function_and_calls(self):
        check(parse_source(ADD + "let r = Add(1, 2)\nshow Add(r, 3)\nAdd(1, 1)"))

    def test_todo_example_is_valid(self):
        check(parse_source(
            "function Name(item1, item2):\n"
            "    if (item1 > item2):\n        give item1\n"
            "    elif (item1 == item2):\n        give 0\n"
            "    else:\n        give item2\n"
            "show Name(1, 2)"))

    def test_parameters_are_declared_in_the_function(self):
        check(parse_source("function F(a):\n    show a"))

    def test_parameter_not_visible_outside(self):
        error = error_for("function F(a):\n    show a\nshow a")
        self.assertEqual(error.line, 3)

    def test_local_variable_not_visible_outside(self):
        error = error_for("function F():\n    let a = 1\n    give a\nshow a")
        self.assertEqual(error.line, 4)

    def test_function_cannot_see_global_variable(self):
        error = error_for("let g = 1\nfunction F():\n    give g\nshow F()")
        self.assertEqual(error.line, 3)
        self.assertIn("inside the function", error.message)
        self.assertIn("function F(g)", error.message)

    def test_same_name_inside_and_outside_is_fine(self):
        check(parse_source(
            "let x = 1\nfunction F():\n    let x = 2\n    give x\nshow F()"))

    def test_let_cannot_redeclare_parameter(self):
        error = error_for("function F(a):\n    let a = 1")
        self.assertEqual(error.line, 2)
        self.assertIn("already declared on line 1", error.message)

    def test_duplicate_parameter(self):
        error = error_for("function F(a, a):\n    show a")
        self.assertEqual(error.line, 1)
        self.assertIn("already declared", error.message)

    def test_duplicate_local_variable(self):
        error = error_for("function F():\n    let a = 1\n    let a = 2")
        self.assertEqual(error.line, 3)

    def test_duplicate_function(self):
        error = error_for(ADD + ADD)
        self.assertEqual(error.line, 3)
        self.assertIn("already defined on line 1", error.message)

    def test_function_name_clashes_with_variable(self):
        error = error_for(ADD + "let Add = 1")
        self.assertEqual(error.line, 3)
        self.assertIn("name of a function", error.message)

    def test_parameter_named_like_function(self):
        error = error_for(ADD + "function G(Add):\n    show Add")
        self.assertEqual(error.line, 3)

    def test_unknown_function(self):
        error = error_for("show Nope(1)")
        self.assertEqual(
            str(error),
            'Error on line 1: I don\'t know a function called "Nope". '
            "Did you forget to write: function Nope(...):")

    def test_calling_a_variable(self):
        error = error_for("let x = 1\nshow x(2)")
        self.assertEqual(error.line, 2)
        self.assertIn("not a function", error.message)

    def test_using_function_name_as_value(self):
        error = error_for(ADD + "show Add")
        self.assertEqual(error.line, 3)
        self.assertIn("is a function", error.message)

    def test_too_few_arguments(self):
        error = error_for(ADD + "show Add(1)")
        self.assertEqual(error.line, 3)
        self.assertIn("needs 2 inputs (a, b), but you gave 1", error.message)

    def test_too_many_arguments(self):
        error = error_for("function One(a):\n    give a\nOne(1, 2)")
        self.assertIn("needs 1 input (a), but you gave 2", error.message)

    def test_arguments_are_checked(self):
        error = error_for(ADD + "show Add(1, nope)")
        self.assertIn('"nope"', error.message)

    def test_call_before_definition_at_top_level(self):
        error = error_for("show Add(1, 2)\n" + ADD)
        self.assertEqual(error.line, 1)
        self.assertIn("before it is written", error.message)

    def test_functions_may_call_each_other_and_themselves(self):
        check(parse_source(
            "function A(n):\n    if n < 1:\n        give 0\n"
            "    else:\n        give B(n - 1)\n"
            "function B(n):\n    give A(n) + 1\n"
            "show A(3)"))

    def test_function_without_give_used_as_value(self):
        error = error_for("function Hi():\n    show 1\nlet x = Hi()")
        self.assertEqual(error.line, 3)
        self.assertIn("never gives anything back", error.message)

    def test_function_without_give_as_statement(self):
        check(parse_source("function Hi():\n    show 1\nHi()"))

    def test_give_not_on_every_path(self):
        error = error_for("function F(a):\n    if a > 1:\n        give 1\n")
        self.assertEqual(error.line, 1)
        self.assertIn("not in all of them", error.message)

    def test_give_after_if_is_fine(self):
        check(parse_source(
            "function F(a):\n    if a > 1:\n        give 1\n    give 2"))

    def test_if_else_where_every_branch_gives_is_fine(self):
        check(parse_source(
            "function F(a):\n    if a > 1:\n        give 1\n"
            "    else:\n        give 2"))

    def test_if_else_with_one_branch_missing_give(self):
        error = error_for(
            "function F(a):\n    if a > 1:\n        give 1\n"
            "    else:\n        show 2")
        self.assertEqual(error.line, 1)

    def test_types_still_checked_inside_functions(self):
        error = error_for('function F():\n    give "a" + 1')
        self.assertEqual(error.line, 2)

    def test_unknown_inputs_are_accepted(self):
        check(parse_source(
            'function F(a, b):\n    give a + b * 2 - -a\nshow F("x", 1)'))

    def test_unknown_with_text_cannot_multiply(self):
        error = error_for('function F(a):\n    give a * "x"')
        self.assertEqual(error.line, 2)

    def test_call_result_in_arithmetic(self):
        check(parse_source(ADD + "show Add(1, 2) * 2 + 1"))

class ForLoopTests(unittest.TestCase):
    def test_valid_loops(self):
        check(parse_source(
            'let word = "hi"\nfor c in word:\n    show c\n'
            'for d in "x" + "y":\n    let up = d + "!"\n    show up'))

    def test_loop_variable_is_text(self):
        check(parse_source('for c in "hi":\n    show c + "!"'))
        error = error_for('for c in "hi":\n    show c + 1')
        self.assertEqual(error.line, 2)
        self.assertIn("mix text and a number", error.message)

    def test_number_literal_is_an_error(self):
        error = error_for("for i in 5:\n    show i")
        self.assertEqual(error.line, 1)
        self.assertEqual(error.message, "You can only go through text with "
                                        "for, but 5 is a number.")

    def test_number_variable_is_an_error(self):
        error = error_for("let n = 3\nfor i in n:\n    show i")
        self.assertEqual(error.line, 2)
        self.assertIn('"n" is a number', error.message)

    def test_number_expression_is_an_error(self):
        error = error_for("for i in 2 * 3:\n    show i")
        self.assertIn("this value is a number", error.message)

    def test_unknown_kind_is_accepted(self):
        check(parse_source(
            'function F(t):\n    for c in t:\n        show c\nF("hi")\n'
            'function G():\n    give "ab"\nfor c in G():\n    show c'))

    def test_undeclared_iterable(self):
        error = error_for("for c in word:\n    show c")
        self.assertEqual(error.line, 1)
        self.assertIn('"word"', error.message)

    def test_loop_variable_disappears_after_loop(self):
        error = error_for('for c in "hi":\n    show c\nshow c')
        self.assertEqual(error.line, 3)
        self.assertIn('"c"', error.message)

    def test_name_can_be_reused_after_loop(self):
        check(parse_source('for c in "hi":\n    show c\nlet c = 1\nshow c'))
        check(parse_source('for c in "a":\n    show c\nfor c in "b":\n'
                           '    show c'))

    def test_variable_made_in_loop_disappears(self):
        error = error_for('for c in "hi":\n    let t = c\nshow t')
        self.assertEqual(error.line, 3)

    def test_loop_variable_cannot_shadow_visible_name(self):
        error = error_for('let c = 1\nfor c in "hi":\n    show c')
        self.assertEqual(error.line, 2)
        self.assertIn("already declared on line 1", error.message)

    def test_loop_variable_cannot_shadow_function_input(self):
        error = error_for('function F(c):\n    for c in "hi":\n        show c')
        self.assertEqual(error.line, 2)
        self.assertIn("already declared", error.message)

    def test_nested_loops_cannot_reuse_the_name(self):
        error = error_for(
            'for c in "ab":\n    for c in "xy":\n        show c')
        self.assertEqual(error.line, 2)

    def test_let_in_loop_cannot_reuse_loop_variable(self):
        error = error_for('for c in "ab":\n    let c = "x"')
        self.assertEqual(error.line, 2)

    def test_loop_variable_cannot_be_function_name(self):
        error = error_for(
            'function F():\n    give 1\nfor F in "ab":\n    show F')
        self.assertEqual(error.line, 3)
        self.assertIn("name of a function", error.message)

    def test_loop_can_see_outer_variables(self):
        check(parse_source('let a = 1\nfor c in "ab":\n    show a + 1'))

    def test_function_loop_cannot_see_global(self):
        error = error_for(
            'let g = "x"\nfunction F():\n    for c in g:\n        show c')
        self.assertEqual(error.line, 3)
        self.assertIn("inside the function", error.message)

    def test_loops_inside_if_and_if_inside_loops(self):
        check(parse_source(
            'let n = 1\nif n == 1:\n    for c in "ab":\n'
            '        if c == "a":\n            show c\n'
            '        else:\n            show 0'))

    def test_error_inside_loop_body_keeps_its_line(self):
        error = error_for('for c in "ab":\n    show z')
        self.assertEqual(error.line, 2)

    def test_give_inside_loop_then_give_after_is_fine(self):
        check(parse_source(
            'function F(t):\n    for c in t:\n        give c\n'
            '    give "none"\nshow F("ab")'))

    def test_give_only_inside_loop_is_not_on_every_path(self):
        error = error_for(
            'function F(t):\n    for c in t:\n        give c\nshow F("a")')
        self.assertEqual(error.line, 1)
        self.assertIn("not in all", error.message)

    def test_if_else_with_loop_branch_is_not_on_every_path(self):
        error = error_for(
            'function F(t):\n    if t == "a":\n        for c in t:\n'
            '            give c\n    else:\n        give "b"')
        self.assertIn("not in all", error.message)

    def test_loop_inside_function_without_give_is_a_statement_only(self):
        check(parse_source(
            'function F(t):\n    for c in t:\n        show c\nF("hi")'))
        error = error_for(
            'function F(t):\n    for c in t:\n        show c\n'
            'show F("hi")')
        self.assertIn("never gives anything back", error.message)

    def test_give_inside_loop_makes_function_usable_as_value(self):
        check(parse_source(
            'function F(t):\n    for c in t:\n        give c\n'
            '    give ""\nshow F("hi")'))


if __name__ == "__main__":
    unittest.main()
