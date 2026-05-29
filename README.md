# CarryFlow 💧

**PE/VC distribution waterfall, carried-interest & exit-structuring engine.**

> Investor-discovery tools find you the capital. **CarryFlow models what happens to the money after the deal** — the part that actually decides who gets paid.

Built for fund managers, GPs, and M&A / exit advisors who structure:
- **Distribution waterfalls** — European (whole-fund) & American (deal-by-deal)
- **Carried interest** — preferred return, GP catch-up, 80/20 splits
- **Fund returns** — IRR / XIRR, MOIC, DPI, TVPI, RVPI
- **Secondary pricing** — LP stake sales at a discount/premium to NAV
- **GP-led continuation vehicles** — roll vs cash-out economics, crystallized carry

---

## Why this exists

Most fundraising / deal tooling stops at *finding investors*. The hard, high-value modeling — **how proceeds flow through the waterfall and how much carry the GP actually earns** — is still done in fragile, error-prone Excel.

CarryFlow turns that into a tested, auditable engine.

---

## Quick start

```bash
carryflow waterfall --proceeds 250 --committed 100 --pref 0.08 --carry 0.20
```

```
💧 CarryFlow — European Waterfall
Committed: 100.0   Proceeds: 250.0   Pref: 8.0%   Carry: 20.0%

 Tier                       LP        GP      Total
 ─────────────────────────────────────────────────
 1. Return of Capital     100.0      0.0     100.0
 2. Preferred Return       46.9      0.0      46.9
 3. GP Catch-up             0.0     11.7      11.7
 4. Carry Split (80/20)    72.3     18.1      90.4
 ─────────────────────────────────────────────────
 TOTAL                    219.2     29.8     250.0

 LP MOIC            2.19x
 GP Carry           29.8
 Effective Carry %  19.9%
```

---

## Commands

### Distribution waterfall
```bash
carryflow waterfall --proceeds 250 --committed 100 \
    --pref 0.08 --carry 0.20 --years 5 --structure european
```

### Secondary stake pricing
```bash
carryflow secondary --nav 50 --bid 0.88
# Seller receives: 44.0  (12.0% discount to NAV)
```

### GP-led continuation vehicle
```bash
carryflow cv --nav 100 --price 110 --cost 40 --rollover 0.6
# Crystallized Carry (GP): 12.x
# Cash-out to exiting LPs / Rolled into CV / New capital required
```

---

## Python API

```python
from carryflow import FundTerms, european_waterfall, xirr, moic
from datetime import date

terms = FundTerms(
    committed_capital=100,      # ₹100 Cr fund
    gp_commitment_pct=0.02,     # 2% GP co-invest
    preferred_return=0.08,      # 8% hurdle
    carry=0.20,                 # 20% carried interest
)

result = european_waterfall(terms, total_proceeds=250, years=5)
print(f"LP gets {result.lp_distribution:.1f} (MOIC {result.lp_moic:.2f}x)")
print(f"GP carry: {result.gp_carry:.1f} ({result.effective_carry_pct:.1%})")

# Fund-level IRR from dated cash flows
flows = [
    (date(2019, 1, 1), -100),
    (date(2024, 6, 1),  250),
]
print(f"Net IRR: {xirr(flows):.1%}")
print(f"MOIC: {moic(100, 250):.2f}x")
```

---

## The waterfall, explained

A European (whole-fund) waterfall pays out in four tiers:

| Tier | Who gets paid | Until |
|------|---------------|-------|
| 1. Return of Capital | LP (+ GP co-invest) | contributed capital is returned |
| 2. Preferred Return | LP | the hurdle (e.g. 8%) is met |
| 3. GP Catch-up | GP | GP reaches its carry % of profit |
| 4. Carried Interest | LP / GP split | all remaining proceeds (e.g. 80/20) |

**American (deal-by-deal)** applies tiers 1–4 to each realized deal individually — more GP-friendly, common in US VC.

---

## Modules

| Module | Purpose |
|--------|---------|
| `waterfall.py` | European & American waterfall engines |
| `metrics.py` | IRR, XIRR, MOIC, DPI, TVPI, RVPI |
| `secondary.py` | Secondary pricing + continuation vehicle modeling |
| `models.py` | `FundTerms`, `WaterfallResult`, tiers, quotes |

Fully tested · zero heavy dependencies · CLI + Python API.

---

© 2026 Bhupendra Gurjar. All rights reserved. Commercial license — contact for terms.
