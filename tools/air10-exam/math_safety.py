"""Bounded input adapters over SymPy and Pint; no Python evaluation of input.

These validate syntax and input complexity. They are not a substitute for a
solver timeout or limits on polynomial degree in the calling solver.
"""
from __future__ import annotations

import ast
from functools import lru_cache
import math
import re

MAX_CHARS = 2048
MAX_NODES = 160
MAX_DEPTH = 20
MAX_POWER = 16
MAX_MATRIX_SIDE = 6
SYMBOL_NAMES = frozenset("s t x y z a b c R L C V I w omega alpha beta theta phi p q".split())


def parse_math(expression: str, symbols: dict | None = None):
    """Parse explicit arithmetic, selected functions, or a <=6x6 list matrix.

    Allowed functions: sin/cos/tan, asin/acos/atan, sinh/cosh/tanh,
    exp/log/sqrt/Abs/conjugate/re/im. Constants are pi, E and I.
    `symbols` may replace only allowed symbols with SymPy Symbol objects.
    Powers require a finite numeric exponent of magnitude <=16 and cannot nest.
    """
    import sympy as sp

    if not isinstance(expression, str) or not expression.strip() or len(expression) > MAX_CHARS:
        raise ValueError(f"expression must contain 1..{MAX_CHARS} characters")
    names = {name: sp.Symbol(name) for name in SYMBOL_NAMES}
    for name, value in (symbols or {}).items():
        if name not in SYMBOL_NAMES or not isinstance(value, sp.Symbol):
            raise ValueError("only explicitly allowed SymPy symbols may be supplied")
        names[name] = value
    names.update(pi=sp.pi, E=sp.E, I=sp.I)
    funcs = {name: getattr(sp, name) for name in (
        "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
        "exp", "log", "sqrt", "Abs", "conjugate", "re", "im")}
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("invalid mathematical expression") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise ValueError(f"expression exceeds {MAX_NODES} syntax nodes")

    def scalar(node, depth=0):
        if depth > MAX_DEPTH:
            raise ValueError("expression nesting is too deep")
        if isinstance(node, ast.Constant):
            value = node.value
            if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e12:
                raise ValueError("only finite numeric literals up to 1e12 are supported")
            return sp.Integer(value) if isinstance(value, int) else sp.Float(value)
        if isinstance(node, ast.Name) and node.id in names:
            return names[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = scalar(node.operand, depth + 1)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)):
            if isinstance(node.op, ast.Pow) and any(isinstance(n, ast.Pow) for n in ast.walk(node.right)):
                raise ValueError("nested powers are unsupported")
            if isinstance(node.op, ast.Pow) and any(isinstance(n, ast.Pow) for n in ast.walk(node.left)):
                raise ValueError("nested powers are unsupported")
            left, right = scalar(node.left, depth + 1), scalar(node.right, depth + 1)
            if isinstance(node.op, ast.Pow):
                if right.is_number is not True or right.is_real is not True or right.is_finite is not True or abs(right) > MAX_POWER:
                    raise ValueError(f"power must be a finite numeric value within +/-{MAX_POWER}")
                value = sp.Pow(left, right)
            elif isinstance(node.op, ast.Div):
                if right.is_zero:
                    raise ValueError("division by zero")
                value = left / right
            elif isinstance(node.op, ast.Add):
                value = left + right
            elif isinstance(node.op, ast.Sub):
                value = left - right
            else:
                value = left * right
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in funcs:
            if node.keywords or len(node.args) != 1:
                raise ValueError("math functions accept one positional argument")
            value = funcs[node.func.id](scalar(node.args[0], depth + 1))
        else:
            raise ValueError(f"unsupported syntax: {type(node).__name__}")
        if value.has(sp.zoo, sp.oo, -sp.oo, sp.nan):
            raise ValueError("expression produces a non-finite value")
        return value

    body = tree.body
    if isinstance(body, (ast.List, ast.Tuple)):
        if not 1 <= len(body.elts) <= MAX_MATRIX_SIDE or not all(isinstance(row, (ast.List, ast.Tuple)) for row in body.elts):
            raise ValueError("matrix requires 1..6 nonempty rows")
        width = len(body.elts[0].elts)
        if not 1 <= width <= MAX_MATRIX_SIDE or any(len(row.elts) != width for row in body.elts):
            raise ValueError("matrix requires 1..6 columns and equally sized rows")
        return [[scalar(entry) for entry in row.elts] for row in body.elts]
    return scalar(body)


@lru_cache(maxsize=1)
def _unit_registry():
    import pint
    registry = pint.UnitRegistry()
    registry.define("volt_ampere = volt * ampere = VA")
    registry.define("reactive_volt_ampere = volt * ampere = VAR = var")
    return registry


def normalize_units(value: str) -> dict:
    """Normalize one EE scalar with case-sensitive SI prefixes through Pint."""
    if not isinstance(value, str) or len(value) > 128:
        return {"ok": False, "error": "give one finite EE quantity, e.g. '11 kV' or '4.7 uF'"}
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*([A-Za-zµμΩ]+)\s*", value)
    if not match:
        return {"ok": False, "error": "give one finite EE quantity, e.g. '11 kV' or '4.7 uF'"}
    magnitude = float(match[1])
    if not math.isfinite(magnitude):
        return {"ok": False, "error": "quantity must be finite"}
    token = match[2].replace("µ", "u").replace("μ", "u").replace("Ω", "ohm")
    token = re.sub(r"Ohm$", "ohm", token)
    bases = {"V": "volt", "A": "ampere", "W": "watt", "F": "farad", "H": "henry", "Hz": "hertz", "ohm": "ohm", "VA": "volt_ampere", "VAR": "reactive_volt_ampere", "var": "reactive_volt_ampere"}
    base = next((suffix for suffix in sorted(bases, key=len, reverse=True) if token.endswith(suffix)), None)
    if base is None:
        return {"ok": False, "error": "unsupported EE unit or incorrect case"}
    try:
        registry = _unit_registry()
        quantity = registry.Quantity(magnitude, registry.Unit(token)).to(bases[base])
        si = float(quantity.magnitude)
        if not math.isfinite(si):
            raise ValueError("converted quantity must be finite")
        return {"ok": True, "si": si, "unit": "VAR" if base == "var" else base}
    except (ValueError, TypeError, OverflowError, ImportError, AttributeError, KeyError) as exc:   # pint UndefinedUnitError is an AttributeError
        return {"ok": False, "error": f"unit conversion unavailable: {type(exc).__name__}"}
