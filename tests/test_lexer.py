import unittest

from errors import ScriptyError
from lexer import (KEYWORD, LPAREN, NAME, NEWLINE, NUMBER, OPERATOR, RPAREN,
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


if __name__ == "__main__":
    unittest.main()
