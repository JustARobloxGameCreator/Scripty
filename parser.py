"""Parser: turns tokens into an AST (see ast_nodes.py).

Grammar:

    program    = { statement }
    statement  = "let" NAME "=" expression NEWLINE
               | NAME "=" expression NEWLINE          (new value, no let)
               | NAME "[" expression "]" "=" expression NEWLINE
                                                      (change one list item)
               | "show" expression NEWLINE
               | "echo" "(" expression ")" NEWLINE
               | call NEWLINE                         (a call as a line)
               | member NEWLINE                       (an action as a line)
               | member "=" expression NEWLINE        (change what an object
                                                       remembers: d.name = 1)
               | "give" expression NEWLINE            (only inside a function)
               | "function" NAME "(" [ NAME { "," NAME } ] ")" block
               | "class" NAME [ "(" NAME ")" ] ":" NEWLINE INDENT
                 { function } DEDENT                  (only functions inside)
               | "if" condition block { "elif" condition block }
                 [ "else" block ]
               | "for" NAME "in" expression block     (per character / item)
    block      = ":" NEWLINE INDENT { statement } DEDENT
    condition  = expression COMPARE expression
               | "(" condition ")"                    (parentheses optional)
    COMPARE    = "==" | "!=" | ">=" | "<=" | ">" | "<"
    expression = term { ("+" | "-") term }
    term       = factor { ("*" | "/") factor }
    factor     = "-" factor | primary { "[" expression "]" }
    primary    = NUMBER | TEXT | call | member | NAME | list
               | "(" expression ")"
    list       = "[" [ expression { "," expression } ] "]"
    call       = NAME "(" [ expression { "," expression } ] ")"
    member     = NAME { "." NAME } [ "." NAME "(" [ expression
                 { "," expression } ] ")" ]
                 (d.name, self.pet.name, a.pop(1), d.speak(), super.init(1))

Design choices (precedence, lists, dots, classes, indexing, for): see
docs/architecture.md, section "Parser".

Errors raise ScriptyError with a line number.
"""

from ast_nodes import (LIST_METHODS, Assign, AssignAttribute, AssignIndex, Attribute,
                       BinaryOp, Branch, Call, CallStatement, ClassDef, Compare,
                       Echo, Expression, For, Function, Give, If, Index, Let,
                       ListLiteral, MethodCall, MethodStatement, Name, Negate,
                       Number, Program, Show, Statement, Text)
from errors import ScriptyError
from lexer import (COLON, COMMA, DEDENT, DOT, INDENT, KEYWORD, LBRACKET, LPAREN,
                   NAME, NEWLINE, NUMBER, OPERATOR, RBRACKET, RPAREN, TEXT,
                   Token)

COMPARISONS = ("==", "!=", ">=", "<=", ">", "<")


def parse(tokens: list[Token]) -> Program:
    """Build a Program from tokens. Raises ScriptyError on bad syntax."""
    return _Parser(tokens).parse_program()


def _describe(token: Token) -> str:
    """Show a token the way the user wrote it, for error messages."""
    if token.kind == NEWLINE:
        return "the end of the line"
    if token.kind in (INDENT, DEDENT):
        return "the end of the block"
    return f'"{token.value}"'


def _dot_error(token: Token) -> ScriptyError:
    """A "." that is not part of a number, a list action or an object."""
    return ScriptyError(
        'A "." only works right after the name of a list, like: '
        'a.remove("Dog") or a.pop(1), or of an object, like: d.speak() or '
        "d.name. For a decimal number write the digit before the dot too, "
        "like 0.5.", token.line)


def _needs_parentheses(name: str, method: str, line: int) -> ScriptyError:
    example = '"Dog"' if method == "remove" else "1"
    return ScriptyError(
        f"{method} needs parentheses with a value inside. "
        f"Try: {name}.{method}({example})", line)


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.last_line = tokens[-1].line if tokens else 1
        self.depth = 0  # how many blocks we are inside
        self.in_function = False

    # -- helpers -----------------------------------------------------------

    def peek(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(NEWLINE, "\n", self.last_line)  # safety net

    def peek_next(self) -> Token:
        if self.pos + 1 < len(self.tokens):
            return self.tokens[self.pos + 1]
        return Token(NEWLINE, "\n", self.last_line)

    def advance(self) -> Token:
        token = self.peek()
        self.pos += 1
        return token

    def is_operator(self, *symbols: str) -> bool:
        token = self.peek()
        return token.kind == OPERATOR and token.value in symbols

    def is_keyword(self, word: str) -> bool:
        token = self.peek()
        return token.kind == KEYWORD and token.value == word

    # -- statements --------------------------------------------------------

    def parse_program(self) -> Program:
        statements: list[Statement] = []
        while self.pos < len(self.tokens):
            statements.append(self.parse_statement())
        return Program(statements)

    def parse_statement(self) -> Statement:
        token = self.peek()
        if token.kind == INDENT:
            raise ScriptyError(
                "This line is indented, but the line above does not end "
                'with a ":". Only the lines inside a function, an if, a for '
                "or a class are indented. Remove the spaces at the start.",
                token.line,
            )
        if token.kind == KEYWORD:
            if token.value == "function":
                return self.parse_function()
            if token.value == "if":
                return self.parse_if()
            if token.value == "for":
                return self.parse_for()
            if token.value == "class":
                return self.parse_class()
            if token.value == "in":
                raise ScriptyError(
                    'in only works in a for line. Try: for letter in "hi":',
                    token.line,
                )
            if token.value in ("elif", "else"):
                raise ScriptyError(
                    f"{token.value} needs an if above it. "
                    f"Start with: if (x > 5):",
                    token.line,
                )
        statement = self.parse_simple_statement(token)
        self.expect_end_of_line()
        return statement

    def parse_simple_statement(self, token: Token) -> Statement:
        if token.kind == KEYWORD and token.value == "let":
            return self.parse_let()
        if token.kind == KEYWORD and token.value == "show":
            return self.parse_show()
        if token.kind == KEYWORD and token.value == "echo":
            return self.parse_echo()
        if token.kind == KEYWORD and token.value == "give":
            return self.parse_give()
        if token.kind == NAME and self.peek_next().kind == LPAREN:
            return CallStatement(self.parse_call(), token.line)
        if token.kind == NAME and self.peek_next().kind == DOT:
            return self.parse_member_statement()
        if token.kind == NAME and self.peek_next().kind == LBRACKET:
            return self.parse_index_statement()
        if token.kind == DOT or self.peek_next().kind == DOT:
            raise _dot_error(token if token.kind == DOT else self.peek_next())
        if (token.kind == NAME and self.peek_next().kind == OPERATOR
                and self.peek_next().value == "="):
            return self.parse_assign()
        raise ScriptyError(
            f"I don't understand a line that starts with "
            f"{_describe(token)}. A line must start with let, show, echo, "
            "give, if, for, function, a function call like Name(1, 2), a "
            "list action like a.pop(1), or a new value for a variable like "
            "x = 5 (or for a list item like a[0] = 5).",
            token.line,
        )

    def parse_member_statement(self) -> Statement:
        """Read a line that starts with `name.`: an action or d.name = value."""
        start = self.peek()
        member = self.parse_member()
        if self.is_operator("="):
            if not isinstance(member, Attribute):
                raise ScriptyError(
                    "You can't give a new value to an action call. To "
                    "change what an object remembers write: "
                    f"{start.value}.name = 5", start.line)
            self.advance()  # the "="
            if self.peek().kind == NEWLINE:
                raise ScriptyError(
                    f"{start.value}.{member.name} has no new value. Write "
                    f'a value after the "=". Try: '
                    f"{start.value}.{member.name} = 5", start.line)
            return AssignAttribute(member.target, member.name,
                                   self.parse_expression(), start.line)
        if isinstance(member, MethodCall):
            return MethodStatement(member, start.line)
        if member.name in LIST_METHODS:
            raise _needs_parentheses(start.value, member.name, start.line)
        raise ScriptyError(
            f"A line can't be only {start.value}.{member.name}. To use it, "
            f"write: show {start.value}.{member.name}  To change it, "
            f"write: {start.value}.{member.name} = 5", start.line)

    def parse_let(self) -> Let:
        keyword = self.advance()
        name = self.peek()
        if name.kind == KEYWORD and name.value == "class":
            raise ScriptyError(
                '"class" is a Scripty keyword (it starts a class), so it '
                "can't be a variable name. Pick another name.", keyword.line)
        if name.kind != NAME:
            raise ScriptyError(
                "You wrote let but forgot the name of the variable. "
                "Try: let x = 5",
                keyword.line,
            )
        self.advance()
        if not self.is_operator("="):
            raise ScriptyError(
                f'I expected "=" after "{name.value}". '
                f"Try: let {name.value} = 5",
                keyword.line,
            )
        self.advance()
        if self.peek().kind == NEWLINE:
            raise ScriptyError(
                f'"{name.value}" has no value. Write a value after the "=". '
                f"Try: let {name.value} = 5",
                keyword.line,
            )
        return Let(name.value, self.parse_expression(), keyword.line)

    def parse_assign(self) -> Assign:
        name = self.advance()
        self.advance()  # the "="
        if self.peek().kind == NEWLINE:
            raise ScriptyError(
                f'"{name.value}" has no new value. Write a value after the '
                f'"=". Try: {name.value} = 5',
                name.line,
            )
        return Assign(name.value, self.parse_expression(), name.line)

    def parse_index_statement(self) -> AssignIndex:
        """Read `name[index] = value` (a line that starts with name[ )."""
        start = self.peek()
        target = self.parse_factor()
        if not self.is_operator("="):
            raise ScriptyError(
                f"A line can't be only {start.value}[...]. To use the item, "
                f"write: show {start.value}[0]  or  let x = {start.value}[0]. "
                f"To change it, write: {start.value}[0] = 5", start.line)
        if not isinstance(target, Index) or not isinstance(target.target, Name):
            raise ScriptyError(
                "Only one item of a list can be changed at a time, by the "
                f"name of the list. Try: {start.value}[0] = 5", start.line)
        self.advance()  # the "="
        if self.peek().kind == NEWLINE:
            raise ScriptyError(
                f"{start.value}[...] has no new value. Write a value after "
                f'the "=". Try: {start.value}[0] = 5', start.line)
        return AssignIndex(target.target, target.index, self.parse_expression(),
                           start.line)

    def parse_show(self) -> Show:
        keyword = self.advance()
        if self.peek().kind == NEWLINE:
            raise ScriptyError(
                "show needs something to show. Try: show x", keyword.line
            )
        return Show(self.parse_expression(), keyword.line)

    def parse_echo(self) -> Echo:
        keyword = self.advance()
        if self.peek().kind != LPAREN:
            raise ScriptyError(
                'echo needs parentheses. Try: echo("Hello world!")',
                keyword.line,
            )
        self.advance()
        value = self.parse_expression()
        if self.peek().kind != RPAREN:
            raise ScriptyError(
                'echo is missing its closing ")". '
                'Try: echo("Hello world!")',
                keyword.line,
            )
        self.advance()
        return Echo(value, keyword.line)

    def parse_give(self) -> Give:
        keyword = self.advance()
        if not self.in_function:
            raise ScriptyError(
                "give only works inside a function. To print something "
                "use show instead.",
                keyword.line,
            )
        if self.peek().kind == NEWLINE:
            raise ScriptyError(
                "give needs a value to hand back. Try: give result",
                keyword.line,
            )
        return Give(self.parse_expression(), keyword.line)

    def expect_end_of_line(self) -> None:
        token = self.peek()
        if token.kind == NEWLINE:
            self.advance()
        elif token.kind == RPAREN:
            raise ScriptyError(
                'This ")" has no matching "(". '
                "Did you add one ) too many?",
                token.line,
            )
        elif token.kind == DOT and self.tokens[self.pos - 1].kind == RPAREN:
            raise ScriptyError(
                'A "." can\'t come right after a closing ")" yet. Keep the '
                "answer in a variable first, like: let d = Dog(\"Rex\", 3) "
                "and then: d.speak()", token.line)
        elif token.kind == DOT:
            raise _dot_error(token)
        elif token.kind == OPERATOR and token.value in COMPARISONS:
            raise ScriptyError(
                f'"{token.value}" compares two values, so it can only be '
                "used after if or elif. Try: if (x "
                f"{token.value} 5):",
                token.line,
            )
        else:
            raise ScriptyError(
                f"I did not expect {_describe(token)} here. "
                "Each line holds one statement, and this one was already "
                "complete before it.",
                token.line,
            )

    # -- functions, if, blocks ---------------------------------------------

    def parse_function(self, in_class: bool = False) -> Function:
        keyword = self.advance()
        # A function is written outside everything, or (an action) directly
        # inside a class, which is one block deep.
        if self.depth > (1 if in_class else 0):
            raise ScriptyError(
                "A function can't be written inside another function, "
                "an if or a for. Put it at the start of a line, outside everything.",
                keyword.line,
            )
        name = self.peek()
        if name.kind == KEYWORD:
            raise ScriptyError(
                f'"{name.value}" is a Scripty keyword, so it can\'t be a '
                "function name. Pick another name.",
                keyword.line,
            )
        if name.kind != NAME:
            raise ScriptyError(
                "You wrote function but forgot its name. "
                "Try: function Add(a, b):",
                keyword.line,
            )
        self.advance()
        if self.peek().kind != LPAREN:
            raise ScriptyError(
                f'function {name.value} needs parentheses for its inputs. '
                f"Try: function {name.value}(a, b):  "
                f"(or {name.value}() for none)",
                keyword.line,
            )
        self.advance()
        params = self.parse_parameters(keyword.line, name.value)
        description = f"function {name.value}"
        body = self.parse_block(
            keyword.line, description,
            f"function {name.value}({', '.join(params)}):",
            is_function=True)
        return Function(name.value, params, body, keyword.line)

    def parse_class(self) -> ClassDef:
        keyword = self.advance()
        if self.depth > 0:
            raise ScriptyError(
                "A class can't be written inside a function, a class, an "
                "if or a for. Put it at the start of a line, outside "
                "everything.", keyword.line)
        name = self.peek()
        if name.kind == KEYWORD:
            raise ScriptyError(
                f'"{name.value}" is a Scripty keyword, so it can\'t be a '
                "class name. Pick another name.", keyword.line)
        if name.kind != NAME:
            raise ScriptyError(
                "You wrote class but forgot its name. Try: class Dog:",
                keyword.line)
        self.advance()
        parent = None
        if self.peek().kind == LPAREN:
            parent = self.parse_parent(keyword.line, name.value)
        example = f"class {name.value}:"
        self.start_block(keyword.line, f"class {name.value}", example)
        self.depth += 1
        methods: list[Function] = []
        while self.pos < len(self.tokens) and self.peek().kind != DEDENT:
            methods.append(self.parse_class_member(name.value))
        self.depth -= 1
        self.advance()  # the DEDENT
        return ClassDef(name.value, parent, methods, keyword.line)

    def parse_parent(self, line: int, class_name: str) -> str:
        """Read `(Parent)` after a class name."""
        self.advance()  # the "("
        parent = self.peek()
        example = f"class {class_name}(Dog):"
        if parent.kind != NAME:
            raise ScriptyError(
                f"class {class_name}( needs the name of the parent class "
                f"after the bracket. Try: {example}", line)
        self.advance()
        if self.peek().kind == COMMA:
            raise ScriptyError(
                f"A class can have only one parent, but {class_name} lists "
                f"more. Try: {example}", line)
        if self.peek().kind != RPAREN:
            raise ScriptyError(
                f"The parent of {class_name} is missing its closing "
                f'")". Try: {example}', line)
        self.advance()
        return parent.value

    def parse_class_member(self, class_name: str) -> Function:
        """One line directly inside a class: it must be a function."""
        token = self.peek()
        if token.kind == KEYWORD and token.value == "function":
            return self.parse_function(in_class=True)
        if token.kind == KEYWORD and token.value == "class":
            raise ScriptyError(
                "A class can't be written inside another class. Put it at "
                "the start of a line, outside everything.", token.line)
        if token.kind == INDENT:
            raise ScriptyError(
                "This line is indented too far. The lines inside a class "
                "are functions, indented by 4 spaces.", token.line)
        raise ScriptyError(
            f"A class can only hold functions (its actions), but I found "
            f"{_describe(token)} inside {class_name}. To give an object "
            "something to remember, set it inside a function with: "
            "self.name = ...", token.line)

    def parse_parameters(self, line: int, function_name: str) -> list[str]:
        params: list[str] = []
        if self.peek().kind == RPAREN:
            self.advance()
            return params
        while True:
            token = self.peek()
            if token.kind != NAME:
                raise ScriptyError(
                    f"I expected an input name here in function "
                    f"{function_name}, but found {_describe(token)}. "
                    f"Try: function {function_name}(a, b):",
                    line,
                )
            params.append(self.advance().value)
            token = self.advance()
            if token.kind == RPAREN:
                return params
            if token.kind != COMMA:
                raise ScriptyError(
                    f"Write a comma between inputs, or close the list with "
                    f'")". I did not expect {_describe(token)} here.',
                    line,
                )

    def parse_for(self) -> For:
        keyword = self.advance()
        example = 'for letter in "hello":'
        name = self.peek()
        if name.kind == KEYWORD and name.value != "in":
            raise ScriptyError(
                f'"{name.value}" is a Scripty keyword, so it can\'t be the '
                "name of a loop variable. Pick another name.",
                keyword.line,
            )
        if name.kind != NAME:
            raise ScriptyError(
                "You wrote for but forgot the name for each step of the "
                f"loop. Try: {example}",
                keyword.line,
            )
        self.advance()
        if not self.is_keyword("in"):
            raise ScriptyError(
                f'I expected "in" after "{name.value}". '
                f'Try: for {name.value} in "hello":',
                keyword.line,
            )
        self.advance()
        if self.peek().kind in (COLON, NEWLINE):
            raise ScriptyError(
                f"for {name.value} in needs a text or a list to go through. "
                f'Try: for {name.value} in "hello":',
                keyword.line,
            )
        iterable = self.parse_expression()
        body = self.parse_block(
            keyword.line, f"the for loop over {name.value}",
            f'for {name.value} in "hello":')
        return For(name.value, iterable, body, keyword.line)

    def parse_if(self) -> If:
        keyword = self.advance()
        branches = [self.parse_branch(keyword, "if")]
        while self.is_keyword("elif"):
            branches.append(self.parse_branch(self.advance(), "elif"))
        else_body = None
        else_line = keyword.line
        if self.is_keyword("else"):
            else_token = self.advance()
            else_line = else_token.line
            if self.is_keyword("if"):
                raise ScriptyError(
                    'Scripty writes "else if" as one word: elif. '
                    "Try: elif (x > 5):",
                    else_token.line,
                )
            else_body = self.parse_block(else_token.line, "else", "else:")
        return If(branches, else_body, else_line, keyword.line)

    def parse_branch(self, keyword: Token, word: str) -> Branch:
        condition = self.parse_condition(keyword, word)
        body = self.parse_block(keyword.line, word, f"{word} (x > 5):")
        return Branch(condition, body, keyword.line)

    def start_block(self, line: int, description: str, example: str) -> None:
        """Read the start of a block: `: NEWLINE INDENT`."""
        token = self.peek()
        if token.kind != COLON:
            if token.kind == NEWLINE:
                raise ScriptyError(
                    f'{description} is missing a ":" at the end of the '
                    f"line. Try: {example}",
                    line,
                )
            raise ScriptyError(
                f"I did not expect {_describe(token)} here. "
                f'I expected a ":" to start the lines inside '
                f"{description}.",
                line,
            )
        self.advance()
        if self.peek().kind != NEWLINE:
            raise ScriptyError(
                f"Put the lines that belong to {description} on the "
                "next lines, indented by 4 spaces.",
                line,
            )
        self.advance()
        if self.peek().kind != INDENT:
            raise ScriptyError(
                f"{description} has nothing inside it. Write its lines "
                "below it, indented by 4 spaces.",
                line,
            )
        self.advance()

    def parse_block(self, line: int, description: str, example: str,
                    is_function: bool = False) -> list[Statement]:
        """Read `: NEWLINE INDENT statements DEDENT`."""
        self.start_block(line, description, example)
        was_in_function = self.in_function
        if is_function:
            self.in_function = True
        self.depth += 1
        body: list[Statement] = []
        while self.pos < len(self.tokens) and self.peek().kind != DEDENT:
            body.append(self.parse_statement())
        self.depth -= 1
        self.in_function = was_in_function
        self.advance()  # the DEDENT
        return body

    # -- conditions --------------------------------------------------------

    def parse_condition(self, keyword: Token, word: str) -> Compare:
        """Parse `x > 5` or `(x > 5)` (the parentheses are optional)."""
        if self.peek().kind in (COLON, NEWLINE):
            raise ScriptyError(
                f"{word} needs a condition. Try: {word} (x > 5):",
                keyword.line,
            )
        if self.peek().kind == LPAREN and self.parentheses_end_condition():
            self.advance()
            condition = self.parse_comparison(keyword, word)
            if self.peek().kind != RPAREN:
                raise ScriptyError(
                    f"I did not expect {_describe(self.peek())} in this "
                    "condition. I expected a closing \")\".",
                    keyword.line,
                )
            self.advance()
            return condition
        return self.parse_comparison(keyword, word)

    def parentheses_end_condition(self) -> bool:
        """True if the "(" at the cursor closes right before the ":"."""
        depth = 0
        for index in range(self.pos, len(self.tokens)):
            kind = self.tokens[index].kind
            if kind == LPAREN:
                depth += 1
            elif kind == RPAREN:
                depth -= 1
                if depth == 0:
                    after = self.tokens[index + 1:index + 2]
                    return bool(after) and after[0].kind == COLON
            elif kind == NEWLINE:
                break
        return False

    def parse_comparison(self, keyword: Token, word: str) -> Compare:
        left = self.parse_expression()
        token = self.peek()
        if token.kind == OPERATOR and token.value == "=":
            raise ScriptyError(
                'A single "=" gives a variable a value. To compare two '
                'values use "==". Try: ' + f"{word} (x == 5):",
                token.line,
            )
        if token.kind != OPERATOR or token.value not in COMPARISONS:
            raise ScriptyError(
                f"The condition after {word} needs a comparison: "
                '== != > < >= <=. Try: ' + f"{word} (x > 5):",
                keyword.line,
            )
        self.advance()
        right = self.parse_expression()
        if self.is_operator(*COMPARISONS):
            raise ScriptyError(
                "A condition compares only two values at a time. "
                f'I did not expect a second "{self.peek().value}" here.',
                self.peek().line,
            )
        return Compare(token.value, left, right, token.line)

    # -- expressions -------------------------------------------------------

    def parse_expression(self) -> Expression:
        left = self.parse_term()
        while self.is_operator("+", "-"):
            op = self.advance()
            right = self.parse_term()
            left = BinaryOp(op.value, left, right, op.line)
        return left

    def parse_term(self) -> Expression:
        left = self.parse_factor()
        while self.is_operator("*", "/"):
            op = self.advance()
            right = self.parse_factor()
            left = BinaryOp(op.value, left, right, op.line)
        return left

    def parse_factor(self) -> Expression:
        token = self.peek()
        if self.is_operator("-"):
            self.advance()
            return Negate(self.parse_factor(), token.line)
        value = self.parse_primary()
        while self.peek().kind == LBRACKET:
            value = self.parse_index(value)
        return value

    def parse_index(self, target: Expression) -> Index:
        """Read `[position]` after a value."""
        opening = self.advance()  # the "["
        if self.peek().kind == RBRACKET:
            raise ScriptyError(
                'Put a position between the [ ], like: a[0]. The first '
                "item is at position 0.", opening.line)
        index = self.parse_expression()
        if self.peek().kind != RBRACKET:
            raise ScriptyError(
                'This "[" has no matching "]". Did you forget to close it? '
                f"I did not expect {_describe(self.peek())} here. "
                "Try: a[0]", opening.line)
        self.advance()
        return Index(target, index, opening.line)

    def parse_primary(self) -> Expression:
        token = self.peek()
        if token.kind == NUMBER:
            self.advance()
            return Number(token.value, token.line)
        if token.kind == TEXT:
            self.advance()
            return Text(token.value, token.line)
        if token.kind == NAME:
            if self.peek_next().kind == LPAREN:
                return self.parse_call()
            if self.peek_next().kind == DOT:
                return self.parse_member()
            self.advance()
            return Name(token.value, token.line)
        if token.kind == LPAREN:
            return self.parse_parentheses()
        if token.kind == LBRACKET:
            return self.parse_list()
        if token.kind == DOT:
            raise _dot_error(token)
        raise self.missing_value_error(token)

    def parse_call(self) -> Call:
        name = self.advance()
        self.advance()  # the "("
        args = self.parse_arguments(name.value, name.line)
        return Call(name.value, args, name.line)

    def parse_member(self) -> Expression:
        """Read what follows a name and a dot.

        `d.name` and `self.pet.name` are attributes; `a.pop(1)`,
        `d.speak()` and `self.pet.speak()` are action calls. A call ends
        the chain.
        """
        first = self.advance()
        value: Expression = Name(first.value, first.line)
        path = first.value
        while self.peek().kind == DOT:
            dot = self.advance()
            member = self.peek()
            if member.kind not in (NAME, KEYWORD):
                raise ScriptyError(
                    'A "." must be followed by a name, like: '
                    'a.remove("Dog"), d.speak() or d.name', dot.line)
            self.advance()
            path += "." + member.value
            if self.peek().kind == LPAREN:
                self.advance()  # the "("
                args = self.parse_arguments(path, first.line)
                return MethodCall(value, member.value, args, first.line)
            value = Attribute(value, member.value, first.line)
        return value

    def parse_arguments(self, name: str, line: int) -> list[Expression]:
        """Read the inputs of a call, after its "(", up to the ")"."""
        args: list[Expression] = []
        if self.peek().kind == RPAREN:
            self.advance()
            return args
        while True:
            args.append(self.parse_expression())
            token = self.peek()
            if token.kind == COMMA:
                self.advance()
            elif token.kind == RPAREN:
                self.advance()
                return args
            else:
                raise ScriptyError(
                    f'The call to {name} is missing its closing ")" '
                    "(or a comma between inputs). "
                    f"I did not expect {_describe(token)} here.",
                    line,
                )

    def parse_list(self) -> ListLiteral:
        opening = self.advance()  # the "["
        items: list[Expression] = []
        if self.peek().kind == RBRACKET:
            self.advance()
            return ListLiteral(items, opening.line)
        while True:
            if self.peek().kind == RBRACKET:
                raise ScriptyError(
                    'There is a comma right before the closing "]". '
                    "Remove the last comma, like: [1, 2, 3]",
                    opening.line,
                )
            items.append(self.parse_expression())
            token = self.peek()
            if token.kind == COMMA:
                self.advance()
            elif token.kind == RBRACKET:
                self.advance()
                return ListLiteral(items, opening.line)
            else:
                raise ScriptyError(
                    'This list is missing its closing "]" (or a comma '
                    f"between items). I did not expect {_describe(token)} "
                    "here. Try: [1, 2, 3]",
                    opening.line,
                )

    def parse_parentheses(self) -> Expression:
        opening = self.advance()
        value = self.parse_expression()
        if self.peek().kind != RPAREN:
            raise ScriptyError(
                'This "(" has no matching ")". Did you forget to close it?',
                opening.line,
            )
        self.advance()
        return value

    def missing_value_error(self, token: Token) -> ScriptyError:
        """Explain why a value (number, text or name) was expected."""
        if token.kind == NEWLINE:
            previous = self.tokens[self.pos - 1] if self.pos else None
            if previous and previous.kind == OPERATOR:
                return ScriptyError(
                    f'There is nothing after "{previous.value}". '
                    f"Write a value after it, like: 5 {previous.value} 2",
                    token.line,
                )
            return ScriptyError(
                "I expected a value (a number, text or name) here, "
                "but the line ended.",
                token.line,
            )
        return ScriptyError(
            f"I did not expect {_describe(token)} here. "
            "I expected a value (a number, text or name).",
            token.line,
        )
