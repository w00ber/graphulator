"""
SymPy utilities for paragraphulator.

This module contains custom LaTeX printing and symbolic math utilities.
"""

import re
from sympy.printing.latex import LatexPrinter
from sympy.core.mul import Mul
from sympy.functions.elementary.complexes import conjugate as Conjugate


class CustomLaTeXPrinter(LatexPrinter):
    """Custom LaTeX printer with magnitude squared and asterisk conjugation notation"""

    def _print_Symbol(self, expr):
        """Override symbol printing to add backslash to beta symbols"""
        name = str(expr.name)
        # Check if the symbol starts with 'beta' or 'Delta'
        if name.startswith('beta'):
            # Extract subscript (everything after 'beta')
            subscript = name[4:]  # Remove 'beta' prefix
            # Strip leading underscore from subscript
            if subscript.startswith('_'):
                subscript = subscript[1:]
            if subscript:
                return r'\beta_{' + subscript + '}'
            else:
                return r'\beta'
        elif name.startswith('Delta'):
            # Extract subscript (everything after 'Delta')
            subscript = name[5:]  # Remove 'Delta' prefix
            # Strip leading underscore from subscript
            if subscript.startswith('_'):
                subscript = subscript[1:]
            if subscript:
                return r'\Delta_{' + subscript + '}'
            else:
                return r'\Delta'
        # For other symbols, use default behavior
        return super()._print_Symbol(expr)

    def _print_Conjugate(self, expr):
        """Override conjugate printing to use asterisk superscript instead of overline"""
        # Get the LaTeX representation of the argument
        arg_latex = self._print(expr.args[0])
        # Return with asterisk superscript
        return arg_latex + r"^{*}"

    def _print_conjugate(self, expr):
        """Override conjugate printing (lowercase method name)"""
        return self._print_Conjugate(expr)

    def _print_Function(self, expr):
        """Override function printing to handle conjugate"""
        # Check if this is a conjugate function
        if expr.func.__name__ == 'conjugate' or str(expr.func) == 'conjugate':
            return self._print_Conjugate(expr)
        # Otherwise use default printing
        return super()._print_Function(expr)

    def _print_Mul(self, expr):
        """Override multiplication printing to detect conjugate pairs and handle -1 coefficients"""
        from sympy import Mul, Pow, Integer

        # Get the factors
        args = list(expr.args)

        # Separate numeric coefficients from symbolic factors
        coeffs = []
        symbolic_args = []
        for arg in args:
            if arg.is_number:
                coeffs.append(arg)
            else:
                symbolic_args.append(arg)

        # Check if coefficient is exactly -1 and handle it specially
        has_minus_one = False
        if len(coeffs) == 1 and coeffs[0] == Integer(-1) and symbolic_args:
            has_minus_one = True
            coeffs = []  # Remove the -1 from coefficients

        # Check if any pair of symbolic args is a variable and its conjugate
        magnitude_base = None
        remaining_args = list(symbolic_args)

        for i, arg1 in enumerate(symbolic_args):
            for j, arg2 in enumerate(symbolic_args):
                if i < j:  # Only check each pair once
                    # Check if arg1 is conjugate(arg2)
                    if isinstance(arg1, Conjugate) and arg1.args[0] == arg2:
                        magnitude_base = arg2
                        remaining_args.remove(arg1)
                        remaining_args.remove(arg2)
                        break
                    # Check if arg2 is conjugate(arg1)
                    elif isinstance(arg2, Conjugate) and arg2.args[0] == arg1:
                        magnitude_base = arg1
                        remaining_args.remove(arg1)
                        remaining_args.remove(arg2)
                        break
            if magnitude_base is not None:
                break

        # If we found a magnitude pair
        if magnitude_base is not None:
            # Get LaTeX representation of the base
            base_latex = self._print(magnitude_base)
            magnitude_latex = r"\left|" + base_latex + r"\right|^{2}"

            # Build the result
            parts = []

            # Add minus sign if coefficient was -1
            if has_minus_one:
                parts.append("-")

            # Add coefficient if present (and not -1)
            if coeffs:
                coeff = Mul(*coeffs, evaluate=False)
                parts.append(self._print(coeff))

            # Add remaining factors if present - use parent's method to preserve structure
            # but it will still use our _print_Conjugate via self._print()
            if remaining_args:
                if len(remaining_args) == 1:
                    parts.append(self._print(remaining_args[0]))
                else:
                    remaining_mul = Mul(*remaining_args, evaluate=False)
                    # Use parent's method which handles structure correctly
                    # It will still call self._print() for conjugates
                    parts.append(super()._print_Mul(remaining_mul))

            # Add magnitude
            parts.append(magnitude_latex)

            return " ".join(parts)

        # If no conjugate pair found, check for -1 coefficient and handle specially
        if has_minus_one:
            # Rebuild the expression without the -1
            if len(symbolic_args) == 1:
                return "- " + self._print(symbolic_args[0])
            else:
                remaining_mul = Mul(*symbolic_args, evaluate=False)
                return "- " + super()._print_Mul(remaining_mul)

        # Otherwise use parent's method which handles divisions correctly
        # The _print_Conjugate override will still be called for any conjugates
        return super()._print_Mul(expr)


def latex_custom(expr, **settings):
    """LaTeX printer that converts z*conjugate(z) to |z|^2 and conjugate(v) to v^*"""
    return CustomLaTeXPrinter(settings).doprint(expr)


def latex_matrix_factored(matrix, printer_func=None, **settings):
    """
    Convert a SymPy Matrix to LaTeX, factoring out common denominators or factors.

    Parameters:
    -----------
    matrix : sympy.Matrix
        The matrix to convert to LaTeX
    printer_func : callable, optional
        The LaTeX printer function to use (defaults to latex_custom)
    **settings : dict
        Additional settings to pass to the printer function

    Returns:
    --------
    str
        LaTeX string representation with factored common terms
    """
    from sympy import Matrix, gcd, simplify, fraction, lcm
    from functools import reduce

    if printer_func is None:
        printer_func = latex_custom

    # Get all matrix elements
    elements = [matrix[i, j] for i in range(matrix.rows) for j in range(matrix.cols)]

    # Get numerators and denominators
    fractions = [fraction(simplify(elem)) for elem in elements]
    numerators = [f[0] for f in fractions]
    denominators = [f[1] for f in fractions]

    # Find common denominator (LCM of all denominators)
    common_denom = reduce(lcm, denominators)

    # If there's a non-trivial common denominator, factor it out
    if common_denom != 1:
        # Create new matrix with factored-out denominator
        new_elements = []
        for i in range(matrix.rows):
            row = []
            for j in range(matrix.cols):
                elem = matrix[i, j]
                num, denom = fraction(simplify(elem))
                # Multiply by common_denom/denom to clear the denominator
                new_elem = simplify(num * common_denom / denom)
                row.append(new_elem)
            new_elements.append(row)

        new_matrix = Matrix(new_elements)

        # Generate LaTeX
        matrix_latex = printer_func(new_matrix, **settings)
        denom_latex = printer_func(common_denom, **settings)

        return f"\\frac{{1}}{{{denom_latex}}} {normalize_matrix_latex(matrix_latex)}"
    else:
        # No common denominator to factor out
        return normalize_matrix_latex(printer_func(matrix, **settings))


def normalize_matrix_latex(latex_str):
    """
    Normalize matrix LaTeX to use consistent bmatrix format.

    Converts SymPy's default output format:
        \\left[\\begin{matrix}...\\end{matrix}\\right]
    To the cleaner bmatrix format:
        \\begin{bmatrix}...\\end{bmatrix}

    Also handles nested cases and leaves already-normalized strings unchanged.
    """
    # Convert \left[\begin{matrix}...\end{matrix}\right] to \begin{bmatrix}...\end{bmatrix}
    # Handle both single and double backslashes (for different contexts)
    result = latex_str

    # Pattern for \left[\begin{matrix}...\end{matrix}\right]
    result = re.sub(
        r'\\left\s*\[\s*\\begin\{matrix\}',
        r'\\begin{bmatrix}',
        result
    )
    result = re.sub(
        r'\\end\{matrix\}\s*\\right\s*\]',
        r'\\end{bmatrix}',
        result
    )

    return result
