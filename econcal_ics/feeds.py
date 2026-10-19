"""Feed definitions: each feed becomes one subscribable .ics calendar."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .client import Event

BIG_EVENT_PATTERNS = [
    r"\bFed Interest Rate Decision\b", r"\bFOMC (Statement|Press Conference|Meeting Minutes|Economic Projections)\b",
    r"^CPI \((MoM|YoY)\)", r"^Core CPI", r"\bNonfarm Payrolls\b", r"^Unemployment Rate\b",
    r"\bCore PCE Price Index\b", r"^GDP \(QoQ\)", r"\bISM (Manufacturing|Non-Manufacturing) PMI\b",
    r"\bRetail Sales \(MoM\)\b", r"^PPI \(MoM\)",
]
CENTRAL_BANK_PATTERNS = [
    r"Interest Rate Decision", r"Deposit Facility Rate", r"Monetary Policy (Statement|Assessment|Report)",
    r"Meeting Minutes", r"Press Conference", r"\bMPC vote\b", r"Fed Chair .* Speaks", r"ECB President .* Speaks",
    r"BoE Gov .* Speaks", r"BoJ Gov .* Speaks", r"Beige Book",
]


def _matches(patterns: list[str]) -> Callable[[Event], bool]:
    rx = [re.compile(p, re.I) for p in patterns]
    return lambda e: any(r.search(e.title) for r in rx)


@dataclass
class Feed:
    slug: str
    name: str
    description: str
    predicate: Callable[[Event], bool]
    alarm_minutes: int | None = 15
    tags: list[str] = field(default_factory=list)


def _cur(code: str) -> Callable[[Event], bool]:
    return lambda e: (e.currency or "").upper() == code


high = lambda e: e.importance == "high"  # noqa: E731
us_big = _matches(BIG_EVENT_PATTERNS)
cb = _matches(CENTRAL_BANK_PATTERNS)

FEEDS: list[Feed] = [
    Feed("high-impact", "High-Impact Economic Events (all countries)",
         "Every 3-star event worldwide: CPI, NFP, GDP, PMIs, rate decisions.", high, tags=["forex", "stocks"]),
    Feed("us-big-releases", "US Big Releases: FOMC, CPI, NFP, PCE, GDP",
         "The US releases that move every market: FOMC decisions, CPI, Nonfarm Payrolls, PCE, GDP, ISM, Retail Sales.",
         lambda e: e.country == "united states" and (us_big(e) or (high(e) and "Speaks" not in e.title)),
         tags=["fomc", "cpi", "nfp"]),
    Feed("central-banks", "Central Bank Decisions & Speeches",
         "Fed, ECB, BoE, BoJ, BoC, RBA, RBNZ, SNB rate decisions, minutes, press conferences and chair speeches.",
         lambda e: cb(e) and e.importance in ("high", "medium"), tags=["rates"]),
    Feed("usd", "USD (United States) - high & medium impact", "All high/medium-impact US events.",
         lambda e: _cur("USD")(e) and e.importance in ("high", "medium"), alarm_minutes=None),
    Feed("eur", "EUR (Euro Zone, Germany, France...) - high & medium impact", "All high/medium-impact EUR events.",
         lambda e: _cur("EUR")(e) and e.importance in ("high", "medium"), alarm_minutes=None),
    Feed("gbp", "GBP (United Kingdom) - high & medium impact", "All high/medium-impact UK events.",
         lambda e: _cur("GBP")(e) and e.importance in ("high", "medium"), alarm_minutes=None),
    Feed("jpy", "JPY (Japan) - high & medium impact", "All high/medium-impact Japanese events.",
         lambda e: _cur("JPY")(e) and e.importance in ("high", "medium"), alarm_minutes=None),
    Feed("bank-holidays", "Market & Bank Holidays", "Public holidays when local markets are closed or thin.",
         lambda e: e.is_holiday, alarm_minutes=None, tags=["holidays"]),
]
