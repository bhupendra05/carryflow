"""Tests for CarryFlow PE/VC waterfall engine."""
from __future__ import annotations
import pytest
from datetime import date
from carryflow.models import FundTerms, WaterfallResult, WaterfallTier
from carryflow.metrics import irr, xirr, moic, dpi, tvpi, rvpi
from carryflow.waterfall import european_waterfall, american_waterfall, _preferred_amount
from carryflow.secondary import price_secondary, model_continuation_vehicle


# ── FundTerms ─────────────────────────────────────────────────────────────────

def test_fund_terms_commitments():
    t = FundTerms(committed_capital=100, gp_commitment_pct=0.02)
    assert t.gp_commitment == 2.0
    assert t.lp_commitment == 98.0

def test_fund_terms_management_fees():
    t = FundTerms(committed_capital=100, management_fee=0.02, fee_years=10)
    assert t.total_management_fees == 20.0

def test_fund_terms_invalid_carry():
    with pytest.raises(ValueError):
        FundTerms(committed_capital=100, carry=1.5)

def test_fund_terms_invalid_capital():
    with pytest.raises(ValueError):
        FundTerms(committed_capital=-10)

def test_fund_terms_invalid_gp_commit():
    with pytest.raises(ValueError):
        FundTerms(committed_capital=100, gp_commitment_pct=1.5)


# ── Preferred amount ──────────────────────────────────────────────────────────

def test_preferred_compound():
    # 100 at 8% over 5 years compounded
    p = _preferred_amount(100, 0.08, 5, compound=True)
    assert abs(p - (100 * (1.08**5 - 1))) < 1e-6

def test_preferred_simple():
    p = _preferred_amount(100, 0.08, 5, compound=False)
    assert abs(p - 40.0) < 1e-6


# ── European Waterfall ────────────────────────────────────────────────────────

def test_european_return_of_capital_only():
    # Proceeds exactly equal capital → all return of capital, no carry
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.0)
    r = european_waterfall(terms, total_proceeds=100, years=5)
    assert abs(r.lp_distribution - 100) < 1e-6
    assert r.gp_carry == 0.0

def test_european_below_capital():
    # Proceeds less than capital → LP gets everything, no carry
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.0)
    r = european_waterfall(terms, total_proceeds=60, years=5)
    assert abs(r.lp_distribution - 60) < 1e-6
    assert r.gp_carry == 0.0

def test_european_full_waterfall_has_carry():
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.0,
                      preferred_return=0.08, carry=0.20)
    r = european_waterfall(terms, total_proceeds=250, years=5)
    assert r.gp_carry > 0
    assert r.lp_distribution > 100  # got capital + pref + split

def test_european_tiers_sum_to_proceeds():
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.02, carry=0.20)
    r = european_waterfall(terms, total_proceeds=300, years=5)
    assert abs(r.total_distributed - 300) < 1e-6

def test_european_four_tiers():
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.0)
    r = european_waterfall(terms, total_proceeds=250, years=5)
    assert len(r.tiers) == 4
    assert r.tiers[0].name.startswith("1.")
    assert r.tiers[3].name.startswith("4.")

def test_european_catchup_gives_gp_carry_share():
    # After full catch-up + split, GP carry should approach ~carry% of profit
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.0,
                      preferred_return=0.08, carry=0.20, catchup_rate=1.0)
    r = european_waterfall(terms, total_proceeds=500, years=5)
    # With a large proceeds and full catch-up, effective carry ~ 20%
    assert r.effective_carry_pct is not None
    assert 0.15 < r.effective_carry_pct < 0.22

def test_european_lp_moic():
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.0)
    r = european_waterfall(terms, total_proceeds=200, years=5)
    assert r.lp_moic is not None
    assert r.lp_moic == pytest.approx(r.lp_distribution / 100)

def test_european_gp_coinvest_returns_capital():
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.10)
    r = european_waterfall(terms, total_proceeds=300, years=5)
    # GP put in 10, should get co-invest back plus carry
    assert r.gp_contributed == 10.0
    assert r.gp_distribution > 10.0

def test_european_higher_carry_more_gp():
    terms_low = FundTerms(committed_capital=100, gp_commitment_pct=0.0, carry=0.10)
    terms_high = FundTerms(committed_capital=100, gp_commitment_pct=0.0, carry=0.30)
    r_low = european_waterfall(terms_low, 400, years=5)
    r_high = european_waterfall(terms_high, 400, years=5)
    assert r_high.gp_carry > r_low.gp_carry

def test_european_higher_pref_more_lp():
    terms_low = FundTerms(committed_capital=100, gp_commitment_pct=0.0, preferred_return=0.06)
    terms_high = FundTerms(committed_capital=100, gp_commitment_pct=0.0, preferred_return=0.12)
    r_low = european_waterfall(terms_low, 300, years=5)
    r_high = european_waterfall(terms_high, 300, years=5)
    assert r_high.lp_distribution >= r_low.lp_distribution


# ── American Waterfall ────────────────────────────────────────────────────────

def test_american_basic():
    terms = FundTerms(committed_capital=100, carry=0.20)
    r = american_waterfall(terms, deal_proceeds=[150], deal_costs=[100], years_per_deal=[3])
    assert r.structure == "American"
    assert r.gp_carry > 0

def test_american_multiple_deals():
    terms = FundTerms(committed_capital=200, carry=0.20)
    r = american_waterfall(terms, deal_proceeds=[150, 80], deal_costs=[100, 100], years_per_deal=[3, 3])
    # Deal 1 profits, deal 2 loses — american takes carry on deal 1 only
    assert r.gp_carry > 0
    assert abs(r.total_proceeds - 230) < 1e-6

def test_american_loss_deal_no_carry():
    terms = FundTerms(committed_capital=100, carry=0.20)
    r = american_waterfall(terms, deal_proceeds=[80], deal_costs=[100], years_per_deal=[3])
    assert r.gp_carry == 0.0

def test_american_vs_european_gp_friendlier():
    # American (deal-by-deal) should give GP >= carry vs European on a mixed portfolio
    terms = FundTerms(committed_capital=200, gp_commitment_pct=0.0, carry=0.20)
    amer = american_waterfall(terms, [300, 50], [100, 100], [3, 3])
    euro = european_waterfall(terms, total_proceeds=350, years=3)
    assert amer.gp_carry >= euro.gp_carry - 1e-6

def test_american_mismatched_lengths():
    terms = FundTerms(committed_capital=100)
    with pytest.raises(ValueError):
        american_waterfall(terms, [100, 200], [100])


# ── Metrics: IRR ──────────────────────────────────────────────────────────────

def test_irr_simple_double():
    # -100 then +200 after 1 period = 100% IRR
    r = irr([-100, 200])
    assert abs(r - 1.0) < 1e-4

def test_irr_known_value():
    # -100, +110 → 10% IRR
    r = irr([-100, 110])
    assert abs(r - 0.10) < 1e-4

def test_irr_multi_period():
    r = irr([-1000, 300, 300, 300, 300])
    assert r is not None
    assert 0.05 < r < 0.10

def test_irr_no_sign_change():
    assert irr([100, 200, 300]) is None
    assert irr([-100, -200]) is None

def test_irr_empty():
    assert irr([]) is None


# ── Metrics: XIRR ─────────────────────────────────────────────────────────────

def test_xirr_one_year_double():
    flows = [(date(2020, 1, 1), -100), (date(2021, 1, 1), 200)]
    r = xirr(flows)
    assert abs(r - 1.0) < 0.01

def test_xirr_known_10pct():
    flows = [(date(2020, 1, 1), -100), (date(2021, 1, 1), 110)]
    r = xirr(flows)
    assert abs(r - 0.10) < 0.01

def test_xirr_multiple_flows():
    flows = [
        (date(2018, 1, 1), -1000),
        (date(2019, 6, 1), 200),
        (date(2020, 6, 1), 400),
        (date(2022, 1, 1), 800),
    ]
    r = xirr(flows)
    assert r is not None and r > 0

def test_xirr_unsorted_input():
    flows = [(date(2021, 1, 1), 200), (date(2020, 1, 1), -100)]
    r = xirr(flows)
    assert abs(r - 1.0) < 0.01

def test_xirr_single_flow_none():
    assert xirr([(date(2020, 1, 1), -100)]) is None


# ── Metrics: Multiples ────────────────────────────────────────────────────────

def test_moic_realized():
    assert moic(100, 250) == 2.5

def test_moic_with_residual():
    assert moic(100, 200, residual_nav=50) == 2.5

def test_moic_zero_contrib():
    assert moic(0, 100) is None

def test_dpi():
    assert dpi(100, 80) == 0.8

def test_rvpi():
    assert rvpi(100, 60) == 0.6

def test_tvpi_equals_dpi_plus_rvpi():
    contrib, dist, nav = 100, 80, 60
    assert tvpi(contrib, dist, nav) == pytest.approx(dpi(contrib, dist) + rvpi(contrib, nav))


# ── Secondary Pricing ─────────────────────────────────────────────────────────

def test_secondary_discount():
    q = price_secondary(nav=100, bid_pct_nav=0.85)
    assert q.price == 85.0
    assert q.is_discount is True
    assert q.discount_premium == pytest.approx(-0.15)

def test_secondary_premium():
    q = price_secondary(nav=100, bid_pct_nav=1.05)
    assert q.price == 105.0
    assert q.is_discount is False
    assert q.discount_premium == pytest.approx(0.05)

def test_secondary_par():
    q = price_secondary(nav=100, bid_pct_nav=1.0)
    assert q.price == 100.0

def test_secondary_with_unfunded():
    # buyer discounts unfunded fully (adjustment=0 → subtract full unfunded)
    q = price_secondary(nav=100, bid_pct_nav=0.90, unfunded=20, unfunded_adjustment=0.0)
    assert q.price == 70.0  # 90 - 20

def test_secondary_negative_nav_raises():
    with pytest.raises(ValueError):
        price_secondary(nav=-10, bid_pct_nav=0.9)


# ── Continuation Vehicle ──────────────────────────────────────────────────────

def test_cv_crystallized_carry():
    terms = FundTerms(committed_capital=40, carry=0.20, preferred_return=0.08)
    r = model_continuation_vehicle(asset_nav=100, purchase_price=110,
                                   asset_cost_basis=40, rollover_pct=0.5, terms=terms)
    assert r.crystallized_carry > 0

def test_cv_no_gain_no_carry():
    terms = FundTerms(committed_capital=100, carry=0.20)
    r = model_continuation_vehicle(asset_nav=100, purchase_price=90,
                                   asset_cost_basis=100, rollover_pct=0.5, terms=terms)
    assert r.crystallized_carry == 0.0

def test_cv_rollover_split():
    terms = FundTerms(committed_capital=40, carry=0.0, preferred_return=0.0)  # no carry for clean split
    r = model_continuation_vehicle(asset_nav=100, purchase_price=100,
                                   asset_cost_basis=40, rollover_pct=0.6, terms=terms)
    # No carry → net proceeds = 100; 60% rolls, 40% cashes out
    assert r.rollover_amount == pytest.approx(60.0)
    assert r.cashout_amount == pytest.approx(40.0)

def test_cv_premium_to_nav():
    terms = FundTerms(committed_capital=40, carry=0.20)
    r = model_continuation_vehicle(asset_nav=100, purchase_price=115,
                                   asset_cost_basis=40, rollover_pct=0.5, terms=terms)
    assert r.premium_to_nav == pytest.approx(0.15)

def test_cv_full_rollover_no_cashout():
    terms = FundTerms(committed_capital=40, carry=0.0)
    r = model_continuation_vehicle(asset_nav=100, purchase_price=100,
                                   asset_cost_basis=40, rollover_pct=1.0, terms=terms)
    assert r.cashout_amount == pytest.approx(0.0)

def test_cv_invalid_rollover():
    terms = FundTerms(committed_capital=40)
    with pytest.raises(ValueError):
        model_continuation_vehicle(100, 100, 40, rollover_pct=1.5, terms=terms)


# ── Integration: realistic fund scenario ─────────────────────────────────────

def test_realistic_fund_scenario():
    """A ₹100 Cr fund returning 2.5x gross — check LP and GP economics make sense."""
    terms = FundTerms(committed_capital=100, gp_commitment_pct=0.02,
                      preferred_return=0.08, carry=0.20)
    r = european_waterfall(terms, total_proceeds=250, years=5)

    # LP should get more than its capital back
    assert r.lp_distribution > r.lp_contributed
    # GP carry should be meaningful but less than total profit
    total_profit = 250 - 100
    assert 0 < r.gp_carry < total_profit
    # Everything reconciles
    assert abs(r.total_distributed - 250) < 1e-6
