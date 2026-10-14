"""Tests for the list actions a.remove(value) and a.pop(index)."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from ast_nodes import (CallStatement, Let, MethodCall, MethodStatement, Name,
                       Number, Text)
from checker import check
from errors import ScriptyError
from generator import generate
from lexer import DOT, NAME, NUMBER, tokenize
from parser import parse
from runner import run_python

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PETS = ('let pets = ["Dog", "Cat", "Dog", "Bird"]\n'
        'pets.remove("Dog")\n'
        "show pets\n"
        'pets.remove("Fish")\n'
        'show "still running"\n'
        "pets.pop(1)\n"
        "show pets\n")


def parse_source(source):
    return parse(tokenize(source))


def run_source(source):
    """Run in-process. Returns (stdout, stderr) text."""
    python, line_map = generate(check(parse_source(source)))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        run_python(python, line_map)
    return out.getvalue(), err.getvalue()


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
    def test_dot_token(self):
        kinds = [t.kind for t in tokenize("a.pop(1)")]
        self.assertEqual(kinds[:3], [NAME, DOT, NAME])

    def test_decimal_numbers_are_still_one_number(self):
        tokens = tokenize("let x = 1.5")
        self.assertEqual(tokens[3].kind, NUMBER)
        self.assertEqual(tokens[3].value, 1.5)
        self.assertNotIn(DOT, [t.kind for t in tokens])

    def test_leading_dot_is_a_dot_token(self):
        self.assertEqual(tokenize(".5")[0].kind, DOT)


class ParserTests(unittest.TestCase):
    def test_remove_statement(self):
        statement = parse_source('a.remove("Dog")').statements[0]
        self.assertEqual(statement, MethodStatement(
            MethodCall(Name("a", 1), "remove", [Text("Dog", 1)], 1), 1))

    def test_pop_statement(self):
        statement = parse_source("a.pop(3)").statements[0]
        self.assertEqual(statement.call.method, "pop")
        self.assertEqual(statement.call.args, [Number(3, 1)])

    def test_sort_still_parses_as_a_call(self):
        self.assertIsInstance(parse_source("sort(a)").statements[0],
                              CallStatement)

    def test_as_a_value(self):
        value = parse_source("let x = a.pop(1)").statements[0].value
        self.assertIsInstance(value, MethodCall)

    def test_comment_after(self):
        self.assertEqual(len(parse_source("a.pop(1) // bye").statements), 1)

    def test_decimal_still_parses(self):
        self.assertEqual(parse_source("let b = 3.5").statements,
                         [Let("b", Number(3.5, 1), 1)])

    def test_unknown_method_name_now_parses(self):
        # Since classes, the parser accepts any action name (objects have
        # their own); the checker explains it for a list (see CheckerTests).
        statement = parse_source("a.add(1)").statements[0]
        self.assertEqual(statement.call.method, "add")

    def test_missing_method_name(self):
        self.assertIn("must be followed", error_in("parse", "a.").message)

    def test_missing_parentheses(self):
        self.assertIn("needs parentheses", error_in("parse", "a.pop").message)

    def test_missing_closing_parenthesis(self):
        self.assertIn('missing its closing ")"',
                      error_in("parse", "a.pop(1").message)

    def test_dot_in_other_places(self):
        for source in (".5", "let x = .5", "let x = 5.", "5.pop(1)",
                       '"hi".remove("h")', "a.pop(1).pop(2)",
                       "let x = a.", "show (a).pop(1)"):
            error = error_in("parse", source)
            self.assertEqual(error.line, 1, source)

    def test_dot_message_mentions_lists(self):
        self.assertIn("right after the name of a list",
                      error_in("parse", "let x = .5").message)
        self.assertIn("right after the name of a list",
                      error_in("parse", "5.pop(1)").message)

    def test_chained_method_is_an_error(self):
        # `a.pop` is now read as a thing called "pop" (objects have such
        # things), so the parser accepts it and the checker rejects it.
        parse_source("a.pop.pop(1)")

    def test_bare_list_action_needs_parentheses(self):
        self.assertIn("needs parentheses",
                      error_in("parse", "a.pop").message)


class CheckerTests(unittest.TestCase):
    def test_valid_programs(self):
        check(parse_source("let a = [1]\na.remove(1)\na.pop(0)"))
        check(parse_source("let a = [1]\nlet b = 0\na.remove(b)\na.pop(b)"))
        check(parse_source("function F(items):\n    items.pop(0)\n"
                           '    items.remove("x")\n'))

    def test_unknown_list(self):
        error = error_in("check", 'z.remove("Dog")')
        self.assertEqual(str(error), 'Error on line 1: I don\'t know what '
                         '"z" is. Did you forget to write: let z = ...')

    def test_number_is_not_a_list(self):
        error = error_in("check", "let n = 5\nn.remove(1)")
        self.assertEqual(error.line, 2)
        self.assertEqual(error.message,
                         'remove only works on lists, but "n" is a number.')

    def test_text_is_not_a_list(self):
        error = error_in("check", 'let t = "hi"\nt.pop(0)')
        self.assertEqual(error.message,
                         'pop only works on lists, but "t" is text.')

    def test_not_a_value(self):
        error = error_in("check", "let a = [1]\nlet x = a.pop(0)")
        self.assertEqual(error.line, 2)
        self.assertIn("gives nothing back", error.message)
        self.assertIn("a.pop(3)", error.message)
        self.assertIn("gives nothing back",
                      error_in("check", "let a = [1]\nshow a.remove(1)").message)

    def test_argument_counts(self):
        for source in ("a.remove()", "a.remove(1, 2)", "a.pop()",
                       "a.pop(1, 2)"):
            error = error_in("check", "let a = [1]\n" + source)
            self.assertIn("needs exactly 1 input", error.message, source)
            self.assertEqual(error.line, 2)

    def test_pop_position_must_be_a_whole_number(self):
        decimal = error_in("check", "let a = [1]\na.pop(1.5)")
        self.assertIn("1.5 has a decimal part", decimal.message)
        text = error_in("check", 'let a = [1]\na.pop("x")')
        self.assertIn("this is text", text.message)
        listed = error_in("check", "let a = [1]\na.pop([0])")
        self.assertIn("a list", listed.message)

    def test_pop_negative_position(self):
        error = error_in("check", "let a = [1]\na.pop(-1)")
        self.assertIn("Positions start at 0 and can't be negative",
                      error.message)

    def test_argument_is_checked(self):
        self.assertIn('I don\'t know what "q"',
                      error_in("check", "let a = [1]\na.remove(q)").message)

    def test_function_cannot_see_outside_lists(self):
        source = "let a = [1]\nfunction F():\n    a.pop(0)\n"
        error = error_in("check", source)
        self.assertEqual(error.line, 3)
        self.assertIn('inside the function "F"', error.message)

    def test_builtin_and_function_names_are_not_lists(self):
        self.assertIn("built-in", error_in("check", "sort.pop(0)").message)
        self.assertIn("is a function", error_in(
            "check", "function F():\n    show 1\nF.pop(0)").message)

    def test_remove_and_pop_are_not_reserved(self):
        check(parse_source("let remove = [1]\nlet pop = 2\nremove.pop(0)"))

    def test_scope_inside_blocks(self):
        error = error_in("check", "if (1 == 1):\n    let a = [1]\na.pop(0)")
        self.assertIn('I don\'t know what "a"', error.message)


class GeneratorTests(unittest.TestCase):
    def python(self, source):
        return generate(check(parse_source(source)))

    def test_remove_and_pop(self):
        source, line_map = self.python(
            "let a = [1]\n\n\na.remove(1)\na.pop(0)\n")
        self.assertEqual(source.splitlines(), [
            "a = [1]", "remove_all(a, 1, 4)", "pop_at(a, 0)"])
        self.assertEqual(line_map, {1: 1, 2: 4, 3: 5})

    def test_text_value_and_expression(self):
        source, _ = self.python('let a = ["x"]\nlet n = 1\n'
                                'a.remove("x")\na.pop(n + 1)')
        self.assertIn("remove_all(a, 'x', 3)", source)
        self.assertIn("pop_at(a, n + 1)", source)

    def test_sort_is_unchanged(self):
        source, _ = self.python("let a = [2, 1]\nsort(a)")
        self.assertEqual(source, "a = [2, 1]\na.sort()\n")

    def test_inside_function_and_if(self):
        source, line_map = self.python(
            "function F(a):\n    if (1 == 1):\n        a.pop(0)\n")
        self.assertEqual(source.splitlines(), [
            "def F(a):", "    if 1 == 1:", "        pop_at(a, 0)"])
        self.assertEqual(line_map[3], 3)

    def test_helper_names_do_not_clash_with_user_names(self):
        source, _ = self.python("let remove_all = [1]\nlet pop_at = 0\n"
                                "remove_all.pop(pop_at)")
        self.assertIn("pop_at_scy", source)
        self.assertEqual(run_source(
            "let remove_all = [1, 2]\nlet pop_at = 0\n"
            "remove_all.pop(pop_at)\nshow remove_all"), ("[2]\n", ""))


class RunTests(unittest.TestCase):
    def test_remove_every_match(self):
        out, err = run_source('let a = ["Dog", "Cat", "Dog"]\n'
                              'a.remove("Dog")\nshow a')
        self.assertEqual((out, err), ('["Cat"]\n', ""))

    def test_remove_can_empty_the_list(self):
        self.assertEqual(run_source("let a = [1, 1]\na.remove(1)\nshow a"),
                         ("[]\n", ""))

    def test_remove_with_a_variable_and_a_calculation(self):
        out, _ = run_source("let a = [1, 2, 3, 4]\nlet n = 2\n"
                            "a.remove(n)\na.remove(1 + 2)\nshow a")
        self.assertEqual(out, "[1, 4]\n")

    def test_remove_nothing_warns_and_continues(self):
        out, err = run_source('let a = ["Cat"]\na.remove("Dog")\nshow a')
        self.assertEqual(out, '["Cat"]\n')
        self.assertEqual(err, 'Warning on line 2: "Dog" is not in the list, '
                              "so nothing was removed.\n")

    def test_warning_shows_numbers_without_quotes(self):
        _, err = run_source("let a = [1]\na.remove(5)")
        self.assertIn("Warning on line 2: 5 is not in the list", err)

    def test_text_never_matches_number(self):
        out, err = run_source('let a = [1, 2]\na.remove("1")\nshow a')
        self.assertEqual(out, "[1, 2]\n")
        self.assertIn('"1" is not in the list', err)

    def test_warning_on_empty_list(self):
        _, err = run_source("let a = []\na.remove(1)")
        self.assertIn("Warning on line 2", err)

    def test_warning_line_inside_function_and_loop(self):
        source = ("function F(items):\n"
                  "\n"
                  "    for x in [1, 2]:\n"
                  "        items.remove(9)\n"
                  "F([0])\n")
        _, err = run_source(source)
        self.assertEqual(err.count("Warning on line 4:"), 2)

    def test_one_warning_per_missed_remove(self):
        _, err = run_source("let a = [1]\na.remove(2)\na.remove(3)")
        self.assertEqual(len(err.splitlines()), 2)

    def test_pop_in_the_middle(self):
        out, _ = run_source("let a = [10, 20, 30, 40]\na.pop(1)\nshow a")
        self.assertEqual(out, "[10, 30, 40]\n")

    def test_pop_first_and_last(self):
        out, _ = run_source("let a = [1, 2, 3]\na.pop(0)\na.pop(1)\nshow a")
        self.assertEqual(out, "[2]\n")

    def test_pop_with_a_whole_decimal_works(self):
        out, _ = run_source("let a = [1, 2, 3]\na.pop(4 / 2)\nshow a")
        self.assertEqual(out, "[1, 2]\n")

    def test_pop_too_big(self):
        error = error_in("run", "let a = [1, 2, 3]\n\na.pop(3)")
        self.assertEqual(str(error), "Error on line 3: The list has 3 items "
                         "(positions 0 to 2), so there is no item at "
                         "position 3.")

    def test_pop_one_item_list(self):
        error = error_in("run", "let a = [1]\na.pop(1)")
        self.assertIn("The list has 1 item (only position 0)", error.message)

    def test_pop_empty_list(self):
        error = error_in("run", "let a = []\na.pop(0)")
        self.assertEqual(error.message, "The list is empty, so there is no "
                         "item at position 0.")

    def test_pop_negative_worked_out_at_run_time(self):
        error = error_in("run", "let a = [1, 2]\nlet n = 0 - 1\na.pop(n)")
        self.assertEqual(error.line, 3)
        self.assertIn("can't be negative", error.message)

    def test_pop_decimal_worked_out_at_run_time(self):
        error = error_in("run", "let a = [1, 2]\nlet n = 3 / 2\na.pop(n)")
        self.assertIn("1.5 has a decimal part", error.message)

    def test_unknown_kinds_are_checked_at_run_time(self):
        source = "function F(x, i):\n    x.pop(i)\n"
        self.assertIn("pop only works on lists, but this value is a number",
                      error_in("run", source + "F(5, 0)").message)
        self.assertIn("pop only works on lists, but this value is text",
                      error_in("run", source + 'F("hi", 0)').message)
        self.assertIn("remove only works on lists",
                      error_in("run", "function F(x):\n    x.remove(1)\n"
                               "F(5)").message)
        self.assertIn("whole number, but this is text",
                      error_in("run", source + 'F([1], "a")').message)

    def test_lists_are_shared_like_other_changes(self):
        out, _ = run_source("function Drop(items):\n    items.pop(0)\n"
                            "let a = [1, 2]\nDrop(a)\nshow a")
        self.assertEqual(out, "[2]\n")
        out, _ = run_source("let a = [1, 2]\nlet b = a\na.remove(1)\nshow b")
        self.assertEqual(out, "[2]\n")

    def test_inside_if_and_for(self):
        source = ("let a = [1, 2, 3, 4]\n"
                  "for n in [1, 2]:\n"
                  "    if (n == 2):\n"
                  "        a.remove(n)\n"
                  "    else:\n"
                  "        a.pop(0)\n"
                  "show a")
        self.assertEqual(run_source(source)[0], "[3, 4]\n")

    def test_todo_style_program(self):
        source = ("let a = [0, 1, 3]\nshow max(a)\na = [0, 4, 2, 6, 3, 4]\n"
                  "sort(a)\na.remove(4)\na.pop(0)\nshow a\nshow len(a)\n")
        self.assertEqual(run_source(source)[0], "3\n[2, 3, 6]\n3\n")


class EndToEndTests(unittest.TestCase):
    def scripty(self, *args):
        return subprocess.run(
            [sys.executable, "scripty.py", *args], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8")

    def scripty_source(self, command, source):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.scy")
            with open(path, "w", encoding="utf-8") as file:
                file.write(source)
            return self.scripty(command, path)

    def test_pets_program(self):
        result = self.scripty_source("run", PETS)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), [
            '["Cat", "Bird"]', "still running", '["Cat"]'])
        self.assertEqual(result.stderr, 'Warning on line 4: "Fish" is not in '
                         "the list, so nothing was removed.\n")

    def test_build_output(self):
        result = self.scripty_source("build", PETS)
        self.assertEqual(result.stdout.splitlines(), [
            "pets = ['Dog', 'Cat', 'Dog', 'Bird']",
            "remove_all(pets, 'Dog', 2)", "print(pets)",
            "remove_all(pets, 'Fish', 4)", "print('still running')",
            "pop_at(pets, 1)", "print(pets)"])

    def test_runtime_error_is_friendly(self):
        result = self.scripty_source("run", "let a = [1, 2]\nshow a\na.pop(5)")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "[1, 2]\n")
        self.assertEqual(result.stderr, "Error on line 3: The list has 2 "
                         "items (positions 0 to 1), so there is no item at "
                         "position 5.\n")

    def test_friendly_errors_have_no_traceback(self):
        for source, expected in (
                ("let n = 5\nn.remove(1)", "Error on line 2: remove only "
                 'works on lists, but "n" is a number.'),
                ("let a = [1]\na.add(1)", "Error on line 2: I don't know "
                 'what "add" does to a list. The list actions are: remove, '
                 "pop."),
                ("let a = [1]\nlet x = a.pop(0)", "Error on line 2: pop "
                 "changes the list itself and gives nothing back"),
                ("let a = [1]\na.pop(-1)", "Error on line 2: Positions "
                 "start at 0"),
                ("let a = [1]\na.pop(1.5)", "Error on line 2: A position "
                 "must be a whole number"),
                ("let x = .5", 'Error on line 1: A "." only works')):
            result = self.scripty_source("run", source)
            self.assertEqual(result.returncode, 1, source)
            self.assertEqual(result.stdout, "")
            self.assertIn(expected, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_example_file(self):
        result = self.scripty("run", os.path.join("examples",
                                                  "list_methods.scy"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            '["Cat", "Bird"]', "still running", '["Cat"]', "[3]"])
        self.assertEqual(result.stderr, 'Warning on line 9: "Fish" is not in '
                         "the list, so nothing was removed.\n")


if __name__ == "__main__":
    unittest.main()
