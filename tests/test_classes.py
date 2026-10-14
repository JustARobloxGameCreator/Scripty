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
        self.assertIn("come right after a closing", error.message)

    def test_dot_without_a_name(self):
        self.assertIn("must be followed", error_in("parse", "d.").message)

    def test_chain_missing_closing_parenthesis(self):
        self.assertIn('missing its closing ")"',
                      error_in("parse", "d.speak(1").message)

    def test_old_assignment_still_works(self):
        self.assertEqual(parse_source("x = 5").statements,
                         [Assign("x", Number(5, 1), 1)])


BARK = '''class Animal:
    function init(self, name):
        self.name = name
    function speak(self):
        give self.name + " makes a sound"
    function rename(self, name):
        self.name = name
class Dog(Animal):
    function speak(self):
        give self.name + " says woof"
'''


class CheckerTests(unittest.TestCase):
    def test_example_program_is_fine(self):
        check(parse_source(DOG_PROGRAM))

    def test_missing_self(self):
        error = error_in("check", "class A:\n    function f(x):\n"
                         "        give 1")
        self.assertEqual(error.line, 2)
        self.assertIn("must be self", error.message)
        self.assertIn("the object the function works on", error.message)
        self.assertIn("function f(self, x):", error.message)

    def test_no_inputs_at_all_in_an_action(self):
        error = error_in("check", "class A:\n    function f():\n        give 1")
        self.assertIn("must be self", error.message)
        self.assertIn("function f(self):", error.message)

    def test_self_second_is_not_enough(self):
        self.assertIn("must be self", error_in(
            "check", "class A:\n    function f(a, self):\n"
            "        give 1").message)

    def test_unknown_action_on_a_known_class(self):
        error = error_in("check", BARK + 'let d = Dog("a")\nshow d.fly()')
        self.assertEqual(error.line, 12)
        self.assertEqual(
            error.message, 'A Dog object has no action called "fly". Its '
            "actions are: speak, rename.")

    def test_action_list_includes_parent_actions(self):
        error = error_in("check", BARK + 'let d = Dog("a")\nd.fly()')
        self.assertIn("rename", error.message)
        self.assertNotIn("init", error.message)

    def test_unknown_attribute_with_a_hint(self):
        error = error_in("check", BARK + 'let d = Dog("a")\nshow d.colour')
        self.assertEqual(error.line, 12)
        self.assertIn('This Dog has nothing called "colour"', error.message)
        self.assertIn("self.colour = ...", error.message)
        self.assertIn("name", error.message)

    def test_unknown_attribute_on_self(self):
        error = error_in("check", "class A:\n    function f(self):\n"
                         "        give self.nope")
        self.assertEqual(error.line, 3)
        self.assertIn('"nope"', error.message)

    def test_attribute_set_in_another_action_is_known(self):
        check(parse_source(
            "class A:\n    function f(self):\n        give self.q\n"
            "    function g(self):\n        self.q = 1\n"))

    def test_attribute_set_outside_the_class_is_known(self):
        check(parse_source(
            "class A:\n    function f(self):\n        give 1\n"
            "let a = A()\na.q = 5\nshow a.q"))

    def test_attribute_set_by_a_child_is_known(self):
        check(parse_source(
            "class A:\n    function f(self):\n        give self.q\n"
            "class B(A):\n    function g(self):\n        self.q = 1\n"))

    def test_attribute_names_are_not_reserved_words(self):
        check(parse_source('class A:\n    function f(self):\n'
                           '        self.class = 1\n        self.show = 2\n'
                           '        give self.class + self.show\n'))

    def test_reading_an_attribute_of_a_number_text_or_list(self):
        for value, word in (("5", "A number"), ('"hi"', "Text"),
                            ("[1]", "A list")):
            error = error_in("check", f"let n = {value}\nshow n.name")
            self.assertEqual(error.line, 2)
            self.assertIn(f'{word} has nothing called "name"', error.message)

    def test_assigning_an_attribute_of_a_number(self):
        error = error_in("check", "let n = 5\nn.name = 1")
        self.assertIn("can't remember things", error.message)

    def test_attribute_is_not_an_action(self):
        error = error_in("check", BARK + 'let d = Dog("a")\nshow d.speak')
        self.assertIn("is an action of Dog", error.message)
        self.assertIn("d.speak(...)", error.message)

    def test_attribute_cannot_have_an_action_name(self):
        error = error_in("check", "class A:\n    function f(self):\n"
                         "        self.f = 1")
        self.assertEqual(error.line, 3)
        self.assertIn("already an action", error.message)

    def test_double_underscore_names_are_reserved(self):
        self.assertIn("two underscores", error_in(
            "check", "class A:\n    function __f(self):\n"
            "        give 1").message)
        self.assertIn("two underscores", error_in(
            "check", "let d = 1\nd.__x = 1").message)

    # -- creating objects --------------------------------------------------

    def test_wrong_number_of_inputs_for_a_class(self):
        error = error_in("check", BARK + "let d = Dog()")
        self.assertEqual(error.line, 11)
        self.assertEqual(error.message, 'The class "Dog" needs 1 input '
                         "(name) to make an object, but you gave 0.")

    def test_inherited_init_counts(self):
        check(parse_source(BARK + 'let d = Dog("a")'))
        self.assertIn("needs 1 input", error_in(
            "check", BARK + 'let d = Dog("a", "b")').message)

    def test_class_without_init_takes_no_inputs(self):
        error = error_in("check", SMALL + "let d = Dog(1)")
        self.assertEqual(error.line, 4)
        self.assertIn("takes no inputs", error.message)
        self.assertIn("function init(self, ...)", error.message)
        check(parse_source(SMALL + "let d = Dog()"))

    def test_class_used_before_it_is_written(self):
        error = error_in("check", "let d = Dog()\n" + SMALL)
        self.assertEqual(error.line, 1)
        self.assertIn("before it is written", error.message)
        self.assertIn("line 2", error.message)

    def test_class_used_inside_a_function_defined_earlier_is_fine(self):
        check(parse_source("function Make():\n    give Dog()\n" + SMALL))

    def test_class_name_alone_is_an_error(self):
        error = error_in("check", SMALL + "show Dog")
        self.assertIn('"Dog" is a class', error.message)

    def test_unknown_parent(self):
        error = error_in("check", "class A(Nope):\n    function f(self):\n"
                         "        give 1")
        self.assertEqual(error.line, 1)
        self.assertIn('I don\'t know a class called "Nope"', error.message)

    def test_parent_must_not_be_a_function(self):
        error = error_in("check", "function F():\n    give 1\n"
                         "class A(F):\n    function f(self):\n        give 1")
        self.assertEqual(error.line, 3)
        self.assertIn('"F" is a function, not a class', error.message)

    def test_parent_must_be_written_above(self):
        error = error_in("check", "class B(A):\n    function g(self):\n"
                         "        give 1\n" + SMALL.replace("Dog", "A"))
        self.assertEqual(error.line, 1)
        self.assertIn("is written below", error.message)
        self.assertIn("line 4", error.message)

    def test_class_cannot_be_its_own_parent(self):
        error = error_in("check", "class A(A):\n    function f(self):\n"
                         "        give 1")
        self.assertIn("written below", error.message)

    def test_duplicate_class(self):
        error = error_in("check", SMALL + SMALL)
        self.assertEqual(error.line, 4)
        self.assertIn('The class "Dog" is already defined on line 1',
                      error.message)

    def test_class_and_function_share_one_name_list(self):
        error = error_in("check", SMALL + "function Dog():\n    give 1")
        self.assertEqual(error.line, 4)
        self.assertIn("already the name of a class", error.message)
        error = error_in("check", "function Dog():\n    give 1\n" + SMALL)
        self.assertEqual(error.line, 3)
        self.assertIn("already the name of a function", error.message)

    def test_class_and_variable_share_one_name_list(self):
        for source in (SMALL + "let Dog = 1", "let Dog = 1\n" + SMALL):
            error = error_in("check", source)
            self.assertIn("already the name of a class", error.message)

    def test_class_cannot_be_named_like_a_builtin_or_self(self):
        self.assertIn("built-in", error_in(
            "check", "class max:\n    function f(self):\n"
            "        give 1").message)
        self.assertIn("reserved for classes", error_in(
            "check", "class self:\n    function f(self):\n"
            "        give 1").message)

    # -- self and super ----------------------------------------------------

    def test_self_outside_an_action(self):
        error = error_in("check", "show self")
        self.assertIn('"self" only works inside a function written in a '
                      "class", error.message)
        self.assertIn('"self"', error_in(
            "check", "function F():\n    show self").message)
        self.assertIn('"self"', error_in("check", "self.x = 1").message)

    def test_self_and_super_cannot_be_names(self):
        for source in ("let self = 1", "let super = 1",
                       "function F(self):\n    give 1",
                       'for self in "ab":\n    show 1',
                       "function self():\n    give 1",
                       "class A:\n    function f(self, super):\n"
                       "        give 1"):
            self.assertIn("reserved for classes",
                          error_in("check", source).message, source)

    def test_self_cannot_be_reassigned(self):
        error = error_in("check", "class A:\n    function f(self):\n"
                         "        self = 1")
        self.assertEqual(error.line, 3)
        self.assertIn("can't be given a new value", error.message)

    def test_super_needs_a_parent(self):
        for source in ("super.init()",
                       "class A:\n    function f(self):\n"
                       "        super.init()"):
            error = error_in("check", source)
            self.assertIn("a class that has a parent", error.message)

    def test_super_alone_is_an_error(self):
        error = error_in("check", BARK.replace(
            'give self.name + " says woof"', "give super"))
        self.assertIn("super.init", error.message)

    def test_super_init_checks_the_inputs_of_the_parent(self):
        source = BARK + ("class Cat(Animal):\n    function init(self):\n"
                         "        super.init()\n")
        error = error_in("check", source)
        self.assertEqual(error.line, 13)
        self.assertIn('needs 1 input (name), but you gave 0', error.message)

    def test_super_action_that_does_not_exist(self):
        source = BARK + ("class Cat(Animal):\n    function f(self):\n"
                         "        super.fly()\n")
        self.assertIn("has no action called", error_in("check", source).message)

    def test_super_init_without_a_parent_init_takes_nothing(self):
        source = SMALL + ("class Puppy(Dog):\n    function init(self):\n"
                          "        super.init()\n")
        check(parse_source(source))
        error = error_in("check", source.replace("super.init()",
                                                  "super.init(1)"))
        self.assertIn("no init function", error.message)

    def test_init_cannot_be_called_on_an_object(self):
        error = error_in("check", BARK + 'let d = Dog("a")\nd.init("b")')
        self.assertIn("init runs by itself", error.message)
        self.assertIn("super.init(...)", error.message)

    # -- actions -----------------------------------------------------------

    def test_wrong_number_of_inputs_for_an_action(self):
        error = error_in("check", BARK + 'let d = Dog("a")\nd.rename()')
        self.assertEqual(error.line, 12)
        self.assertEqual(error.message, 'The action "rename" of class '
                         '"Animal" needs 1 input (name), but you gave 0.')
        self.assertIn("needs 0 inputs (none)", error_in(
            "check", BARK + 'let d = Dog("a")\nd.speak(1)').message)

    def test_action_without_give_is_not_a_value(self):
        error = error_in("check", BARK + 'let d = Dog("a")\nshow d.rename("b")')
        self.assertIn("never gives anything back", error.message)

    def test_action_with_give_can_be_a_line_on_its_own(self):
        check(parse_source(BARK + 'let d = Dog("a")\nd.speak()'))

    def test_give_must_be_on_every_path(self):
        error = error_in("check", "class A:\n    function f(self):\n"
                         "        if (1 == 1):\n            give 1\n")
        self.assertEqual(error.line, 2)
        self.assertIn("in some cases but not in all", error.message)

    def test_init_cannot_give(self):
        error = error_in("check", "class A:\n    function init(self):\n"
                         "        give 1")
        self.assertIn("can't give a value back", error.message)

    def test_action_cannot_see_variables_outside(self):
        error = error_in("check", "let x = 1\nclass A:\n    function f(self):\n"
                         "        show x")
        self.assertEqual(error.line, 4)
        self.assertIn('inside the function "f"', error.message)
        self.assertIn("function f(self, x):", error.message)

    def test_action_can_call_functions_and_other_actions(self):
        check(parse_source(
            "function Twice(n):\n    give n * 2\n"
            "class A:\n    function f(self):\n        give Twice(self.g())\n"
            "    function g(self):\n        give 4\n"))

    def test_action_can_make_objects_of_any_class_written_above(self):
        check(parse_source(SMALL + "class B:\n    function f(self):\n"
                           "        give Dog()\n"))

    def test_two_actions_with_one_name(self):
        error = error_in("check", SMALL + "    function speak(self):\n"
                         "        give 2\n")
        self.assertIn('already has an action called "speak"', error.message)

    def test_a_method_name_can_equal_a_function_or_variable_name(self):
        check(parse_source("function speak():\n    give 1\n" + SMALL))

    def test_duplicate_inputs_are_an_error(self):
        self.assertIn("already declared", error_in(
            "check", "class A:\n    function f(self, a, a):\n"
            "        give 1").message)

    # -- kinds of values ---------------------------------------------------

    def test_actions_on_a_number_or_text(self):
        self.assertEqual(error_in("check", "let n = 5\nn.speak()").message,
                         "A number has no action called speak.")
        self.assertEqual(
            error_in("check", 'let t = "hi"\nshow t.speak()').message,
            "Text has no action called speak.")

    def test_unknown_action_on_a_list_still_lists_the_choices(self):
        error = error_in("check", "let a = [1]\na.add(1)")
        self.assertEqual(error.line, 2)
        self.assertIn('I don\'t know what "add" does to a list. The list '
                      "actions are: remove, pop.", error.message)

    def test_chained_list_action_is_still_an_error(self):
        error = error_in("check", "let a = [1]\na.pop.pop(1)")
        self.assertEqual(error.line, 2)
        self.assertIn("pop needs parentheses", error.message)

    def test_list_actions_with_other_kinds_keep_their_messages(self):
        self.assertEqual(error_in("check", "let n = 5\nn.pop(1)").message,
                         'pop only works on lists, but "n" is a number.')

    def test_unknown_kinds_are_accepted(self):
        check(parse_source("function F(x):\n    x.speak()\n    show x.name\n"
                           "    x.name = 1\n    show x.pop(1)\n"))

    def test_objects_reject_calculations_and_ordering(self):
        for source in ("show d + 1", "show d * d", "show -d"):
            self.assertIn("object", error_in(
                "check", SMALL + "let d = Dog()\n" + source).message, source)
        error = error_in("check", SMALL + "let d = Dog()\nif (d > d):\n"
                         "    show 1")
        self.assertEqual(error.line, 5)
        self.assertIn('"=="', error.message)

    def test_objects_can_be_compared_for_sameness(self):
        check(parse_source(SMALL + "let d = Dog()\nif (d == d):\n    show 1\n"
                           "if (d != Dog()):\n    show 2"))

    def test_for_over_an_object(self):
        error = error_in("check", SMALL + "let d = Dog()\nfor x in d:\n"
                         "    show x")
        self.assertEqual(error.line, 5)
        self.assertIn("a Dog object", error.message)

    def test_indexing_an_object(self):
        error = error_in("check", SMALL + "let d = Dog()\nshow d[0]")
        self.assertIn('"d" is a Dog object', error.message)

    def test_builtins_reject_objects(self):
        self.assertIn("a Dog object", error_in(
            "check", SMALL + "show len(Dog())").message)

    def test_reassigning_an_object(self):
        check(parse_source(BARK + 'let a = Animal("x")\na = Dog("y")'))
        check(parse_source(BARK + 'let d = Dog("x")\nd = Dog("y")'))
        error = error_in("check", BARK + 'let d = Dog("x")\nd = Animal("y")')
        self.assertIn('holds a Dog object (made on line 11)', error.message)
        self.assertIn("an Animal object", error.message)
        self.assertIn("can't be changed", error_in(
            "check", BARK + 'let d = Dog("x")\nd = 5').message)
        error = error_in("check", BARK + 'let n = 5\nn = Dog("a")')
        self.assertIn("holds a number", error.message)
        self.assertIn("changed to a Dog object", error.message)

    def test_objects_in_lists_are_fine(self):
        check(parse_source(SMALL + "let a = [Dog(), Dog()]\nshow a[0]"))

    def test_checker_records_how_to_write_each_call(self):
        program = check(parse_source(
            BARK + 'let d = Dog("a")\nd.rename("b")\nshow d.name\n'
            "let a = [1]\na.pop(0)\n"
            "function F(x):\n    x.pop(0)\n    show x.name\n"))
        statements = program.statements
        self.assertEqual(statements[3].call.target_kind, "object")
        self.assertEqual(statements[4].value.target_kind, "object")
        self.assertEqual(statements[6].call.target_kind, "list")
        self.assertEqual(statements[7].body[0].call.target_kind, "unknown")
        self.assertEqual(statements[7].body[1].value.target_kind, "unknown")


class GeneratorTests(unittest.TestCase):
    def python(self, source):
        return generate(check(parse_source(source)))

    def test_example_program(self):
        source, line_map = self.python(DOG_PROGRAM)
        self.assertEqual(source, '''class Dog:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def speak(self):
        return self.name + ' says woof'

    def birthday(self):
        self.age = self.age + 1

class Puppy(Dog):
    def speak(self):
        return self.name + ' says yip'

d = Dog('Rex', 3)
print(d.speak())
d.birthday()
print(d.age)
d.name = 'Max'
p = Puppy('Bit', 1)
print(p.speak())
''')
        # Every code line has a Scripty line; blank lines have none.
        python_lines = source.splitlines()
        for number, text in enumerate(python_lines, start=1):
            self.assertEqual(number in line_map, bool(text), (number, text))
        self.assertEqual(line_map[1], 1)   # class Dog:
        self.assertEqual(line_map[2], 2)   # def __init__
        self.assertEqual(line_map[3], 3)
        self.assertEqual(line_map[6], 5)   # def speak
        self.assertEqual(line_map[7], 6)
        self.assertEqual(line_map[12], 10)  # class Puppy(Dog):
        self.assertEqual(line_map[16], 14)  # let d = ...

    def test_super_init_and_super_action(self):
        source, _ = self.python(
            BARK + "class Cat(Animal):\n    function init(self):\n"
            '        super.init("cat")\n    function speak(self):\n'
            '        give super.speak() + "!"\n')
        self.assertIn("super().__init__('cat')", source)
        self.assertIn("return super().speak() + '!'", source)

    def test_names_that_clash_with_python_get_a_suffix(self):
        source, _ = self.python(
            "class None:\n    function def(self, lambda):\n"
            "        self.class = lambda\n        self.print = 1\n"
            "        give self.class\n"
            "let pass = None()\npass.def(5)\nshow pass.class\n")
        self.assertIn("class None_scy:", source)
        self.assertIn("def def_scy(self, lambda_scy):", source)
        self.assertIn("self.class_scy = lambda_scy", source)
        self.assertIn("self.print_scy = 1", source)
        self.assertIn("pass_scy = None_scy()", source)
        self.assertIn("pass_scy.def_scy(5)", source)
        self.assertIn("print(pass_scy.class_scy)", source)

    def test_helper_names_are_reserved(self):
        source, _ = self.python("let call_action = 1\nlet get_attr = 2")
        self.assertEqual(source, "call_action_scy = 1\nget_attr_scy = 2\n")

    def test_unknown_kinds_use_helpers(self):
        source, _ = self.python(
            "function F(x):\n    x.speak(1)\n    show x.name\n"
            "    show x.speak()\n    x.name = 5\n")
        self.assertEqual(source.splitlines(), [
            "def F(x):",
            "    call_action(x, 'speak', [1], 2)",
            "    print(get_attr(x, 'name'))",
            "    print(call_action(x, 'speak', [], 4, True))",
            "    x.name = 5"])

    def test_list_actions_are_written_as_before(self):
        source, _ = self.python(
            "let a = [1, 2]\na.remove(1)\na.pop(0)\n"
            "function F(x):\n    x.pop(0)\n    x.remove(1)\n")
        self.assertEqual(source.splitlines(), [
            "a = [1, 2]", "remove_all(a, 1, 2)", "pop_at(a, 0)",
            "def F(x):", "    pop_at(x, 0)", "    remove_all(x, 1, 6)"])

    def test_list_action_with_other_inputs_on_unknown_kind(self):
        source, _ = self.python("function F(x):\n    x.pop()\n"
                                "    let y = x.pop(1)\n")
        self.assertIn("call_action(x, 'pop', [], 2)", source)
        self.assertIn("y = call_action(x, 'pop', [1], 3, True)", source)

    def test_attribute_chain_and_assignment(self):
        source, _ = self.python(
            "class A:\n    function init(self):\n        self.pet = self\n"
            "        self.pet.pet.age = 3\n"
            "        show self.pet.age\n")
        # Things an object remembers have no known kind, so a chain through
        # them goes through the helpers.
        self.assertIn("get_attr(self.pet, 'pet').age = 3", source)
        self.assertIn("print(get_attr(self.pet, 'age'))", source)

    def test_class_without_methods_after_it_has_no_blank_at_the_end(self):
        source, _ = self.python(SMALL)
        self.assertFalse(source.endswith("\n\n"))

    def test_generated_code_is_valid_python(self):
        source, _ = self.python(DOG_PROGRAM)
        compile(source, "<test>", "exec")


class RunTests(unittest.TestCase):
    def test_the_example_program(self):
        self.assertEqual(run_source(DOG_PROGRAM), (DOG_OUTPUT, ""))

    def test_class_without_init(self):
        out, _ = run_source('class A:\n    function hi(self):\n'
                            '        give "hi"\nlet a = A()\nshow a.hi()')
        self.assertEqual(out, "hi\n")

    def test_init_runs_when_the_object_is_made(self):
        out, _ = run_source('class A:\n    function init(self):\n'
                            '        show "made"\nlet a = A()\nshow "after"')
        self.assertEqual(out, "made\nafter\n")

    def test_attributes_read_and_write(self):
        out, _ = run_source(BARK + 'let d = Dog("Rex")\nshow d.name\n'
                            'd.name = "Max"\nshow d.name\nd.rename("Bo")\n'
                            "show d.name")
        self.assertEqual(out, "Rex\nMax\nBo\n")

    def test_attribute_created_outside_the_class(self):
        out, _ = run_source(SMALL + "let d = Dog()\nd.colour = \"red\"\n"
                            "show d.colour")
        self.assertEqual(out, "red\n")

    def test_objects_have_their_own_attributes(self):
        out, _ = run_source(BARK + 'let a = Dog("A")\nlet b = Dog("B")\n'
                            'a.rename("C")\nshow a.name\nshow b.name')
        self.assertEqual(out, "C\nB\n")

    def test_inheritance_and_override(self):
        out, _ = run_source(BARK + 'let a = Animal("x")\nlet d = Dog("y")\n'
                            "show a.speak()\nshow d.speak()\n"
                            'd.rename("z")\nshow d.speak()')
        self.assertEqual(out, "x makes a sound\ny says woof\nz says woof\n")

    def test_grandchild_inherits_everything(self):
        out, _ = run_source(BARK + "class Puppy(Dog):\n    function cute(self):"
                            '\n        give self.name + " is cute"\n'
                            'let p = Puppy("Bit")\nshow p.speak()\nshow p.cute()')
        self.assertEqual(out, "Bit says woof\nBit is cute\n")

    def test_super_init_and_super_action(self):
        out, _ = run_source(
            BARK + "class Cat(Animal):\n    function init(self, lives):\n"
            '        super.init("cat")\n        self.lives = lives\n'
            '    function speak(self):\n'
            '        give super.speak() + " (" + self.name + ")"\n'
            "let c = Cat(9)\nshow c.speak()\nshow c.lives")
        self.assertEqual(out, "cat makes a sound (cat)\n9\n")

    def test_child_that_skips_super_init_gets_a_friendly_error(self):
        error = error_in("run", BARK + "class Cat(Animal):\n"
                         "    function init(self):\n        show 1\n"
                         "let c = Cat()\nshow c.name")
        self.assertEqual(error.line, 15)
        self.assertEqual(error.message, 'This Cat has nothing called "name". '
                         "Did you forget to give it one with: self.name = ...")

    def test_actions_calling_actions(self):
        out, _ = run_source(
            "class Counter:\n    function init(self):\n        self.n = 0\n"
            "    function add(self):\n        self.n = self.n + 1\n"
            "    function add_twice(self):\n        self.add()\n"
            "        self.add()\n        give self.n\n"
            "let c = Counter()\nshow c.add_twice()\nshow c.add_twice()")
        self.assertEqual(out, "2\n4\n")

    def test_actions_can_call_functions_and_make_objects(self):
        out, _ = run_source(
            "function Twice(n):\n    give n * 2\n"
            "class Box:\n    function init(self, v):\n        self.v = v\n"
            "    function doubled(self):\n        give Box(Twice(self.v))\n"
            "let b = Box(4)\nlet c = b.doubled()\nshow c.v")
        self.assertEqual(out, "8\n")

    def test_objects_inside_objects(self):
        out, _ = run_source(
            "class Node:\n    function init(self, v):\n        self.v = v\n"
            "        self.next = 0\n"
            "let a = Node(1)\nlet b = Node(2)\na.next = b\nb.v = 5\n"
            "show a.next.v\na.next.v = 7\nshow b.v")
        self.assertEqual(out, "5\n7\n")

    def test_objects_in_lists_and_functions(self):
        out, _ = run_source(
            BARK + 'let pets = [Animal("a"), Dog("b")]\n'
            "for pet in pets:\n    show pet.speak()\n"
            "function Loud(x):\n    give x.speak() + \"!\"\n"
            "show Loud(pets[1])\nshow len(pets)")
        self.assertEqual(out, "a makes a sound\nb says woof\n"
                              "b says woof!\n2\n")

    def test_objects_are_shared_not_copied(self):
        out, _ = run_source(
            BARK + 'function Change(x):\n    x.rename("changed")\n'
            'let d = Dog("a")\nlet e = d\nChange(d)\nshow e.name')
        self.assertEqual(out, "changed\n")

    def test_show_an_object(self):
        out, _ = run_source(BARK + 'let d = Dog("a")\nshow d\n'
                            'show [d, Animal("b")]\necho(d)')
        self.assertEqual(out, "<Dog object>\n[<Dog object>, <Animal object>]\n"
                              "<Dog object>\n")

    def test_equal_means_the_same_object(self):
        out, _ = run_source(
            BARK + 'let a = Dog("a")\nlet b = Dog("a")\nlet c = a\n'
            'if (a == c):\n    show "same"\nif (a == b):\n    show "bad"\n'
            'else:\n    show "different"\nif (a != b):\n    show "not equal"')
        self.assertEqual(out, "same\ndifferent\nnot equal\n")

    def test_python_keywords_work_as_names(self):
        out, _ = run_source(
            "class None:\n    function def(self, lambda):\n"
            "        self.class = lambda\n        give self.class\n"
            "let pass = None()\nshow pass.def(5)\nshow pass.class\nshow pass")
        self.assertEqual(out, "5\n5\n<None object>\n")

    def test_recursion_in_an_action(self):
        out, _ = run_source(
            "class M:\n    function fact(self, n):\n        if (n <= 1):\n"
            "            give 1\n        else:\n"
            "            give n * self.fact(n - 1)\n"
            "let m = M()\nshow m.fact(5)")
        self.assertEqual(out, "120\n")

    def test_user_actions_named_like_list_actions(self):
        out, _ = run_source(
            "class Stack:\n    function init(self):\n        self.items = []\n"
            "    function push(self, x):\n"
            "        self.items = self.items + [x]\n"
            "    function pop(self):\n        let top = self.items[-1]\n"
            "        self.items.pop(len(self.items) - 1)\n        give top\n"
            "    function remove(self, x):\n        self.items.remove(x)\n"
            "let s = Stack()\ns.push(1)\ns.push(2)\ns.push(3)\n"
            "s.remove(1)\nshow s.pop()\nshow s.items\n"
            "function Top(thing):\n    give thing.pop()\nshow Top(s)\n"
            "function Drop(thing):\n    thing.remove(2)\nDrop(s)\nshow s.items")
        self.assertEqual(out, "3\n[2]\n2\n[]\n")

    # -- friendly runtime errors -------------------------------------------

    def test_missing_attribute(self):
        error = error_in("run", "class A:\n    function f(self):\n"
                         "        give self.q\n    function g(self):\n"
                         "        self.q = 1\nlet a = A()\nshow a.f()")
        self.assertEqual(error.line, 3)
        self.assertEqual(str(error), 'Error on line 3: This A has nothing '
                         'called "q". Did you forget to give it one with: '
                         "self.q = ...")

    def test_missing_attribute_with_a_renamed_name(self):
        error = error_in("run", "class A:\n    function f(self):\n"
                         "        give self.class\n    function g(self):\n"
                         "        self.class = 1\nlet a = A()\nshow a.f()")
        self.assertIn('nothing called "class"', error.message)

    def test_actions_of_the_wrong_kind_of_value(self):
        source = "function F(x):\n    show x.speak()\n"
        self.assertEqual(error_in("run", source + "F(5)").message,
                         "A number has no action called speak.")
        self.assertEqual(error_in("run", source + 'F("hi")').message,
                         "Text has no action called speak.")
        self.assertEqual(error_in("run", source + "F([1])").message,
                         "A list has no action called speak.")
        error = error_in("run", SMALL + "function F(x):\n    x.speak()\n"
                         "F(5)")
        self.assertEqual(error.line, 5)

    def test_missing_action_on_an_object(self):
        error = error_in("run", SMALL + "function F(x):\n    x.fly()\n"
                         "F(Dog())")
        self.assertEqual(error.message, 'This Dog has no action called "fly".')

    def test_wrong_inputs_to_an_action_found_at_run_time(self):
        error = error_in("run", SMALL + "function F(x):\n    show x.speak(1)\n"
                         "F(Dog())")
        self.assertEqual(error.line, 5)
        self.assertIn('The action "speak" of class "Dog" needs 0 inputs, '
                      "but you gave 1.", error.message)

    def test_action_that_gives_nothing_used_as_a_value_at_run_time(self):
        source = ("class A:\n    function f(self):\n        show 1\n"
                  "function F(x):\n    show x.f()\nF(A())")
        self.assertIn("never gives anything back",
                      error_in("run", source).message)

    def test_attributes_of_the_wrong_kind_of_value(self):
        source = "function F(x):\n    show x.name\n"
        self.assertEqual(error_in("run", source + "F(5)").message,
                         'A number has nothing called "name". Only objects '
                         "made from a class remember things like that.")
        self.assertIn("Text has nothing called", error_in(
            "run", source + 'F("hi")').message)

    def test_setting_an_attribute_of_a_number(self):
        error = error_in("run", "function F(x):\n    x.name = 1\nF(5)")
        self.assertEqual(error.line, 2)
        self.assertIn("A number has nothing called", error.message)

    def test_action_used_like_a_thing_at_run_time(self):
        error = error_in("run", SMALL + "function F(x):\n    show x.speak\n"
                         "F(Dog())")
        self.assertIn('"speak" is an action of Dog', error.message)

    def test_init_called_at_run_time(self):
        error = error_in("run", "class A:\n    function init(self):\n"
                         "        show 1\nfunction F(x):\n    x.init()\n"
                         "F(A())")
        self.assertIn("init runs by itself", error.message)

    def test_division_by_zero_inside_an_action(self):
        error = error_in("run", "class A:\n    function init(self, n):\n"
                         "        self.n = n\n\n    function f(self):\n"
                         "        give 10 / self.n\nlet a = A(0)\n"
                         "show a.f()")
        self.assertEqual(error.line, 6)
        self.assertIn("divide by zero", error.message)

    def test_error_in_init_reports_the_line_inside_init(self):
        error = error_in("run", "class A:\n    function init(self, n):\n"
                         "        self.n = 1 / n\nlet a = A(0)")
        self.assertEqual(error.line, 3)

    def test_error_in_a_nested_action_call(self):
        error = error_in("run", "class A:\n    function f(self):\n"
                         "        give self.g()\n    function g(self):\n"
                         "        give 1 / 0\nlet a = A()\nshow a.f()")
        self.assertEqual(error.line, 5)

    def test_calculating_with_objects_at_run_time(self):
        source = SMALL + "function F(x):\n    give x + 1\nshow F(Dog())"
        self.assertIn("can't calculate with objects",
                      error_in("run", source).message)

    def test_going_through_an_object_at_run_time(self):
        source = SMALL + "function F(x):\n    for c in x:\n        show c\n"
        error = error_in("run", source + "F(Dog())")
        self.assertEqual(error.line, 5)
        self.assertIn("this value is an object", error.message)

    def test_len_of_an_object_at_run_time(self):
        source = SMALL + "function F(x):\n    give len(x)\nshow F(Dog())"
        self.assertIn("len needs a list or text, but this value is an object",
                      error_in("run", source).message)

    def test_endless_recursion_in_an_action(self):
        error = error_in("run", "class A:\n    function f(self):\n"
                         "        give self.f()\nlet a = A()\nshow a.f()")
        self.assertIn("kept calling itself", error.message)


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

    def test_the_to_do_example_runs(self):
        result = self.scripty_source("run", DOG_PROGRAM)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, DOG_OUTPUT)
        self.assertEqual(result.stderr, "")

    def test_build_output_is_readable_python(self):
        result = self.scripty_source("build", DOG_PROGRAM)
        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "class Dog:")
        self.assertEqual(lines[1], "    def __init__(self, name, age):")
        self.assertIn("class Puppy(Dog):", lines)
        self.assertIn("d = Dog('Rex', 3)", lines)
        self.assertNotIn("get_attr", result.stdout)
        self.assertNotIn("call_action", result.stdout)

    def test_example_file(self):
        result = self.scripty("run", os.path.join("examples", "classes.scy"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [
            "Tom says meow", "10", "3", "yes", "Tommy says meow",
            "Rex says woof!", '["sit", "roll"]', "no", "Tommy says meow",
            "Rex says woof!", "<Dog object>"])
        self.assertEqual(result.stderr, "")

    def test_friendly_errors_have_no_traceback(self):
        for source, expected in (
                ("class A:\n    function f(x):\n        give 1",
                 "Error on line 2: The first input of"),
                (BARK + 'let d = Dog("a")\nshow d.fly()',
                 'Error on line 12: A Dog object has no action called "fly"'),
                (BARK + 'let d = Dog("a")\nshow d.colour',
                 'Error on line 12: This Dog has nothing called "colour"'),
                (BARK + "let d = Dog()",
                 'Error on line 11: The class "Dog" needs 1 input (name)'),
                ("let n = 5\nshow n.speak()",
                 "Error on line 2: A number has no action called speak."),
                ("class A:\n    function f(self):\n        give self.q\n"
                 "    function g(self):\n        self.q = 1\nlet a = A()\n"
                 "show a.f()",
                 'Error on line 3: This A has nothing called "q"')):
            result = self.scripty_source("run", source)
            self.assertEqual(result.returncode, 1, source)
            self.assertEqual(result.stdout, "")
            self.assertIn(expected, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_list_actions_still_work(self):
        source = ('let a = ["Dog", "Cat", "Dog"]\na.remove("Dog")\nshow a\n'
                  "a.pop(0)\nshow a\nlet b = [3, 1, 2]\nsort(b)\nshow b\n")
        result = self.scripty_source("run", source)
        self.assertEqual(result.stdout, '["Cat"]\n[]\n[1, 2, 3]\n')


if __name__ == "__main__":
    unittest.main()
