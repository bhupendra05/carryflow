"""
Secondary stake pricing and GP-led continuation vehicle modeling.

These are exactly the structures specialist exit-advisors handle:
  - Secondary sale: an LP sells its fund stake to a buyer at a % of NAV
  - Continuation vehicle (CV): GP moves an asset into a new vehicle; existing
    LPs choose to cash out or roll, new LPs bring fresh capital, GP crystallizes carry.
"""
from __future__ import annotations
from typing import Optional
from .models import SecondaryQuote, ContinuationVehicleResult, FundTerms


def price_secondary(
    nav: float,
    bid_pct_nav: float,
    unfunded: float = 0.0,
    unfunded_adjustment: float = 1.0,
) -> SecondaryQuote:
    """
    Price a secondary sale of an LP fund interest.

    Args:
        nav: current net asset value of the stake
        bid_pct_nav: buyer's bid as a fraction of NAV (0.90 = 10% discount)
        unfunded: remaining unfunded commitment (a liability to the buyer)
        unfunded_adjustment: how much the buyer discounts the unfunded
                             commitment (1.0 = full value transferred)

    Returns:
        SecondaryQuote with price and discount/premium.
    """
    if nav < 0:
        raise ValueError("nav cannot be negative")
    if bid_pct_nav < 0:
        raise ValueError("bid_pct_nav cannot be negative")

    base_price = nav * bid_pct_nav
    # Buyer takes on unfunded commitment; this can reduce what they'll pay today
    price = base_price - unfunded * (1 - unfunded_adjustment)
    discount_premium = (price / nav - 1.0) if nav else 0.0

    return SecondaryQuote(
        nav=nav,
        unfunded=unfunded,
        bid_pct_nav=bid_pct_nav,
        price=round(price, 2),
        discount_premium=round(discount_premium, 4),
    )


def model_continuation_vehicle(
    asset_nav: float,
    purchase_price: float,
    asset_cost_basis: float,
    rollover_pct: float,
    terms: FundTerms,
    holding_years: float = 5.0,
    new_lp_capital: Optional[float] = None,
) -> ContinuationVehicleResult:
    """
    Model a GP-led continuation vehicle transaction.

    The GP sells an asset out of the old fund into a new CV at `purchase_price`.
    - GP crystallizes carry on the realized gain (purchase_price - cost_basis)
    - Existing LPs choose to roll (stay in CV) or cash out at purchase_price
    - New LPs provide fresh capital to fund the cash-out + future needs

    Args:
        asset_nav: current marked NAV of the asset
        purchase_price: price the CV pays the old fund (often NAV or a premium)
        asset_cost_basis: original cost of the asset in the old fund
        rollover_pct: fraction of existing LPs choosing to roll (0–1)
        terms: FundTerms (uses carry, preferred_return)
        holding_years: years used to compute the pref on crystallized gain
        new_lp_capital: fresh capital from new LPs (defaults to cash-out amount)
    """
    if not 0 <= rollover_pct <= 1:
        raise ValueError("rollover_pct must be between 0 and 1")
    if purchase_price < 0 or asset_nav < 0:
        raise ValueError("prices cannot be negative")

    realized_gain = max(0.0, purchase_price - asset_cost_basis)

    # Crystallized carry: GP takes carry on the gain above a pref hurdle on cost
    pref_hurdle = asset_cost_basis * ((1 + terms.preferred_return) ** holding_years - 1)
    carryable_gain = max(0.0, realized_gain - pref_hurdle)
    crystallized_carry = carryable_gain * terms.carry

    # Proceeds to existing LPs (net of crystallized carry)
    net_proceeds = purchase_price - crystallized_carry
    cashout_amount = net_proceeds * (1 - rollover_pct)
    rollover_amount = net_proceeds * rollover_pct

    # New LPs typically fund the cash-out portion
    new_capital = new_lp_capital if new_lp_capital is not None else cashout_amount

    premium_to_nav = (purchase_price / asset_nav - 1.0) if asset_nav else 0.0

    return ContinuationVehicleResult(
        asset_nav=asset_nav,
        purchase_price=purchase_price,
        crystallized_carry=round(crystallized_carry, 2),
        rollover_pct=rollover_pct,
        cashout_amount=round(cashout_amount, 2),
        rollover_amount=round(rollover_amount, 2),
        new_capital=round(new_capital, 2),
        premium_to_nav=round(premium_to_nav, 4),
    )
