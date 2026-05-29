"""CLI for CarryFlow."""
from __future__ import annotations
import sys
import click
from .models import FundTerms
from .waterfall import european_waterfall, american_waterfall
from .secondary import price_secondary, model_continuation_vehicle
from .metrics import moic, dpi, tvpi

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    console = Console()
    _RICH = True
except ImportError:
    console = None
    _RICH = False


def _m(v): return f"{v:,.1f}"
def _pct(v): return f"{v*100:.1f}%" if v is not None else "N/A"


@click.group()
def cli():
    """CarryFlow — PE/VC waterfall, carry & exit-structuring engine."""


@cli.command("waterfall")
@click.option("--proceeds", required=True, type=float, help="Total proceeds to distribute")
@click.option("--committed", required=True, type=float, help="Committed capital")
@click.option("--gp-commit", default=0.02, help="GP commitment % (default 2%)")
@click.option("--pref", default=0.08, help="Preferred return / hurdle (default 8%)")
@click.option("--carry", default=0.20, help="Carried interest (default 20%)")
@click.option("--years", default=5.0, help="Holding period in years")
@click.option("--structure", type=click.Choice(["european", "american"]), default="european")
def waterfall_cmd(proceeds, committed, gp_commit, pref, carry, years, structure):
    """Run a distribution waterfall.

    Example: carryflow waterfall --proceeds 250 --committed 100 --pref 0.08 --carry 0.20
    """
    terms = FundTerms(
        committed_capital=committed, gp_commitment_pct=gp_commit,
        preferred_return=pref, carry=carry,
    )

    if structure == "european":
        result = european_waterfall(terms, proceeds, years=years)
    else:
        # Single pooled "deal" for the simple CLI american case
        result = american_waterfall(terms, [proceeds], [committed], [years])

    if not _RICH:
        print(result.summary())
        return

    console.print(Panel(
        f"[bold]{result.structure} Waterfall[/]\n"
        f"Committed: {_m(committed)}   Proceeds: {_m(proceeds)}   "
        f"Pref: {_pct(pref)}   Carry: {_pct(carry)}",
        title="[bold cyan]💧 CarryFlow[/]", border_style="cyan",
    ))

    t = Table(box=box.SIMPLE_HEAVY)
    t.add_column("Tier", style="bold")
    t.add_column("LP", justify="right")
    t.add_column("GP", justify="right")
    t.add_column("Total", justify="right")
    for tier in result.tiers:
        t.add_row(tier.name, _m(tier.lp_amount), _m(tier.gp_amount), _m(tier.total))
    t.add_row("[bold]TOTAL[/]",
              f"[bold green]{_m(result.lp_distribution)}[/]",
              f"[bold yellow]{_m(result.gp_distribution)}[/]",
              f"[bold]{_m(result.total_distributed)}[/]")
    console.print(t)

    summary = Table(box=box.SIMPLE, show_header=False)
    summary.add_column("k", style="dim")
    summary.add_column("v", justify="right")
    if result.lp_moic:
        summary.add_row("LP MOIC", f"{result.lp_moic:.2f}x")
    summary.add_row("LP Profit", _m(result.lp_profit))
    summary.add_row("GP Carry", f"[yellow]{_m(result.gp_carry)}[/]")
    if result.effective_carry_pct:
        summary.add_row("Effective Carry %", _pct(result.effective_carry_pct))
    console.print(summary)


@cli.command("secondary")
@click.option("--nav", required=True, type=float, help="NAV of the LP stake")
@click.option("--bid", required=True, type=float, help="Bid as % of NAV (0.90 = 10% discount)")
@click.option("--unfunded", default=0.0, help="Unfunded commitment")
def secondary_cmd(nav, bid, unfunded):
    """Price a secondary sale of an LP fund stake.

    Example: carryflow secondary --nav 50 --bid 0.88
    """
    q = price_secondary(nav, bid, unfunded=unfunded)
    label = "discount" if q.is_discount else "premium"
    if not _RICH:
        print(f"Price: {_m(q.price)}  ({_pct(abs(q.discount_premium))} {label} to NAV)")
        return
    console.print(Panel(
        f"NAV: {_m(q.nav)}   Bid: {_pct(bid)} of NAV\n"
        f"[bold]Seller receives: {_m(q.price)}[/]   "
        f"([{'red' if q.is_discount else 'green'}]{_pct(abs(q.discount_premium))} {label}[/])",
        title="[bold]Secondary Quote[/]", border_style="blue",
    ))


@cli.command("cv")
@click.option("--nav", required=True, type=float, help="Asset NAV")
@click.option("--price", required=True, type=float, help="CV purchase price")
@click.option("--cost", required=True, type=float, help="Asset cost basis")
@click.option("--rollover", default=0.5, help="Fraction of LPs rolling (0-1)")
@click.option("--carry", default=0.20, help="Carry rate")
@click.option("--pref", default=0.08, help="Preferred return")
@click.option("--years", default=5.0, help="Holding years")
def cv_cmd(nav, price, cost, rollover, carry, pref, years):
    """Model a GP-led continuation vehicle.

    Example: carryflow cv --nav 100 --price 110 --cost 40 --rollover 0.6
    """
    terms = FundTerms(committed_capital=cost or 1, carry=carry, preferred_return=pref)
    r = model_continuation_vehicle(nav, price, cost, rollover, terms, holding_years=years)
    if not _RICH:
        print(f"Crystallized Carry: {_m(r.crystallized_carry)}")
        print(f"Cash-out: {_m(r.cashout_amount)}   Rollover: {_m(r.rollover_amount)}")
        return
    console.print(Panel(
        f"Asset NAV: {_m(r.asset_nav)}   Purchase: {_m(r.purchase_price)} "
        f"([{'green' if r.premium_to_nav>=0 else 'red'}]{_pct(r.premium_to_nav)} to NAV[/])\n"
        f"[bold yellow]Crystallized Carry (GP): {_m(r.crystallized_carry)}[/]\n"
        f"Cash-out to exiting LPs: {_m(r.cashout_amount)}\n"
        f"Rolled into CV: {_m(r.rollover_amount)}  ({_pct(r.rollover_pct)} rolled)\n"
        f"New LP capital required: {_m(r.new_capital)}",
        title="[bold]GP-Led Continuation Vehicle[/]", border_style="magenta",
    ))


def main():
    cli()
