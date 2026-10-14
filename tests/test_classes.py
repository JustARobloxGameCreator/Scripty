"""Tests for classes: class Dog:, objects, attributes, actions, inheritance."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from ast_nodes import (Assign, AssignAttribute, Attribute, ClassDef, Function,
                       MethodCall, MethodStatement, Name, Number, Show, Text)
from checker import check
from errors import ScriptyError
from generator import generate
from lexer import KEYWORD, NAME, tokenize
from parser import parse
from runner import run_python

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The example from the to-do list, exactly.
DOG_PROGRAM = '''class Dog:
    function init(self, name, age):
        self.name = name
        self.age = age
    function speak(self):
        give self.name + " says woof"
    function birthday(self):
        self.age = self.age + 1

class Puppy(Dog):
    function speak(self):
        give self.name + " says yip"

let d = Dog("Rex", 3)
show d.speak()
d.birthday()
show d.age
d.name = "Max"
let p = Puppy("Bit", 1)
show p.speak()
'''
DOG_OUTPUT = "Rex says woof\n4\nBit says yip\n"

SMALL = "class Dog:\n    function speak(self):\n        give 1\n"


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
    def test_class_is_a_keyword(self):
        token = tokenize("class Dog:")[0]
        self.assertEqual((token.kind, token.value), (KEYWORD, "class"))

    def test_self_and_super_are_plain_names(self):
        kinds = [t.kind for t in tokenize("self.x = super")]
        self.assertEqual(kinds[0], NAME)
        self.assertEqual(kinds[-2], NAME)


class ParserTests(unittest.TestCase):
    def test_class_with_methods(self):
        program = parse_source(SMALL)
        self.assertEqual(len(program.statements), 1)
        cls = program.statements[0]
        self.assertIsInstance(cls, ClassDef)
        self.assertEqual((cls.name, cls.parent, cls.line), ("Dog", None, 1))
        self.assertEqual([m.name for m in cls.methods], ["speak"])
        self.assertIsInstance(cls.methods[0], Function)
        self.assertEqual(cls.methods[0].params, ["self"])
        self.assertEqual(cls.methods[0].line, 2)

    def test_class_with_parent(self):
        cls = parse_source("class Puppy(Dog):\n    function f(self):\n"
                           "        show 1\n").statements[0]
        self.assertEqual((cls.name, cls.parent), ("Puppy", "Dog"))

    def test_whole_example_parses(self):
        program = parse_source(DOG_PROGRAM)
        self.assertEqual([type(s).__name__ for s in program.statements],
                         ["ClassDef", "ClassDef", "Let", "Show",
                          "MethodStatement", "Show", "AssignAttribute",
                          "Let", "Show"])

    def test_statements_after_the_class_are_outside_it(self):
        program = parse_source(SMALL + "show 5\n")
        self.assertEqual(len(program.statements), 2)
        self.assertIsInstance(program.statements[1], Show)

    def test_attribute_read(self):
        value = parse_source("show d.name").statements[0].value
        self.assertEqual(value, Attribute(Name("d", 1), "name", 1))

    def test_attribute_chain(self):
        value = parse_source("show self.pet.name").statements[0].value
        self.assertEqual(value, Attribute(
            Attribute(Name("self", 1), "pet", 1), "name", 1))

    def test_attribute_assignment(self):
        statement = parse_source('d.name = "Max"').statements[0]
        self.assertEqual(statement, AssignAttribute(
            Name("d", 1), "name", Text("Max", 1), 1))

    def test_assignment_to_a_chain(self):
        statement = parse_source("self.pet.age = 1").statements[0]
        self.assertEqual(statement.target,
                         Attribute(Name("self", 1), "pet", 1))
        self.assertEqual(statement.name, "age")

    def test_method_call_as_value(self):
        value = parse_source("let s = d.speak(1, 2)").statements[0].value
        self.assertEqual(value, MethodCall(
            Name("d", 1), "speak", [Number(1, 1), Number(2, 1)], 1))

    def test_method_call_as_statement(self):
        statement = parse_source("d.birthday()").statements[0]
        self.assertIsInstance(statement, MethodStatement)
        self.assertEqual(statement.call.method, "birthday")

    def test_method_call_on_a_chain(self):
        statement = parse_source("self.pet.speak()").statements[0]
        self.assertEqual(statement.call.target,
                         Attribute(Name("self", 1), "pet", 1))

    def test_super_call(self):
        statement = parse_source("super.init(name, 1)").statements[0]
        self.assertEqual(statement.call.target, Name("super", 1))
        self.assertEqual(statement.call.method, "init")

    def test_keywords_and_class_work_after_a_dot(self):
        statement = parse_source("self.class = 1").statements[0]
        self.assertEqual(statement.name, "class")
        self.assertEqual(parse_source("show d.show").statements[0].value.name,
                         "show")

    def test_class_name_is_not_a_variable_name(self):
        # class is a reserved word now, so it can't name a variable
        error = error_in("parse", "let class = 5")
        self.assertEqual(error.line, 1)
        self.assertIn("is a Scripty keyword", error.message)

    def test_assignment_in_an_expression_context_is_still_a_comparison_error(
            self):
        error = error_in("parse", "if d.age = 5:\n    show 1")
        self.assertIn("==", error.message)

    # -- errors ----------------------------------------------------------

    def test_class_needs_a_name(self):
        error = error_in("parse", "class:\n    function f(self):\n"
                         "        show 1")
        self.assertIn("forgot its name", error.message)
        self.assertEqual(error.line, 1)

    def test_class_name_cannot_be_a_keyword(self):
        self.assertIn("keyword", error_in(
            "parse", "class show:\n    function f(self):\n"
            "        show 1").message)

    def test_class_needs_a_colon(self):
        error = error_in("parse", "class Dog\n    function f(self):\n"
                         "        show 1")
        self.assertIn('missing a ":"', error.message)

    def test_class_needs_a_body(self):
        self.assertIn("nothing inside it", error_in("parse",
                                                     "class Dog:\nshow 1").message)

    def test_class_with_two_parents(self):
        error = error_in("parse", "class A(B, C):\n    function f(self):\n"
                         "        show 1")
        self.assertIn("only one parent", error.message)

    def test_class_with_empty_parent(self):
        self.assertIn("name of the parent class", error_in(
            "parse", "class A():\n    function f(self):\n"
            "        show 1").message)

    def test_class_parent_not_closed(self):
        self.assertIn("closing", error_in(
            "parse", "class A(B:\n    function f(self):\n"
            "        show 1").message)

    def test_only_functions_inside_a_class(self):
        error = error_in("parse", "class Dog:\n    let x = 5\n")
        self.assertEqual(error.line, 2)
        self.assertIn("only hold functions", error.message)
        self.assertIn("self.name = ...", error.message)

    def test_class_inside_a_class(self):
        error = error_in("parse", "class A:\n    class B:\n"
                         "        function f(self):\n            show 1\n")
        self.assertEqual(error.line, 2)
        self.assertIn("inside another class", error.message)

    def test_class_inside_function_if_and_for(self):
        body = "    class A:\n        function f(self):\n            show 1\n"
        for header in ("function F():\n", "if (1 == 1):\n",
                       'for c in "ab":\n'):
            error = error_in("parse", header + body)
            self.assertEqual(error.line, 2, header)
            self.assertIn("A class can't be written inside", error.message)

    def test_function_inside_a_method(self):
        error = error_in("parse", "class A:\n    function f(self):\n"
                         "        function g():\n            show 1\n")
        self.assertEqual(error.line, 3)
        self.assertIn("inside another function", error.message)

    def test_give_works_inside_a_method(self):
        parse_source(SMALL)

    def test_give_outside_function_is_still_an_error(self):
        self.assertIn("give only works inside a function",
                      error_in("parse", "give 1").message)

    def test_bare_attribute_line(self):
        error = error_in("parse", "d.name")
        self.assertIn("can't be only d.name", error.message)

    def test_attribute_without_a_value(self):
        self.assertIn("no new value", error_in("parse", "d.name =").message)

    def test_cannot_assign_to_a_call(self):
        self.assertIn("action call", error_in("parse", "d.speak() = 5").message)

    def test_nothing_after_a_call(self):
        error = error_in("parse", "show d.speak().name")
        self.assertIn('A "." only works', error.message)

    def test_dot_without_a_name(self):
        self.assertIn("must be followed", error_in("parse", "d.").message)

    def test_chain_missing_closing_parenthesis(self):
        self.assertIn('missing its closing ")"',
                      error_in("parse", "d.speak(1").message)

    def test_old_assignment_still_works(self):
        self.assertEqual(parse_source("x = 5").statements,
                         [Assign("x", Number(5, 1), 1)])


if __name__ == "__main__":
    unittest.main()
