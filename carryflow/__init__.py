"""
CarryFlow — PE/VC distribution waterfall & carried-interest engine.

Models the deal economics that investor-discovery tools ignore:
  - European (whole-fund) & American (deal-by-deal) waterfalls
  - Preferred return (hurdle), GP catch-up, carried interest splits
  - MOIC, IRR/XIRR, DPI, TVPI, RVPI
  - Secondary stake pricing (NAV discount/premium)
  - GP-led continuation vehicles (roll vs cash-out economics)
"""
from .models import (
    FundTerms, CashFlow, WaterfallTier, WaterfallResult,
    SecondaryQuote, ContinuationVehicleResult,
)
from .metrics import xirr, irr, moic, dpi, tvpi, rvpi
from .waterfall import european_waterfall, american_waterfall
from .secondary import price_secondary, model_continuation_vehicle

__version__ = "1.0.0"
