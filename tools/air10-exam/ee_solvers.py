"""ee_solvers.py - exam_solve kinds built on proven open-source libraries (2026-09-27, from Rajon's study-repo collection):

  netlist  lcapy (symbolic linear circuits): node voltages, element V/I, Thevenin/Norton, DC / AC / step transients
  control  python-control: margins, step info (Mp, tr, ts, tp), bandwidth, system type + Kp/Kv/Ka; state space: controllability etc.
  logic    SymPy boolean algebra: truth table, minterms, minimal SOP / POS (from an expression or minterm list)
  twoport  closed-form Z / Y / ABCD / h conversions + reciprocity / symmetry checks

Security: nothing from the caller is evaluated. Netlists are checked line by line against a strict grammar and every value goes through
math_safety.parse_math (bounded AST -> SymPy). Boolean expressions go through a whitelist AST walk. Work is bounded by a timeout.
"""
from __future__ import annotations

import ast
import cmath
import concurrent.futures as cf
import re

TIMEOUT_S = 25
_POOL = cf.ThreadPoolExecutor(2)


def _bounded(fn, *a):
    fut = _POOL.submit(fn, *a)
    try:
        return fut.result(timeout=TIMEOUT_S)
    except cf.TimeoutError:
        return {"ok": False, "error": f"took longer than {TIMEOUT_S}s; simplify the circuit/expression"}


# ------------------------------------------------------------------------------------------------ netlist (lcapy)
_NODE = r"[A-Za-z0-9_]{1,12}"
_LINE = re.compile(rf"^([RLCVIEGFH][A-Za-z0-9_]{{0,10}})\s+({_NODE})\s+({_NODE})(?:\s+(.*))?$")
_KEYWORDS = {"dc", "ac", "step", "s"}


def _check_value(tok):
    from math_safety import parse_math
    import sympy as sp
    parse_math(tok, {"s": sp.Symbol("s"), "t": sp.Symbol("t", real=True)})   # raises ValueError on anything unsafe
    return tok


def _clean_netlist(text):
    lines = [l.strip() for l in re.split(r"[\n;]+", text or "") if l.strip() and not l.strip().startswith("#")]
    if not 1 <= len(lines) <= 40:
        raise ValueError("give 1-40 netlist lines, e.g. 'V1 1 0 10' / 'R1 1 2 2' / 'C1 2 0 1e-6' / 'V1 1 0 step 10'")
    out, names = [], set()
    for line in lines:
        m = _LINE.match(line)
        if not m or len(line) > 120:
            raise ValueError(f"bad netlist line: {line[:60]!r}")
        name, n1, n2, rest = m.group(1), m.group(2), m.group(3), (m.group(4) or "").split()
        if name in names:
            raise ValueError(f"duplicate element {name}")
        names.add(name)
        kind = name[0]
        if kind in "EG":            # VCVS / VCCS: n+ n- nc+ nc- gain
            if len(rest) != 3 or not all(re.fullmatch(_NODE, x) for x in rest[:2]):
                raise ValueError(f"{name}: use '{name} n+ n- nc+ nc- gain'")
            out.append(f"{name} {n1} {n2} {rest[0]} {rest[1]} {_check_value(rest[2])}")
        elif kind in "FH":          # CCCS / CCVS: n+ n- Vcontrol gain
            if len(rest) != 2 or rest[0] not in names and not re.fullmatch(r"V[A-Za-z0-9_]{0,10}", rest[0]):
                raise ValueError(f"{name}: use '{name} n+ n- Vcontrol gain'")
            out.append(f"{name} {n1} {n2} {rest[0]} {_check_value(rest[1])}")
        else:
            if not rest:
                raise ValueError(f"{name}: missing value")
            kw = [x for x in rest if x.lower() in _KEYWORDS]
            vals = [x for x in rest if x.lower() not in _KEYWORDS]
            if len(kw) > 1 or not 1 <= len(vals) <= 2 or (kind in "RLC" and (kw or len(vals) != 1)):
                raise ValueError(f"{name}: value must be '<number>' or '[dc|ac|step] <number> [phase]'")
            out.append(" ".join([name, n1, n2, *kw, *[_check_value(v) for v in vals]]))
    return "\n".join(out)


def _netlist(text, query, a, b, elements):
    from lcapy import Circuit
    net = _clean_netlist(text)
    c = Circuit(net)
    res = {"ok": True, "kind": "netlist", "netlist": net.split("\n")}
    nodes = sorted({n for n in c.node_list if str(n) != "0"}, key=str)
    if query in ("all", "nodes"):
        res["node_voltages"] = {str(n): str(c[n].v) for n in nodes}
    want = elements or [str(e) for e in c.elements if str(e)[0] in "RLC"]
    if query in ("all", "elements"):
        res["elements"] = {e: {"v": str(c[e].v), "i": str(c[e].i)} for e in want[:15] if e in c.elements}
    if query in ("thevenin", "norton", "all") and a is not None:
        th = c.thevenin(a, b if b is not None else 0)
        tm = lambda q: q.time() if hasattr(q, "time") else q
        res["thevenin"] = {"between": [a, b if b is not None else 0], "Voc": str(tm(th.Voc)), "Zth": str(th.Z)}
        no = c.norton(a, b if b is not None else 0)
        res["norton"] = {"Isc": str(tm(no.Isc)), "Yn": str(no.Y)}
    kws = {w.lower() for line in net.split("\n") for w in line.split()[3:]}
    res["analysis"] = ("step transient, expressions in t (Heaviside(t) = switched on at t=0)" if "step" in kws else
                       "AC phasor steady state" if "ac" in kws else "DC steady state")
    return res


def netlist(text="", query="all", a=None, b=None, elements=None):
    try:
        return _bounded(_netlist, text, query, a, b, elements)
    except ValueError as e:
        return {"ok": False, "error": str(e)}


# ------------------------------------------------------------------------------------------------ control (python-control)
def _coeffs(expr_or_list):
    if isinstance(expr_or_list, (list, tuple)):
        vals = [float(x) for x in expr_or_list]
        if not 1 <= len(vals) <= 12:
            raise ValueError("polynomial must have 1-12 coefficients")
        return vals
    raise ValueError("num/den must be lists of numbers (descending powers of s)")


def _control(p):
    import numpy as np
    import control as ct
    import sympy as sp
    from math_safety import parse_math
    out = {"ok": True, "kind": "control"}
    if "A" in p:
        A, B, C = (np.array(p[k], dtype=float) for k in ("A", "B", "C"))
        D = np.array(p.get("D", np.zeros((C.shape[0], B.shape[1]))), dtype=float)
        if max(A.shape) > 8:
            raise ValueError("state matrix up to 8x8")
        sys_ = ct.ss(A, B, C, D)
        Wc, Wo = ct.ctrb(A, B), ct.obsv(A, C)
        out.update({"eigenvalues": [str(np.round(e, 5)) for e in np.linalg.eigvals(A)], "controllable": bool(np.linalg.matrix_rank(Wc) == A.shape[0]),
                    "observable": bool(np.linalg.matrix_rank(Wo) == A.shape[0]), "rank_ctrb": int(np.linalg.matrix_rank(Wc)),
                    "rank_obsv": int(np.linalg.matrix_rank(Wo))})
        tf = ct.ss2tf(sys_)
        out["transfer_function"] = str(tf).strip()
        G = tf if (B.shape[1] == 1 and C.shape[0] == 1) else None
    else:
        if "G" in p:
            s = sp.Symbol("s")
            num, den = sp.fraction(sp.together(parse_math(str(p["G"]), {"s": s})))
            num, den = [float(x) for x in sp.Poly(num, s).all_coeffs()], [float(x) for x in sp.Poly(den, s).all_coeffs()]
        else:
            num, den = _coeffs(p.get("num")), _coeffs(p.get("den"))
        G = ct.tf(num, den)
        poles, zeros = ct.poles(G), ct.zeros(G)
        typ = int(sum(1 for x in poles if abs(x) < 1e-9))
        s = sp.Symbol("s")
        Gs = sp.Poly(num, s).as_expr() / sp.Poly(den, s).as_expr()
        k = {name: str(sp.limit(s ** n * Gs, s, 0)) for n, name in ((0, "Kp"), (1, "Kv"), (2, "Ka"))}
        out.update({"poles": [str(np.round(x, 5)) for x in poles], "zeros": [str(np.round(x, 5)) for x in zeros], "system_type": typ,
                    "error_constants_open_loop": k, "stable_open_loop": bool(all(np.real(poles) < 0))})
    if G is not None:
        gm, pm, wcg, wcp = ct.margin(G)
        cl = ct.feedback(G, 1)
        info = ct.step_info(cl)
        db = lambda x: None if not np.isfinite(x) else round(20 * np.log10(x), 4)
        out.update({"gain_margin_db": db(gm), "phase_margin_deg": None if not np.isfinite(pm) else round(float(pm), 4),
                    "w_gc": None if not np.isfinite(wcp) else round(float(wcp), 5), "w_pc": None if not np.isfinite(wcg) else round(float(wcg), 5),
                    "closed_loop_unity_feedback": {"poles": [str(np.round(x, 5)) for x in ct.poles(cl)], "stable": bool(all(np.real(ct.poles(cl)) < 0)),
                                                   "overshoot_pct": round(info["Overshoot"], 4), "rise_time": round(info["RiseTime"], 5),
                                                   "settling_time_2pct": round(info["SettlingTime"], 5), "peak_time": round(info["PeakTime"], 5),
                                                   "bandwidth": (lambda b: None if not np.isfinite(b) else round(float(b), 5))(ct.bandwidth(cl)),
                                                   "dc_gain": round(float(ct.dcgain(cl)), 6)}})
    return out


def control(p):
    try:
        return _bounded(_control, dict(p or {}))
    except (ValueError, TypeError, KeyError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ------------------------------------------------------------------------------------------------ logic (SymPy)
_BOOL_OPS = {ast.BitAnd: "And", ast.BitOr: "Or", ast.BitXor: "Xor"}


def _bool_ast(node, syms):
    import sympy.logic.boolalg as B
    import sympy as sp
    if isinstance(node, ast.Expression):
        return _bool_ast(node.body, syms)
    if isinstance(node, ast.Name) and re.fullmatch(r"[A-Za-z][A-Za-z0-9]?", node.id):
        return syms.setdefault(node.id, sp.Symbol(node.id))
    if isinstance(node, ast.Constant) and node.value in (0, 1):
        return sp.true if node.value else sp.false
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Invert, ast.Not)):
        return B.Not(_bool_ast(node.operand, syms))
    if isinstance(node, ast.BinOp) and type(node.op) in _BOOL_OPS:
        return getattr(B, _BOOL_OPS[type(node.op)])(_bool_ast(node.left, syms), _bool_ast(node.right, syms))
    if isinstance(node, ast.BoolOp):
        return (B.And if isinstance(node.op, ast.And) else B.Or)(*[_bool_ast(v, syms) for v in node.values])
    raise ValueError(f"unsupported boolean syntax: {type(node).__name__}")


def _primes(e):
    """postfix complement: A' -> ~(A); (A+B)' -> ~((A+B)); repeated primes nest."""
    out = ""
    for ch in e:
        if ch != "'":
            out += ch; continue
        j = len(out) - 1
        while j >= 0 and out[j] == " ":
            j -= 1
        if j >= 0 and out[j] == ")":
            depth, k = 0, j
            while k >= 0:
                depth += out[k] == ")"; depth -= out[k] == "("
                if depth == 0:
                    break
                k -= 1
            if k < 0:
                raise ValueError("unbalanced parentheses before '")
            out = out[:k] + "~(" + out[k:j + 1] + ")"
        else:
            m = re.search(r"([A-Za-z][0-9]?|~\([^()]*\))\s*$", out)
            if not m:
                raise ValueError("' must follow a variable or a parenthesis")
            out = out[:m.start()] + "~(" + m.group(1) + ")"
    return out


def _normalize_bool(expr):
    e = expr.replace("·", "&").replace("*", "&").replace("+", "|").replace("⊕", "^").replace("!", "~")
    e = re.sub(r"\bAND\b", "&", e, flags=re.I); e = re.sub(r"\bOR\b", "|", e, flags=re.I)
    e = re.sub(r"\bXOR\b", "^", e, flags=re.I); e = re.sub(r"\bNOT\b", "~", e, flags=re.I)
    e = _primes(e)                                              # A' -> ~(A), (A+B)' -> ~((A+B))
    e = re.sub(r"(?<=[A-Za-z0-9)])\s*\.\s*(?=[A-Za-z(~])", "&", e)   # A.B -> A&B
    e = re.sub(r"\s+", "", e)
    prev = None
    while prev != e:   # textbook juxtaposition: AB, A(B|C), ~(A)B -> explicit &  (variables are 1 letter + optional digit)
        prev = e
        e = re.sub(r"([A-Za-z][0-9]?|\))(?=[A-Za-z(~])", r"\1&", e)
    return e


def logic(expression="", minterms=None, dontcares=None, variables=None):
    import sympy as sp
    from sympy.logic import SOPform, POSform
    try:
        if expression:
            if len(expression) > 200:
                raise ValueError("expression too long (max 200 chars)")
            syms = {}
            f = _bool_ast(ast.parse(_normalize_bool(expression), mode="eval"), syms)
            vs = [syms[k] for k in sorted(syms)] if not variables else [sp.Symbol(v) for v in variables]
            if len(vs) > 8:
                raise ValueError("at most 8 variables")
            mins = [i for i in range(2 ** len(vs))
                    if bool(f.subs({v: bool((i >> (len(vs) - 1 - j)) & 1) for j, v in enumerate(vs)}))]
            dc = []
        else:
            vs = [sp.Symbol(v) for v in (variables or [])]
            if not 1 <= len(vs) <= 8:
                raise ValueError("give variables (1-8) with minterms")
            mins, dc = sorted({int(x) for x in minterms or []}), sorted({int(x) for x in dontcares or []})
            if any(not 0 <= m < 2 ** len(vs) for m in mins + dc):
                raise ValueError("minterm outside range")
        bits = lambda i: [int(b) for b in format(i, f"0{len(vs)}b")]
        sop, pos = SOPform(vs, [bits(m) for m in mins], [bits(d) for d in dc]), POSform(vs, [bits(m) for m in mins], [bits(d) for d in dc])
        return {"ok": True, "kind": "logic", "variables": [str(v) for v in vs], "minterms": mins, "dont_cares": dc,
                "maxterms": [i for i in range(2 ** len(vs)) if i not in mins and i not in dc],
                "minimal_SOP": str(sop), "minimal_POS": str(pos), "sop_literals": sum(len(a.args) if a.args else 1 for a in (sop.args if isinstance(sop, sp.Or) else [sop]))}
    except (ValueError, SyntaxError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ------------------------------------------------------------------------------------------------ twoport
def _cx(x):
    if isinstance(x, (int, float)):
        return complex(x)
    s = str(x).replace(" ", "").replace("i", "j")
    if not re.fullmatch(r"[0-9eE.+\-j]{1,40}", s):
        raise ValueError(f"not a number: {x!r}")
    return complex(s)


def twoport(p):
    try:
        given = next(k for k in ("Z", "Y", "ABCD", "h") if k in p)
        m = [[_cx(v) for v in row] for row in p[given]]
        if len(m) != 2 or any(len(r) != 2 for r in m):
            raise ValueError("matrix must be 2x2")
        a, b, c, d = m[0][0], m[0][1], m[1][0], m[1][1]
        det = a * d - b * c
        if given == "Z":
            Z = m
        elif given == "Y":
            Z = [[d / det, -b / det], [-c / det, a / det]]
        elif given == "ABCD":   # A B / C D
            Z = [[a / c, det / c], [1 / c, d / c]]
        else:                   # h11 h12 / h21 h22
            Z = [[det / d, b / d], [-c / d, 1 / d]]
        z11, z12, z21, z22 = Z[0][0], Z[0][1], Z[1][0], Z[1][1]
        dz = z11 * z22 - z12 * z21
        Y = [[z22 / dz, -z12 / dz], [-z21 / dz, z11 / dz]]
        ABCD = [[z11 / z21, dz / z21], [1 / z21, z22 / z21]]
        H = [[dz / z22, z12 / z22], [-z21 / z22, 1 / z22]]
        fmt = lambda M: [[(round(x.real, 6) if abs(x.imag) < 1e-12 else f"{x.real:.6g}{x.imag:+.6g}j") for x in r] for r in M]
        adbc = ABCD[0][0] * ABCD[1][1] - ABCD[0][1] * ABCD[1][0]
        return {"ok": True, "kind": "twoport", "given": given, "Z": fmt(Z), "Y": fmt(Y), "ABCD": fmt(ABCD), "h": fmt(H),
                "reciprocal": bool(abs(z12 - z21) < 1e-9 * max(1, abs(z12))), "symmetric": bool(abs(z11 - z22) < 1e-9 * max(1, abs(z11))),
                "AD_minus_BC": fmt([[adbc]])[0][0]}
    except StopIteration:
        return {"ok": False, "error": "give one of Z, Y, ABCD, h as [[a, b], [c, d]]"}
    except (ValueError, ZeroDivisionError, TypeError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e} (a parameter set may not exist for this network)"}
