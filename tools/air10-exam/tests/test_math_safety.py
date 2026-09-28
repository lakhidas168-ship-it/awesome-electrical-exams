import sys
from pathlib import Path

import pytest
import sympy as sp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from math_safety import normalize_units, parse_math


@pytest.mark.parametrize("expression,expected", [
    ("25/(s**2+6*s+25)", "25/(s**2 + 6*s + 25)"),
    ("1/(s+2)", "1/(s + 2)"),
    ("x+y", "x + y"),
    ("10*exp(I*pi*90/180)", "10*I"),
    ("sin(pi/2)+sqrt(4)", "3"),
    ("s**(1/2)", "sqrt(s)"),
])
def test_real_solver_expression_compatibility(expression, expected):
    assert str(parse_math(expression)) == expected


def test_matrix_and_symbol_identity():
    matrix = sp.Matrix(parse_math("[[0,1],[-2,-3]]"))
    assert set(matrix.eigenvals()) == {-1, -2}
    s = sp.Symbol("s", real=True)
    assert parse_math("s+1", {"s":s}).free_symbols == {s}


@pytest.mark.parametrize("expression", [
    "__import__('os').getcwd()", "open('/tmp/never-open')", "s.__class__", "[x for x in [1]]",
    "(lambda: 1)()", "sin(x,1)", "sin(x, evaluate=False)", "2**1000000000", "9**9**9", "(s**2)**2",
    "s**s", "factorial(1000000)", "True", "'s'", "{}", "1/0", "1e999", "s[0]", "sin.__call__(1)",
    "[[1],[2,3]]", "[]", "[1,2]", "log(0)", "0**-1", "unknown+1", "sin(" + "s+"*1000 + "1)",
    "("*250 + "s" + ")"*250,
])
def test_reject_unsafe_or_unbounded_syntax(expression):
    with pytest.raises(ValueError):
        parse_math(expression)


def test_no_expression_side_effect(tmp_path):
    marker = tmp_path/'must-not-exist'
    with pytest.raises(ValueError):
        parse_math(f"__import__('pathlib').Path({str(marker)!r}).write_text('bad')")
    assert not marker.exists()


@pytest.mark.parametrize("value,si,unit", [
    ("11 kV",11000,"V"), ("1 MV",1e6,"V"), ("1 mV",1e-3,"V"),
    ("1 MW",1e6,"W"), ("1 mW",1e-3,"W"), ("1 mOhm",1e-3,"ohm"), ("1 MOhm",1e6,"ohm"),
    ("4.7 uF",4.7e-6,"F"), ("4.7 µF",4.7e-6,"F"), ("4.7 μF",4.7e-6,"F"),
    ("2 MVA",2e6,"VA"), ("3 kVAR",3000,"VAR"), ("3 kvar",3000,"VAR"),
    ("10 mH",0.01,"H"), ("50 Hz",50,"Hz"), ("1E-3 A",0.001,"A"), ("2 kΩ",2000,"ohm"),
])
def test_units_preserve_case_and_prefix(value,si,unit):
    result=normalize_units(value)
    assert result['ok'], result
    assert result['unit']==unit
    assert result['si']==pytest.approx(si)


@pytest.mark.parametrize("value", ["1e999 V","NaN A","inf W","11 kv","1 mV + 2 V","1 V; print(1)","1 badV","1 ft","1.2.3 V"])
def test_units_reject_invalid(value):
    assert normalize_units(value)['ok'] is False
