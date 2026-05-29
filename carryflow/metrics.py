"""Fund performance metrics: IRR, XIRR, MOIC, DPI, TVPI, RVPI."""
from __future__ import annotations
from datetime import date
from typing import List, Tuple, Optional


# ── IRR / XIRR ────────────────────────────────────────────────────────────────

def _npv(rate: float, amounts: List[float]) -> float:
    """NPV for equal-period cash flows (period 0, 1, 2, ...)."""
    return sum(cf / (1 + rate) ** i for i, cf in enumerate(amounts))


def irr(amounts: List[float], guess: float = 0.1) -> Optional[float]:
    """
    Internal rate of return for equal-period cash flows.
    amounts[0] is period 0 (usually negative contribution).
    Uses bisection for robustness. Returns None if no sign change.
    """
    if not amounts or all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return None

    lo, hi = -0.9999, 10.0
    f_lo, f_hi = _npv(lo, amounts), _npv(hi, amounts)
    if f_lo * f_hi > 0:
        return None  # no root in range

    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, amounts)
        if abs(f_mid) < 1e-9:
            return round(mid, 6)
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return round((lo + hi) / 2, 6)


def _xnpv(rate: float, flows: List[Tuple[date, float]]) -> float:
    t0 = flows[0][0]
    return sum(
        cf / (1 + rate) ** ((d - t0).days / 365.0)
        for d, cf in flows
    )


def xirr(flows: List[Tuple[date, float]], guess: float = 0.1) -> Optional[float]:
    """
    IRR for irregularly-dated cash flows (the PE/VC standard).
    flows: list of (date, amount); negative = contribution, positive = distribution.
    """
    if len(flows) < 2:
        return None
    amounts = [a for _, a in flows]
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return None

    flows = sorted(flows, key=lambda f: f[0])
    lo, hi = -0.9999, 100.0
    f_lo, f_hi = _xnpv(lo, flows), _xnpv(hi, flows)
    if f_lo * f_hi > 0:
        return None

    for _ in range(300):
        mid = (lo + hi) / 2
        f_mid = _xnpv(mid, flows)
        if abs(f_mid) < 1e-7:
            return round(mid, 6)
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return round((lo + hi) / 2, 6)


# ── Multiples ─────────────────────────────────────────────────────────────────

def moic(contributions: float, distributions: float, residual_nav: float = 0.0) -> Optional[float]:
    """
    Multiple on Invested Capital = (distributions + residual NAV) / contributions.
    Pass residual_nav=0 for realized MOIC.
    """
    if contributions <= 0:
        return None
    return (distributions + residual_nav) / contributions


def dpi(contributions: float, distributions: float) -> Optional[float]:
    """Distributions to Paid-In — realized cash returned per dollar in."""
    if contributions <= 0:
        return None
    return distributions / contributions


def rvpi(contributions: float, residual_nav: float) -> Optional[float]:
    """Residual Value to Paid-In — unrealized value per dollar in."""
    if contributions <= 0:
        return None
    return residual_nav / contributions


def tvpi(contributions: float, distributions: float, residual_nav: float) -> Optional[float]:
    """Total Value to Paid-In = DPI + RVPI."""
    if contributions <= 0:
        return None
    return (distributions + residual_nav) / contributions
