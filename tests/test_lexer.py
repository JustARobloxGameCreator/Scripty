import unittest

from errors import ScriptyError
from lexer import (COLON, COMMA, DEDENT, INDENT, KEYWORD, LPAREN, NAME,
                   NEWLINE, NUMBER, OPERATOR, RPAREN,
                   TEXT, Token, tokenize)


class LexerTests(unittest.TestCase):
    def test_let_statement(self):
        self.assertEqual(
            tokenize("let x = 5"),
            [Token(KEYWORD, "let", 1), Token(NAME, "x", 1),
             Token(OPERATOR, "=", 1), Token(NUMBER, 5, 1),
             Token(NEWLINE, "\n", 1)],
        )

    def test_float_and_int_values(self):
        values = [t.value for t in tokenize("3.14 7") if t.kind == NUMBER]
        self.assertEqual(values, [3.14, 7])
        self.assertIsInstance(values[0], float)
        self.assertIsInstance(values[1], int)

    def test_operators(self):
        ops = [t.value for t in tokenize("a + b - c * d / e") if t.kind == OPERATOR]
        self.assertEqual(ops, ["+", "-", "*", "/"])

    def test_echo_with_text(self):
        kinds = [t.kind for t in tokenize('echo("Hello world!")')]
        self.assertEqual(kinds, [KEYWORD, LPAREN, TEXT, RPAREN, NEWLINE])
        self.assertEqual(tokenize('echo("Hello world!")')[2].value, "Hello world!")

    def test_line_numbers_and_blank_lines(self):
        tokens = tokenize("let x = 5\n\n   \nshow x\n")
        self.assertEqual([t.line for t in tokens if t.kind == KEYWORD], [1, 4])
        self.assertEqual(sum(t.kind == NEWLINE for t in tokens), 2)

    def test_comments_are_ignored(self):
        self.assertEqual(tokenize("# nothing here"), [])
        self.assertEqual(len(tokenize("show x # prints x")), 3)

    def test_hash_inside_text_is_kept(self):
        self.assertEqual(tokenize('show "a # b"')[1].value, "a # b")

    def test_empty_source(self):
        self.assertEqual(tokenize(""), [])

    def test_unknown_character(self):
        with self.assertRaises(ScriptyError) as ctx:
            tokenize("let x = 5\nlet y = 3 @ 2")
        self.assertEqual(ctx.exception.line, 2)
        self.assertEqual(
            str(ctx.exception),
            'Error on line 2: I don\'t know what "@" is. '
            "Scripty doesn't use that character here.",
        )

    def test_unclosed_string(self):
        with self.assertRaises(ScriptyError) as ctx:
            tokenize('show 1\nshow "oops')
        self.assertEqual(ctx.exception.line, 2)
        self.assertTrue(str(ctx.exception).startswith("Error on line 2:"))
        self.assertIn("never ends", str(ctx.exception))



class ComparisonAndCommentTests(unittest.TestCase):
    def test_all_comparison_operators(self):
        ops = [t.value for t in tokenize("a == b != c >= d <= e > f < g")
               if t.kind == OPERATOR]
        self.assertEqual(ops, ["==", "!=", ">=", "<=", ">", "<"])

    def test_single_equals_stays_assignment(self):
        self.assertEqual(tokenize("=")[0], Token(OPERATOR, "=", 1))

    def test_lonely_bang_is_friendly_error(self):
        with self.assertRaises(ScriptyError) as ctx:
            tokenize("if x ! 5:")
        self.assertIn("!=", str(ctx.exception))

    def test_new_keywords(self):
        words = "function if elif else give"
        kinds = [t.kind for t in tokenize(words)]
        self.assertEqual(kinds, [KEYWORD] * 5 + [NEWLINE])

    def test_colon_and_comma(self):
        kinds = [t.kind for t in tokenize("function f(a, b):")]
        self.assertEqual(kinds, [KEYWORD, NAME, LPAREN, NAME, COMMA, NAME,
                                 RPAREN, COLON, NEWLINE])

    def test_slash_slash_comment(self):
        self.assertEqual(tokenize("// nothing"), [])
        self.assertEqual(len(tokenize("show x // prints x")), 3)

    def test_hash_comment_still_works(self):
        self.assertEqual(len(tokenize("show x # prints x")), 3)

    def test_slash_slash_inside_text_is_text(self):
        tokens = tokenize('show "http://a.b" // real comment')
        self.assertEqual(tokens[1], Token(TEXT, "http://a.b", 1))
        self.assertEqual(len(tokens), 3)

    def test_single_slash_is_division(self):
        self.assertEqual(len(tokenize("show 4 / 2")), 5)


class IndentationTests(unittest.TestCase):
    def kinds(self, source):
        return [t.kind for t in tokenize(source)]

    def test_indent_and_dedent(self):
        tokens = tokenize("if a > 1:\n    show a\nshow 2")
        self.assertEqual(
            [(t.kind, t.line) for t in tokens if t.kind in (INDENT, DEDENT)],
            [(INDENT, 2), (DEDENT, 3)])

    def test_dedents_at_end_of_file(self):
        tokens = tokenize("function f():\n    if a > 1:\n        give 1\n")
        self.assertEqual([t.kind for t in tokens[-3:]],
                         [NEWLINE, DEDENT, DEDENT])
        self.assertEqual(tokens[-1].line, 3)

    def test_two_levels_close_together(self):
        tokens = tokenize("function f():\n    if a > 1:\n        give 1\nshow 2")
        self.assertEqual(sum(t.kind == DEDENT for t in tokens), 2)

    def test_blank_and_comment_lines_do_not_change_indentation(self):
        source = "if a > 1:\n    show a\n\n// note\n  \n    show b\n"
        self.assertEqual(self.kinds(source).count(INDENT), 1)
        self.assertEqual(self.kinds(source).count(DEDENT), 1)

    def test_tab_is_rejected(self):
        with self.assertRaises(ScriptyError) as ctx:
            tokenize("if a > 1:\n\tshow a")
        self.assertEqual(ctx.exception.line, 2)
        self.assertIn("tab", ctx.exception.message)

    def test_wrong_number_of_spaces(self):
        with self.assertRaises(ScriptyError) as ctx:
            tokenize("if a > 1:\n  show a")
        self.assertEqual(ctx.exception.line, 2)
        self.assertIn("4 spaces", ctx.exception.message)

    def test_indent_too_far(self):
        with self.assertRaises(ScriptyError) as ctx:
            tokenize("if a > 1:\n        show a")
        self.assertEqual(ctx.exception.line, 2)
        self.assertIn("too far", ctx.exception.message)


class ForLoopTests(unittest.TestCase):
    def test_for_and_in_are_keywords(self):
        tokens = tokenize('for i in "hi":\n    show i')
        self.assertEqual(
            [(t.kind, t.value) for t in tokens[:5]],
            [(KEYWORD, "for"), (NAME, "i"), (KEYWORD, "in"),
             (TEXT, "hi"), (COLON, ":")])

    def test_for_body_is_indented(self):
        kinds = [t.kind for t in tokenize('for i in "hi":\n    show i')]
        self.assertEqual(kinds.count(INDENT), 1)
        self.assertEqual(kinds.count(DEDENT), 1)

    def test_names_that_only_contain_for_or_in_are_names(self):
        tokens = tokenize("let inside = format")
        self.assertEqual([t.kind for t in tokens if t.kind == NAME],
                         [NAME, NAME])
        self.assertEqual([t.value for t in tokens if t.kind == KEYWORD],
                         ["let"])


if __name__ == "__main__":
    unittest.main()
