import math
from fractions import Fraction
from smart_calculator import MathEngine, SymbolicMathEngine

def fallback(raw_term, t, sign):
    try:
        expr = t
        subterms = []
        fact = 1.0
        for i in range(5):
            try:
                val = MathEngine.eval_at(expr, 0.0)
                if math.isnan(val) or math.isinf(val):
                    return None, f"Unsupported term (singular at x=0): {raw_term}", raw_term
            except Exception:
                return None, f"Unsupported term (eval error at x=0): {raw_term}", raw_term
                
            if abs(val) > 1e-7:
                new_n = i + 1
                coef = (val * sign) / (fact * new_n)
                frac = Fraction(str(round(coef, 5))).limit_denominator(1000)
                if frac.numerator != 0:
                    var_part = f"x^{new_n}" if new_n > 1 else "x"
                    subterms.append((frac, var_part))
            
            expr = SymbolicMathEngine.get_symbolic_derivative(expr)
            fact *= (i + 1)
            
        if not subterms:
            return None, f"Unsupported term: {raw_term}", raw_term
            
        rule = f"Maclaurin Series Expansion Approximation: integral ({raw_term}) dx"
        return subterms, rule, raw_term
    except Exception as e:
        return None, f"Unsupported term: {raw_term} (Error: {e})", raw_term

print(fallback("sin(cos(x))", "sin(cos(x))", 1))
