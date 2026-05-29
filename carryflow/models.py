"""Data models for CarryFlow waterfall engine. All amounts in same currency unit."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple


@dataclass
class FundTerms:
    """Standard PE/VC fund economic terms."""
    committed_capital: float                  # Total LP + GP commitments
    gp_commitment_pct: float = 0.02           # GP co-invest (typically 1–2%)
    preferred_return: float = 0.08            # Hurdle / pref rate (8% typical)
    carry: float = 0.20                       # Carried interest (20% typical)
    catchup_rate: float = 1.0                 # GP catch-up speed (1.0 = 100% to GP)
    management_fee: float = 0.02              # Annual mgmt fee on committed capital
    fee_years: int = 10                       # Years mgmt fee is charged
    hurdle_compounding: bool = True           # Compound the pref vs simple

    def __post_init__(self):
        if not 0 <= self.carry < 1:
            raise ValueError("carry must be between 0 and 1")
        if not 0 <= self.gp_commitment_pct < 1:
            raise ValueError("gp_commitment_pct must be between 0 and 1")
        if self.committed_capital <= 0:
            raise ValueError("committed_capital must be positive")

    @property
    def lp_commitment(self) -> float:
        return self.committed_capital * (1 - self.gp_commitment_pct)

    @property
    def gp_commitment(self) -> float:
        return self.committed_capital * self.gp_commitment_pct

    @property
    def total_management_fees(self) -> float:
        return self.committed_capital * self.management_fee * self.fee_years


@dataclass
class CashFlow:
    """A single dated cash flow. Negative = contribution (paid in), positive = distribution."""
    when: date
    amount: float
    label: str = ""


@dataclass
class WaterfallTier:
    """One tier of the distribution waterfall."""
    name: str
    lp_amount: float = 0.0
    gp_amount: float = 0.0

    @property
    def total(self) -> float:
        return self.lp_amount + self.gp_amount


@dataclass
class WaterfallResult:
    """Result of running a distribution waterfall."""
    structure: str                            # "European" or "American"
    total_proceeds: float
    lp_contributed: float
    gp_contributed: float
    tiers: List[WaterfallTier] = field(default_factory=list)

    lp_distribution: float = 0.0
    gp_distribution: float = 0.0
    gp_carry: float = 0.0                      # Carry portion only (excl. GP co-invest return)

    @property
    def total_distributed(self) -> float:
        return self.lp_distribution + self.gp_distribution

    @property
    def lp_profit(self) -> float:
        return self.lp_distribution - self.lp_contributed

    @property
    def gp_profit(self) -> float:
        return self.gp_distribution - self.gp_contributed

    @property
    def lp_moic(self) -> Optional[float]:
        return self.lp_distribution / self.lp_contributed if self.lp_contributed else None

    @property
    def gp_moic(self) -> Optional[float]:
        return self.gp_distribution / self.gp_contributed if self.gp_contributed else None

    @property
    def effective_carry_pct(self) -> Optional[float]:
        """GP's carry as % of total profit above return of capital."""
        total_profit = self.total_distributed - (self.lp_contributed + self.gp_contributed)
        return self.gp_carry / total_profit if total_profit > 0 else None

    def summary(self) -> str:
        lines = [
            f"{self.structure} Waterfall",
            f"Total Proceeds:   {self.total_proceeds:,.1f}",
            f"LP Distribution:  {self.lp_distribution:,.1f}  (MOIC {self.lp_moic:.2f}x)"
            if self.lp_moic else f"LP Distribution:  {self.lp_distribution:,.1f}",
            f"GP Distribution:  {self.gp_distribution:,.1f}",
            f"  of which Carry:  {self.gp_carry:,.1f}",
        ]
        return "\n".join(lines)


@dataclass
class SecondaryQuote:
    """Pricing for a secondary sale of an LP fund stake."""
    nav: float                                # Current net asset value of the stake
    unfunded: float                           # Remaining unfunded commitment
    bid_pct_nav: float                        # Bid as % of NAV (0.85 = 15% discount)
    price: float = 0.0                        # Cash the seller receives
    discount_premium: float = 0.0             # +ve = premium, -ve = discount

    @property
    def is_discount(self) -> bool:
        return self.bid_pct_nav < 1.0


@dataclass
class ContinuationVehicleResult:
    """Economics of a GP-led continuation vehicle transaction."""
    asset_nav: float
    purchase_price: float                     # Price CV pays old fund for the asset
    crystallized_carry: float                 # Carry GP locks in on the sale
    rollover_pct: float                       # % of existing LPs who roll into CV
    cashout_amount: float                     # Cash paid to LPs who exit
    rollover_amount: float                    # Value rolled into the CV
    new_capital: float = 0.0                  # Fresh capital from new LPs
    premium_to_nav: float = 0.0
