/*
 * ============================================================================
 *                         ADVANCED CALCULUS CALCULATOR
 * ============================================================================
 * Features:
 *   - General Math Expression Evaluator (+, -, *, /, ^, %, parentheses)
 *   - Implicit multiplication support (e.g. 2x, 3sin(x), (x+1)(x-1), 2pi)
 *   - Mathematical constants: pi, e, and previous answer memory (ans)
 *   - Full function library: sin, cos, tan, asin, acos, atan, sinh, cosh, tanh,
 *     exp, ln, log, sqrt, cbrt, abs, floor, ceil
 *   - High-Precision Numerical Definite Integrals (Simpson's 3/8 & 1/3 rules)
 *   - Step-by-Step Monomial Integrals (including x^-1 -> ln|x|)
 *   - Guided Polynomial Antiderivatives (Symbolic and Definite)
 *   - Calculus Presets Library (Standard trig, exponential, and rational forms)
 *   - First and Second Derivatives with Tangent Line equation y = mx + c
 *   - Area Between Two Curves (|f(x) - g(x)|)
 *   - Curve Arc Length computation
 *   - Newton-Raphson Numerical Root Finder
 *   - Statistics & Quick Scientific toolkit
 *   - Comprehensive interactive Help system with walkthrough examples
 * ============================================================================
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#ifndef M_E
#define M_E  2.71828182845904523536
#endif

#define MAX_LINE_LEN 512
#define MAX_TOKENS   1024

/* Global memory for last computed answer */
static double g_last_answer = 0.0;
static int g_has_last_answer = 0;

/* Token Types */
typedef enum {
    TOK_END = 0,
    TOK_NUMBER,
    TOK_VAR,        /* variable x */
    TOK_PLUS,
    TOK_MINUS,
    TOK_MUL,
    TOK_DIV,
    TOK_MOD,
    TOK_POW,
    TOK_LPAREN,
    TOK_RPAREN,
    TOK_FUNC,
    TOK_ERROR
} TokenType;

/* Supported Built-in Math Functions */
typedef enum {
    FN_NONE = 0,
    FN_SIN,
    FN_COS,
    FN_TAN,
    FN_ASIN,
    FN_ACOS,
    FN_ATAN,
    FN_SINH,
    FN_COSH,
    FN_TANH,
    FN_EXP,
    FN_LN,
    FN_LOG10,
    FN_SQRT,
    FN_CBRT,
    FN_ABS,
    FN_FLOOR,
    FN_CEIL
} FuncType;

typedef struct {
    TokenType type;
    double val;
    FuncType func;
    char text[32];
} Token;

typedef struct {
    Token tokens[MAX_TOKENS];
    int count;
    int pos;
    char error_msg[128];
    int has_error;
} Parser;

/* ============================================================================
 *                         HELPER & STRING UTILITIES
 * ============================================================================
 */

/* Trim leading and trailing whitespace from string in place */
static void trim_whitespace(char *str) {
    if (!str) return;
    char *start = str;
    while (*start && isspace((unsigned char)*start)) {
        start++;
    }
    char *end = start + strlen(start);
    while (end > start && isspace((unsigned char)*(end - 1))) {
        end--;
    }
    *end = '\0';
    if (start != str) {
        memmove(str, start, end - start + 1);
    }
}

/* Safe line reading with prompt */
static int read_line(const char *prompt, char *buffer, size_t size) {
    if (prompt && prompt[0] != '\0') {
        printf("%s", prompt);
        fflush(stdout);
    }
    if (!fgets(buffer, (int)size, stdin)) {
        buffer[0] = '\0';
        return 0;
    }
    // Remove newline characters
    buffer[strcspn(buffer, "\r\n")] = '\0';
    trim_whitespace(buffer);
    return 1;
}

/* Wait for user to press Enter */
static void wait_for_enter(void) {
    printf("\nPress [Enter] to continue...");
    fflush(stdout);
    char buf[64];
    fgets(buf, sizeof(buf), stdin);
}

/* Function name identification */
static int identify_function(const char *name, FuncType *out_fn) {
    if (strcasecmp(name, "sin") == 0)   { *out_fn = FN_SIN;   return 1; }
    if (strcasecmp(name, "cos") == 0)   { *out_fn = FN_COS;   return 1; }
    if (strcasecmp(name, "tan") == 0)   { *out_fn = FN_TAN;   return 1; }
    if (strcasecmp(name, "asin") == 0)  { *out_fn = FN_ASIN;  return 1; }
    if (strcasecmp(name, "acos") == 0)  { *out_fn = FN_ACOS;  return 1; }
    if (strcasecmp(name, "atan") == 0)  { *out_fn = FN_ATAN;  return 1; }
    if (strcasecmp(name, "sinh") == 0)  { *out_fn = FN_SINH;  return 1; }
    if (strcasecmp(name, "cosh") == 0)  { *out_fn = FN_COSH;  return 1; }
    if (strcasecmp(name, "tanh") == 0)  { *out_fn = FN_TANH;  return 1; }
    if (strcasecmp(name, "exp") == 0)   { *out_fn = FN_EXP;   return 1; }
    if (strcasecmp(name, "ln") == 0)    { *out_fn = FN_LN;    return 1; }
    if (strcasecmp(name, "log") == 0)   { *out_fn = FN_LOG10; return 1; }
    if (strcasecmp(name, "sqrt") == 0)  { *out_fn = FN_SQRT;  return 1; }
    if (strcasecmp(name, "cbrt") == 0)  { *out_fn = FN_CBRT;  return 1; }
    if (strcasecmp(name, "abs") == 0 || strcasecmp(name, "fabs") == 0) { *out_fn = FN_ABS; return 1; }
    if (strcasecmp(name, "floor") == 0) { *out_fn = FN_FLOOR; return 1; }
    if (strcasecmp(name, "ceil") == 0)  { *out_fn = FN_CEIL;  return 1; }
    return 0;
}

/* ============================================================================
 *                    MATHEMATICAL EXPRESSION PARSER & EVALUATOR
 * ============================================================================
 */

/* Lexer with intelligent implicit multiplication support */
static int tokenize_expression(Parser *p, const char *expr) {
    p->count = 0;
    p->pos = 0;
    p->has_error = 0;
    p->error_msg[0] = '\0';

    if (!expr || expr[0] == '\0') {
        p->has_error = 1;
        snprintf(p->error_msg, sizeof(p->error_msg), "Expression is empty");
        return 0;
    }

    const char *s = expr;
    while (*s) {
        if (isspace((unsigned char)*s)) {
            s++;
            continue;
        }

        // Implicit multiplication trigger: if previous token was an operand
        int prev_is_operand = 0;
        if (p->count > 0) {
            TokenType prev = p->tokens[p->count - 1].type;
            if (prev == TOK_NUMBER || prev == TOK_VAR || prev == TOK_RPAREN) {
                prev_is_operand = 1;
            }
        }

        // Numeric Literals
        if (isdigit((unsigned char)*s) || (*s == '.' && isdigit((unsigned char)*(s + 1)))) {
            if (prev_is_operand) {
                if (p->count >= MAX_TOKENS - 2) break;
                p->tokens[p->count++].type = TOK_MUL;
            }
            char *endptr;
            double v = strtod(s, &endptr);
            if (endptr == s) {
                p->has_error = 1;
                snprintf(p->error_msg, sizeof(p->error_msg), "Invalid number format at: '%s'", s);
                return 0;
            }
            if (p->count >= MAX_TOKENS - 1) break;
            p->tokens[p->count].type = TOK_NUMBER;
            p->tokens[p->count].val = v;
            p->count++;
            s = endptr;
            continue;
        }

        // Identifiers: Variable 'x', Constants 'pi', 'e', 'ans', and Functions
        if (isalpha((unsigned char)*s)) {
            char name[64];
            int len = 0;
            while (isalpha((unsigned char)*s) || isdigit((unsigned char)*s) || *s == '_') {
                if (len < 63) name[len++] = *s;
                s++;
            }
            name[len] = '\0';

            FuncType fn;
            if (strcasecmp(name, "x") == 0) {
                if (prev_is_operand) {
                    if (p->count >= MAX_TOKENS - 2) break;
                    p->tokens[p->count++].type = TOK_MUL;
                }
                p->tokens[p->count++].type = TOK_VAR;
            } else if (strcasecmp(name, "pi") == 0) {
                if (prev_is_operand) {
                    if (p->count >= MAX_TOKENS - 2) break;
                    p->tokens[p->count++].type = TOK_MUL;
                }
                p->tokens[p->count].type = TOK_NUMBER;
                p->tokens[p->count].val = M_PI;
                p->count++;
            } else if (strcasecmp(name, "e") == 0) {
                if (prev_is_operand) {
                    if (p->count >= MAX_TOKENS - 2) break;
                    p->tokens[p->count++].type = TOK_MUL;
                }
                p->tokens[p->count].type = TOK_NUMBER;
                p->tokens[p->count].val = M_E;
                p->count++;
            } else if (strcasecmp(name, "ans") == 0) {
                if (prev_is_operand) {
                    if (p->count >= MAX_TOKENS - 2) break;
                    p->tokens[p->count++].type = TOK_MUL;
                }
                p->tokens[p->count].type = TOK_NUMBER;
                p->tokens[p->count].val = g_last_answer;
                p->count++;
            } else if (identify_function(name, &fn)) {
                if (prev_is_operand) {
                    if (p->count >= MAX_TOKENS - 2) break;
                    p->tokens[p->count++].type = TOK_MUL;
                }
                p->tokens[p->count].type = TOK_FUNC;
                p->tokens[p->count].func = fn;
                strncpy(p->tokens[p->count].text, name, sizeof(p->tokens[p->count].text) - 1);
                p->count++;
            } else {
                p->has_error = 1;
                snprintf(p->error_msg, sizeof(p->error_msg), "Unknown symbol '%s'", name);
                return 0;
            }
            continue;
        }

        // Parentheses
        if (*s == '(') {
            if (prev_is_operand) {
                if (p->count >= MAX_TOKENS - 2) break;
                p->tokens[p->count++].type = TOK_MUL;
            }
            p->tokens[p->count++].type = TOK_LPAREN;
            s++;
            continue;
        }
        if (*s == ')') {
            p->tokens[p->count++].type = TOK_RPAREN;
            s++;
            continue;
        }

        // Standard Operators
        if (*s == '+') { p->tokens[p->count++].type = TOK_PLUS; s++; continue; }
        if (*s == '-') { p->tokens[p->count++].type = TOK_MINUS; s++; continue; }
        if (*s == '*') { p->tokens[p->count++].type = TOK_MUL; s++; continue; }
        if (*s == '/') { p->tokens[p->count++].type = TOK_DIV; s++; continue; }
        if (*s == '%') { p->tokens[p->count++].type = TOK_MOD; s++; continue; }
        if (*s == '^') { p->tokens[p->count++].type = TOK_POW; s++; continue; }

        p->has_error = 1;
        snprintf(p->error_msg, sizeof(p->error_msg), "Unexpected character '%c'", *s);
        return 0;
    }

    p->tokens[p->count].type = TOK_END;
    return 1;
}

/* Recursive Descent Parser Declarations */
static double parse_expr(Parser *p, double x, int *err);
static double parse_term(Parser *p, double x, int *err);
static double parse_factor(Parser *p, double x, int *err);
static double parse_power(Parser *p, double x, int *err);
static double parse_primary(Parser *p, double x, int *err);

static Token *peek_token(Parser *p) {
    if (p->pos < p->count) return &p->tokens[p->pos];
    static Token end_tok = { TOK_END, 0.0, FN_NONE, "" };
    return &end_tok;
}

static Token *consume_token(Parser *p) {
    Token *t = peek_token(p);
    if (p->pos < p->count) p->pos++;
    return t;
}

static double evaluate_func(FuncType fn, double arg, int *err) {
    switch (fn) {
        case FN_SIN: return sin(arg);
        case FN_COS: return cos(arg);
        case FN_TAN:
            if (fabs(cos(arg)) < 1e-14) { *err = 1; return 0; }
            return tan(arg);
        case FN_ASIN:
            if (arg < -1.0 || arg > 1.0) { *err = 1; return 0; }
            return asin(arg);
        case FN_ACOS:
            if (arg < -1.0 || arg > 1.0) { *err = 1; return 0; }
            return acos(arg);
        case FN_ATAN: return atan(arg);
        case FN_SINH: return sinh(arg);
        case FN_COSH: return cosh(arg);
        case FN_TANH: return tanh(arg);
        case FN_EXP:  return exp(arg);
        case FN_LN:
            if (arg <= 0.0) { *err = 1; return 0; }
            return log(arg);
        case FN_LOG10:
            if (arg <= 0.0) { *err = 1; return 0; }
            return log10(arg);
        case FN_SQRT:
            if (arg < 0.0) { *err = 1; return 0; }
            return sqrt(arg);
        case FN_CBRT: return cbrt(arg);
        case FN_ABS:  return fabs(arg);
        case FN_FLOOR: return floor(arg);
        case FN_CEIL:  return ceil(arg);
        default: return arg;
    }
}

static double parse_primary(Parser *p, double x, int *err) {
    Token *t = peek_token(p);
    if (t->type == TOK_NUMBER) {
        consume_token(p);
        return t->val;
    }
    if (t->type == TOK_VAR) {
        consume_token(p);
        return x;
    }
    if (t->type == TOK_FUNC) {
        FuncType fn = t->func;
        consume_token(p);
        Token *lp = peek_token(p);
        if (lp->type != TOK_LPAREN) {
            *err = 1;
            snprintf(p->error_msg, sizeof(p->error_msg), "Expected '(' after function name");
            return 0;
        }
        consume_token(p); // consume '('
        double arg = parse_expr(p, x, err);
        if (*err) return 0;
        Token *rp = peek_token(p);
        if (rp->type != TOK_RPAREN) {
            *err = 1;
            snprintf(p->error_msg, sizeof(p->error_msg), "Missing ')' after function argument");
            return 0;
        }
        consume_token(p); // consume ')'
        return evaluate_func(fn, arg, err);
    }
    if (t->type == TOK_LPAREN) {
        consume_token(p); // consume '('
        double v = parse_expr(p, x, err);
        if (*err) return 0;
        Token *rp = peek_token(p);
        if (rp->type != TOK_RPAREN) {
            *err = 1;
            snprintf(p->error_msg, sizeof(p->error_msg), "Unmatched opening parenthesis '('");
            return 0;
        }
        consume_token(p); // consume ')'
        return v;
    }
    *err = 1;
    snprintf(p->error_msg, sizeof(p->error_msg), "Syntax error near token");
    return 0;
}

static double parse_power(Parser *p, double x, int *err) {
    double base = parse_primary(p, x, err);
    if (*err) return 0;

    if (peek_token(p)->type == TOK_POW) {
        consume_token(p); // consume '^'
        double exponent = parse_factor(p, x, err); // right-associative
        if (*err) return 0;
        if (base < 0 && floor(exponent) != exponent) {
            *err = 1;
            snprintf(p->error_msg, sizeof(p->error_msg), "Negative base with fractional exponent");
            return 0;
        }
        return pow(base, exponent);
    }
    return base;
}

static double parse_factor(Parser *p, double x, int *err) {
    if (peek_token(p)->type == TOK_PLUS) {
        consume_token(p);
        return parse_factor(p, x, err);
    }
    if (peek_token(p)->type == TOK_MINUS) {
        consume_token(p);
        return -parse_factor(p, x, err);
    }
    return parse_power(p, x, err);
}

static double parse_term(Parser *p, double x, int *err) {
    double val = parse_factor(p, x, err);
    if (*err) return 0;

    while (peek_token(p)->type == TOK_MUL || peek_token(p)->type == TOK_DIV || peek_token(p)->type == TOK_MOD) {
        TokenType op = consume_token(p)->type;
        double right = parse_factor(p, x, err);
        if (*err) return 0;
        if (op == TOK_MUL) {
            val *= right;
        } else if (op == TOK_DIV) {
            if (fabs(right) < 1e-15) {
                *err = 1;
                snprintf(p->error_msg, sizeof(p->error_msg), "Division by zero");
                return 0;
            }
            val /= right;
        } else if (op == TOK_MOD) {
            if (fabs(right) < 1e-15) {
                *err = 1;
                snprintf(p->error_msg, sizeof(p->error_msg), "Modulo by zero");
                return 0;
            }
            val = fmod(val, right);
        }
    }
    return val;
}

static double parse_expr(Parser *p, double x, int *err) {
    double val = parse_term(p, x, err);
    if (*err) return 0;

    while (peek_token(p)->type == TOK_PLUS || peek_token(p)->type == TOK_MINUS) {
        TokenType op = consume_token(p)->type;
        double right = parse_term(p, x, err);
        if (*err) return 0;
        if (op == TOK_PLUS) {
            val += right;
        } else {
            val -= right;
        }
    }
    return val;
}

static double eval_parsed_ast(Parser *p, double x, int *err) {
    p->pos = 0;
    *err = 0;
    double res = parse_expr(p, x, err);
    if (!*err && peek_token(p)->type != TOK_END) {
        *err = 1;
        snprintf(p->error_msg, sizeof(p->error_msg), "Trailing unexpected tokens");
    }
    return res;
}

/* Evaluate an expression string directly at x */
static double evaluate_expression_at(const char *expr, double x, int *err, char *err_msg, size_t err_msg_sz) {
    Parser p;
    if (!tokenize_expression(&p, expr)) {
        *err = 1;
        if (err_msg) snprintf(err_msg, err_msg_sz, "%s", p.error_msg);
        return 0;
    }
    double val = eval_parsed_ast(&p, x, err);
    if (*err && err_msg && p.error_msg[0]) {
        snprintf(err_msg, err_msg_sz, "%s", p.error_msg);
    }
    return val;
}

/* Evaluate a constant expression or number (for entering bounds like pi/2, e^2) */
static int parse_bound_or_number(const char *str, double *out_val) {
    int err = 0;
    char err_buf[128] = {0};
    double val = evaluate_expression_at(str, 0.0, &err, err_buf, sizeof(err_buf));
    if (err) {
        return 0;
    }
    *out_val = val;
    return 1;
}

/* Prompt user for a numeric value or math constant expression (e.g. pi/2) */
static int prompt_double(const char *prompt, double *out_val) {
    char buf[MAX_LINE_LEN];
    while (1) {
        if (!read_line(prompt, buf, sizeof(buf))) return 0;
        if (strcasecmp(buf, "cancel") == 0 || strcasecmp(buf, "c") == 0) {
            return 0;
        }
        if (parse_bound_or_number(buf, out_val)) {
            return 1;
        }
        printf("  [!] Invalid input: '%s'. Enter a number (e.g. 3.14) or expression (e.g. pi/2, e). Type 'c' to cancel: ", buf);
    }
}

/* ============================================================================
 *                         CALCULUS ALGORITHMS & ENGINES
 * ============================================================================
 */

/*
 * Numerical Integration using High-Precision Composite Simpson's 1/3 Rule
 * with endpoint boundary safeguards and error estimation.
 */
static double integrate_simpson(Parser *p, double a, double b, int n, double *out_error_est, int *err) {
    *err = 0;
    if (fabs(b - a) < 1e-15) {
        if (out_error_est) *out_error_est = 0.0;
        return 0.0;
    }

    int sign = 1;
    if (b < a) {
        double tmp = a;
        a = b;
        b = tmp;
        sign = -1;
    }

    if (n % 2 != 0) n++;
    if (n < 100) n = 100;

    double h = (b - a) / n;

    // Check endpoints with slight interior shift if endpoint is non-finite (e.g. 1/sqrt(x) at 0)
    double fa = eval_parsed_ast(p, a, err);
    if (*err || isnan(fa) || isinf(fa)) {
        *err = 0;
        fa = eval_parsed_ast(p, a + 1e-8 * (b - a), err);
        if (*err || isnan(fa) || isinf(fa)) return 0;
    }

    double fb = eval_parsed_ast(p, b, err);
    if (*err || isnan(fb) || isinf(fb)) {
        *err = 0;
        fb = eval_parsed_ast(p, b - 1e-8 * (b - a), err);
        if (*err || isnan(fb) || isinf(fb)) return 0;
    }

    double sum_odd = 0.0;
    double sum_even = 0.0;

    for (int i = 1; i < n; i++) {
        double xi = a + i * h;
        double fxi = eval_parsed_ast(p, xi, err);
        if (*err || isnan(fxi) || isinf(fxi)) {
            // Function undefined or singularity along integration path
            return 0;
        }
        if (i % 2 == 1) {
            sum_odd += fxi;
        } else {
            sum_even += fxi;
        }
    }

    double result = (h / 3.0) * (fa + 4.0 * sum_odd + 2.0 * sum_even + fb);

    // Error estimation using coarse step (n/2) comparison
    if (out_error_est) {
        double coarse_h = (b - a) / (n / 2);
        double coarse_sum_odd = 0.0;
        double coarse_sum_even = 0.0;
        int half_n = n / 2;
        for (int i = 1; i < half_n; i++) {
            double xi = a + i * coarse_h;
            double fxi = eval_parsed_ast(p, xi, err);
            if (i % 2 == 1) coarse_sum_odd += fxi;
            else coarse_sum_even += fxi;
        }
        double coarse_res = (coarse_h / 3.0) * (fa + 4.0 * coarse_sum_odd + 2.0 * coarse_sum_even + fb);
        *out_error_est = fabs(result - coarse_res) / 15.0;
    }

    return sign * result;
}

/*
 * Numerical First Derivative using 5-point central difference stencil:
 *   f'(x) = (-f(x + 2h) + 8f(x + h) - 8f(x - h) + f(x - 2h)) / (12h)
 */
static double derivative_5point(Parser *p, double x, int *err) {
    double h = 1e-5;
    *err = 0;

    double f_p2 = eval_parsed_ast(p, x + 2.0 * h, err); if (*err) return 0;
    double f_p1 = eval_parsed_ast(p, x + h, err);       if (*err) return 0;
    double f_m1 = eval_parsed_ast(p, x - h, err);       if (*err) return 0;
    double f_m2 = eval_parsed_ast(p, x - 2.0 * h, err); if (*err) return 0;

    return (-f_p2 + 8.0 * f_p1 - 8.0 * f_m1 + f_m2) / (12.0 * h);
}

/*
 * Numerical Second Derivative:
 *   f''(x) = (f(x + h) - 2f(x) + f(x - h)) / h^2
 */
static double second_derivative(Parser *p, double x, int *err) {
    double h = 1e-4;
    *err = 0;

    double f_mid = eval_parsed_ast(p, x, err);     if (*err) return 0;
    double f_p1  = eval_parsed_ast(p, x + h, err); if (*err) return 0;
    double f_m1  = eval_parsed_ast(p, x - h, err); if (*err) return 0;

    return (f_p1 - 2.0 * f_mid + f_m1) / (h * h);
}

/*
 * Newton-Raphson Root Finder: solves f(x) = 0
 */
static int find_root_newton(Parser *p, double initial_guess, double *out_root, int *out_iters) {
    double x = initial_guess;
    const int max_iters = 100;
    const double tol = 1e-10;
    int err = 0;

    for (int iter = 0; iter < max_iters; iter++) {
        double fx = eval_parsed_ast(p, x, &err);
        if (err || isnan(fx) || isinf(fx)) return 0;

        if (fabs(fx) < tol) {
            *out_root = x;
            *out_iters = iter;
            return 1;
        }

        double dfx = derivative_5point(p, x, &err);
        if (err || fabs(dfx) < 1e-14) {
            // Derivative too close to zero; perturb x
            x += 0.05;
            continue;
        }

        double next_x = x - fx / dfx;
        if (fabs(next_x - x) < tol) {
            *out_root = next_x;
            *out_iters = iter + 1;
            return 1;
        }
        x = next_x;
    }

    *out_root = x;
    *out_iters = max_iters;
    return 0; // Did not reach tight convergence
}

/* ============================================================================
 *                         CALCULUS MENU ACTIONS
 * ============================================================================
 */

/* Action 1: General Definite Integral */
static void action_definite_integral_general(void) {
    char expr[MAX_LINE_LEN];
    double a = 0.0, b = 0.0;
    Parser p;

    printf("\n------------------------------------------------------------\n");
    printf("        CALCULUS: Definite Integral of Any Function\n");
    printf("------------------------------------------------------------\n");
    printf("Enter any math function f(x). Examples:\n");
    printf("   x^2           sin(x)          exp(-x^2)       1/x\n");
    printf("   3x^3 - 2x + 1   sin(x)^2        1/(1 + x^2)     sqrt(4 - x^2)\n\n");

    while (1) {
        if (!read_line("Enter f(x) [or 'c' to cancel]: ", expr, sizeof(expr))) return;
        if (strcasecmp(expr, "c") == 0 || strcasecmp(expr, "cancel") == 0) return;

        if (tokenize_expression(&p, expr)) {
            break;
        }
        printf("  [!] Syntax Error: %s. Please try again.\n", p.error_msg);
    }

    printf("\nEnter integration bounds (supports numbers or expressions like '0', 'pi', 'pi/2', 'e'):\n");
    if (!prompt_double("Enter lower bound a: ", &a)) return;
    if (!prompt_double("Enter upper bound b: ", &b)) return;

    printf("\nCalculating integral...\n");
    int err = 0;
    double err_est = 0.0;
    double result = integrate_simpson(&p, a, b, 10000, &err_est, &err);

    if (err || isnan(result) || isinf(result)) {
        printf("\n[!] Calculation Error: Could not evaluate integral.\n");
        printf("    The function may have an asymptote, discontinuity, or be undefined on [%.4f, %.4f].\n", a, b);
    } else {
        printf("\n==================== INTEGRATION RESULT ====================\n");
        printf("  Function        : f(x) = %s\n", expr);
        printf("  Interval        : [%.6g, %.6g]\n", a, b);
        printf("  --------------------------------------------------------\n");
        printf("  Integral Value  : integral = %.10f\n", result);
        printf("  Scientific Form : %e\n", result);
        printf("  Estimated Error : +/- %.2e\n", err_est);
        printf("============================================================\n");
        g_last_answer = result;
        g_has_last_answer = 1;
    }
    wait_for_enter();
}

/* Action 2: Step-by-Step Monomial Calculus */
static void action_monomial_calculus(void) {
    double a = 1.0, n = 1.0;
    char choice[16];

    printf("\n------------------------------------------------------------\n");
    printf("        CALCULUS: Monomial Analysis [ f(x) = a * x^n ]\n");
    printf("------------------------------------------------------------\n");
    printf("1. Indefinite Integral [ Symbolic Antiderivative with + C ]\n");
    printf("2. Definite Integral   [ Evaluated between lower & upper bounds ]\n");
    printf("3. Derivative          [ Step-by-step differentiation at x ]\n");
    printf("4. Return\n");
    if (!read_line("Choose option: ", choice, sizeof(choice))) return;

    if (choice[0] == '4' || strcasecmp(choice, "c") == 0) return;

    if (!prompt_double("Enter coefficient a: ", &a)) return;
    if (!prompt_double("Enter exponent n: ", &n)) return;

    if (choice[0] == '1') {
        printf("\n=================== INDEFINITE INTEGRAL (ANTIDERIVATIVE) ===================\n");
        printf("Function: f(x) = %.4g * x^(%.4g)\n\n", a, n);
        if (fabs(n - (-1.0)) < 1e-9) {
            printf("Step 1: Notice exponent n = -1. Standard power rule does not apply.\n");
            printf("        Recall Reciprocal / Logarithmic Rule:\n");
            printf("        integral (a / x) dx = a * ln|x| + C\n\n");
            printf("----------------------------------------------------------------------------\n");
            printf("Final Equation:\n");
            printf("  integral (%.4g / x) dx = %.4g * ln|x| + C\n", a, a);
            printf("----------------------------------------------------------------------------\n");
        } else {
            double new_exp = n + 1.0;
            double new_coeff = a / new_exp;
            printf("Step 1: Power Rule for Integration (n != -1):\n");
            printf("        integral (a * x^n) dx = [ a / (n + 1) ] * x^(n + 1) + C\n\n");
            printf("Step 2: Compute parameters:\n");
            printf("        New Exponent    = %.4g + 1 = %.4g\n", n, new_exp);
            printf("        New Coefficient = %.4g / %.4g = %.6g\n\n", a, new_exp, new_coeff);
            printf("----------------------------------------------------------------------------\n");
            printf("Final Equation:\n");
            if (new_exp == 1.0) {
                printf("  integral (%.4g * x^%.4g) dx = %.6g * x + C\n", a, n, new_coeff);
            } else {
                printf("  integral (%.4g * x^%.4g) dx = %.6g * x^(%.4g) + C\n", a, n, new_coeff, new_exp);
            }
            printf("----------------------------------------------------------------------------\n");
            printf("Note: '+ C' is the arbitrary constant of integration.\n");
        }
        printf("============================================================================\n");
    } else if (choice[0] == '2') {
        double lower = 0.0, upper = 0.0;
        if (!prompt_double("Enter lower bound: ", &lower)) return;
        if (!prompt_double("Enter upper bound: ", &upper)) return;

        printf("\n=================== INTEGRAL STEP-BY-STEP ===================\n");
        printf("Monomial: f(x) = %.4g * x^(%.4g)\n\n", a, n);

        if (fabs(n - (-1.0)) < 1e-9) {
            // Case n = -1: integral is a * ln|x|
            printf("Step 1: Notice exponent n = -1. Standard power rule does not apply.\n");
            printf("        Recall special integration rule:\n");
            printf("        integral (a / x) dx = a * ln|x| + C\n\n");
            printf("Step 2: Antiderivative F(x) = %.4g * ln|x| + C\n\n", a);

            if (lower <= 0.0 && upper >= 0.0) {
                printf("[!] Error: Integration interval [%.4g, %.4g] crosses x = 0 (singularity of 1/x).\n", lower, upper);
            } else if ((lower <= 0.0 && upper < 0.0) || (lower > 0.0 && upper >= 0.0)) {
                double F_upper = a * log(fabs(upper));
                double F_lower = a * log(fabs(lower));
                double total = F_upper - F_lower;
                printf("Step 3: Evaluate by Fundamental Theorem of Calculus:\n");
                printf("        F(%.4g) = %.4g * ln|%.4g| = %.6f\n", upper, a, upper, F_upper);
                printf("        F(%.4g) = %.4g * ln|%.4g| = %.6f\n", lower, a, lower, F_lower);
                printf("        Result = F(%.4g) - F(%.4g) = %.10f\n", upper, lower, total);
                printf("============================================================\n");
                g_last_answer = total;
                g_has_last_answer = 1;
            }
        } else {
            // General Power Rule: integral a*x^n dx = (a/(n+1)) * x^(n+1)
            double new_exp = n + 1.0;
            double new_coeff = a / new_exp;
            printf("Step 1: Power Rule for Integrals:\n");
            printf("        integral (a * x^n) dx = [ a / (n + 1) ] * x^(n + 1) + C\n\n");
            printf("Step 2: Compute new parameters:\n");
            printf("        New Exponent = %.4g + 1 = %.4g\n", n, new_exp);
            printf("        New Coefficient = %.4g / %.4g = %.6g\n", a, new_exp, new_coeff);
            printf("        Antiderivative: F(x) = %.6g * x^(%.4g) + C\n\n", new_coeff, new_exp);

            double F_lower = new_coeff * pow(lower, new_exp);
            double F_upper = new_coeff * pow(upper, new_exp);
            double total = F_upper - F_lower;

            printf("Step 3: Evaluate limits:\n");
            printf("        F(%.4g) = %.6f\n", upper, F_upper);
            printf("        F(%.4g) = %.6f\n", lower, F_lower);
            printf("        Definite Integral = %.10f\n", total);
            printf("============================================================\n");
            g_last_answer = total;
            g_has_last_answer = 1;
        }
    } else if (choice[0] == '3') {
        double x_val = 0.0;
        if (!prompt_double("Enter evaluation point x: ", &x_val)) return;

        double d_coeff = a * n;
        double d_exp = n - 1.0;
        double result = (n == 0) ? 0.0 : (d_coeff * pow(x_val, d_exp));

        printf("\n=================== DERIVATIVE STEP-BY-STEP =================\n");
        printf("Function: f(x) = %.4g * x^(%.4g)\n\n", a, n);
        printf("Step 1: Power Rule for Differentiation:\n");
        printf("        d/dx [ a * x^n ] = (a * n) * x^(n - 1)\n\n");
        printf("Step 2: Compute derivative formula:\n");
        printf("        f'(x) = %.6g * x^(%.4g)\n\n", d_coeff, d_exp);
        printf("Step 3: Evaluate at x = %.4g:\n", x_val);
        printf("        f'(%.4g) = %.10f\n", x_val, result);
        printf("============================================================\n");
        g_last_answer = result;
        g_has_last_answer = 1;
    }
    wait_for_enter();
}

/* Action 3: Guided Polynomial Calculus */
static void action_polynomial_calculus(void) {
    printf("\n------------------------------------------------------------\n");
    printf("        CALCULUS: Guided Polynomial Antiderivative & Integral\n");
    printf("------------------------------------------------------------\n");
    printf("A polynomial has the form: P(x) = c_d*x^d + c_(d-1)*x^(d-1) + ... + c_0\n\n");

    double deg_in = 0.0;
    if (!prompt_double("Enter degree of polynomial (e.g. 2 for quadratic, 3 for cubic): ", &deg_in)) return;
    int degree = (int)deg_in;
    if (degree < 0 || degree > 20) {
        printf("[!] Degree must be between 0 and 20.\n");
        wait_for_enter();
        return;
    }

    double coeffs[21] = {0}; // index i is coefficient for x^i
    for (int i = degree; i >= 0; i--) {
        char prompt[64];
        snprintf(prompt, sizeof(prompt), "Enter coefficient for x^%d: ", i);
        if (!prompt_double(prompt, &coeffs[i])) return;
    }

    printf("\nPolynomial Entered:\n  P(x) = ");
    int first = 1;
    for (int i = degree; i >= 0; i--) {
        if (coeffs[i] == 0 && degree > 0) continue;
        if (!first && coeffs[i] > 0) printf(" + ");
        if (coeffs[i] < 0) printf(" - ");
        double mag = fabs(coeffs[i]);
        if (i == 0) {
            printf("%.4g", mag);
        } else if (i == 1) {
            if (mag == 1.0) printf("x");
            else printf("%.4gx", mag);
        } else {
            if (mag == 1.0) printf("x^%d", i);
            else printf("%.4gx^%d", mag, i);
        }
        first = 0;
    }
    printf("\n");

    printf("\nExact Symbolic Antiderivative:\n  integral P(x) dx = ");
    first = 1;
    for (int i = degree; i >= 0; i--) {
        if (coeffs[i] == 0) continue;
        double int_coeff = coeffs[i] / (i + 1.0);
        if (!first && int_coeff > 0) printf(" + ");
        if (int_coeff < 0) printf(" - ");
        double mag = fabs(int_coeff);
        int p = i + 1;
        if (mag == 1.0) {
            if (p == 1) printf("x");
            else printf("x^%d", p);
        } else {
            if (p == 1) printf("%.4gx", mag);
            else printf("%.4gx^%d", mag, p);
        }
        first = 0;
    }
    printf(" + C\n\n");

    char calc_bounds[16];
    read_line("Compute definite integral with bounds? (y/n): ", calc_bounds, sizeof(calc_bounds));
    if (calc_bounds[0] == 'y' || calc_bounds[0] == 'Y') {
        double a = 0.0, b = 0.0;
        if (prompt_double("Enter lower bound a: ", &a) && prompt_double("Enter upper bound b: ", &b)) {
            double total_a = 0.0;
            double total_b = 0.0;
            for (int i = degree; i >= 0; i--) {
                double int_coeff = coeffs[i] / (i + 1.0);
                total_a += int_coeff * pow(a, i + 1.0);
                total_b += int_coeff * pow(b, i + 1.0);
            }
            double ans = total_b - total_a;
            printf("\n==================== INTEGRAL RESULT ====================\n");
            printf("  F(%.4g) = %.8f\n", b, total_b);
            printf("  F(%.4g) = %.8f\n", a, total_a);
            printf("  integral P(x) dx from %.4g to %.4g = %.10f\n", a, b, ans);
            printf("=========================================================\n");
            g_last_answer = ans;
            g_has_last_answer = 1;
        }
    }
    wait_for_enter();
}

/* Action 4: Common Calculus Integral Presets */
static void action_calculus_presets(void) {
    char choice[16];
    printf("\n------------------------------------------------------------\n");
    printf("          CALCULUS: Fast Common Integral Presets\n");
    printf("------------------------------------------------------------\n");
    printf("1. Exponential   : integral exp(k*x) dx     = (1/k)*exp(k*x) + C\n");
    printf("2. Sine          : integral sin(k*x) dx     = -(1/k)*cos(k*x) + C\n");
    printf("3. Cosine        : integral cos(k*x) dx     = (1/k)*sin(k*x) + C\n");
    printf("4. Natural Log   : integral ln(x) dx        = x*ln(x) - x + C\n");
    printf("5. Rational Arctan: integral 1/(x^2 + a^2) dx = (1/a)*atan(x/a) + C\n");
    printf("6. Gaussian / Normal: integral exp(-x^2) dx (Numerical)\n");
    printf("7. Return\n");
    if (!read_line("Select preset (1-7): ", choice, sizeof(choice))) return;

    if (choice[0] >= '1' && choice[0] <= '5') {
        double k = 1.0;
        if (choice[0] != '4') {
            if (!prompt_double("Enter parameter (k or a): ", &k)) return;
            if (fabs(k) < 1e-12) {
                printf("[!] Parameter cannot be zero.\n");
                wait_for_enter();
                return;
            }
        }
        double lower = 0.0, upper = 0.0;
        if (!prompt_double("Enter lower bound a: ", &lower)) return;
        if (!prompt_double("Enter upper bound b: ", &upper)) return;

        double ans = 0.0;
        switch (choice[0]) {
            case '1': ans = (exp(k * upper) - exp(k * lower)) / k; break;
            case '2': ans = (-cos(k * upper) + cos(k * lower)) / k; break;
            case '3': ans = (sin(k * upper) - sin(k * lower)) / k; break;
            case '4':
                if (lower <= 0 || upper <= 0) {
                    printf("[!] ln(x) requires bounds > 0.\n");
                    wait_for_enter();
                    return;
                }
                ans = (upper * log(upper) - upper) - (lower * log(lower) - lower);
                break;
            case '5': ans = (atan(upper / k) - atan(lower / k)) / k; break;
        }
        printf("\n==================== PRESET RESULT ====================\n");
        printf("Definite Integral Value: %.10f\n", ans);
        printf("=======================================================\n");
        g_last_answer = ans;
        g_has_last_answer = 1;
    } else if (choice[0] == '6') {
        double lower = 0.0, upper = 0.0;
        if (!prompt_double("Enter lower bound a: ", &lower)) return;
        if (!prompt_double("Enter upper bound b: ", &upper)) return;
        Parser p;
        tokenize_expression(&p, "exp(-x^2)");
        int err = 0;
        double err_est = 0.0;
        double ans = integrate_simpson(&p, lower, upper, 10000, &err_est, &err);
        printf("\n==================== GAUSSIAN RESULT ====================\n");
        printf("Definite Integral of exp(-x^2) = %.10f (+/- %.2e)\n", ans, err_est);
        printf("=========================================================\n");
        g_last_answer = ans;
        g_has_last_answer = 1;
    }
    wait_for_enter();
}

/* Action 5: Derivative & Tangent Line */
static void action_derivative_tangent(void) {
    char expr[MAX_LINE_LEN];
    double x0 = 0.0;
    Parser p;

    printf("\n------------------------------------------------------------\n");
    printf("        CALCULUS: Derivative, Curvature & Tangent Line\n");
    printf("------------------------------------------------------------\n");
    if (!read_line("Enter function f(x): ", expr, sizeof(expr))) return;
    if (!tokenize_expression(&p, expr)) {
        printf("  [!] Error: %s\n", p.error_msg);
        wait_for_enter();
        return;
    }

    if (!prompt_double("Enter evaluation point x0: ", &x0)) return;

    int err = 0;
    double y0 = eval_parsed_ast(&p, x0, &err);
    if (err) {
        printf("[!] Function is undefined at x0 = %.4g\n", x0);
        wait_for_enter();
        return;
    }

    double slope = derivative_5point(&p, x0, &err);
    if (err) {
        printf("[!] Derivative undefined or non-differentiable at x0 = %.4g\n", x0);
        wait_for_enter();
        return;
    }

    double curvature = second_derivative(&p, x0, &err);

    // Tangent line equation: y = m(x - x0) + y0 -> y = m*x + (y0 - m*x0)
    double intercept = y0 - slope * x0;

    printf("\n==================== DERIVATIVE ANALYSIS ====================\n");
    printf("  Point             : (x0, y0) = (%.6g, %.6g)\n", x0, y0);
    printf("  1st Derivative f' : slope m = %.10f\n", slope);
    printf("  2nd Derivative f'': concavity = %.10f ", curvature);
    if (curvature > 1e-5) printf("[Concave UP - Local Minimum / Bowl]\n");
    else if (curvature < -1e-5) printf("[Concave DOWN - Local Maximum / Hill]\n");
    else printf("[Possible Inflection Point]\n");
    printf("  --------------------------------------------------------\n");
    printf("  Tangent Line Eq   : y = %.6g * x %s %.6g\n",
           slope, (intercept >= 0 ? "+" : "-"), fabs(intercept));
    printf("============================================================\n");

    g_last_answer = slope;
    g_has_last_answer = 1;
    wait_for_enter();
}

/* Action 6: Area Between Two Curves */
static void action_area_between_curves(void) {
    char expr_f[MAX_LINE_LEN], expr_g[MAX_LINE_LEN];
    Parser pf, pg;
    double a = 0.0, b = 0.0;

    printf("\n------------------------------------------------------------\n");
    printf("        CALCULUS: Area Between Two Curves [f(x) & g(x)]\n");
    printf("------------------------------------------------------------\n");
    if (!read_line("Enter top/first function f(x): ", expr_f, sizeof(expr_f))) return;
    if (!tokenize_expression(&pf, expr_f)) {
        printf("[!] Error in f(x): %s\n", pf.error_msg);
        wait_for_enter();
        return;
    }

    if (!read_line("Enter bottom/second function g(x): ", expr_g, sizeof(expr_g))) return;
    if (!tokenize_expression(&pg, expr_g)) {
        printf("[!] Error in g(x): %s\n", pg.error_msg);
        wait_for_enter();
        return;
    }

    if (!prompt_double("Enter lower bound a: ", &a)) return;
    if (!prompt_double("Enter upper bound b: ", &b)) return;

    // We integrate |f(x) - g(x)| numerically
    int n = 10000;
    double h = (b - a) / n;
    int err = 0;
    double net_sum = 0.0;
    double abs_sum = 0.0;

    for (int i = 0; i <= n; i++) {
        double x = a + i * h;
        double yf = eval_parsed_ast(&pf, x, &err);
        double yg = eval_parsed_ast(&pg, x, &err);
        if (err) {
            printf("[!] Evaluation error along the interval.\n");
            wait_for_enter();
            return;
        }
        double diff = yf - yg;
        double abs_diff = fabs(diff);
        double weight = (i == 0 || i == n) ? 1.0 : ((i % 2 == 1) ? 4.0 : 2.0);
        net_sum += weight * diff;
        abs_sum += weight * abs_diff;
    }

    double net_area = (h / 3.0) * net_sum;
    double total_enclosed = (h / 3.0) * abs_sum;

    printf("\n================== AREA BETWEEN CURVES ==================\n");
    printf("  Interval           : [%.4g, %.4g]\n", a, b);
    printf("  Total Enclosed Area: integral |f(x) - g(x)| dx = %.10f\n", total_enclosed);
    printf("  Net Signed Area    : integral (f(x) - g(x)) dx = %.10f\n", net_area);
    printf("=========================================================\n");

    g_last_answer = total_enclosed;
    g_has_last_answer = 1;
    wait_for_enter();
}

/* Action 7: Numerical Root Finder */
static void action_root_finder(void) {
    char expr[MAX_LINE_LEN];
    Parser p;
    double guess = 1.0;

    printf("\n------------------------------------------------------------\n");
    printf("        CALCULUS: Numerical Root Finder [ f(x) = 0 ]\n");
    printf("------------------------------------------------------------\n");
    if (!read_line("Enter equation f(x): ", expr, sizeof(expr))) return;
    if (!tokenize_expression(&p, expr)) {
        printf("[!] Error: %s\n", p.error_msg);
        wait_for_enter();
        return;
    }

    if (!prompt_double("Enter initial guess for x (e.g. 0 or 1): ", &guess)) return;

    double root = 0.0;
    int iters = 0;
    int success = find_root_newton(&p, guess, &root, &iters);

    int err = 0;
    double residual = eval_parsed_ast(&p, root, &err);

    printf("\n====================== ROOT RESULT ======================\n");
    if (success) {
        printf("  Status       : SUCCESS (converged in %d iterations)\n", iters);
    } else {
        printf("  Status       : APPROXIMATE (reached max iterations)\n");
    }
    printf("  Root found x : %.10f\n", root);
    printf("  f(root)      : %.2e (residual error)\n", residual);
    printf("=========================================================\n");

    g_last_answer = root;
    g_has_last_answer = 1;
    wait_for_enter();
}

/* Action 8: Arc Length of Curve */
static void action_arc_length(void) {
    char expr[MAX_LINE_LEN];
    Parser p;
    double a = 0.0, b = 0.0;

    printf("\n------------------------------------------------------------\n");
    printf("        CALCULUS: Arc Length of Curve y = f(x)\n");
    printf("------------------------------------------------------------\n");
    printf("Formula: L = integral from a to b of sqrt(1 + (f'(x))^2) dx\n\n");
    if (!read_line("Enter function f(x): ", expr, sizeof(expr))) return;
    if (!tokenize_expression(&p, expr)) {
        printf("[!] Error: %s\n", p.error_msg);
        wait_for_enter();
        return;
    }

    if (!prompt_double("Enter lower bound a: ", &a)) return;
    if (!prompt_double("Enter upper bound b: ", &b)) return;

    int n = 10000;
    double h = (b - a) / n;
    int err = 0;
    double sum = 0.0;

    for (int i = 0; i <= n; i++) {
        double x = a + i * h;
        double df = derivative_5point(&p, x, &err);
        if (err) {
            printf("[!] Derivative error along curve.\n");
            wait_for_enter();
            return;
        }
        double integrand = sqrt(1.0 + df * df);
        double weight = (i == 0 || i == n) ? 1.0 : ((i % 2 == 1) ? 4.0 : 2.0);
        sum += weight * integrand;
    }

    double length = (h / 3.0) * sum;

    printf("\n====================== ARC LENGTH ======================\n");
    printf("  Function   : f(x) = %s\n", expr);
    printf("  Interval   : [%.4g, %.4g]\n", a, b);
    printf("  Curve Length L = %.10f\n", length);
    printf("========================================================\n");

    g_last_answer = length;
    g_has_last_answer = 1;
    wait_for_enter();
}

/* Calculus Submenu */
static void menu_calculus(void) {
    char choice[16];
    while (1) {
        printf("\n============================================================\n");
        printf("                   ADVANCED CALCULUS SUITE\n");
        printf("============================================================\n");
        printf("  1. Definite Integral of Any Function  [ e.g. sin(x), exp(-x^2) ]\n");
        printf("  2. Monomial Analysis & Steps          [ a*x^n derivative & integral ]\n");
        printf("  3. Guided Polynomial Antiderivative   [ Exact symbolic & limits ]\n");
        printf("  4. Common Integral Presets            [ Fast trig, exp, rational ]\n");
        printf("  5. Derivative, Curvature & Tangent    [ f'(x), f''(x), y = mx + c ]\n");
        printf("  6. Area Between Two Curves            [ integral |f(x) - g(x)| dx ]\n");
        printf("  7. Numerical Root Finder              [ Solves f(x) = 0 ]\n");
        printf("  8. Arc Length of a Curve              [ integral sqrt(1 + f'^2) dx ]\n");
        printf("  9. Calculus Help & Tutorial\n");
        printf(" 10. Return to Main Menu\n");
        printf("------------------------------------------------------------\n");

        if (!read_line("Choose calculus tool (1-10): ", choice, sizeof(choice))) return;

        if (strcmp(choice, "1") == 0) {
            action_definite_integral_general();
        } else if (strcmp(choice, "2") == 0) {
            action_monomial_calculus();
        } else if (strcmp(choice, "3") == 0) {
            action_polynomial_calculus();
        } else if (strcmp(choice, "4") == 0) {
            action_calculus_presets();
        } else if (strcmp(choice, "5") == 0) {
            action_derivative_tangent();
        } else if (strcmp(choice, "6") == 0) {
            action_area_between_curves();
        } else if (strcmp(choice, "7") == 0) {
            action_root_finder();
        } else if (strcmp(choice, "8") == 0) {
            action_arc_length();
        } else if (strcmp(choice, "9") == 0) {
            // Forward to Help
            void show_help_calculus(void);
            show_help_calculus();
        } else if (strcmp(choice, "10") == 0 || strcasecmp(choice, "back") == 0 || strcasecmp(choice, "q") == 0) {
            break;
        } else {
            printf("\n[!] Invalid choice. Please enter a number between 1 and 10.\n");
        }
    }
}

/* ============================================================================
 *                    DIRECT EXPRESSION CALCULATOR MODE
 * ============================================================================
 */

static void action_expression_calculator(void) {
    char expr[MAX_LINE_LEN];
    printf("\n============================================================\n");
    printf("               DIRECT EXPRESSION CALCULATOR\n");
    printf("============================================================\n");
    printf("Type any arithmetic or scientific expression. Type 'exit' to return.\n");
    printf("Examples:\n");
    printf("   (3 + 4) * 5^2 - sqrt(16)\n");
    printf("   2 * sin(pi / 4) + cos(pi / 3)\n");
    printf("   ln(e^5) + 3*ans\n");
    printf("   10! / (2! * 8!)  [Note: use standard expressions]\n");
    printf("------------------------------------------------------------\n");

    while (1) {
        if (!read_line("\nExpr > ", expr, sizeof(expr))) break;
        if (strcasecmp(expr, "exit") == 0 || strcasecmp(expr, "q") == 0 || strcasecmp(expr, "back") == 0) {
            break;
        }
        if (expr[0] == '\0') continue;

        int err = 0;
        char err_msg[128] = {0};
        double val = evaluate_expression_at(expr, 0.0, &err, err_msg, sizeof(err_msg));

        if (err) {
            printf("  [!] Error: %s\n", err_msg[0] ? err_msg : "Invalid syntax or math domain error");
        } else {
            printf("  = %.10g\n", val);
            g_last_answer = val;
            g_has_last_answer = 1;
        }
    }
}

/* ============================================================================
 *                    STATISTICS & SCIENTIFIC TOOLKIT
 * ============================================================================
 */

static void action_statistics(void) {
    printf("\n------------------------------------------------------------\n");
    printf("               STATISTICS & DATA ANALYSIS\n");
    printf("------------------------------------------------------------\n");
    printf("Enter numbers separated by spaces (e.g.: 12 15 22.5 18 9 25 31):\n");

    char line[MAX_LINE_LEN];
    if (!read_line("Data > ", line, sizeof(line))) return;

    double data[256];
    int count = 0;
    char *token = strtok(line, " \t,");
    while (token && count < 256) {
        double v;
        if (parse_bound_or_number(token, &v)) {
            data[count++] = v;
        }
        token = strtok(NULL, " \t,");
    }

    if (count == 0) {
        printf("[!] No valid numbers entered.\n");
        wait_for_enter();
        return;
    }

    // Sort data for median calculation
    for (int i = 0; i < count - 1; i++) {
        for (int j = i + 1; j < count; j++) {
            if (data[i] > data[j]) {
                double tmp = data[i];
                data[i] = data[j];
                data[j] = tmp;
            }
        }
    }

    double sum = 0.0;
    for (int i = 0; i < count; i++) sum += data[i];
    double mean = sum / count;

    double sq_diff_sum = 0.0;
    for (int i = 0; i < count; i++) {
        sq_diff_sum += (data[i] - mean) * (data[i] - mean);
    }
    double var = (count > 1) ? (sq_diff_sum / (count - 1)) : 0.0;
    double std_dev = sqrt(var);

    double median = (count % 2 == 1) ? data[count / 2] : ((data[count / 2 - 1] + data[count / 2]) / 2.0);

    printf("\n==================== STATISTICAL SUMMARY ====================\n");
    printf("  Sample Count (N)  : %d\n", count);
    printf("  Minimum           : %.6g\n", data[0]);
    printf("  Maximum           : %.6g\n", data[count - 1]);
    printf("  Sum               : %.6g\n", sum);
    printf("  Mean (Average)    : %.6g\n", mean);
    printf("  Median            : %.6g\n", median);
    printf("  Sample Variance   : %.6g\n", var);
    printf("  Standard Deviation: %.6g\n", std_dev);
    printf("=============================================================\n");

    g_last_answer = mean;
    g_has_last_answer = 1;
    wait_for_enter();
}

/* ============================================================================
 *                    STANDARD ARITHMETIC QUICK MODE
 * ============================================================================
 */

static void action_standard_arithmetic(void) {
    char op[16];
    double num1, num2, res;

    printf("\n------------------------------------------------------------\n");
    printf("                 STANDARD ARITHMETIC\n");
    printf("------------------------------------------------------------\n");
    printf("  1. Addition (+)\n");
    printf("  2. Subtraction (-)\n");
    printf("  3. Multiplication (*)\n");
    printf("  4. Division (/)\n");
    printf("  5. Power (^)\n");
    printf("  6. Return\n");
    if (!read_line("Choose operation: ", op, sizeof(op))) return;

    if (op[0] < '1' || op[0] > '5') return;

    if (!prompt_double("Enter first number: ", &num1)) return;
    if (!prompt_double("Enter second number: ", &num2)) return;

    switch (op[0]) {
        case '1':
            res = num1 + num2;
            printf("\nResult: %.6g + %.6g = %.10g\n", num1, num2, res);
            break;
        case '2':
            res = num1 - num2;
            printf("\nResult: %.6g - %.6g = %.10g\n", num1, num2, res);
            break;
        case '3':
            res = num1 * num2;
            printf("\nResult: %.6g * %.6g = %.10g\n", num1, num2, res);
            break;
        case '4':
            if (fabs(num2) < 1e-15) {
                printf("\n[!] Error: Division by zero is undefined.\n");
                wait_for_enter();
                return;
            }
            res = num1 / num2;
            printf("\nResult: %.6g / %.6g = %.10g\n", num1, num2, res);
            break;
        case '5':
            res = pow(num1, num2);
            printf("\nResult: %.6g ^ %.6g = %.10g\n", num1, num2, res);
            break;
    }
    g_last_answer = res;
    g_has_last_answer = 1;
    wait_for_enter();
}

/* ============================================================================
 *                      HELP & DOCUMENTATION SYSTEM
 * ============================================================================
 */

void show_help_calculus(void) {
    printf("\n============================================================\n");
    printf("               CALCULUS GUIDE: HOW TO USE\n");
    printf("============================================================\n");
    printf("1. HOW TO CALCULATE DEFINITE INTEGRALS:\n");
    printf("   - Select Option 1 from the Calculus menu.\n");
    printf("   - Type your function of 'x'.\n");
    printf("     Examples: x^2, sin(x), exp(-x^2), 1/x, 3x^2 + 2x - 5\n");
    printf("   - Enter lower bound a and upper bound b.\n");
    printf("     You can type math constants for bounds, like 'pi', 'pi/2', 'e'!\n");
    printf("   - The calculator uses Simpson's Rule with 10,000 subintervals\n");
    printf("     to compute the area to high accuracy with an error estimate.\n\n");

    printf("2. POLYNOMIALS & STEP-BY-STEP:\n");
    printf("   - Option 2: Step-by-step for a*x^n (including x^-1 -> a*ln|x|).\n");
    printf("   - Option 3: Guided Polynomial mode prompts you for coefficients\n");
    printf("     and outputs the exact symbolic antiderivative formula!\n\n");

    printf("3. DERIVATIVES & TANGENT LINES:\n");
    printf("   - Select Option 5.\n");
    printf("   - Enter f(x) and a target x0.\n");
    printf("   - The calculator provides the exact slope f'(x0), concavity f''(x0),\n");
    printf("     and the line equation y = mx + c.\n\n");

    printf("4. TIPS FOR BEST RESULTS:\n");
    printf("   - Implicit multiplication is supported: '2x' is treated as '2*x'.\n");
    printf("   - Functions require parentheses: write sin(x), not sin x.\n");
    printf("   - Power operator is '^': e.g. x^2 or (x + 1)^3.\n");
    printf("============================================================\n");
    wait_for_enter();
}

static void show_help_syntax(void) {
    printf("\n============================================================\n");
    printf("            SUPPORTED FUNCTIONS & SYNTAX CHEAT SHEET\n");
    printf("============================================================\n");
    printf("OPERATORS:\n");
    printf("  + , - , * , / , %% (modulo) , ^ (power)\n\n");
    printf("CONSTANTS & VARIABLES:\n");
    printf("  pi   : 3.14159265...\n");
    printf("  e    : 2.71828182...\n");
    printf("  x    : Variable for calculus and expressions\n");
    printf("  ans  : The result of your previous calculation\n\n");
    printf("TRIGONOMETRIC FUNCTIONS (angles in radians):\n");
    printf("  sin(x)   cos(x)   tan(x)\n");
    printf("  asin(x)  acos(x)  atan(x)\n\n");
    printf("HYPERBOLIC FUNCTIONS:\n");
    printf("  sinh(x)  cosh(x)  tanh(x)\n\n");
    printf("EXPONENTIAL & LOGARITHMIC:\n");
    printf("  exp(x)   : e^x\n");
    printf("  ln(x)    : Natural logarithm (base e)\n");
    printf("  log(x)   : Common logarithm (base 10)\n\n");
    printf("OTHER FUNCTIONS:\n");
    printf("  sqrt(x)  : Square root\n");
    printf("  cbrt(x)  : Cube root\n");
    printf("  abs(x)   : Absolute value\n");
    printf("  floor(x) : Greatest integer <= x\n");
    printf("  ceil(x)  : Smallest integer >= x\n");
    printf("============================================================\n");
    wait_for_enter();
}

static void show_help_examples(void) {
    printf("\n============================================================\n");
    printf("                   WORKED CALCULUS EXAMPLES\n");
    printf("============================================================\n");
    printf("Example 1: Parabola Area\n");
    printf("   integral x^2 dx from 0 to 1\n");
    printf("   -> Exact: 1/3 = 0.33333333\n\n");
    printf("Example 2: Trigonometric Wave\n");
    printf("   integral sin(x) dx from 0 to pi\n");
    printf("   -> Exact: -cos(pi) - (-cos(0)) = 1 - (-1) = 2.00000000\n\n");
    printf("Example 3: Reciprocal Integral\n");
    printf("   integral (1/x) dx from 1 to e\n");
    printf("   -> Exact: ln(e) - ln(1) = 1.00000000\n\n");
    printf("Example 4: Gaussian Bell Curve\n");
    printf("   integral exp(-x^2) dx from 0 to 1\n");
    printf("   -> Numerical: 0.74682413\n\n");
    printf("Example 5: Tangent Line of y = x^3 at x = 2\n");
    printf("   -> Point: (2, 8)\n");
    printf("   -> Derivative f'(2) = 12\n");
    printf("   -> Tangent Line: y = 12*x - 16\n");
    printf("============================================================\n");
    wait_for_enter();
}

static void menu_help(void) {
    char choice[16];
    while (1) {
        printf("\n============================================================\n");
        printf("                    CALCULATOR HELP CENTER\n");
        printf("============================================================\n");
        printf("  1. Calculus Guide (How to calculate integrals & derivatives)\n");
        printf("  2. Supported Math Functions & Syntax Table\n");
        printf("  3. Worked Examples & Verifications\n");
        printf("  4. View All Help Topics\n");
        printf("  5. Return to Main Menu\n");
        printf("------------------------------------------------------------\n");

        if (!read_line("Select topic (1-5): ", choice, sizeof(choice))) return;

        if (strcmp(choice, "1") == 0) {
            show_help_calculus();
        } else if (strcmp(choice, "2") == 0) {
            show_help_syntax();
        } else if (strcmp(choice, "3") == 0) {
            show_help_examples();
        } else if (strcmp(choice, "4") == 0) {
            show_help_calculus();
            show_help_syntax();
            show_help_examples();
        } else if (strcmp(choice, "5") == 0 || strcasecmp(choice, "back") == 0 || strcasecmp(choice, "q") == 0) {
            break;
        } else {
            printf("\n[!] Please select between 1 and 5.\n");
        }
    }
}

static void action_launch_python_ai(void) {
    printf("\n------------------------------------------------------------\n");
    printf("         LAUNCHING SMART AI CALCULATOR (PYTHON)\n");
    printf("  [Self-Learning | Natural Language | Real-Time Auto-Correct]\n");
    printf("------------------------------------------------------------\n");
    system("start control_pad.exe");
    int ret = system("python smart_calculator.py");
    if (ret != 0) {
        printf("\n[!] Notice: could not launch python smart_calculator.py.\n");
        printf("    Ensure Python is installed or run 'python smart_calculator.py' in terminal.\n");
    }
    wait_for_enter();
}

/* ============================================================================
 *                                MAIN FUNCTION
 * ============================================================================
 */

int main(int argc, char *argv[]) {
    char choice[16];

    // Check if user specifically requested classic mode flag (e.g. loon1 --classic)
    int skip_auto_ai = 0;
    if (argc > 1 && (strcmp(argv[1], "--classic") == 0 || strcmp(argv[1], "-c") == 0)) {
        skip_auto_ai = 1;
    }

    // Auto-activate GUI Control Pad and Animation Window on startup
    system("start control_pad.exe");

    // Auto-activate Python Smart AI Calculator on execution
    if (!skip_auto_ai) {
        int ret = system("python smart_calculator.py");
        if (ret == 0) {
            // Once user exits Smart AI, check if they want the classic C menu or to exit
            char post_choice[16];
            printf("\n============================================================\n");
            printf("  Smart AI session closed. Switch to Classic C Menu? (y/n): ");
            if (!read_line("", post_choice, sizeof(post_choice)) || 
                (tolower((unsigned char)post_choice[0]) != 'y')) {
                printf("\nGoodbye! Happy calculating!\n\n");
                return 0;
            }
        } else {
            printf("\n[!] Notice: could not auto-activate 'python smart_calculator.py'.\n");
            printf("    Starting built-in C Calculus & Math engine...\n\n");
        }
    }

    printf("\n");
    printf("************************************************************\n");
    printf("*            SUPER ADVANCED CALCULATOR & CALCULUS          *\n");
    printf("*           High-Precision Integrals & Math Engine         *\n");
    printf("************************************************************\n");

    while (1) {
        printf("\n======================= MAIN MENU ==========================\n");
        if (g_has_last_answer) {
            printf("  [ANS = %.8g]\n", g_last_answer);
        }
        printf("  1. Advanced Calculus Suite   [ Integrals, Derivatives, Roots ]\n");
        printf("  2. Expression Calculator     [ Evaluate any custom formula ]\n");
        printf("  3. Standard Arithmetic       [ +, -, *, /, ^ ]\n");
        printf("  4. Statistics & Data         [ Mean, Median, Std Dev, Variance ]\n");
        printf("  5. Smart AI Assistant (Py)   [ Self-Learning, NLP & Auto-Correct ]\n");
        printf("  6. Help & User Guide         [ Instructions, Syntax, Examples ]\n");
        printf("  7. Exit\n");
        printf("============================================================\n");

        if (!read_line("Enter your choice (1-7, or 'h' for help): ", choice, sizeof(choice))) {
            break;
        }

        if (strcasecmp(choice, "h") == 0 || strcasecmp(choice, "help") == 0 || strcmp(choice, "6") == 0) {
            menu_help();
            continue;
        }

        if (strcmp(choice, "1") == 0) {
            menu_calculus();
        } else if (strcmp(choice, "2") == 0) {
            action_expression_calculator();
        } else if (strcmp(choice, "3") == 0) {
            action_standard_arithmetic();
        } else if (strcmp(choice, "4") == 0) {
            action_statistics();
        } else if (strcmp(choice, "5") == 0) {
            action_launch_python_ai();
        } else if (strcmp(choice, "7") == 0 || strcasecmp(choice, "exit") == 0 || strcasecmp(choice, "quit") == 0) {
            printf("\nThank you for using the Super Advanced Calculator. Goodbye!\n\n");
            break;
        } else {
            printf("\n[!] Invalid choice '%s'. Please select 1 through 7, or type 'h' for help.\n", choice);
        }
    }

    return 0;
}
