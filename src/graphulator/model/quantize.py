"""Quantize user-entered numbers to their widget's precision (decision Q2).

A user-entered quantity is stored as the number its widget shows:
sgn(x) * round(|x|, d), ties away from zero, applied to the exact binary
value of x. That is what ``QDoubleSpinBox`` does (checked against Qt on 40k
values, exact ties included: -0.125 -> -0.13, while 2.675 -> 2.67 because the
double 2.675 is 2.67499...). Python's ``round``/``f"{x:.2f}"`` round exact ties
to even (-0.125 -> -0.12) and are NOT used.

Derived numbers (linspace grids, computed rates) are never quantized.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .. import graphulator_para_config as _cfg  # Qt-free


def quantize(x: float, decimals: int) -> float:
    """sgn(x) * round(|x|, decimals), ties away from zero; -0.0 -> 0.0."""
    q = float(Decimal(float(x)).quantize(Decimal(1).scaleb(-int(decimals)),
                                         rounding=ROUND_HALF_UP))
    return q + 0.0


def spin(x: float, lo: float, hi: float, decimals: int) -> float:
    """QDoubleSpinBox.setValue: quantize to the display decimals, then clamp."""
    return min(max(quantize(x, decimals), lo), hi)


def sweep_decimals():
    """(center, span, points) decimals of the GUI's sweep spin boxes."""
    return (_cfg.FREQ_CENTER_DECIMALS, _cfg.FREQ_SPAN_DECIMALS, _cfg.FREQ_POINTS_DECIMALS)


def quantize_sweep(center: float, span: float, points):
    """A sweep as its spin boxes would hold it (precision only; the range
    clamp is a GUI limit, applied where the grid is built, not to stored data)."""
    dc, ds, _ = sweep_decimals()
    return quantize(center, dc), quantize(span, ds), int(points)
