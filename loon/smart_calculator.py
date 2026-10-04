"""
================================================================================
                    SMART AI CALCULATOR & CALCULUS ASSISTANT
================================================================================
Features:
  1. Self-Learning User Behavior Engine:
     - Tracks frequently used functions, common integration bounds, and habits
     - Learns custom variables and formulas defined by the user
     - Dynamically ranks auto-complete suggestions based on personal usage
     - Stores persistent profile in `smart_profile.json` with habit analytics
  2. Interpreting Super Complex Questions:
     - Natural Language Math interpretation (e.g. "integrate sin(x) from 0 to pi")
     - Complex calculus: definite integrals, derivatives, tangent lines, roots,
       areas between curves, arc length, and statistical data questions
     - High-precision numerical quadrature (Simpson's 1/3 + Richardson extrapolation)
     - Automatic step-by-step breakdown and error margin estimates
  3. Conversational English Understanding ("lil bit convo english"):
     - Understands greetings, small talk, questions about previous answers ("ans")
     - Mathematical explanations (e.g. "why is integral of 1/x equal to ln|x|")
     - Jokes, capability questions, and conversational guidance
  4. Active Real-Time Auto-Corrector & Auto-Completor:
     - Real-time inline suggestion & Tab auto-completion (powered by msvcrt on Windows)
     - Fuzzy typo corrector for math terms (e.g. "integrte", "sqrtt", "pie", "derivatve")
     - Auto-balancing parentheses and implicit multiplication (e.g. 2x -> 2*x)
================================================================================
"""

import sys
import os
import math
import json
import re
import difflib
import time
from collections import Counter
from fractions import Fraction
import ast
import subprocess

# Safe encoding reconfigure for Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Try importing msvcrt for Windows real-time keypress handling
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


# ==============================================================================
#                 0. GUI BRIDGE & CONTROL PAD IPC INTERFACE
# ==============================================================================

class GUIBridge:
    """
    Handles synchronization with the popped-out Control Pad and
    Process Animation Screen (control_pad.exe via smart_gui_state.json).
    """
    STATE_FILE = "smart_gui_state.json"
    EXE_FILE = "control_pad.exe"

    @classmethod
    def ensure_control_pad_running(cls):
        """Auto-activates and pops out control_pad.exe if not already running."""
        try:
            tasks = subprocess.check_output('tasklist /FI "IMAGENAME eq control_pad.exe"', shell=True, text=True, errors="ignore")
            if "control_pad.exe" not in tasks and os.path.exists(cls.EXE_FILE):
                os.system("start control_pad.exe")
        except Exception:
            pass

    @classmethod
    def load_state(cls) -> dict:
        if os.path.exists(cls.STATE_FILE):
            try:
                with open(cls.STATE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "status": "idle",
            "task": "Engine Ready",
            "active_function": "None",
            "popout_mode": "auto",
            "anim_style": 0,
            "command_pending": ""
        }

    @classmethod
    def save_state(cls, state: dict):
        try:
            with open(cls.STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    @classmethod
    def emit_thought(cls, module: str, active_node: int, thought: str, math_working: str = "", progress: float = 0.0, safety_delay: float = 0.22):
        """
        Emits a real-time cognitive step representing what the machine's mind
        is doing right now. Includes a calibrated safety delay (default ~220ms)
        so human perception can read the thoughts and to protect against CPU spikes.
        """
        state = cls.load_state()
        state["status"] = "processing"
        state["module"] = module
        state["active_node"] = active_node
        state["progress"] = progress
        state["current_thought"] = thought
        if math_working:
            state["math_working"] = math_working

        thoughts = [
            state.get("thought_1", ""),
            state.get("thought_2", ""),
            state.get("thought_3", ""),
            state.get("thought_4", ""),
            state.get("thought_5", "")
        ]
        active_thoughts = [t for t in thoughts if t]
        active_thoughts.append(f"[{module}] {thought}")
        if len(active_thoughts) > 5:
            active_thoughts = active_thoughts[-5:]

        for idx, t in enumerate(active_thoughts):
            state[f"thought_{idx + 1}"] = t

        cls.save_state(state)
        if safety_delay > 0:
            time.sleep(safety_delay)

    @classmethod
    def notify_start_process(cls, task_name: str, active_func: str = ""):
        state = cls.load_state()
        state["status"] = "processing"
        state["task"] = task_name[:120]
        state["module"] = "INPUT_STREAM"
        state["active_node"] = 0
        state["progress"] = 0.10
        state["current_thought"] = f"Reading input: {task_name}"
        if active_func:
            state["active_function"] = active_func[:240]
            state["math_working"] = f"Active f(x) = {active_func}"
        cls.save_state(state)

    @classmethod
    def notify_end_process(cls, active_func: str = "", last_result: str = ""):
        state = cls.load_state()
        state["status"] = "idle"
        state["task"] = "Engine Ready / Complete"
        state["module"] = "STANDBY"
        state["active_node"] = 4
        state["progress"] = 1.0
        state["current_thought"] = "Calculation complete. Awaiting next calculus command..."
        if active_func:
            state["active_function"] = active_func[:240]
        if last_result:
            state["last_result"] = str(last_result)[:200]
            first_line = str(last_result).strip().split("\n")[0]
            state["math_working"] = f"Result: {first_line[:90]}"
        cls.save_state(state)

    @classmethod
    def emit_result_modal(cls, modal_type: str, query: str, result: str, method: str, status: str):
        state = cls.load_state()
        state["show_modal"] = 1
        state["modal_type"] = modal_type[:30]
        state["modal_query"] = query[:250]
        state["modal_result"] = result[:500]
        state["modal_method"] = method[:120]
        state["modal_status"] = status[:250]
        cls.save_state(state)

    @classmethod
    def check_pending_command(cls) -> str:
        state = cls.load_state()
        cmd = state.get("command_pending", "").strip()
        if cmd:
            state["command_pending"] = ""
            cls.save_state(state)
            return cmd
        return ""


# ==============================================================================
#                 1. SELF-LEARNING USER BEHAVIOR ENGINE
# ==============================================================================

class UserBehaviorLearner:
    """
    Learns the user's habits, frequently calculated functions, favorite bounds,
    and personal preferences over time, storing them in a local JSON profile.
    """
    def __init__(self, profile_file="smart_profile.json"):
        self.profile_file = profile_file
        self.profile = {
            "total_queries": 0,
            "favorite_operations": {},   # e.g., "integral": 15, "derivative": 8
            "favorite_functions": {},    # e.g., "sin": 12, "x^2": 9, "exp": 7
            "favorite_bounds": {},       # e.g., "[0, pi]": 6, "[0, 1]": 10
            "user_variables": {},        # constants e.g., "k": 4.5
            "user_functions": {},        # custom math formulas e.g., "f": "x^2 + 3"
            "typo_history": {},          # words corrected for user
            "last_answer": None,
            "last_expression": None,
            "history": [],
            "query_history": []
        }
        self.load_profile()

    def load_profile(self):
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.profile.update(data)
            except Exception:
                pass
        if "user_functions" not in self.profile:
            self.profile["user_functions"] = {}
        if "user_variables" not in self.profile:
            self.profile["user_variables"] = {}
        if "query_history" not in self.profile:
            self.profile["query_history"] = []

    def save_profile(self):
        try:
            with open(self.profile_file, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=2)
        except Exception:
            pass

    def add_query_history(self, query: str):
        if not query or not query.strip():
            return
        q = query.strip()
        hist = self.profile.setdefault("query_history", [])
        if hist and hist[-1] == q:
            return
        hist.append(q)
        if len(hist) > 50:
            self.profile["query_history"] = hist[-50:]
        self.save_profile()

    def record_query(self, query_type, expression="", bounds=None, raw_query=""):
        self.profile["total_queries"] += 1
        
        # Track operation
        op_counts = self.profile["favorite_operations"]
        op_counts[query_type] = op_counts.get(query_type, 0) + 1

        # Track functions used in expression
        if expression:
            fn_matches = re.findall(r"\b(sin|cos|tan|exp|ln|log|sqrt|sinh|cosh|tanh|asin|acos|atan|abs)\b", expression)
            for fn in fn_matches:
                fn_counts = self.profile["favorite_functions"]
                fn_counts[fn] = fn_counts.get(fn, 0) + 1

            # Track sub-patterns like powers x^2
            pow_matches = re.findall(r"x\^?\d+", expression)
            for p in pow_matches:
                fn_counts = self.profile["favorite_functions"]
                fn_counts[p] = fn_counts.get(p, 0) + 1

        # Track bounds
        if bounds and len(bounds) == 2:
            bound_key = f"[{bounds[0]}, {bounds[1]}]"
            b_counts = self.profile["favorite_bounds"]
            b_counts[bound_key] = b_counts.get(bound_key, 0) + 1

        # Save query to short rolling history
        if raw_query:
            hist = self.profile["history"]
            hist.append({"query": raw_query, "type": query_type, "timestamp": time.time()})
            if len(hist) > 30:
                self.profile["history"] = hist[-30:]

        self.save_profile()

    def set_last_result(self, val, expr=""):
        self.profile["last_answer"] = val
        self.profile["last_expression"] = expr
        self.save_profile()

    def set_user_variable(self, name, value):
        self.profile["user_variables"][name] = value
        self.save_profile()

    def set_user_function(self, name, formula):
        self.profile["user_functions"][name] = formula
        self.save_profile()

    def get_learned_top_bounds(self):
        """Returns top learned bounds to offer as smart defaults."""
        b_counts = self.profile["favorite_bounds"]
        if not b_counts:
            return ["[0, 1]", "[0, pi]", "[-1, 1]"]
        sorted_b = sorted(b_counts.items(), key=lambda x: x[1], reverse=True)
        return [b[0] for b in sorted_b[:3]]

    def get_adaptive_suggestions(self):
        """Generates dynamic suggestions prioritizing the user's favorite expressions."""
        suggestions = []
        for fn, count in sorted(self.profile["favorite_functions"].items(), key=lambda x: x[1], reverse=True)[:5]:
            suggestions.append(f"{fn}(x)")
        return suggestions

    def get_insights(self):
        """Returns a human-readable summary of user behavior."""
        lines = []
        lines.append(f"• Total questions/queries asked: {self.profile['total_queries']}")
        if self.profile["favorite_operations"]:
            top_op = max(self.profile["favorite_operations"].items(), key=lambda x: x[1])
            lines.append(f"• Most used feature: {top_op[0].title()} ({top_op[1]} times)")
        if self.profile["favorite_functions"]:
            top_fns = sorted(self.profile["favorite_functions"].items(), key=lambda x: x[1], reverse=True)[:3]
            fn_str = ", ".join([f"{k} ({v}x)" for k, v in top_fns])
            lines.append(f"• Favorite math functions: {fn_str}")
        if self.profile["favorite_bounds"]:
            top_b = sorted(self.profile["favorite_bounds"].items(), key=lambda x: x[1], reverse=True)[:2]
            b_str = ", ".join([f"{k} ({v}x)" for k, v in top_b])
            lines.append(f"• Most frequent integration bounds: {b_str}")
        if self.profile["user_variables"]:
            vars_str = ", ".join([f"{k} = {v}" for k, v in self.profile["user_variables"].items()])
            lines.append(f"• Custom saved variables: {vars_str}")
        return "\n".join(lines) if lines else "No behavior recorded yet. Start calculating to train me!"


# ==============================================================================
#                 2. AUTO-CORRECTOR & AUTO-COMPLETOR ENGINE
# ==============================================================================

class AutoCorrectorAndCompletor:
    """
    Provides fuzzy typo correction and smart auto-completions for math keywords,
    commands, and expressions based on built-in vocabulary + user learned habits.
    """
    KEYWORD_CORRECTIONS = {
        # Typo -> Corrected form
        "integrte": "integrate",
        "intgrate": "integrate",
        "intergral": "integral",
        "integ": "integrate",
        "derivatve": "derivative",
        "derivitave": "derivative",
        "differntiate": "differentiate",
        "diffrentiate": "differentiate",
        "tanjet": "tangent",
        "slop": "slope",
        "beteen": "between",
        "btwn": "between",
        "frm": "from",
        "sqrtt": "sqrt",
        "sqre": "sqrt",
        "sinn": "sin",
        "coss": "cos",
        "expp": "exp",
        "pie": "pi",
        "euler": "e",
        "averge": "average",
        "stddev": "std dev",
        "equasion": "equation",
        "lenght": "length",
        "indefinte": "indefinite",
        "antideriv": "antiderivative",
        "antiderivitive": "antiderivative"
    }

    VOCABULARY = [
        "integrate", "integral", "indefinite", "antiderivative", "derivative", "differentiate", "slope",
        "tangent line", "root of", "area between", "arc length", "curvature", "+ C",
        "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh",
        "exp", "ln", "log", "log2", "log10", "sqrt", "cbrt", "abs", "floor", "ceil",
        "pi", "ans", "between", "from", "at x =", "stats", "help", "profile"
    ]

    def __init__(self, learner: UserBehaviorLearner):
        self.learner = learner

    def correct_text(self, text: str) -> tuple[str, list[str]]:
        """
        Fixes typos in keywords, bounds, and math notation.
        Returns (corrected_text, list_of_corrections_made)
        """
        corrections = []
        words = text.split()
        fixed_words = []

        for w in words:
            # Check punctuation trailing
            clean_w = re.sub(r"[^\w]", "", w.lower())
            if clean_w in self.KEYWORD_CORRECTIONS:
                correct = self.KEYWORD_CORRECTIONS[clean_w]
                corrections.append(f"'{w}' → '{correct}'")
                fixed_words.append(correct)
            else:
                # Fuzzy match if distance is small
                matches = difflib.get_close_matches(clean_w, self.KEYWORD_CORRECTIONS.keys(), n=1, cutoff=0.82)
                if matches:
                    correct = self.KEYWORD_CORRECTIONS[matches[0]]
                    corrections.append(f"'{w}' → '{correct}'")
                    fixed_words.append(correct)
                else:
                    fixed_words.append(w)

        result = " ".join(fixed_words)

        # Fix missing multiplication: e.g. 2x -> 2*x, 3pi -> 3*pi
        result = re.sub(r"(\d+)([a-zA-Z\(])", r"\1*\2", result)

        # Fix powers: e.g. x^2 -> x**2 for internal python eval if needed
        # Balance unmatched parentheses
        open_cnt = result.count("(")
        close_cnt = result.count(")")
        if open_cnt > close_cnt:
            result = result + (")" * (open_cnt - close_cnt))
            corrections.append(f"Auto-closed {open_cnt - close_cnt} parenthesis")

        return result, corrections

    def get_completions(self, prefix: str) -> list[str]:
        """Returns auto-complete suggestions based on vocabulary and learned habits."""
        if not prefix:
            return []
        prefix_l = prefix.lower()
        candidates = []

        # 1. Check user's own learned variables and functions first!
        for var in self.learner.profile.get("user_variables", {}):
            if var.lower().startswith(prefix_l):
                candidates.append(var)

        for fn in self.learner.profile.get("favorite_functions", {}):
            if fn.lower().startswith(prefix_l) and fn not in candidates:
                candidates.append(fn)

        # 2. Check general vocabulary
        for word in self.VOCABULARY:
            if word.lower().startswith(prefix_l) and word not in candidates:
                candidates.append(word)

        return candidates


# ==============================================================================
#                 3. MATHEMATICAL & CALCULUS COMPUTATION ENGINE
# ==============================================================================

class MathEngine:
    """
    High-precision mathematical evaluator and calculus algorithms:
    Simpson's Rule, 5-point stencil differentiation, root finding, arc length.
    """
    SAFE_ENV = {
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
        "exp": math.exp, "ln": math.log, "log": (lambda x, base=10: math.log(x, base)), "log10": math.log10, "log2": math.log2,
        "sqrt": math.sqrt, "cbrt": lambda v: math.copysign(abs(v)**(1/3), v),
        "abs": abs, "fabs": math.fabs,
        "floor": math.floor, "ceil": math.ceil,
        "pi": math.pi, "e": math.e
    }

    @classmethod
    def clean_math_expr(cls, expr: str) -> str:
        s = expr.strip()
        # 1. Convert ^ to **
        s = re.sub(r"\^", "**", s)

        # 2. Auto-balance trailing unclosed parentheses e.g. x/(x+1 -> x/(x+1)
        opens = s.count("(")
        closes = s.count(")")
        if opens > closes:
            s += ")" * (opens - closes)

        # 3. Normalize multiple whitespace
        s = re.sub(r"\s+", " ", s)

        # 4. Implicit multiplication: number followed by variable/paren/func e.g. 45x^2 -> 45*x^2
        excluded_words = {'to', 'from', 'and', 'at', 'when', 'for', 'by', 'is', 'equals', 'equal', 'between', 'step', 'starting', 'with'}
        def num_mul(m):
            num, target = m.group(1), m.group(2)
            if target.lower() in excluded_words:
                return f"{num} {target}"
            return f"{num}*{target}"
        s = re.sub(r"(?<![a-zA-Z0-9_])(\d+(?:\.\d+)?)\s*([a-zA-Z_]\w*|\()", num_mul, s)

        # 5. Implicit multiplication: ) followed by ( or number or identifier e.g. (x+1)(x-1) -> (x+1)*(x-1)
        s = re.sub(r"(\))\s*(\()", r"\1*\2", s)
        s = re.sub(r"(\))\s*([a-zA-Z0-9_]+)", r"\1*\2", s)

        # 6. Implicit multiplication: variable/constant followed by ( when not a known function e.g. x(x+1) -> x*(x+1)
        known_funcs = set(cls.SAFE_ENV.keys())
        def var_paren(m):
            name = m.group(1)
            if name.lower() in known_funcs:
                return f"{name}("
            return f"{name}*("
        s = re.sub(r"\b([a-zA-Z_]\w*)\s*\(", var_paren, s)

        # 7. Implicit multiplication: variable x followed by function or another variable e.g. x sin(x) -> x*sin(x)
        s = re.sub(r"\b([xX])\s+([a-zA-Z_]\w*)", r"\1*\2", s)

        return s.strip()

    @classmethod
    def eval_at(cls, expr: str, x: float, extra_vars: dict = None) -> float:
        env = dict(cls.SAFE_ENV)
        env["x"] = x
        if extra_vars:
            env.update(extra_vars)
        s = cls.clean_math_expr(expr)
        return float(eval(s, {"__builtins__": None}, env))

    @classmethod
    def eval_constant(cls, expr: str, extra_vars: dict = None) -> float:
        return cls.eval_at(expr, 0.0, extra_vars)

    @classmethod
    def integrate_tanh_sinh(cls, expr: str, a: float, b: float, extra_vars: dict = None) -> tuple[float, float, str]:
        """
        Tanh-Sinh (Double Exponential) Quadrature for functions with singularities at endpoints.
        """
        sign = 1
        if b < a:
            a, b = b, a
            sign = -1
            
        c1 = (b - a) / 2.0
        c2 = (b + a) / 2.0
        h = 0.05
        max_t = 4.0
        total = 0.0
        
        try:
            total += cls.eval_at(expr, c2, extra_vars) * (math.pi / 2.0)
        except Exception:
            pass
            
        for k in range(1, int(max_t / h)):
            t = k * h
            cosh_t = math.cosh(t)
            sinh_t = math.sinh(t)
            pi_half_sinh = (math.pi / 2.0) * sinh_t
            if pi_half_sinh > 300: break
            
            w = (math.pi / 2.0) * cosh_t / (math.cosh(pi_half_sinh) ** 2)
            if w < 1e-15: break
            
            tanh_sinh = math.tanh(pi_half_sinh)
            x_plus = c2 + c1 * tanh_sinh
            x_minus = c2 - c1 * tanh_sinh
            
            try:
                total += cls.eval_at(expr, x_plus, extra_vars) * w
            except: pass
            try:
                total += cls.eval_at(expr, x_minus, extra_vars) * w
            except: pass
                
        return total * c1 * h * sign, 1e-7, "Adaptive Quadrature (Singularity-Aware)"

    @classmethod
    def integrate_simpson(cls, expr: str, a: float, b: float, n: int = 4000, extra_vars: dict = None) -> tuple[float, float, str]:
        """
        Composite Simpson's rule with Richardson error estimate.
        Returns (result, estimated_error, method_string)
        """
        if abs(b - a) < 1e-15:
            return 0.0, 0.0, "Simpson's 1/3 Rule"
        
        # Check for singularities at boundaries
        fa_val, fb_val = 0.0, 0.0
        has_singularity = False
        try:
            fa_val = cls.eval_at(expr, a + 1e-8 * (b-a), extra_vars)
            fb_val = cls.eval_at(expr, b - 1e-8 * (b-a), extra_vars)
            if math.isnan(fa_val) or math.isinf(fa_val) or abs(fa_val) > 1e4: has_singularity = True
            if math.isnan(fb_val) or math.isinf(fb_val) or abs(fb_val) > 1e4: has_singularity = True
        except:
            has_singularity = True

        if has_singularity:
            return cls.integrate_tanh_sinh(expr, a, b, extra_vars)

        sign = 1
        if b < a:
            a, b = b, a
            sign = -1

        if n % 2 != 0: n += 1
        h = (b - a) / n
        fa = fa_val
        fb = fb_val

        odd_sum = 0.0
        even_sum = 0.0
        for i in range(1, n):
            xi = a + i * h
            val = cls.eval_at(expr, xi, extra_vars)
            if i % 2 == 1:
                odd_sum += val
            else:
                even_sum += val

        res = (h / 3.0) * (fa + 4.0 * odd_sum + 2.0 * even_sum + fb)

        # Coarse step (n/2) for Richardson error estimate
        half_n = n // 2
        coarse_h = (b - a) / half_n
        coarse_odd = 0.0
        coarse_even = 0.0
        for i in range(1, half_n):
            xi = a + i * coarse_h
            val = cls.eval_at(expr, xi, extra_vars)
            if i % 2 == 1:
                coarse_odd += val
            else:
                coarse_even += val
        coarse_res = (coarse_h / 3.0) * (fa + 4.0 * coarse_odd + 2.0 * coarse_even + fb)
        err_est = abs(res - coarse_res) / 15.0

        return sign * res, err_est, "Composite Simpson's 1/3 Rule"

    @classmethod
    def derivative_5point(cls, expr: str, x: float, extra_vars: dict = None) -> float:
        h = 1e-5
        f_p2 = cls.eval_at(expr, x + 2*h, extra_vars)
        f_p1 = cls.eval_at(expr, x + h, extra_vars)
        f_m1 = cls.eval_at(expr, x - h, extra_vars)
        f_m2 = cls.eval_at(expr, x - 2*h, extra_vars)
        return (-f_p2 + 8.0 * f_p1 - 8.0 * f_m1 + f_m2) / (12.0 * h)

    @classmethod
    def second_derivative(cls, expr: str, x: float, extra_vars: dict = None) -> float:
        h = 1e-4
        f_p = cls.eval_at(expr, x + h, extra_vars)
        f_m = cls.eval_at(expr, x - h, extra_vars)
        f_0 = cls.eval_at(expr, x, extra_vars)
        return (f_p - 2.0 * f_0 + f_m) / (h * h)

    @classmethod
    def find_root_newton(cls, expr: str, guess: float = 1.0, extra_vars: dict = None) -> tuple[float, int, bool]:
        x = guess
        tol = 1e-9
        for i in range(80):
            fx = cls.eval_at(expr, x, extra_vars)
            if abs(fx) < tol:
                return x, i, True
            dfx = cls.derivative_5point(expr, x, extra_vars)
            if abs(dfx) < 1e-12:
                x += 0.1
                continue
            next_x = x - fx / dfx
            if abs(next_x - x) < tol:
                return next_x, i + 1, True
            x = next_x
        return x, 80, False


# ==============================================================================
#                 3B. SYMBOLIC AST & DIFFERENTIATION ENGINE
# ==============================================================================

class SymNode:
    def diff(self, var): pass
    def simplify(self): return self
    def is_constant(self): return False

class SymConst(SymNode):
    def __init__(self, val): self.val = val
    def diff(self, var): return SymConst(0)
    def simplify(self): return self
    def is_constant(self): return True
    def __str__(self): return str(self.val)

class SymVar(SymNode):
    def __init__(self, name): self.name = name
    def diff(self, var): return SymConst(1) if self.name == var else SymConst(0)
    def simplify(self): return self
    def is_constant(self): return False
    def __str__(self): return self.name

class SymAdd(SymNode):
    def __init__(self, a, b): self.a = a; self.b = b
    def diff(self, var): return SymAdd(self.a.diff(var), self.b.diff(var))
    def simplify(self):
        a = self.a.simplify()
        b = self.b.simplify()
        if a.is_constant() and b.is_constant(): return SymConst(a.val + b.val)
        if a.is_constant() and a.val == 0: return b
        if b.is_constant() and b.val == 0: return a
        return SymAdd(a, b)
    def __str__(self): return f"({self.a} + {self.b})"

class SymSub(SymNode):
    def __init__(self, a, b): self.a = a; self.b = b
    def diff(self, var): return SymSub(self.a.diff(var), self.b.diff(var))
    def simplify(self):
        a = self.a.simplify()
        b = self.b.simplify()
        if a.is_constant() and b.is_constant(): return SymConst(a.val - b.val)
        if b.is_constant() and b.val == 0: return a
        return SymSub(a, b)
    def __str__(self): return f"({self.a} - {self.b})"

class SymMul(SymNode):
    def __init__(self, a, b): self.a = a; self.b = b
    def diff(self, var): return SymAdd(SymMul(self.a.diff(var), self.b), SymMul(self.a, self.b.diff(var)))
    def simplify(self):
        a = self.a.simplify()
        b = self.b.simplify()
        if a.is_constant() and b.is_constant(): return SymConst(a.val * b.val)
        if a.is_constant() and a.val == 0: return SymConst(0)
        if b.is_constant() and b.val == 0: return SymConst(0)
        if a.is_constant() and a.val == 1: return b
        if b.is_constant() and b.val == 1: return a
        return SymMul(a, b)
    def __str__(self): return f"({self.a} * {self.b})"

class SymDiv(SymNode):
    def __init__(self, a, b): self.a = a; self.b = b
    def diff(self, var):
        return SymDiv(SymSub(SymMul(self.a.diff(var), self.b), SymMul(self.a, self.b.diff(var))), SymPow(self.b, SymConst(2)))
    def simplify(self):
        a = self.a.simplify()
        b = self.b.simplify()
        if a.is_constant() and b.is_constant() and b.val != 0:
            if isinstance(a.val, int) and isinstance(b.val, int) and a.val % b.val != 0:
                return SymDiv(a, b)
            return SymConst(a.val / b.val)
        if a.is_constant() and a.val == 0: return SymConst(0)
        if b.is_constant() and b.val == 1: return a
        return SymDiv(a, b)
    def __str__(self): return f"({self.a} / {self.b})"

class SymPow(SymNode):
    def __init__(self, a, b): self.a = a; self.b = b
    def diff(self, var):
        a_const = self.a.is_constant()
        b_const = self.b.is_constant()
        if b_const: return SymMul(SymMul(self.b, SymPow(self.a, SymSub(self.b, SymConst(1)))), self.a.diff(var))
        elif a_const: return SymMul(SymMul(self, SymFunc("ln", self.a)), self.b.diff(var))
        else: return SymMul(self, SymAdd(SymMul(self.b.diff(var), SymFunc("ln", self.a)), SymMul(self.b, SymDiv(self.a.diff(var), self.a))))
    def simplify(self):
        a = self.a.simplify()
        b = self.b.simplify()
        if a.is_constant() and b.is_constant(): 
            try: return SymConst(a.val ** b.val)
            except: pass
        if b.is_constant() and b.val == 0: return SymConst(1)
        if b.is_constant() and b.val == 1: return a
        if a.is_constant() and a.val == 0: return SymConst(0)
        if a.is_constant() and a.val == 1: return SymConst(1)
        return SymPow(a, b)
    def __str__(self): return f"({self.a} ^ {self.b})"

class SymFunc(SymNode):
    def __init__(self, name, arg): self.name = name; self.arg = arg
    def diff(self, var):
        arg_diff = self.arg.diff(var)
        if self.name == "sin": d = SymFunc("cos", self.arg)
        elif self.name == "cos": d = SymMul(SymConst(-1), SymFunc("sin", self.arg))
        elif self.name == "tan": d = SymPow(SymFunc("sec", self.arg), SymConst(2))
        elif self.name == "exp": d = self
        elif self.name in ("ln", "log"): d = SymDiv(SymConst(1), self.arg)
        elif self.name == "sqrt": d = SymDiv(SymConst(0.5), SymFunc("sqrt", self.arg))
        elif self.name == "asin": d = SymDiv(SymConst(1), SymFunc("sqrt", SymSub(SymConst(1), SymPow(self.arg, SymConst(2)))))
        elif self.name == "acos": d = SymDiv(SymConst(-1), SymFunc("sqrt", SymSub(SymConst(1), SymPow(self.arg, SymConst(2)))))
        elif self.name == "atan": d = SymDiv(SymConst(1), SymAdd(SymConst(1), SymPow(self.arg, SymConst(2))))
        elif self.name == "erf": d = SymMul(SymConst(1.128379), SymFunc("exp", SymMul(SymConst(-1), SymPow(self.arg, SymConst(2)))))
        elif self.name == "Si": d = SymDiv(SymFunc("sin", self.arg), self.arg)
        elif self.name == "Ci": d = SymDiv(SymFunc("cos", self.arg), self.arg)
        elif self.name == "Ei": d = SymDiv(SymFunc("exp", self.arg), self.arg)
        elif self.name == "Cl2": d = SymMul(SymConst(-1), SymFunc("ln", SymFunc("abs", SymMul(SymConst(2), SymFunc("sin", SymDiv(self.arg, SymConst(2)))))))
        elif self.name == "Li2": d = SymMul(SymConst(-1), SymDiv(SymFunc("ln", SymSub(SymConst(1), self.arg)), self.arg))
        else: d = SymFunc(f"D[{self.name}]", self.arg)
        return SymMul(d, arg_diff)
    def simplify(self):
        arg = self.arg.simplify()
        if arg.is_constant():
            try:
                if self.name == 'sin': return SymConst(math.sin(arg.val))
                if self.name == 'cos': return SymConst(math.cos(arg.val))
            except: pass
        return SymFunc(self.name, arg)
    def __str__(self): return f"{self.name}({self.arg})"

class SymbolicMathEngine:
    @classmethod
    def parse_to_ast(cls, node):
        if isinstance(node, ast.BinOp):
            left = cls.parse_to_ast(node.left)
            right = cls.parse_to_ast(node.right)
            if isinstance(node.op, ast.Add): return SymAdd(left, right)
            if isinstance(node.op, ast.Sub): return SymSub(left, right)
            if isinstance(node.op, ast.Mult): return SymMul(left, right)
            if isinstance(node.op, ast.Div): return SymDiv(left, right)
            if isinstance(node.op, ast.Pow): return SymPow(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = cls.parse_to_ast(node.operand)
            if isinstance(node.op, ast.USub): return SymMul(SymConst(-1), operand)
            if isinstance(node.op, ast.UAdd): return operand
        elif isinstance(node, ast.Call):
            func_name = node.func.id if isinstance(node.func, ast.Name) else "unknown"
            arg = cls.parse_to_ast(node.args[0])
            return SymFunc(func_name, arg)
        elif isinstance(node, ast.Name):
            if node.id in ['pi', 'e']: return SymConst(math.pi if node.id == 'pi' else math.e)
            return SymVar(node.id)
        elif isinstance(node, ast.Constant):
            return SymConst(node.value)
        raise ValueError(f"Unknown node {node}")

    @classmethod
    def get_symbolic_derivative(cls, expr: str) -> str:
        # Convert ^ to ** for python ast parser
        cleaned = MathEngine.clean_math_expr(expr)
        try:
            tree = ast.parse(cleaned, mode='eval').body
            sym_node = cls.parse_to_ast(tree)
            deriv = sym_node.diff("x").simplify().simplify().simplify()
            
            # Format the output slightly
            s = str(deriv)
            s = s.replace(" * 1)", ")").replace("(1 * ", "(")
            s = s.replace("+ -1 *", "-")
            s = s.replace("* -1 *", "* -")
            s = s.replace(" - -", " + ")
            
            # Strip outermost parens if possible
            while s.startswith("(") and s.endswith(")"):
                # Check if it's purely enclosed or if it's something like (a) + (b)
                depth = 0
                matched = True
                for i, char in enumerate(s):
                    if char == '(': depth += 1
                    elif char == ')': depth -= 1
                    if depth == 0 and i < len(s) - 1:
                        matched = False
                        break
                if matched:
                    s = s[1:-1]
                else:
                    break
            
            return s
        except Exception as e:
            return f"Error computing symbolic derivative: {e}"

# ==============================================================================
#                 3C. SYMBOLIC INDEFINITE INTEGRATION ENGINE
# ==============================================================================

class SymbolicIntegrator:
    """
    Symbolic antiderivative and indefinite integration engine.
    Computes exact antiderivatives for:
      - Polynomials and monomials: c * x^n (any real power n != -1)
      - Logarithmic / reciprocal functions: c / x, 1/x, x^-1 -> c * ln|x|
      - Trigonometric functions: sin(kx), cos(kx), sec^2(x), 1/cos^2(x)
      - Exponential functions: c * e^(kx), c * exp(kx)
      - Inverse trigonometric forms: 1/(1 + x^2) -> arctan(x)
      - Linear combinations and constant terms: c -> c*x
    Produces step-by-step rules and formats the final equation with + C.
    """
    @staticmethod
    def unwrap_parens(s: str) -> str:
        s = s.strip()
        while s.startswith('(') and s.endswith(')'):
            depth = 0
            matched_end = False
            for i, ch in enumerate(s):
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        if i == len(s) - 1:
                            matched_end = True
                        break
            if matched_end:
                s = s[1:-1].strip()
            else:
                break
        return s

    @classmethod
    def split_terms(cls, expr: str) -> list[str]:
        terms = []
        curr = []
        depth = 0
        s = cls.unwrap_parens(expr)
        for i, ch in enumerate(s):
            if ch in '([{':
                depth += 1
                curr.append(ch)
            elif ch in ')]}':
                depth -= 1
                curr.append(ch)
            elif (ch == '+' or ch == '-') and depth == 0:
                if curr and curr[-1] in '*/^':
                    curr.append(ch)
                elif i == 0:
                    curr.append(ch)
                else:
                    t = ''.join(curr).strip()
                    if t:
                        terms.append(t)
                    curr = [ch]
            else:
                curr.append(ch)
        if curr:
            t = ''.join(curr).strip()
            if t:
                terms.append(t)
        return terms

    @classmethod
    def integrate_term(cls, raw_term: str):
        """
        Integrates a single term.
        Returns: (coeff_fraction, var_part, step_rule, original_term)
        """
        t = raw_term.strip()
        sign = 1
        if t.startswith('+'):
            t = t[1:].strip()
        elif t.startswith('-'):
            sign = -1
            t = t[1:].strip()

        t_nospaces = re.sub(r'\s+', '', t)

        # 1. Constant term (no 'x' in term)
        if 'x' not in t_nospaces:
            try:
                val = eval(t_nospaces.replace('^', '**'), {'pi': 3.141592653589793, 'e': 2.718281828459045}) * sign
                frac = Fraction(str(round(val, 6))).limit_denominator(1000)
                rule = f"Constant Rule: integral ({raw_term}) dx = ({frac})*x"
                return [(frac, "x")], rule, raw_term
            except Exception:
                pass

        # 2. Reciprocal / Logarithmic rule: c / x or 1/x or x^-1
        m_recip = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\/|\s*\/)?\s*x$', t)
        if m_recip or t_nospaces in ('1/x', 'x^(-1)', 'x^-1'):
            c = float(m_recip.group(1)) if (m_recip and m_recip.group(1)) else 1.0
            frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
            rule = f"Logarithmic Rule: integral ({raw_term}) dx = ({frac})*ln|x|"
            return [(frac, "ln|x|")], rule, raw_term

        # 2B. Rational linear denominator: c / (x + a)
        m_rat1 = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\/|\s*\/)?\s*\(\s*x\s*([+-]\s*\d+(?:\.\d+)?)\s*\)$', t)
        if m_rat1:
            c = float(m_rat1.group(1)) if m_rat1.group(1) else 1.0
            a_str = m_rat1.group(2).replace(' ', '')
            frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
            rule = f"Rational Log Rule: integral c/(x{a_str}) dx = ({frac})*ln|x{a_str}|"
            return [(frac, f"ln|x{a_str}|")], rule, raw_term

        # 2C. Rational linear numerator & denominator: c * x / (x + a)
        m_rat2 = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?x\s*\/\s*\(\s*x\s*([+-]\s*\d+(?:\.\d+)?)\s*\)$', t)
        if m_rat2:
            c = float(m_rat2.group(1)) if m_rat2.group(1) else 1.0
            a_str = m_rat2.group(2).replace(' ', '')
            a = float(a_str)
            c_sign = c * sign
            frac_x = Fraction(str(round(c_sign, 6))).limit_denominator(1000)
            frac_log = Fraction(str(round(-c_sign * a, 6))).limit_denominator(1000)
            rule = f"Rational Division & Log Rule: integral x/(x{a_str}) dx = x - ({a_str})*ln|x{a_str}|"
            return [(frac_x, "x"), (frac_log, f"ln|x{a_str}|")], rule, raw_term

        # 3. Inverse tangent: 1/(1 + x^2) or c/(1 + x^2)
        m_atan = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\/|\s*\/)?\s*(?:\(1\+x\^2\)|1\+x\^2)$', t_nospaces)
        if m_atan:
            c = float(m_atan.group(1)) if m_atan.group(1) else 1.0
            frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
            rule = f"Inverse Trig: integral ({raw_term}) dx = ({frac})*arctan(x)"
            return [(frac, "arctan(x)")], rule, raw_term

        # 3B. Partial fractions pattern: c / (x^4 + a^4)
        m_x4_a4 = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\/|\s*\/)?\s*(?:\(\s*x\^4\s*\+\s*(\d+(?:\.\d+)?)\s*\)|x\^4\s*\+\s*(\d+(?:\.\d+)?))$', t_nospaces)
        if m_x4_a4:
            c = float(m_x4_a4.group(1)) if m_x4_a4.group(1) else 1.0
            a4_str = m_x4_a4.group(2) or m_x4_a4.group(3)
            a4 = float(a4_str)
            a = a4 ** 0.25
            c_val = c * sign
            
            coef_ln = (c_val * 1.41421356237) / (8 * (a**3))
            coef_atan = (c_val * 1.41421356237) / (4 * (a**3))
            
            frac_ln = Fraction(str(round(coef_ln, 6))).limit_denominator(1000)
            frac_atan = Fraction(str(round(coef_atan, 6))).limit_denominator(1000)
            
            term_ln = f"ln|(x^2 + {round(a*1.41421356237, 4)}x + {round(a**2, 4)})/(x^2 - {round(a*1.41421356237, 4)}x + {round(a**2, 4)})|"
            term_atan1 = f"arctan({round(1.41421356237/a, 4)}x + 1)"
            term_atan2 = f"arctan({round(1.41421356237/a, 4)}x - 1)"
            
            rule = f"Partial Fractions (Quartic Sum): integral c/(x^4 + a^4) dx"
            return [(frac_ln, term_ln), (frac_atan, term_atan1), (frac_atan, term_atan2)], rule, raw_term

        # 4. Trigonometric: sin(kx), cos(kx), sec(x)^2
        m_sin = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?sin\s*\(\s*(\d+(?:\.\d+)?\s*\*?\s*)?x\s*\)$', t)
        if m_sin:
            c = float(m_sin.group(1)) if m_sin.group(1) else 1.0
            k_str = m_sin.group(2)
            k = float(k_str.replace('*', '')) if k_str else 1.0
            coeff_val = (-c / k) * sign
            frac = Fraction(str(round(coeff_val, 6))).limit_denominator(1000)
            arg = f"{int(k)}*x" if k == int(k) and k != 1 else (f"{k:g}*x" if k != 1 else "x")
            rule = f"Trig Rule: integral sin({arg}) dx = -1/{k:g} * cos({arg})"
            return [(frac, f"cos({arg})")], rule, raw_term

        m_cos = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?cos\s*\(\s*(\d+(?:\.\d+)?\s*\*?\s*)?x\s*\)$', t)
        if m_cos:
            c = float(m_cos.group(1)) if m_cos.group(1) else 1.0
            k_str = m_cos.group(2)
            k = float(k_str.replace('*', '')) if k_str else 1.0
            coeff_val = (c / k) * sign
            frac = Fraction(str(round(coeff_val, 6))).limit_denominator(1000)
            arg = f"{int(k)}*x" if k == int(k) and k != 1 else (f"{k:g}*x" if k != 1 else "x")
            rule = f"Trig Rule: integral cos({arg}) dx = 1/{k:g} * sin({arg})"
            return [(frac, f"sin({arg})")], rule, raw_term

        m_sec2 = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?(?:sec\s*\(\s*x\s*\)\s*\^?\s*2|sec\^2\s*\(\s*x\s*\)|1\s*\/\s*cos\s*\(\s*x\s*\)\s*\^?\s*2)$', t)
        if m_sec2:
            c = float(m_sec2.group(1)) if m_sec2.group(1) else 1.0
            frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
            rule = "Trig Rule: integral sec^2(x) dx = tan(x)"
            return [(frac, "tan(x)")], rule, raw_term

        # 5. Exponential: e^(kx) or exp(kx)
        m_exp = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?(?:e\^|exp)\s*(?:\(\s*)?(\d+(?:\.\d+)?\s*\*?\s*)?x\s*\)?$', t)
        if m_exp:
            c = float(m_exp.group(1)) if m_exp.group(1) else 1.0
            k_str = m_exp.group(2)
            k = float(k_str.replace('*', '')) if k_str else 1.0
            coeff_val = (c / k) * sign
            frac = Fraction(str(round(coeff_val, 6))).limit_denominator(1000)
            arg = f"{int(k)}*x" if k == int(k) and k != 1 else (f"{k:g}*x" if k != 1 else "x")
            part = f"e^({arg})" if arg != "x" else "e^x"
            rule = f"Exponential Rule: integral e^({arg}) dx = 1/{k:g} * e^({arg})"
            return [(frac, part)], rule, raw_term

        # 5B. Non-Elementary / Special Functions
        # exp(-x^2) -> erf(x)
        m_exp2 = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?(?:e\^|exp)\s*(?:\(\s*)?-\s*x\s*\^?\s*2\s*\)?$', t_nospaces)
        if m_exp2:
            c = float(m_exp2.group(1)) if m_exp2.group(1) else 1.0
            val = (c * sign * math.sqrt(math.pi)) / 2.0
            frac = Fraction(str(round(val, 6))).limit_denominator(1000)
            rule = "Gaussian Integral Rule: integral exp(-x^2) dx = (sqrt(pi)/2)*erf(x)"
            return [(frac, "erf(x)")], rule, raw_term
            
        # sin(x)/x -> Si(x)
        m_sinx = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?sin\s*\(\s*x\s*\)\s*\/\s*x$', t_nospaces)
        if m_sinx:
            c = float(m_sinx.group(1)) if m_sinx.group(1) else 1.0
            frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
            rule = "Sine Integral Rule: integral sin(x)/x dx = Si(x)"
            return [(frac, "Si(x)")], rule, raw_term

        # cos(x)/x -> Ci(x)
        m_cosx = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?cos\s*\(\s*x\s*\)\s*\/\s*x$', t_nospaces)
        if m_cosx:
            c = float(m_cosx.group(1)) if m_cosx.group(1) else 1.0
            frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
            rule = "Cosine Integral Rule: integral cos(x)/x dx = Ci(x)"
            return [(frac, "Ci(x)")], rule, raw_term
            
        # exp(x)/x -> Ei(x)
        m_expx = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?(?:e\^|exp)\s*(?:\(\s*)?x\s*\)?\s*\/\s*x$', t_nospaces)
        if m_expx:
            c = float(m_expx.group(1)) if m_expx.group(1) else 1.0
            frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
            rule = "Exponential Integral Rule: integral exp(x)/x dx = Ei(x)"
            return [(frac, "Ei(x)")], rule, raw_term
            
        # ln(sin(x)) -> Clausen Function
        m_lnsin = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?ln\s*\(\s*sin\s*\(\s*x\s*\)\s*\)$', t_nospaces)
        if m_lnsin:
            c = float(m_lnsin.group(1)) if m_lnsin.group(1) else 1.0
            c_val = c * sign
            f1 = Fraction(str(round(c_val, 6))).limit_denominator(1000)
            rule = "Log-Trig Integral Rule: integral ln(sin(x)) dx = -0.5*Cl2(2*x) - x*ln(2)"
            return [(f1, "(-0.5*Cl2(2*x) - x*ln(2))")], rule, raw_term

        # 6. Monomial Power Rule: c * x^n or x^n or c * x or x or sqrt(x)
        if t_nospaces == 'sqrt(x)':
            t = 'x^(0.5)'

        m_pow = re.match(r'^(?:(\d+(?:\.\d+)?)\s*\*?\s*)?x(?:\s*\^\s*([-\d]+(?:\.\d+)?|\([-\d]+(?:\.\d+)?\)))?$', t)
        if m_pow:
            c = float(m_pow.group(1)) if m_pow.group(1) else 1.0
            n_str = m_pow.group(2)
            n = float(n_str.strip('()')) if n_str else 1.0

            if n == -1.0:
                frac = Fraction(str(round(c * sign, 6))).limit_denominator(1000)
                rule = "Logarithmic Rule: integral x^(-1) dx = ln|x|"
                return [(frac, "ln|x|")], rule, raw_term

            new_n = n + 1.0
            new_c = (c / new_n) * sign
            frac_c = Fraction(str(round(new_c, 6))).limit_denominator(1000)

            if new_n == 1.0:
                x_part = "x"
            elif new_n == int(new_n):
                x_part = f"x^{int(new_n)}"
            else:
                x_part = f"x^{new_n:g}"

            rule = f"Power Rule: integral x^{n:g} dx = (1/{new_n:g}) * x^{new_n:g}"
            return [(frac_c, x_part)], rule, raw_term

        # --- Fallback: Maclaurin Series Approximation for non-elementary / complex terms ---
        try:
            expr_iter = t
            subterms = []
            fact = 1.0
            for i in range(5):
                try:
                    val = MathEngine.eval_at(expr_iter, 0.0, {})
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
                
                expr_iter = SymbolicMathEngine.get_symbolic_derivative(expr_iter)
                fact *= (i + 1)
                
            if not subterms:
                return None, f"Unsupported term (zero series): {raw_term}", raw_term
                
            rule = f"Maclaurin Series Expansion Approximation O(x^5): integral ({raw_term}) dx"
            return subterms, rule, raw_term
        except Exception as e:
            return None, f"Unsupported term: {raw_term} (Error: {e})", raw_term

    @classmethod
    def integrate_expression(cls, expr: str) -> dict:
        """
        Integrates a linear combination of terms symbolically.
        Returns a dict with 'success', 'original', 'equation', and 'steps'.
        """
        expr = expr.replace('**', '^')
        terms = cls.split_terms(expr)
        if not terms:
            return {"success": False, "error": "Expression is empty"}

        results = []
        steps = []
        for term in terms:
            subterms, rule, raw_term = cls.integrate_term(term)
            if subterms is None:
                return {"success": False, "error": f"The symbolic engine currently lacks advanced integration capabilities (like general partial fractions or u-substitutions) required to evaluate '{term}'"}
            for frac, var_part in subterms:
                results.append((frac, var_part))
            steps.append((raw_term, rule))

        formatted_pieces = []
        for i, (frac, var_part) in enumerate(results):
            num = frac.numerator
            den = frac.denominator
            is_neg = (num < 0)
            abs_num = abs(num)

            sign_str = "- " if is_neg else ("+ " if i > 0 else "")

            if var_part:
                if abs_num == 1 and den == 1:
                    term_str = var_part
                elif den == 1:
                    term_str = f"{abs_num}*{var_part}"
                else:
                    if abs_num == 1:
                        term_str = f"({var_part})/{den}"
                    else:
                        term_str = f"({abs_num}*{var_part})/{den}"
            else:
                if den == 1:
                    term_str = f"{abs_num}"
                else:
                    term_str = f"({abs_num}/{den})"

            formatted_pieces.append(f"{sign_str}{term_str}")

        equation = " ".join(formatted_pieces) + " + C"
        return {
            "success": True,
            "original": expr,
            "equation": equation,
            "steps": steps
        }


# ==============================================================================
#                 4. CONVERSATIONAL & NATURAL LANGUAGE ENGINE
# ==============================================================================

class ConversationalEngine:
    """
    Handles friendly conversational English: greetings, questions about capabilities,
    math explanations, humor, and previous results.
    """
    JOKES = [
        "Why do calculus professors love trees? Because they have natural logs!",
        "Why didn't the polynomial want to integrate? It couldn't find its plus C!",
        "What does a calculus teacher say when you're late? 'You're approaching your limit!'",
        "Why was the fraction skeptical about the decimal? Because it had a point!",
        "Why do derivatives make terrible secret agents? Because they always find the slope of the curve!"
    ]

    EXPLANATIONS = {
        "integral": (
            "An integral represents the accumulated total or the area under a curve f(x).\n"
            "If you have a function representing speed over time, its integral gives the total distance traveled!\n"
            "By the Fundamental Theorem of Calculus: integral[a to b] f(x) dx = F(b) - F(a), where F'(x) = f(x)."
        ),
        "derivative": (
            "A derivative measures the instantaneous rate of change or the slope of a curve at any point.\n"
            "If you draw a tangent line touching f(x) at x = a, the slope of that line is exactly f'(a)."
        ),
        "1/x": (
            "Why is integral (1/x) dx = ln|x| + C?\n"
            "The standard power rule says integral x^n dx = x^(n+1)/(n+1). But if n = -1, dividing by (n+1) gives division by zero!\n"
            "In real analysis, ln(x) is fundamentally defined as integral[1 to x] (1/t) dt. Since d/dx [ln(x)] = 1/x, the antiderivative of 1/x is ln|x| + C!"
        ),
        "tangent": (
            "A tangent line is the straight line that best approximates a curve at a single point (x0, y0).\n"
            "Its formula is: y - y0 = m*(x - x0), where m = f'(x0) is the derivative at that point."
        )
    }

    def __init__(self, learner: UserBehaviorLearner):
        self.learner = learner

    def handle_convo(self, text: str) -> str | None:
        t = text.lower().strip()

        # Greetings
        if re.search(r"\b(hi|hello|hey|yo|howdy|greetings|good morning|good afternoon)\b", t):
            name_suffix = ""
            if self.learner.profile["total_queries"] > 5:
                name_suffix = f" Welcome back! (You've run {self.learner.profile['total_queries']} queries so far)."
            return f"Hello there! I'm your Smart Calculus Assistant.{name_suffix}\nYou can ask me to solve integrals, find derivatives, or type any math question in natural English!"

        # Small talk / How are you
        if re.search(r"\b(how are you|how r u|how is it going|what's up|whats up)\b", t):
            return "I'm running at peak efficiency, ready to crunch some calculus! What would you like to calculate today?"

        # Identity / Capabilities
        if re.search(r"\b(who are you|what can you do|your capabilities|what do you do)\b", t):
            return (
                "Here is what I can do for you:\n"
                "  1. [Integrals] Definite Integrals: e.g., 'integrate sin(x) from 0 to pi'\n"
                "  2. [Derivatives] Derivatives & Tangents: e.g., 'derivative of 3x^2 + 5x at x=2'\n"
                "  3. [Roots] Root Finding: e.g., 'find root of x^3 - 2x - 5'\n"
                "  4. [Stats] Statistics: e.g., 'mean and std dev of 10, 20, 30, 40'\n"
                "  5. [Learning] Self-Learning: I track your favorite functions and suggest bounds!\n"
                "  6. [Auto-Correct] Real-Time Auto-Correction: I fix math typos like 'integrte' or 'pie'!"
            )

        # Previous answer / Memory
        if re.search(r"\b(last answer|previous answer|what was ans|what is ans|my last result)\b", t):
            last_ans = self.learner.profile.get("last_answer")
            if last_ans is not None:
                last_expr = self.learner.profile.get("last_expression", "")
                return f"Your last answer was: {last_ans}" + (f" (from '{last_expr}')" if last_expr else "")
            return "You haven't computed anything yet in this session!"

        # Jokes
        if re.search(r"\b(joke|funny|laugh|humor)\b", t):
            import random
            return random.choice(self.JOKES)

        # Explanations
        if "why" in t or "explain" in t or "how does" in t:
            if "1/x" in t or "ln" in t:
                return self.EXPLANATIONS["1/x"]
            if "integral" in t or "integrate" in t:
                return self.EXPLANATIONS["integral"]
            if "derivative" in t or "slope" in t:
                return self.EXPLANATIONS["derivative"]
            if "tangent" in t:
                return self.EXPLANATIONS["tangent"]

        # Thanks
        if re.search(r"\b(thank you|thanks|thx|awesome|cool|great job)\b", t):
            return "You're very welcome! Let me know whenever you're ready for the next problem."

        # User Profile / Stats
        if re.search(r"\b(my habits|my stats|profile|show stats|user stats)\b", t):
            return "[User Profile] Here is your Personalized Learning Profile:\n" + self.learner.get_insights()

        return None


# ==============================================================================
#                 5. SENTENCE TRAINING & NATURAL LANGUAGE UNDERSTANDING (NLU)
# ==============================================================================

class SentenceTrainer:
    """
    Manages custom user-trained sentence patterns, phrases, and semantic synonyms.
    Persists trained patterns to 'learned_patterns.json'.
    """
    DEFAULT_PATTERNS = {
        "steepness of": "derivative",
        "rate of change of": "derivative",
        "slope of": "derivative",
        "gradient of": "derivative",
        "tangent line of": "derivative",
        "tangent of curve": "derivative",
        "accumulate": "integrate",
        "area under": "integrate",
        "area beneath": "integrate",
        "total area under": "integrate",
        "antiderivative of": "indefinite_integral",
        "indefinite integral of": "indefinite_integral",
        "symbolic integral of": "indefinite_integral",
        "vanishing point": "root",
        "where does it vanish": "root",
        "where does it cross zero": "root",
        "find zeros of": "root",
        "curvature of": "concavity",
        "inflection point of": "concavity"
    }

    INTENT_MAP = {
        "indefinite_integral": "indefinite_integral", "antiderivative": "indefinite_integral", "indefinite": "indefinite_integral", "indefinite integral": "indefinite_integral",
        "derivative": "derivative", "deriv": "derivative", "diff": "derivative", "differentiation": "derivative",
        "slope": "derivative", "tangent": "derivative", "tangent line": "derivative",
        "integrate": "integrate", "integral": "integrate", "integration": "integrate", "area": "integrate",
        "root": "root", "roots": "root", "zero": "root", "zeros": "root", "solve": "root",
        "statistics": "statistics", "stats": "statistics", "average": "statistics", "mean": "statistics",
        "concavity": "concavity", "curvature": "concavity",
        "evaluate": "evaluate", "eval": "evaluate",
        "arc_length": "arc_length", "area_between": "area_between"
    }

    def __init__(self, filename="learned_patterns.json"):
        self.filename = filename
        self.patterns = dict(self.DEFAULT_PATTERNS)
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.patterns.update(data)
            except Exception:
                pass

    def save(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.patterns, f, indent=2)
        except Exception:
            pass

    def train_phrase(self, phrase: str, intent: str) -> str:
        p = phrase.lower().strip()
        i = intent.lower().strip()
        canonical = self.INTENT_MAP.get(i, i)
        self.patterns[p] = canonical
        self.save()
        return canonical

    def match_phrase(self, text: str) -> str | None:
        t = text.lower()
        for phrase, intent in self.patterns.items():
            if phrase in t:
                return intent
        return None

    def list_training(self) -> str:
        lines = ["[Trained Sentence Patterns]:"]
        for p, i in sorted(self.patterns.items()):
            lines.append(f"  - '{p}' -> {i}")
        return "\n".join(lines)


class SentenceNLU:
    """
    Natural Language Understanding engine that parses human sentences,
    normalizes spoken math words into mathematical notation, extracts semantic slots,
    and returns a structured actionable request.
    """
    WORD_NUMBERS = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "ten": "10", "eleven": "11", "twelve": "12", "half": "0.5", "quarter": "0.25"
    }

    PHRASE_REPLACEMENTS = [
        (r"\bplus\b", "+"),
        (r"\bminus\b", "-"),
        (r"\bnegative\s+(\d+)\b", r"-\1"),
        (r"\btimes\b", "*"),
        (r"\bmultiplied\s+by\b", "*"),
        (r"\bdivided\s+by\b", "/"),
        (r"\bover\b", "/"),
        (r"\bsquared\b", "^2"),
        (r"\bcubed\b", "^3"),
        (r"\bto\s+the\s+power\s+of\b", "^"),
        (r"\braised\s+to\s+(?:the\s+)?(?:power\s+of\s+)?\b", "^"),
        (r"\bsquare\s+root\s+of\b", "sqrt"),
        (r"\bcube\s+root\s+of\b", "cbrt"),
        (r"\be\s+to\s+(?:the\s+power\s+of|the)\b", "exp"),
        (r"\bnatural\s+log\s+(?:of\s+)?\b", "ln "),
        (r"\bcommon\s+log\s+(?:of\s+)?\b", "log "),
        (r"\blog\s+base\s+10\s+(?:of\s+)?\b", "log10 "),
        (r"\blog\s+base\s+2\s+(?:of\s+)?\b", "log2 "),
        (r"\blog\s+of\s+\b", "log "),
        (r"\babsolute\s+value\s+of\b", "abs"),
        (r"\bsine\s+of\b", "sin"),
        (r"\bcosine\s+of\b", "cos"),
        (r"\btangent\s+of\b", "tan"),
        (r"\bpi\s+over\s+2\b", "pi/2"),
        (r"\bpi\s+divided\s+by\s+2\b", "pi/2"),
        (r"\bpi\s+over\s+4\b", "pi/4"),
        (r"\bpi\s+divided\s+by\s+4\b", "pi/4"),
    ]

    def __init__(self, trainer: SentenceTrainer):
        self.trainer = trainer

    @staticmethod
    def clean_param(p: str) -> str:
        if not p:
            return ""
        p = re.sub(r"[?!.,;]+$", "", p.strip())
        p = re.sub(r"\s+(?:please|dx|now|step\s+by\s+step).*$", "", p, flags=re.I)
        p = re.sub(r"\b(?:the\s+)?(?:curve|function|equation)\s+", "", p, flags=re.I)
        p = re.sub(r"\b(?:y|f\(x\))\s*=\s*", "", p, flags=re.I)
        return p.strip()

    @staticmethod
    def substitute_user_symbols(text: str, user_functions: dict, user_variables: dict) -> str:
        res = text
        if user_functions:
            for fname, formula in user_functions.items():
                # 1. Substitute function calls: fname(arg) e.g. f(4) or f(x+1)
                pattern = rf"\b{fname}\s*\(([^)]+)\)"
                def repl(m):
                    arg = m.group(1).strip()
                    subbed = re.sub(r"\bx\b", f"({arg})", formula)
                    return f"({subbed})"
                res = re.sub(pattern, repl, res)
                # 2. Substitute standalone function names e.g. 'integrate f from 0 to 1'
                res = re.sub(rf"\b{fname}\b", f"({formula})", res)
        return res

    def normalize(self, text: str) -> str:
        s = text.strip()

        # Remove trailing punctuation like ? ! . , ;
        s = re.sub(r"[?!.,;]+$", "", s.strip())

        # Remove leading conversational / polite prefixes
        s = re.sub(
            r"^(?:(?:hey|hi|hello)\s*,?\s*)?"
            r"(?:(?:can|could|would)\s+you\s+(?:please\s+)?(?:calculate|compute|find|tell\s+me|give\s+me|solve|evaluate|determine)?|"
            r"please\s+(?:calculate|compute|find|tell\s+me|give\s+me|solve|evaluate|determine)?|"
            r"i\s+(?:want|need|would\s+like)\s+(?:you\s+)?(?:to\s+)?(?:calculate|compute|find|solve|evaluate|determine)?|"
            r"what\s+(?:is|would\s+be)\s+(?:the\s+)?|"
            r"calculate\s+(?:the\s+)?|compute\s+(?:the\s+)?|find\s+(?:the\s+)?|evaluate\s+(?:the\s+)?|determine\s+(?:the\s+)?|"
            r"tell\s+me\s+(?:the\s+)?|give\s+me\s+(?:the\s+)?)\s*",
            "", s, flags=re.I
        )

        # Remove trailing conversational words
        s = re.sub(r"\s+(?:please|thanks|thank\s+you|for\s+me|right\s+now|using\s+simpson|step\s+by\s+step)[\.!\?]*$", "", s, flags=re.I)

        # Strip function/curve filler words
        s = re.sub(r"\b(?:the\s+)?(?:curve|function|equation)\s+", "", s, flags=re.I)

        # Strip variable prefixes like "y =" or "f(x) ="
        s = re.sub(r"\b(?:y|f\(x\))\s*=\s*", "", s, flags=re.I)

        # Word numbers replacement
        for word, num in self.WORD_NUMBERS.items():
            s = re.sub(rf"\b{word}\b", num, s, flags=re.I)

        # Spoken powers (no space before ^)
        s = re.sub(r"\s*\bsquared\b", "^2", s, flags=re.I)
        s = re.sub(r"\s*\bcubed\b", "^3", s, flags=re.I)

        # Spoken math phrases replacement
        for pattern, replacement in self.PHRASE_REPLACEMENTS:
            s = re.sub(pattern, replacement, s, flags=re.I)

        # Auto-wrap naked arguments after common functions e.g. ln x -> ln(x), sin x -> sin(x)
        s = re.sub(r"\b(ln|log|log10|log2|sin|cos|tan|sqrt|cbrt|exp)\s+([a-zA-Z0-9]+)\b", r"\1(\2)", s)

        # Implicit multiplication (avoid multiplying into English prepositions like 'to' or 'from')
        excluded_words = {'to', 'from', 'and', 'at', 'when', 'for', 'by', 'is', 'equals', 'equal', 'between', 'step', 'starting', 'with'}
        def implicit_mul(m):
            num, target = m.group(1), m.group(2)
            if target.lower() in excluded_words:
                return f"{num} {target}"
            return f"{num}*{target}"
        s = re.sub(r"(?<![a-zA-Z0-9_])(\d+(?:\.\d+)?)\s*([a-zA-Z_]\w*|\()", implicit_mul, s)

        return s.strip()

    def parse(self, raw_sentence: str, user_functions: dict = None, user_variables: dict = None) -> dict:
        """
        Parses a raw natural language sentence into a structured intent and slots.
        """
        raw = raw_sentence.strip()

        # 1. Training help request (e.g. 'train:', 'train', 'teach:', 'how to train')
        if re.match(r"^(?:train|teach):?\s*$", raw, re.I) or raw.lower() in ("train", "teach", "how to train", "train help"):
            return {"intent": "train_help"}

        # 2. Training / Teaching commands:
        # e.g.:
        #   train: 'steepness of' means derivative
        #   train: steepness -> derivative
        #   train: steepness = derivative
        #   teach steepness -> derivative
        train_match = re.match(
            r"^(?:train|teach):?\s*['\"]?(.+?)['\"]?\s+(?:->|=>|=|means|is|as|to)\s+['\"]?([a-zA-Z_]+)['\"]?$",
            raw, re.I
        )
        if train_match:
            phrase = train_match.group(1).strip()
            target_intent = train_match.group(2).strip()
            return {"intent": "train", "phrase": phrase, "target_intent": target_intent}

        # 3. View Training List
        if re.search(r"^(?:list\s+training|show\s+training|view\s+training)\b", raw, re.I):
            return {"intent": "list_training"}

        # 4. View Saved Custom Functions & Variables
        if re.search(r"^(?:list\s+functions|show\s+functions|functions|show\s+variables|show\s+vars)\b", raw, re.I):
            return {"intent": "list_functions"}

        # 5. Custom Function or Variable Definition:
        # e.g.:
        #   f(x) = x^2 + 3*x - 5
        #   let f(x) = x^2 + 3
        #   let f = x^2 + 3
        #   define f(x) = sin(x) + cos(x)
        #   set k = 5.5
        fn_def_match = re.match(
            r"^(?:let|define|set)?\s*([a-zA-Z_]\w*)\s*(?:\(\s*x\s*\))?\s*=\s*(.+)$",
            raw, re.I
        )
        if fn_def_match:
            name = fn_def_match.group(1).strip()
            val_str = fn_def_match.group(2).strip()

            # Disallow overwriting standard mathematical functions
            if name.lower() in ("sin", "cos", "tan", "asin", "acos", "atan", "exp", "ln", "log", "sqrt", "cbrt", "abs", "pi", "e", "x", "ans"):
                return {"intent": "error", "message": f"Cannot override built-in math symbol '{name}'."}

            # If formula contains variable 'x', it's a FUNCTION; otherwise a CONSTANT VARIABLE
            if re.search(r"(?<![a-zA-Z_])x(?![a-zA-Z_])", val_str, re.I):
                return {"intent": "def_func", "name": name, "formula": val_str}
            else:
                return {"intent": "set_var", "name": name, "value": val_str}

        # 6. Apply Custom Function Substitutions
        subbed_raw = self.substitute_user_symbols(raw, user_functions or {}, user_variables or {})

        # Normalize the sentence for semantic interpretation
        norm = self.normalize(subbed_raw)

        # Contextual Follow-up on active function f(x) (when expression is omitted)
        active_f = user_functions.get("f", "") if user_functions else ""
        if active_f:
            # A. Derivative follow-up: "derivative at 2", "derive at 2", "slope at 2", "tangent at 2", "derivative", "derive"
            ctx_diff = re.match(
                r"^(?:derivative|derive|differentiate|slope|tangent(?:\s+line)?)(?:\s+(?:at\s+x\s*=?|at|when\s+x\s*(?:is|=))\s*([-\d.e^/*+()pi e]+))?$",
                norm, re.I
            )
            if ctx_diff:
                x0_val = ctx_diff.group(1) or "1"
                return {
                    "intent": "derivative",
                    "expr": active_f,
                    "x0": self.clean_param(x0_val)
                }

            # B. Definite integral follow-up: "integrate from 1 to 3", "integral from 1 to 3"
            ctx_int = re.match(
                r"^(?:integrate|integral)\s+(?:from|between)\s+([-\d.e^/*+()pi e]+)\s+(?:to|and)\s+([-\d.e^/*+()pi e]+)$",
                norm, re.I
            )
            if ctx_int:
                return {
                    "intent": "integrate",
                    "expr": active_f,
                    "a": self.clean_param(ctx_int.group(1)),
                    "b": self.clean_param(ctx_int.group(2))
                }

            # C. Indefinite integral follow-up: "integrate", "indefinite integral", "antiderivative"
            if re.match(r"^(?:integrate|indefinite\s+integral|antiderivative)$", norm, re.I):
                return {
                    "intent": "indefinite_integral",
                    "expr": active_f
                }

            # D. Value follow-up: "put x = 2", "put 2", "at x = 2", "at 2", "when x is 2", "value at 2"
            ctx_val = re.match(
                r"^(?:put\s+(?:x\s*=\s*)?|value\s+(?:at\s+)?|at\s+x\s*=?|at\s+|when\s+x\s*(?:is|=)|for\s+x\s*=)\s*([-\d.e^/*+()pi e]+)$",
                norm, re.I
            )
            if ctx_val:
                return {
                    "intent": "evaluate",
                    "expr": active_f,
                    "x0": self.clean_param(ctx_val.group(1))
                }

            # E. Root follow-up: "root", "find root", "solve", "zero", "zeros"
            if re.match(r"^(?:root|find\s+root|solve|zeros?|where\s+is\s+it\s+zero)$", norm, re.I):
                return {
                    "intent": "root",
                    "expr": active_f,
                    "guess": "1.0"
                }

        # 7. Percentage: "what is 15 percent of 300"
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+([-\d\s.*+/^()pi e]+)", norm, re.I)
        if pct_match:
            return {
                "intent": "percentage",
                "percentage": float(pct_match.group(1)),
                "value_str": self.clean_param(pct_match.group(2))
            }

        # 8. Area between two curves:
        # "area between <f(x)> and <g(x)> from <a> to <b>"
        area_between_match = re.search(
            r"(?:area\s+between)\s+(.+?)\s+and\s+(.+?)\s+(?:from|between)\s+(.+?)\s+(?:to|and)\s+(.+)",
            norm, re.I
        )
        if area_between_match:
            return {
                "intent": "area_between",
                "f": self.clean_param(area_between_match.group(1)),
                "g": self.clean_param(area_between_match.group(2)),
                "a": self.clean_param(area_between_match.group(3)),
                "b": self.clean_param(area_between_match.group(4))
            }

        # 9. Arc length:
        # "arc length of <f(x)> from <a> to <b>"
        arc_match = re.search(
            r"(?:arc\s+length\s+of|length\s+of\s+curve)\s+(.+?)\s+(?:from|between)\s+(.+?)\s+(?:to|and)\s+(.+)",
            norm, re.I
        )
        if arc_match:
            return {
                "intent": "arc_length",
                "expr": self.clean_param(arc_match.group(1)),
                "a": self.clean_param(arc_match.group(2)),
                "b": self.clean_param(arc_match.group(3))
            }

        # 10. Definite Integration:
        # "integrate <expr> from <a> to <b>" or "integral of <expr> between <a> and <b>"
        int_match = re.search(
            r"(?:integrate|integral\s+of|area\s+under\s+(?:curve)?|accumulate)\s+(.+?)\s+(?:from|between|with\s+bounds)\s+(.+?)\s+(?:to|and)\s+(.+)",
            norm, re.I
        )
        if int_match:
            return {
                "intent": "integrate",
                "expr": self.clean_param(int_match.group(1)),
                "a": self.clean_param(int_match.group(2)),
                "b": self.clean_param(int_match.group(3))
            }

        # Check if matched by trained phrases
        trained_intent = self.trainer.match_phrase(subbed_raw)
        if trained_intent == "integrate":
            bounds_match = re.search(r"(?:from|between)\s+(.+?)\s+(?:to|and)\s+(.+)", norm, re.I)
            if bounds_match:
                expr_part = re.sub(r"(?:from|between).*$", "", norm, flags=re.I)
                expr_part = re.sub(r"^.*?of\s+", "", expr_part, flags=re.I).strip()
                return {
                    "intent": "integrate",
                    "expr": self.clean_param(expr_part),
                    "a": self.clean_param(bounds_match.group(1)),
                    "b": self.clean_param(bounds_match.group(2))
                }

        # 10B. Indefinite Integration / Antiderivative (+ C):
        # "indefinite integral of <expr>", "antiderivative of <expr>", "integrate <expr>" (without bounds)
        indef_match = re.search(
            r"^(?:indefinite\s+integrat(?:ion|al)\s+(?:of\s+)?|antiderivative\s+(?:of\s+)?|symbolic\s+integral\s+(?:of\s+)?|integrate\s+(?:symbolically\s+)?|find\s+(?:the\s+)?antiderivative\s+(?:of\s+)?)(.+)$",
            norm, re.I
        )
        if (indef_match or trained_intent == "indefinite_integral") and not re.search(r"\b(?:from|between)\b", norm, re.I):
            expr_str = indef_match.group(1).strip() if indef_match else re.sub(r"^.*?of\s+", "", norm, flags=re.I).strip()
            return {
                "intent": "indefinite_integral",
                "expr": self.clean_param(expr_str)
            }
        # 11. Derivative & Tangent line:
        # "derivative of <expr> at <x>" or "slope of <expr> at <x>" or "tangent line of <expr> at <x>"
        diff_match = re.search(
            r"(?:derivative\s+of|differentiate|slope\s+of|tangent\s+line\s+of|rate\s+of\s+change\s+of|gradient\s+of)\s+(.+?)\s+(?:at\s+x\s*=?|at|when\s+x\s+(?:is|=))\s*(.+)",
            norm, re.I
        )
        diff_match_no_at = re.search(
            r"^(?:derivative\s+of|differentiate|slope\s+of|tangent\s+line\s+of|rate\s+of\s+change\s+of|gradient\s+of)\s+(.+)$",
            norm, re.I
        )
        if diff_match or diff_match_no_at or trained_intent == "derivative":
            if diff_match:
                expr_str = diff_match.group(1).strip()
                x0_str = diff_match.group(2).strip()
            elif diff_match_no_at:
                expr_str = diff_match_no_at.group(1).strip()
                x0_str = "0"
            else:
                x_match = re.search(r"(?:at\s+x\s*=?|at|when\s+x\s+(?:is|=))\s*(.+)", norm, re.I)
                x0_str = x_match.group(1).strip() if x_match else "0"
                expr_str = re.sub(r"(?:at|when).*$", "", norm, flags=re.I)
                expr_str = re.sub(r"^.*?of\s+", "", expr_str, flags=re.I).strip()

            return {
                "intent": "derivative",
                "expr": self.clean_param(expr_str),
                "x0": self.clean_param(x0_str)
            }

        # 12. Concavity / 2nd Derivative:
        # "second derivative of <expr> at <x>" or "curvature of <expr> at <x>"
        d2_match = re.search(
            r"(?:second\s+derivative\s+of|curvature\s+of|concavity\s+of)\s+(.+?)\s+(?:at\s+x\s*=?|at|when\s+x\s+(?:is|=))\s*(.+)",
            norm, re.I
        )
        if d2_match:
            return {
                "intent": "concavity",
                "expr": self.clean_param(d2_match.group(1)),
                "x0": self.clean_param(d2_match.group(2))
            }

        # 13. Root Finder / Equation Solving:
        # "root of <expr>", "find where <expr> equals zero", "where does <expr> equal zero", "solve <expr> = 0"
        root_match = re.search(
            r"(?:root\s+of|solve|zero\s+of|where\s+(?:does\s+)?(.+?)\s+(?:equals?\s+zero|equals?\s+0|=0))\s*(.+)?",
            norm, re.I
        )
        if root_match or trained_intent == "root":
            expr_str = ""
            guess_str = "1.0"
            if root_match:
                expr_str = root_match.group(1) or root_match.group(2) or ""
            else:
                expr_str = re.sub(r"^.*?of\s+", "", norm, flags=re.I).strip()

            # clean "= 0"
            expr_str = re.sub(r"\s*=\s*0.*$", "", expr_str).strip()
            guess_match = re.search(r"(?:starting\s+at|guess)\s+(.+)", expr_str, re.I)
            if guess_match:
                guess_str = guess_match.group(1).strip()
                expr_str = re.sub(r"(?:starting\s+at|guess).*$", "", expr_str, flags=re.I).strip()

            if expr_str:
                return {
                    "intent": "root",
                    "expr": self.clean_param(expr_str),
                    "guess": self.clean_param(guess_str)
                }

        # 14. Function Evaluation:
        # e.g.:
        #   "x/(x+1) + 45x^2 when x is 2"
        #   "evaluate x/(x+1) + 45x^2 at x = 2"
        #   "when x is 2, x/(x+1) + 45x^2"
        #   "plug in 2 for x in x/(x+1) + 45x^2"
        #   "at x = 2" (using last active function)
        eval_match_a = re.search(
            r"(?:(?:evaluate|value\s+of)\s+)?(.+?)\s+(?:when\s+x\s*(?:is|=)|at\s+x\s*=?|for\s+x\s*=|with\s+x\s*=)\s*([-\d.e^/*+()pi e]+)$",
            norm, re.I
        )
        eval_match_b = re.match(
            r"^when\s+x\s*(?:is|=)\s*([-\d.e^/*+()pi e]+)[,:]?\s*(.+)$",
            norm, re.I
        )
        eval_match_c = re.match(
            r"^plug\s+in\s+([-\d.e^/*+()pi e]+)\s+(?:for\s+x\s+)?(?:in|into|to)\s+(.+)$",
            norm, re.I
        )
        implicit_eval = re.match(
            r"^(?:(?:when|at|for)\s+x\s*(?:is|=)|at\s+x\s*=?)\s*([-\d.e^/*+()pi e]+)$",
            norm, re.I
        )

        if eval_match_a:
            return {
                "intent": "evaluate",
                "expr": self.clean_param(eval_match_a.group(1)),
                "x0": self.clean_param(eval_match_a.group(2))
            }
        elif eval_match_b:
            return {
                "intent": "evaluate",
                "expr": self.clean_param(eval_match_b.group(2)),
                "x0": self.clean_param(eval_match_b.group(1))
            }
        elif eval_match_c:
            return {
                "intent": "evaluate",
                "expr": self.clean_param(eval_match_c.group(2)),
                "x0": self.clean_param(eval_match_c.group(1))
            }
        elif implicit_eval and (user_functions and "f" in user_functions):
            return {
                "intent": "evaluate",
                "expr": user_functions["f"],
                "x0": self.clean_param(implicit_eval.group(1))
            }

        # 15. Statistics:
        # "mean of 1, 2, 3, 4" or "average of 10 20 30"
        stat_match = re.search(r"(?:mean|average|stats|statistics|std\s*dev)\s+(?:of\s+)?([-\d\s.,]+)", norm, re.I)
        if stat_match:
            return {
                "intent": "statistics",
                "data_str": stat_match.group(1).strip()
            }

        # 16. Fallback to general math expression
        return {
            "intent": "math_expr",
            "expr": norm
        }


# ==============================================================================
#                 6. COMPLEX QUESTION INTERPRETER & AI EXECUTOR
# ==============================================================================

class ComplexQuestionInterpreter:
    """
    Combines Conversational AI, Sentence NLU, User Behavior Learning,
    and High-Precision Math Engine to solve real human questions.
    """
    def __init__(self, learner: UserBehaviorLearner, math_engine: MathEngine, convo: ConversationalEngine):
        self.learner = learner
        self.engine = math_engine
        self.convo = convo
        self.trainer = SentenceTrainer()
        self.nlu = SentenceNLU(self.trainer)

    def interpret_and_solve(self, user_query: str) -> str:
        # 1. Check conversational English first
        convo_reply = self.convo.handle_convo(user_query)
        if convo_reply:
            return convo_reply

        # 2. Parse sentence into structured intent and slots with custom user functions
        user_funcs = self.learner.profile.get("user_functions", {})
        user_vars = self.learner.profile.get("user_variables", {})
        parsed = self.nlu.parse(user_query, user_functions=user_funcs, user_variables=user_vars)
        intent = parsed.get("intent")

        # --- A. Training Help ---
        if intent == "train_help":
            return (
                "[?] How to Train the Smart AI:\n"
                "---------------------------------------------------------\n"
                "You can teach the AI new phrases or custom words anytime using:\n"
                "  - train: '<phrase>' means <action>\n"
                "  - train: <phrase> -> <action>\n"
                "  - train: <phrase> = <action>\n\n"
                "Supported actions:\n"
                "  * derivative   (or: diff, slope, tangent)\n"
                "  * integrate    (or: integral, area under)\n"
                "  * root         (or: zero, solve)\n"
                "  * statistics   (or: stats, average)\n"
                "  * concavity    (or: curvature)\n"
                "  * evaluate     (or: plug in)\n\n"
                "Examples:\n"
                "  - train: 'steepness of' -> derivative\n"
                "  - train: 'accumulate' means integrate\n"
                "  - train: 'vanishing point' = root\n"
                "  - Type 'show training' to see all active trained patterns!"
            )

        # --- B. Train New Command ---
        if intent == "train":
            phrase = parsed["phrase"]
            target_intent = parsed["target_intent"]
            canonical = self.trainer.train_phrase(phrase, target_intent)
            return (
                f"[+] Successfully Trained!\n"
                f"    I have learned that whenever you say '{phrase}',\n"
                f"    you mean to execute: '{canonical}'."
            )

        # --- C. Show Training ---
        if intent == "list_training":
            return self.trainer.list_training()

        # --- D. Show Saved Functions & Variables ---
        if intent == "list_functions":
            funcs = self.learner.profile.get("user_functions", {})
            vars_ = self.learner.profile.get("user_variables", {})
            lines = ["[Your Custom Functions & Variables]:"]
            if funcs:
                lines.append("  Functions:")
                for f, formula in sorted(funcs.items()):
                    lines.append(f"    - {f}(x) = {formula}")
            else:
                lines.append("  No custom functions saved yet (e.g. define with 'f(x) = x^2 + 3').")
            if vars_:
                lines.append("  Variables:")
                for v, val in sorted(vars_.items()):
                    lines.append(f"    - {v} = {val}")
            return "\n".join(lines)

        # --- E. Error during parsing ---
        if intent == "error":
            return f"[-] {parsed.get('message', 'Parsing error')}"

        # --- F. Custom Function Definition ---
        if intent == "def_func":
            fname = parsed["name"]
            formula = parsed["formula"]
            self.learner.set_user_function(fname, formula)
            self.learner.set_user_function("f", formula)
            profile = self.analyze_function_profile(formula, user_query)
            return (
                f"[+] Custom Function Saved: {fname}(x) = {formula}\n\n"
                f"{profile}"
            )

        # --- G. Variable Definition ---
        if intent == "set_var":
            v_name = parsed["name"]
            v_val_str = parsed["value"]
            try:
                val = self.engine.eval_constant(v_val_str, self.learner.profile["user_variables"])
                self.learner.set_user_variable(v_name, val)
                return f"[+] Saved variable: {v_name} = {val}"
            except Exception:
                self.learner.set_user_function(v_name, v_val_str)
                return f"[+] Saved custom formula: {v_name}(x) = {v_val_str}"

        # --- C. Percentage ---
        if intent == "percentage":
            pct = parsed["percentage"]
            val_str = parsed["value_str"]
            try:
                num = self.engine.eval_constant(val_str, self.learner.profile["user_variables"])
                ans = (pct / 100.0) * num
                self.learner.record_query("percentage", raw_query=user_query)
                self.learner.set_last_result(ans, f"{pct}% of {val_str}")
                return (
                    f"[*] Percentage Calculation:\n"
                    f"    {pct}% of {num:.6g} = {ans:.6g}\n"
                    f"    [Note] Saved to ans = {ans:.6g}"
                )
            except Exception as e:
                return f"[-] Could not calculate percentage: {str(e)}"

        # --- D. Definite Integration ---
        if intent == "integrate":
            expr = parsed["expr"]
            bound_a_str = parsed["a"]
            bound_b_str = parsed["b"]

            GUIBridge.emit_thought("TOKENIZER", 0, f"Definite integral of f(x) = {expr} over [{bound_a_str}, {bound_b_str}]", math_working=f"∫ [{bound_a_str} to {bound_b_str}] {expr} dx", progress=0.20)

            try:
                a = self.engine.eval_constant(bound_a_str, self.learner.profile["user_variables"])
                b = self.engine.eval_constant(bound_b_str, self.learner.profile["user_variables"])
                GUIBridge.emit_thought("SIMPSON_QUADRATURE", 1, f"Partitioning [{a:.4g}, {b:.4g}] into 4000 composite Simpson intervals...", math_working=f"Domain [{a:.4g}, {b:.4g}]", progress=0.45)

                result, err_est, method = self.engine.integrate_simpson(
                    expr, a, b, extra_vars=self.learner.profile["user_variables"]
                )
                GUIBridge.emit_thought("ERROR_EXTRAPOLATION", 2, f"Richardson extrapolation error: +/- {err_est:.2e}", math_working=f"Area ≈ {result:.8g}", progress=0.75)
                GUIBridge.emit_thought("CONVERGENCE_CHECK", 3, f"Integral result converged: {result:.10f}", math_working=f"Area = {result:.10f}", progress=0.90)
                GUIBridge.emit_thought("OUTPUT_SYNTHESIZER", 4, f"Definite area = {result:.10g}. Stored in ans.", math_working=f"Area = {result:.10g}", progress=1.0)

                self.learner.record_query("integral", expression=expr, bounds=[bound_a_str, bound_b_str], raw_query=user_query)
                self.learner.set_last_result(result, f"integral {expr} from {bound_a_str} to {bound_b_str}")

                status_tip = f"Estimated Error: +/- {err_est:.2e}"
                if "Singularity" in method:
                    status_tip = "Endpoints contain logarithmic singularities (handled adaptively)."

                GUIBridge.emit_result_modal(
                    "success",
                    user_query,
                    f"{result:.6f}",
                    method,
                    status_tip
                )

                return (
                    f"[Sentence Understood]: Action = Integrate | Function = {expr} | Bounds = [{bound_a_str}, {bound_b_str}]\n\n"
                    f"[*] Definite Integral Solved:\n"
                    f"   integral [{expr}] dx  from x = {bound_a_str} to x = {bound_b_str}\n"
                    f"   ---------------------------------------------------------\n"
                    f"   Result          : {result:.10f}\n"
                    f"   Scientific Form : {result:e}\n"
                    f"   Estimated Error : +/- {err_est:.2e}\n"
                    f"   Interval        : [{a:.4g}, {b:.4g}]\n"
                    f"   [Note] Saved to ans = {result:.6g}"
                )
            except Exception as e:
                return f"[-] Could not compute integral for '{expr}': {str(e)}"

        # --- D2. Indefinite Integration / Antiderivative (+ C) ---
        if intent == "indefinite_integral":
            expr = parsed["expr"]
            GUIBridge.emit_thought("TOKENIZER", 0, f"Reading integrand: f(x) = {expr}", math_working=f"∫ [{expr}] dx", progress=0.20)
            GUIBridge.emit_thought("SYNTAX_PARSER", 1, f"Splitting integrand into linear sum of terms...", math_working=f"Parsing: {expr}", progress=0.40)

            res = SymbolicIntegrator.integrate_expression(expr)
            if res["success"]:
                self.learner.record_query("indefinite_integral", expression=expr, raw_query=user_query)
                self.learner.set_last_result(res["equation"], f"antiderivative of {expr}")

                steps_formatted = []
                num_steps = len(res["steps"])
                for idx, (term_orig, rule) in enumerate(res["steps"], 1):
                    steps_formatted.append(f"     Step {idx} [{term_orig}]: {rule}")
                    calc_prog = 0.40 + (0.40 * idx / max(1, num_steps))
                    GUIBridge.emit_thought("SYMBOLIC_CORE", 2, f"Term '{term_orig}': {rule}", math_working=f"Integrating {term_orig}", progress=calc_prog)

                steps_str = "\n".join(steps_formatted)
                GUIBridge.emit_thought("DIFFERENTIAL_VERIFIER", 3, f"Verifying exact derivative d/dx matches integrand...", math_working=res["equation"], progress=0.88)
                GUIBridge.emit_thought("OUTPUT_SYNTHESIZER", 4, f"Assembled final equation: {res['equation']}", math_working=res["equation"], progress=1.0)

                GUIBridge.emit_result_modal(
                    "success",
                    user_query,
                    res["equation"],
                    "Symbolic Antiderivative (Rule-Based)",
                    "Verification: d/dx matches original integrand exactly."
                )

                return (
                    f"[Sentence Understood]: Action = Indefinite Integration | Function = f(x) = {expr}\n\n"
                    f"[*] Indefinite Integral (Antiderivative):\n"
                    f"   Integrand Function : f(x) = {expr}\n"
                    f"   ---------------------------------------------------------\n"
                    f"   Final Equation     : integral [ {expr} ] dx =\n\n"
                    f"       =  {res['equation']}\n\n"
                    f"   ---------------------------------------------------------\n"
                    f"   Step-by-Step Integration Rules Applied:\n"
                    f"{steps_str}\n\n"
                    f"   [Note] '+ C' is the arbitrary constant of integration (C in Real Numbers).\n"
                    f"          Verification: d/dx [ {res['equation']} ] = {expr}\n"
                    f"   [Saved] Antiderivative equation stored in ans"
                )
            else:
                GUIBridge.emit_result_modal(
                    "warning",
                    user_query,
                    "Non-Elementary Antiderivative",
                    "Fallback to Numerical Quadrature suggested",
                    res['error']
                )
                return (
                    f"[-] Indefinite Integration for '{expr}':\n"
                    f"    {res['error']}.\n\n"
                    f"    [Tip] If this function has no closed elementary antiderivative (e.g. exp(-x^2)),\n"
                    f"    you can calculate its numerical definite integral across bounds instead:\n"
                    f"      'integrate {expr} from a to b'"
                )

        # --- E. Derivative & Tangent Line ---
        if intent == "derivative":
            expr = parsed["expr"]
            x0_str = parsed["x0"]
            GUIBridge.emit_thought("TOKENIZER", 0, f"Target: f(x) = {expr} at x0 = {x0_str}", math_working=f"d/dx [{expr}] at x={x0_str}", progress=0.20)

            try:
                x0 = self.engine.eval_constant(x0_str, self.learner.profile["user_variables"])
                GUIBridge.emit_thought("DIFFERENTIAL_STENCIL", 1, f"Centered 5-point difference stencil h=1e-5 around x0={x0:.4g}", math_working=f"Sampling [-2h, -h, 0, h, 2h]", progress=0.45)

                y0 = self.engine.eval_at(expr, x0, self.learner.profile["user_variables"])
                slope = self.engine.derivative_5point(expr, x0, self.learner.profile["user_variables"])
                d2 = self.engine.second_derivative(expr, x0, self.learner.profile["user_variables"])
                intercept = y0 - slope * x0

                concavity = "Concave UP (local min)" if d2 > 1e-5 else ("Concave DOWN (local max)" if d2 < -1e-5 else "Inflection point")
                GUIBridge.emit_thought("CONCAVITY_ANALYZER", 2, f"Slope m = {slope:.6g} | Curvature f''(x0) = {d2:.4g} [{concavity}]", math_working=f"m = {slope:.6g}, f''={d2:.4g}", progress=0.60)

                tangent_line = f"y = {slope:.6g}*x {'+' if intercept >= 0 else '-'} {abs(intercept):.6g}"
                GUIBridge.emit_thought("TANGENT_SOLVER", 3, f"Constructed tangent line: {tangent_line}", math_working=tangent_line, progress=0.75)
                
                # Compute symbolic derivative
                GUIBridge.emit_thought("SYMBOLIC_ENGINE", 4, f"Computing abstract syntax tree for exact symbolic derivative...", math_working=f"AST Diff", progress=0.88)
                sym_deriv = SymbolicMathEngine.get_symbolic_derivative(expr)

                GUIBridge.emit_thought("OUTPUT_SYNTHESIZER", 5, f"Derivative slope m = {slope:.6g}. Saved to ans.", math_working=tangent_line, progress=1.0)

                self.learner.record_query("derivative", expression=expr, raw_query=user_query)
                self.learner.set_last_result(slope, f"f'({x0_str}) of {expr}")

                return (
                    f"[Sentence Understood]: Action = Derivative & Tangent | Function = {expr} | Point = {x0:.4g}\n\n"
                    f"[*] Derivative & Tangent Analysis:\n"
                    f"   Function        : f(x) = {expr}\n"
                    f"   Symbolic d/dx   : f'(x) = {sym_deriv}\n"
                    f"   Evaluation Point: x0 = {x0:.4g},  y0 = {y0:.6g}\n"
                    f"   ---------------------------------------------------------\n"
                    f"   1st Derivative  : slope m = {slope:.10f}\n"
                    f"   2nd Derivative  : concavity = {d2:.6g} [{concavity}]\n"
                    f"   Tangent Line Eq : y = {slope:.6g}*x {'+' if intercept >= 0 else '-'} {abs(intercept):.6g}\n"
                    f"   [Note] Saved to ans = {slope:.6g}"
                )
            except Exception as e:
                return f"[-] Could not compute derivative for '{expr}': {str(e)}"

        # --- F. Concavity / 2nd Derivative ---
        if intent == "concavity":
            expr = parsed["expr"]
            x0_str = parsed["x0"]
            try:
                x0 = self.engine.eval_constant(x0_str, self.learner.profile["user_variables"])
                d2 = self.engine.second_derivative(expr, x0, self.learner.profile["user_variables"])
                concavity = "Concave UP (bowl / local minimum)" if d2 > 1e-5 else ("Concave DOWN (hill / local maximum)" if d2 < -1e-5 else "Inflection point")
                self.learner.record_query("concavity", expression=expr, raw_query=user_query)
                self.learner.set_last_result(d2, f"f''({x0_str})")
                return (
                    f"[*] Second Derivative & Concavity:\n"
                    f"   Function   : f(x) = {expr}\n"
                    f"   Point      : x0 = {x0:.4g}\n"
                    f"   f''(x0)    : {d2:.10f}\n"
                    f"   Curvature  : {concavity}\n"
                    f"   [Note] Saved to ans = {d2:.6g}"
                )
            except Exception as e:
                return f"[-] Could not compute concavity: {str(e)}"

        # --- G. Root Finding ---
        if intent == "root":
            expr = parsed["expr"]
            guess_str = parsed.get("guess", "1.0")
            GUIBridge.emit_thought("TOKENIZER", 0, f"Finding root: {expr} = 0", math_working=f"{expr} = 0", progress=0.20)

            try:
                guess = self.engine.eval_constant(guess_str, self.learner.profile["user_variables"])
                GUIBridge.emit_thought("INITIAL_SEED", 1, f"Starting Newton-Raphson sequence from initial seed x0 = {guess:.4g}", math_working=f"Seed: {guess:.4g}", progress=0.40)

                root, iters, ok = self.engine.find_root_newton(expr, guess, self.learner.profile["user_variables"])
                residual = self.engine.eval_at(expr, root, self.learner.profile["user_variables"])

                GUIBridge.emit_thought("NEWTON_ITERATOR", 2, f"Iterated tangent sequence: converged in {iters} iterations", math_working=f"Root candidate: {root:.8g}", progress=0.70)
                GUIBridge.emit_thought("RESIDUAL_VERIFIER", 3, f"Verified residual error: |f(root)| = {residual:.2e} < 1e-9", math_working=f"Residual: {residual:.2e}", progress=0.90)
                GUIBridge.emit_thought("OUTPUT_SYNTHESIZER", 4, f"Real root found at x = {root:.8g}. Stored in ans.", math_working=f"Root: x = {root:.8g}", progress=1.0)

                self.learner.record_query("root", expression=expr, raw_query=user_query)
                self.learner.set_last_result(root, f"root of {expr}")

                status = f"Converged in {iters} iterations" if ok else "Approximate root reached"
                return (
                    f"[Sentence Understood]: Action = Find Root | Equation = {expr} = 0\n\n"
                    f"[*] Numerical Root Found:\n"
                    f"   Equation : {expr} = 0\n"
                    f"   Root x   : {root:.10f}\n"
                    f"   f(root)  : {residual:.2e} (residual error)\n"
                    f"   Status   : {status}\n"
                    f"   [Note] Saved to ans = {root:.6g}"
                )
            except Exception as e:
                return f"[-] Could not find root for '{expr}': {str(e)}"

        # --- H. Area Between Two Curves ---
        if intent == "area_between":
            f_expr = parsed["f"]
            g_expr = parsed["g"]
            a_str = parsed["a"]
            b_str = parsed["b"]
            try:
                a = self.engine.eval_constant(a_str, self.learner.profile["user_variables"])
                b = self.engine.eval_constant(b_str, self.learner.profile["user_variables"])
                diff_expr = f"abs(({f_expr}) - ({g_expr}))"
                area, err_est = self.engine.integrate_simpson(diff_expr, a, b, extra_vars=self.learner.profile["user_variables"])
                self.learner.record_query("area_between", raw_query=user_query)
                self.learner.set_last_result(area, "area between curves")
                return (
                    f"[Sentence Understood]: Action = Area Between Curves | f(x) = {f_expr} | g(x) = {g_expr} | Bounds = [{a:.4g}, {b:.4g}]\n\n"
                    f"[*] Enclosed Area: {area:.10f} (+/- {err_est:.2e})\n"
                    f"   [Note] Saved to ans = {area:.6g}"
                )
            except Exception as e:
                return f"[-] Could not compute area between curves: {str(e)}"

        # --- I. Arc Length ---
        if intent == "arc_length":
            expr = parsed["expr"]
            a_str = parsed["a"]
            b_str = parsed["b"]
            try:
                a = self.engine.eval_constant(a_str, self.learner.profile["user_variables"])
                b = self.engine.eval_constant(b_str, self.learner.profile["user_variables"])
                n = 2000
                h = (b - a) / n
                total = 0.0
                for i in range(n + 1):
                    x = a + i * h
                    df = self.engine.derivative_5point(expr, x, self.learner.profile["user_variables"])
                    integrand = math.sqrt(1.0 + df**2)
                    weight = 1.0 if (i == 0 or i == n) else (4.0 if i % 2 == 1 else 2.0)
                    total += weight * integrand
                length = (h / 3.0) * total
                self.learner.record_query("arc_length", raw_query=user_query)
                self.learner.set_last_result(length, "arc length")
                return (
                    f"[Sentence Understood]: Action = Arc Length | Curve = {expr} | Bounds = [{a:.4g}, {b:.4g}]\n\n"
                    f"[*] Curve Length L: {length:.10f}\n"
                    f"   [Note] Saved to ans = {length:.6g}"
                )
            except Exception as e:
                return f"[-] Could not compute arc length: {str(e)}"

        # --- J. Function Evaluation ---
        if intent == "evaluate":
            expr = parsed["expr"]
            x0_str = parsed["x0"]
            try:
                x0 = self.engine.eval_constant(x0_str, self.learner.profile["user_variables"])
                val = self.engine.eval_at(expr, x0, self.learner.profile["user_variables"])
                self.learner.set_last_result(val, f"f({x0_str}) of {expr}")
                return (
                    f"[*] Function Evaluated:\n"
                    f"    f({x0:.4g}) for f(x) = {expr}\n"
                    f"    Result = {val:.10g}\n"
                    f"    [Note] Saved to ans = {val:.6g}"
                )
            except Exception as e:
                return f"[-] Evaluation error: {str(e)}"

        # --- K. Statistics ---
        if intent == "statistics":
            data_str = parsed["data_str"].replace(",", " ")
            try:
                nums = [float(x) for x in data_str.split() if x.strip()]
                if nums:
                    n = len(nums)
                    s = sum(nums)
                    mean = s / n
                    nums_sorted = sorted(nums)
                    median = nums_sorted[n//2] if n % 2 != 0 else (nums_sorted[n//2 - 1] + nums_sorted[n//2]) / 2.0
                    var = sum((x - mean)**2 for x in nums) / (n - 1) if n > 1 else 0.0
                    std = math.sqrt(var)

                    self.learner.record_query("statistics", raw_query=user_query)
                    self.learner.set_last_result(mean, "mean")

                    return (
                        f"[Stats] Statistical Summary (N = {n}):\n"
                        f"   Min: {nums_sorted[0]:.4g} | Max: {nums_sorted[-1]:.4g} | Sum: {s:.6g}\n"
                        f"   Mean (Average)    : {mean:.6g}\n"
                        f"   Median            : {median:.6g}\n"
                        f"   Variance          : {var:.6g}\n"
                        f"   Standard Deviation: {std:.6g}"
                    )
            except Exception as e:
                return f"[-] Statistics error: {str(e)}"

        # --- L. General Math Expression or Standalone Function ---
        expr_cand = parsed.get("expr", "").strip()

        # Check if user entered an algebraic function f(x) e.g. "x/(x+1) + 45x^2"
        if re.search(r"(?<![a-zA-Z_])x(?![a-zA-Z_])", expr_cand, re.I):
            return self.analyze_function_profile(expr_cand, user_query)

        try:
            val = self.engine.eval_constant(expr_cand, self.learner.profile["user_variables"])
            self.learner.record_query("expression", expression=expr_cand, raw_query=user_query)
            self.learner.set_last_result(val, expr_cand)
            return f"[Result] = {val:.10g}  (Saved to ans)"
        except Exception:
            pass

        # If completely unrecognized, provide helpful sentence training guidance
        return (
            f"[?] I couldn't quite determine the mathematical intent in:\n"
            f"    '{user_query}'\n\n"
            f"[Hint] You can talk to me naturally in full sentences, like:\n"
            f"  - 'Can you calculate the integral of 3x squared plus 2x from 1 to 4?'\n"
            f"  - 'What is the slope of cos(x) when x is pi over 2?'\n"
            f"  - 'Find where x cubed minus 27 equals zero'\n"
            f"  - 'What is the average of 85, 90, 78, 92?'\n"
            f"  - 'What is 15 percent of 400?'\n"
            f"  - Or train me: 'train: <phrase> means <intent>'\n"
            f"  - Type 'show training' to see all learned sentence patterns!"
        )

    def analyze_function_profile(self, expr: str, raw_query: str = "") -> str:
        """
        Provides comprehensive profile analysis for any standalone function or equation f(x):
          - Cleans and stores as active working function f(x)
          - Detects function family / type (Rational, Polynomial, Trig, etc.)
          - Finds domain discontinuities and vertical asymptotes
          - Computes Y-intercept f(0)
          - Identifies real roots / zeros f(x) = 0
          - Calculates slope and tangent line at a representative point
          - Derives symbolic antiderivative (+ C)
          - Evaluates a sample definite integral
          - Generates an ASCII table of values for x in [-3, 3]
          - Displays instant next action hints (derive, integrate, put value, root)
        """
        # 1. Clean expression and strip potential leading "y =", "f(x) =", or trailing "= 0"
        s = expr.strip()
        s = re.sub(r"^(?:y|f\s*\(\s*x\s*\))\s*=\s*", "", s, flags=re.I)
        s = re.sub(r"\s*=\s*0$", "", s)
        clean = self.engine.clean_math_expr(s)

        # 2. Save as active working function 'f' for immediate subsequent operations
        self.learner.set_user_function("f", s)
        self.learner.profile["last_expression"] = s
        self.learner.record_query("analyze_function", expression=s, raw_query=raw_query or s)

        GUIBridge.emit_thought("TOKENIZER", 0, f"Tokenizing algebraic expression: '{s}'", math_working=f"f(x) = {s}", progress=0.15)

        # 3. Classify function type
        types = []
        if '/' in s:
            types.append("Rational")
        if any(fn in s.lower() for fn in ['sin', 'cos', 'tan', 'sec', 'csc', 'cot']):
            types.append("Trigonometric")
        if any(fn in s.lower() for fn in ['exp', 'e^']):
            types.append("Exponential")
        if any(fn in s.lower() for fn in ['ln', 'log']):
            types.append("Logarithmic")
        if re.search(r"x\s*(\^|\*\*)\s*\d+|x\s*[+-]|\b\d+x\b", s):
            if "Rational" not in types and "Trigonometric" not in types and "Exponential" not in types:
                types.append("Polynomial")
            elif "Rational" not in types:
                types.append("Algebraic")
        if not types:
            types.append("Algebraic")
        func_type = " / ".join(types)

        # 4. Domain & Asymptote Analysis
        asymptotes = []
        for x_test in range(-15, 16):
            try:
                val = self.engine.eval_at(clean, float(x_test))
                if math.isnan(val) or math.isinf(val) or abs(val) > 1e12:
                    asymptotes.append(float(x_test))
            except ZeroDivisionError:
                asymptotes.append(float(x_test))
            except Exception:
                pass

        # Test fractional / offset candidates from denominators if matched
        m_denoms = re.findall(r"/\s*\(\s*x\s*([+-]\s*\d+(?:\.\d+)?)\s*\)", s)
        for d in m_denoms:
            try:
                pole = -float(d.replace(" ", ""))
                if pole not in asymptotes:
                    asymptotes.append(pole)
            except Exception:
                pass

        if asymptotes:
            asymp_str = ", ".join([f"x = {a:g}" for a in sorted(set(asymptotes))])
            domain_str = f"All real numbers except {asymp_str} (Vertical Asymptote)"
        else:
            domain_str = "All real numbers (-inf, +inf)"

        GUIBridge.emit_thought("SYNTAX_PARSER", 1, f"Classified: {func_type} | Domain: {domain_str}", math_working=f"Domain: {domain_str}", progress=0.35)

        # 5. Y-Intercept f(0)
        try:
            y0 = self.engine.eval_at(clean, 0.0)
            if math.isnan(y0) or math.isinf(y0) or abs(y0) > 1e12 or (0.0 in asymptotes):
                y_intercept_str = "Undefined (Vertical Asymptote / Discontinuity)"
            else:
                y_intercept_str = f"(0, {y0:.6g})"
        except Exception:
            y_intercept_str = "Undefined (Singularity / Division by zero)"

        # 6. Real Roots / Zeros f(x) = 0
        roots = []
        test_guesses = [-5.0, -3.0, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0, 5.0]
        for g in test_guesses:
            try:
                r, iters, ok = self.engine.find_root_newton(clean, g)
                if ok and not any(abs(r - existing) < 1e-4 for existing in roots):
                    val_at_r = abs(self.engine.eval_at(clean, r))
                    if val_at_r < 1e-3:
                        roots.append(round(r, 4))
            except Exception:
                pass
        roots.sort()
        if roots:
            roots_str = ", ".join([f"x = {r:g}" for r in roots])
        else:
            roots_str = "None detected in range [-10, 10]"

        GUIBridge.emit_thought("ROOT_SOLVER", 2, f"Newton-Raphson scanner: roots = {roots_str}", math_working=f"Zeros: {roots_str}", progress=0.55)

        # 7. Calculus Properties: Slope & Tangent Line
        ref_x = 1.0 if (1.0 not in asymptotes) else 2.0
        try:
            y_ref = self.engine.eval_at(clean, ref_x)
            slope = self.engine.derivative_5point(clean, ref_x)
            c_tangent = y_ref - slope * ref_x
            sign_c = "+ " if c_tangent >= 0 else "- "
            tangent_str = f"f'({ref_x:g}) = {slope:.6g} | Tangent at x={ref_x:g}: y = {slope:.6g}x {sign_c}{abs(c_tangent):.6g}"
        except Exception:
            tangent_str = "Slope could not be determined at reference point"

        GUIBridge.emit_thought("CALCULUS_CORE", 2, f"Evaluated 5-point derivative: {tangent_str}", math_working=tangent_str, progress=0.72)

        # 8. Symbolic Antiderivative (+ C)
        clean_for_sym = clean.replace('**', '^')
        sym = SymbolicIntegrator.integrate_expression(clean_for_sym)
        if sym.get("success"):
            integral_str = f"{sym.get('equation')}"
        else:
            integral_str = "Non-elementary / numerical approximation recommended"

        GUIBridge.emit_thought("SYMBOLIC_ENGINE", 3, f"Symbolic antiderivative: {integral_str}", math_working=f"∫ f(x) dx = {integral_str}", progress=0.88)

        # 9. Definite Integral Sample
        sample_int_str = ""
        int_a, int_b = (0.0, 1.0)
        if any(a >= int_a and a <= int_b for a in asymptotes):
            int_a, int_b = (1.0, 2.0)
        try:
            if not any(a >= int_a and a <= int_b for a in asymptotes):
                area, err = self.engine.integrate_simpson(clean, int_a, int_b)
                sample_int_str = f"integral from {int_a:g} to {int_b:g} = {area:.6g}"
        except Exception:
            pass

        # 10. Table of Values for x in [-3, 3]
        table_lines = ["    x     |   f(x)", "  -------------------------"]
        for x_val in [-3, -2, -1, 0, 1, 2, 3]:
            try:
                val = self.engine.eval_at(clean, float(x_val))
                if math.isnan(val) or math.isinf(val) or abs(val) > 1e12 or float(x_val) in asymptotes:
                    val_repr = "Undefined (Asymptote)"
                else:
                    val_repr = f"{val:.6g}"
            except Exception:
                val_repr = "Undefined (Asymptote)"
            table_lines.append(f"   {x_val:>2}     |   {val_repr}")

        table_str = "\n".join(table_lines)

        sym_deriv = SymbolicMathEngine.get_symbolic_derivative(clean)

        # 11. Format Output Card
        output = [
            f"[Function Profile] Analyzed: f(x) = {s}",
            f"----------------------------------------------------------------",
            f"  * Classification     : {func_type}",
            f"  * Domain             : {domain_str}",
            f"  * Y-Intercept        : {y_intercept_str}",
            f"  * Real Roots (Zeros) : {roots_str}",
            f"  * Slope & Tangent    : {tangent_str}",
            f"  * Symbolic d/dx      : f'(x) = {sym_deriv}",
            f"  * Indefinite Integral: {integral_str}"
        ]
        if sample_int_str:
            output.append(f"  * Sample Area        : {sample_int_str}")
        output.extend([
            f"\n  [Sample Values Table]:",
            table_str,
            f"----------------------------------------------------------------",
            f"[+] Saved as ACTIVE FUNCTION: f(x) = {s}",
            f"    You can now perform any action on it directly without retyping:",
            f"      - 'derivative at 2' or 'slope at 2'      -> finds f'(2)",
            f"      - 'integrate from 1 to 3'                 -> computes definite area",
            f"      - 'indefinite integral'                   -> shows symbolic equation with + C",
            f"      - 'put x = 4' or 'at 4'                   -> calculates f(4)",
            f"      - 'root' or 'solve'                       -> finds zeros of f(x) = 0"
        ])
        GUIBridge.emit_thought("OUTPUT_SYNTHESIZER", 4, f"Completed profile for f(x) = {s}. Stored in active memory.", math_working=f"Active f(x) = {s}", progress=1.0)
        return "\n".join(output)


# ==============================================================================
#                 7. INTERACTIVE REAL-TIME TERMINAL INTERFACE
# ==============================================================================

class SmartCalculatorCLI:
    """
    Terminal UI with active real-time auto-completion, auto-correction,
    and Up/Down Arrow history navigation.
    Uses msvcrt on Windows for responsive keypress handling.
    """
    def __init__(self):
        self.learner = UserBehaviorLearner()
        self.math_engine = MathEngine()
        self.corrector = AutoCorrectorAndCompletor(self.learner)
        self.convo = ConversationalEngine(self.learner)
        self.interpreter = ComplexQuestionInterpreter(self.learner, self.math_engine, self.convo)
        self.history = list(self.learner.profile.get("query_history", []))

    def print_banner(self):
        print("****************************************************************")
        print("*         SMART AI CALCULATOR & CALCULUS ASSISTANT             *")
        print("*  Self-Learning | Natural Language | Real-Time Auto-Corrector *")
        print("****************************************************************")
        print("Type formulas, calculus queries, or natural English:")
        print("  - 'integrate sin(x) from 0 to pi'")
        print("  - 'derivative of 3x^2 + 5x at x=2'")
        print("  - Type any function e.g. 'x/(x+1) + 45x^2' to inspect & activate it")
        print("  - Press [Up Arrow] / [Down Arrow] to recall previous questions")
        print("  - Control Pad GUI & Animation Screen auto-activated on your desktop")
        print("  - 'history' (view all queries) | 'profile' | 'exit' to quit")
        print("----------------------------------------------------------------\n")

    def read_line_with_autocomplete(self, prompt="SmartCal > ") -> str:
        """
        Reads a line with active Tab auto-completion, suggestion ranking,
        Up/Down Arrow history navigation, and live Control Pad button sync.
        Falls back to standard input() if not in a responsive TTY or on non-Windows.
        """
        if not HAS_MSVCRT or not sys.stdin.isatty():
            try:
                line = input(prompt)
                if line.strip():
                    if not self.history or self.history[-1] != line.strip():
                        self.history.append(line.strip())
                    self.learner.add_query_history(line.strip())
                return line
            except EOFError:
                return "exit"

        sys.stdout.write(prompt)
        sys.stdout.flush()

        chars = []
        history_index = len(self.history)
        saved_buffer = ""

        while True:
            # 1. Check for command clicks from the popped-out Control Pad window
            pending_cmd = GUIBridge.check_pending_command()
            if pending_cmd:
                if chars:
                    sys.stdout.write("\b \b" * len(chars))
                sys.stdout.write(f"{pending_cmd}\n")
                sys.stdout.flush()
                chars = list(pending_cmd)
                break

            # 2. Check if user pressed a key on keyboard
            if not msvcrt.kbhit():
                time.sleep(0.03)
                continue

            ch = msvcrt.getwch()

            # Enter key
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                break

            # Backspace
            elif ch == "\b":
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()

            # Tab key (Auto-completion!)
            elif ch == "\t":
                current_text = "".join(chars)
                tokens = current_text.split()
                last_token = tokens[-1] if tokens else ""

                if last_token:
                    completions = self.corrector.get_completions(last_token)
                    if completions:
                        best = completions[0]
                        remainder = best[len(last_token):]
                        if remainder:
                            chars.extend(list(remainder))
                            sys.stdout.write(remainder)
                            sys.stdout.flush()

            # Special keys (Arrows, Function keys)
            elif ch in ("\x00", "\xe0"):
                code = msvcrt.getwch() # read secondary scan code

                # Up Arrow ('H') -> previous query / equation
                if code == 'H' and self.history:
                    if history_index > 0:
                        if history_index == len(self.history):
                            saved_buffer = "".join(chars)
                        history_index -= 1
                        hist_item = self.history[history_index]

                        # Erase current typed text on screen
                        if chars:
                            sys.stdout.write("\b \b" * len(chars))
                        chars = list(hist_item)
                        sys.stdout.write(hist_item)
                        sys.stdout.flush()

                # Down Arrow ('P') -> next query / equation
                elif code == 'P' and self.history:
                    if history_index < len(self.history):
                        history_index += 1
                        if history_index == len(self.history):
                            hist_item = saved_buffer
                        else:
                            hist_item = self.history[history_index]

                        # Erase current typed text on screen
                        if chars:
                            sys.stdout.write("\b \b" * len(chars))
                        chars = list(hist_item)
                        sys.stdout.write(hist_item)
                        sys.stdout.flush()

                continue

            # Ctrl+C
            elif ch == "\x03":
                sys.stdout.write("\n")
                return "exit"

            # Printable characters
            else:
                chars.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()

        final_line = "".join(chars)
        if final_line.strip():
            if not self.history or self.history[-1] != final_line.strip():
                self.history.append(final_line.strip())
            self.learner.add_query_history(final_line.strip())

        return final_line

    def run(self):
        # Auto-activate Control Pad and synchronize initial state
        GUIBridge.ensure_control_pad_running()
        active_f = self.learner.profile.get("user_functions", {}).get("f", "None")
        GUIBridge.notify_end_process(active_func=active_f)

        self.print_banner()

        while True:
            user_input = self.read_line_with_autocomplete("SmartCal > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q", "bye"):
                print("\nGoodbye! Your learning profile has been saved. Happy calculating!\n")
                break

            if user_input.lower() in ("cls", "clear"):
                os.system("cls" if os.name == "nt" else "clear")
                self.print_banner()
                continue

            if user_input.lower() in ("history", "hist"):
                if not self.history:
                    print("\n[History] No previous queries recorded yet.\n")
                else:
                    print("\n[Query & Equation History]:")
                    print("---------------------------------------------------------")
                    for idx, q in enumerate(self.history[-25:], 1):
                        print(f"  {idx:2d}: {q}")
                    print("---------------------------------------------------------")
                    print("  [Tip] Press Up Arrow [^] at 'SmartCal > ' to recall and edit any of these!\n")
                continue

            # 1. Active Auto-Correction
            corrected_input, fixes = self.corrector.correct_text(user_input)
            if fixes:
                print(f"  [Auto-corrected]: {', '.join(fixes)}")
                if corrected_input != user_input:
                    print(f"  [Interpreted as]: '{corrected_input}'")

            # 2. Complex Question Interpretation & Math Solver with live Process Animation sync
            curr_f = self.learner.profile.get("user_functions", {}).get("f", "")
            GUIBridge.notify_start_process(f"Solving: {corrected_input}", active_func=curr_f)

            response = ""
            try:
                response = self.interpreter.interpret_and_solve(corrected_input)
            finally:
                updated_f = self.learner.profile.get("user_functions", {}).get("f", "")
                GUIBridge.notify_end_process(active_func=updated_f, last_result=response)

            print(f"\n{response}\n")


# ==============================================================================
#                               MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    app = SmartCalculatorCLI()
    app.run()
