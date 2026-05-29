"""
Distribution waterfall engines.

European (whole-fund): carry only after the WHOLE fund returns capital + pref.
American (deal-by-deal): carry taken on each realized deal's profit.

Standard 4-tier European waterfall:
  1. Return of Capital  → LPs get contributed capital back
  2. Preferred Return   → LPs get the hurdle (e.g. 8%)
  3. GP Catch-up        → GP catches up to its carry % of profit
  4. Carried Interest   → remaining split (e.g. 80/20)
"""
from __future__ import annotations
from typing import List, Optional
from .models import FundTerms, WaterfallTier, WaterfallResult


def _preferred_amount(capital: float, rate: float, years: float, compound: bool) -> float:
    """Total preferred return owed on capital over `years`."""
    if compound:
        return capital * ((1 + rate) ** years - 1)
    return capital * rate * years


def european_waterfall(
    terms: FundTerms,
    total_proceeds: float,
    years: float = 5.0,
    lp_contributed: Optional[float] = None,
    gp_contributed: Optional[float] = None,
) -> WaterfallResult:
    """
    Whole-fund (European) waterfall — LP-friendly, the institutional standard.

    Args:
        terms: FundTerms with pref, carry, catch-up
        total_proceeds: total cash available to distribute
        years: holding period (drives the compounded preferred return)
        lp_contributed / gp_contributed: override contributed capital
    """
    lp_cap = lp_contributed if lp_contributed is not None else terms.lp_commitment
    gp_cap = gp_contributed if gp_contributed is not None else terms.gp_commitment
    total_cap = lp_cap + gp_cap

    result = WaterfallResult(
        structure="European",
        total_proceeds=total_proceeds,
        lp_contributed=lp_cap,
        gp_contributed=gp_cap,
    )

    remaining = total_proceeds
    lp_share = lp_cap / total_cap if total_cap else 1.0
    gp_share = gp_cap / total_cap if total_cap else 0.0

    # ── Tier 1: Return of Capital (pro-rata to LP and GP co-invest) ──────────
    roc = min(remaining, total_cap)
    t1 = WaterfallTier("1. Return of Capital",
                       lp_amount=roc * lp_share, gp_amount=roc * gp_share)
    result.tiers.append(t1)
    remaining -= roc

    # ── Tier 2: Preferred Return (to LP; GP co-invest also earns pref) ───────
    pref_total = _preferred_amount(total_cap, terms.preferred_return, years,
                                   terms.hurdle_compounding)
    pref_paid = min(remaining, pref_total)
    t2 = WaterfallTier("2. Preferred Return",
                       lp_amount=pref_paid * lp_share, gp_amount=pref_paid * gp_share)
    result.tiers.append(t2)
    remaining -= pref_paid

    # ── Tier 3: GP Catch-up ──────────────────────────────────────────────────
    # GP catches up so its carry equals `carry` % of (pref + catch-up).
    # Target catch-up = pref_to_lp × carry / (1 - carry).
    carry = terms.carry
    pref_to_lp = pref_paid * lp_share  # only LP pref counts toward catch-up base
    catchup_target = pref_to_lp * carry / (1 - carry) if carry < 1 else 0.0
    catchup_paid = min(remaining, catchup_target * terms.catchup_rate)
    t3 = WaterfallTier("3. GP Catch-up", lp_amount=0.0, gp_amount=catchup_paid)
    result.tiers.append(t3)
    remaining -= catchup_paid
    gp_carry = catchup_paid

    # ── Tier 4: Carried Interest Split ───────────────────────────────────────
    lp_split = remaining * (1 - carry)
    gp_split = remaining * carry
    t4 = WaterfallTier(f"4. Carry Split ({int((1-carry)*100)}/{int(carry*100)})",
                       lp_amount=lp_split, gp_amount=gp_split)
    result.tiers.append(t4)
    gp_carry += gp_split

    # ── Totals ───────────────────────────────────────────────────────────────
    result.lp_distribution = sum(t.lp_amount for t in result.tiers)
    result.gp_distribution = sum(t.gp_amount for t in result.tiers)
    result.gp_carry = gp_carry
    return result


def american_waterfall(
    terms: FundTerms,
    deal_proceeds: List[float],
    deal_costs: List[float],
    years_per_deal: Optional[List[float]] = None,
) -> WaterfallResult:
    """
    Deal-by-deal (American) waterfall — GP-friendly. Carry is taken on each
    profitable deal as it realizes, with return of capital + pref per deal.

    Args:
        terms: FundTerms
        deal_proceeds: realized proceeds per deal
        deal_costs: invested cost per deal
        years_per_deal: holding period per deal (for pref); defaults to 3y each
    """
    if len(deal_proceeds) != len(deal_costs):
        raise ValueError("deal_proceeds and deal_costs must be same length")
    n = len(deal_proceeds)
    if years_per_deal is None:
        years_per_deal = [3.0] * n
    if len(years_per_deal) != n:
        raise ValueError("years_per_deal must match number of deals")

    total_cost = sum(deal_costs)
    total_proceeds = sum(deal_proceeds)
    carry = terms.carry

    result = WaterfallResult(
        structure="American",
        total_proceeds=total_proceeds,
        lp_contributed=total_cost,
        gp_contributed=0.0,  # simplified: track LP economics
    )

    tier_roc = WaterfallTier("1. Return of Capital (per deal)")
    tier_pref = WaterfallTier("2. Preferred Return (per deal)")
    tier_carry = WaterfallTier(f"3. Carry ({int(carry*100)}% per deal)")

    for proceeds, cost, yrs in zip(deal_proceeds, deal_costs, years_per_deal):
        remaining = proceeds
        # Return of capital for this deal
        roc = min(remaining, cost)
        tier_roc.lp_amount += roc
        remaining -= roc
        if remaining <= 0:
            continue
        # Preferred return for this deal
        pref = _preferred_amount(cost, terms.preferred_return, yrs,
                                 terms.hurdle_compounding)
        pref_paid = min(remaining, pref)
        tier_pref.lp_amount += pref_paid
        remaining -= pref_paid
        if remaining <= 0:
            continue
        # GP catch-up + carry on remaining profit (combined for per-deal)
        catchup_target = pref_paid * carry / (1 - carry) if carry < 1 else 0.0
        catchup = min(remaining, catchup_target)
        tier_carry.gp_amount += catchup
        remaining -= catchup
        # Split the rest
        tier_carry.lp_amount += remaining * (1 - carry)
        tier_carry.gp_amount += remaining * carry

    result.tiers = [tier_roc, tier_pref, tier_carry]
    result.lp_distribution = sum(t.lp_amount for t in result.tiers)
    result.gp_distribution = sum(t.gp_amount for t in result.tiers)
    result.gp_carry = tier_carry.gp_amount
    return result
