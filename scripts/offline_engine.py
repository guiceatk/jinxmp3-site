#!/usr/bin/env python3
"""
Offline Recursive Function-Capable Engine
A lightweight, zero-dependency interpreter for custom DSL scripts supporting:
- User-defined functions & recursion
- Scoped stack frames & local variable environments
- IF / WHILE control flow with return signals
- Constant-folding AST expression optimization
- Offline module imports (.mini files)
"""

import re
import sys
import os
from pathlib import Path

# -------------------------
# 1. LEXICAL ANALYSIS
# -------------------------
def tokenize(code):
    token_spec = [
        ("NUMBER", r"\d+(\.\d*)?"),
        ("COMP", r"==|<=|>=|<|>|!="),
        ("ASSIGN", r"="),
        ("END", r";"),
        ("ID", r"[A-Za-z_]\w*"),
        ("OP", r"[+\-*/]"),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
        ("LBRACE", r"\{"),
        ("RBRACE", r"\}"),
        ("COMMA", r","),
        ("NEWLINE", r"\n"),
        ("SKIP", r"[ \t]+"),
        ("MISMATCH", r"."),
    ]
    tok_regex = "|".join(f"(?P<{name}>{pattern})" for name, pattern in token_spec)
    tokens = []
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()
        if kind == "NUMBER":
            value = float(value) if "." in value else int(value)
        elif kind in ("ID", "OP", "COMP", "ASSIGN", "LPAREN", "RPAREN", "LBRACE", "RBRACE", "COMMA", "END"):
            pass
        elif kind in ("SKIP", "NEWLINE"):
            continue
        elif kind == "MISMATCH":
            raise SyntaxError(f"Unexpected character: '{value}'")
        tokens.append((kind, value))
    return tokens

# -------------------------
# 2. PARSER (Recursive Descent)
# -------------------------
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def consume(self, expected_type=None, expected_val=None):
        token = self.peek()
        if expected_type and token[0] != expected_type:
            raise SyntaxError(f"Expected token type '{expected_type}', got '{token[0]}'")
        if expected_val and token[1] != expected_val:
            raise SyntaxError(f"Expected '{expected_val}', got '{token[1]}'")
        self.pos += 1
        return token

    def parse(self):
        statements = []
        while self.pos < len(self.tokens):
            statements.append(self.statement())
        return ("program", statements)

    def statement(self):
        tok_type, tok_val = self.peek()

        if tok_val == "if":
            return self.if_statement()
        elif tok_val == "while":
            return self.while_statement()
        elif tok_val == "func":
            return self.function_def()
        elif tok_val == "import":
            return self.import_statement()
        elif tok_val == "return":
            return self.return_statement()
        elif tok_type == "ID":
            # Check if assignment vs expression/call
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1][0] == "ASSIGN":
                return self.assignment()
            else:
                expr = self.expression()
                if self.peek()[0] == "END":
                    self.consume("END")
                return expr
        else:
            expr = self.expression()
            if self.peek()[0] == "END":
                self.consume("END")
            return expr

    def block(self):
        self.consume("LBRACE")
        stmts = []
        while self.peek()[0] != "RBRACE" and self.pos < len(self.tokens):
            stmts.append(self.statement())
        self.consume("RBRACE")
        return ("block", stmts)

    def if_statement(self):
        self.consume("ID", "if")
        condition = self.expression()
        then_block = self.block()
        else_block = None
        if self.peek()[1] == "else":
            self.consume("ID", "else")
            else_block = self.block()
        return ("if", condition, then_block, else_block)

    def while_statement(self):
        self.consume("ID", "while")
        condition = self.expression()
        body = self.block()
        return ("while", condition, body)

    def function_def(self):
        self.consume("ID", "func")
        name = self.consume("ID")[1]
        self.consume("LPAREN")
        params = []
        while self.peek()[0] != "RPAREN":
            params.append(self.consume("ID")[1])
            if self.peek()[0] == "COMMA":
                self.consume("COMMA")
        self.consume("RPAREN")
        body = self.block()
        return ("func_def", name, params, body)

    def import_statement(self):
        self.consume("ID", "import")
        filename = self.consume("ID")[1]
        if self.peek()[0] == "END":
            self.consume("END")
        return ("import", filename)

    def return_statement(self):
        self.consume("ID", "return")
        expr = None
        if self.peek()[0] not in ("END", "RBRACE"):
            expr = self.expression()
        if self.peek()[0] == "END":
            self.consume("END")
        return ("return", expr)

    def assignment(self):
        name = self.consume("ID")[1]
        self.consume("ASSIGN")
        expr = self.expression()
        if self.peek()[0] == "END":
            self.consume("END")
        return ("assign", name, expr)

    def expression(self):
        left = self.comp_expr()
        return left

    def comp_expr(self):
        left = self.arith_expr()
        while self.peek()[0] == "COMP":
            op = self.consume("COMP")[1]
            right = self.arith_expr()
            left = ("binop", op, left, right)
        return left

    def arith_expr(self):
        left = self.term()
        while self.peek()[1] in ("+", "-"):
            op = self.consume("OP")[1]
            right = self.term()
            left = ("binop", op, left, right)
        return left

    def term(self):
        left = self.factor()
        while self.peek()[1] in ("*", "/"):
            op = self.consume("OP")[1]
            right = self.factor()
            left = ("binop", op, left, right)
        return left

    def factor(self):
        tok_type, tok_val = self.peek()
        if tok_type == "NUMBER":
            self.consume("NUMBER")
            return ("num", tok_val)
        elif tok_type == "ID":
            # Function call vs variable reference
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1][0] == "LPAREN":
                name = self.consume("ID")[1]
                self.consume("LPAREN")
                args = []
                while self.peek()[0] != "RPAREN":
                    args.append(self.expression())
                    if self.peek()[0] == "COMMA":
                        self.consume("COMMA")
                self.consume("RPAREN")
                return ("call", name, args)
            else:
                name = self.consume("ID")[1]
                return ("var", name)
        elif tok_type == "LPAREN":
            self.consume("LPAREN")
            expr = self.expression()
            self.consume("RPAREN")
            return expr
        else:
            raise SyntaxError(f"Unexpected token: '{tok_val}'")

# -------------------------
# 3. RETURN EXCEPTION
# -------------------------
class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

# -------------------------
# 4. AST OPTIMIZER (Constant Folding)
# -------------------------
def optimize_ast(node):
    if not isinstance(node, tuple):
        return node
    
    node_type = node[0]

    if node_type == "binop":
        op, left, right = node[1], optimize_ast(node[2]), optimize_ast(node[3])
        if left[0] == "num" and right[0] == "num":
            v1, v2 = left[1], right[1]
            if op == "+": return ("num", v1 + v2)
            if op == "-": return ("num", v1 - v2)
            if op == "*": return ("num", v1 * v2)
            if op == "/": return ("num", v1 / v2 if v2 != 0 else 0)
            if op == "==": return ("num", 1 if v1 == v2 else 0)
            if op == "!=": return ("num", 1 if v1 != v2 else 0)
            if op == "<": return ("num", 1 if v1 < v2 else 0)
            if op == ">": return ("num", 1 if v1 > v2 else 0)
            if op == "<=": return ("num", 1 if v1 <= v2 else 0)
            if op == ">=": return ("num", 1 if v1 >= v2 else 0)
        return ("binop", op, left, right)

    elif node_type == "assign":
        return ("assign", node[1], optimize_ast(node[2]))

    elif node_type == "if":
        cond = optimize_ast(node[1])
        then_b = optimize_ast(node[2])
        else_b = optimize_ast(node[3]) if node[3] else None
        return ("if", cond, then_b, else_b)

    elif node_type == "while":
        return ("while", optimize_ast(node[1]), optimize_ast(node[2]))

    elif node_type == "block":
        return ("block", [optimize_ast(stmt) for stmt in node[1]])

    elif node_type == "program":
        return ("program", [optimize_ast(stmt) for stmt in node[1]])

    elif node_type == "call":
        return ("call", node[1], [optimize_ast(a) for a in node[2]])

    elif node_type == "func_def":
        return ("func_def", node[1], node[2], optimize_ast(node[3]))

    return node

# -------------------------
# 5. INTERPRETER
# -------------------------
class Interpreter:
    def __init__(self, base_dir="."):
        self.globals = {}
        self.functions = {}
        self.base_dir = Path(base_dir)

    def eval(self, node, local_vars=None):
        if local_vars is None:
            local_vars = {}

        node_type = node[0]

        if node_type == "num":
            return node[1]

        elif node_type == "var":
            var_name = node[1]
            if var_name in local_vars:
                return local_vars[var_name]
            if var_name in self.globals:
                return self.globals[var_name]
            raise NameError(f"Undefined variable: '{var_name}'")

        elif node_type == "binop":
            op = node[1]
            left = self.eval(node[2], local_vars)
            right = self.eval(node[3], local_vars)
            if op == "+": return left + right
            if op == "-": return left - right
            if op == "*": return left * right
            if op == "/": return left / right if right != 0 else 0
            if op == "==": return 1 if left == right else 0
            if op == "!=": return 1 if left != right else 0
            if op == "<": return 1 if left < right else 0
            if op == ">": return 1 if left > right else 0
            if op == "<=": return 1 if left <= right else 0
            if op == ">=": return 1 if left >= right else 0
            raise ValueError(f"Unknown operator: '{op}'")

        elif node_type == "assign":
            var_name = node[1]
            val = self.eval(node[2], local_vars)
            if local_vars is not None and len(local_vars) > 0:
                local_vars[var_name] = val
            else:
                self.globals[var_name] = val
            return val

        elif node_type == "if":
            cond_val = self.eval(node[1], local_vars)
            if cond_val:
                return self.eval(node[2], local_vars)
            elif node[3]:
                return self.eval(node[3], local_vars)
            return None

        elif node_type == "while":
            last_val = None
            while self.eval(node[1], local_vars):
                last_val = self.eval(node[2], local_vars)
            return last_val

        elif node_type == "block":
            last_val = None
            for stmt in node[1]:
                last_val = self.eval(stmt, local_vars)
            return last_val

        elif node_type == "program":
            last_val = None
            for stmt in node[1]:
                last_val = self.eval(stmt, local_vars)
            return last_val

        elif node_type == "func_def":
            name = node[1]
            params = node[2]
            body = node[3]
            self.functions[name] = (params, body)
            return f"<function {name}>"

        elif node_type == "call":
            func_name = node[1]
            arg_values = [self.eval(arg, local_vars) for arg in node[2]]
            
            # Built-in helper functions
            if func_name == "print":
                print(*arg_values)
                return arg_values[0] if arg_values else None

            if func_name not in self.functions:
                raise NameError(f"Undefined function: '{func_name}'")

            params, body = self.functions[func_name]
            if len(params) != len(arg_values):
                raise TypeError(f"Function '{func_name}' expects {len(params)} arguments, got {len(arg_values)}")

            # Create isolated stack frame for function execution
            frame_vars = dict(zip(params, arg_values))
            try:
                self.eval(body, frame_vars)
            except ReturnSignal as ret:
                return ret.value
            return None

        elif node_type == "return":
            val = self.eval(node[1], local_vars) if node[1] else None
            raise ReturnSignal(val)

        elif node_type == "import":
            mod_name = node[1]
            mod_path = self.base_dir / f"{mod_name}.mini"
            if not mod_path.exists():
                raise FileNotFoundError(f"Offline module not found: '{mod_path}'")
            with open(mod_path, "r", encoding="utf-8") as f:
                mod_code = f.read()
            tokens = tokenize(mod_code)
            parser = Parser(tokens)
            ast = optimize_ast(parser.parse())
            return self.eval(ast, local_vars)

        else:
            raise ValueError(f"Unknown AST node type: '{node_type}'")

def run_mini_script(source_code, base_dir="."):
    tokens = tokenize(source_code)
    parser = Parser(tokens)
    raw_ast = parser.parse()
    optimized_ast = optimize_ast(raw_ast)
    interpreter = Interpreter(base_dir=base_dir)
    return interpreter.eval(optimized_ast)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        filepath = Path(sys.argv[1])
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
            run_mini_script(code, base_dir=filepath.parent)
        else:
            print(f"[!] File not found: {filepath}")
    else:
        # Self-test demonstration of recursion (Factorial & Fibonacci)
        print("=== OFFLINE ENGINE RECURSION TEST ===")
        sample_code = """
        func factorial(n) {
            if n <= 1 {
                return 1;
            }
            return n * factorial(n - 1);
        }

        func fibonacci(n) {
            if n <= 0 { return 0; }
            if n == 1 { return 1; }
            return fibonacci(n - 1) + fibonacci(n - 2);
        }

        f5 = factorial(5);
        fib8 = fibonacci(8);
        print(f5);
        print(fib8);
        """
        result = run_mini_script(sample_code)
        print(f"[+] Execution completed cleanly.")
