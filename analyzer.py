"""
Core analysis logic: detectability of assumable mortgages and profitability scoring.
"""
import re
import math
from dataclasses import dataclass, field
from typing import Optional


CURRENT_RATE = 7.25  # current 30-yr fixed benchmark

ASSUMABLE_KEYWORDS = [
    r"\bassumable\b",
    r"\bassume\s+(?:the\s+)?(?:loan|mortgage)\b",
    r"\bva\s+(?:loan|mortgage|assumable)\b",
    r"\bfha\s+(?:loan|mortgage|assumable)\b",
    r"\busda\s+(?:loan|mortgage|assumable)\b",
    r"\blow\s+rate\s+(?:va|fha|usda)\b",
    r"\b(?:va|fha)\s+financ",
]

PREFORECLOSURE_KEYWORDS = [
    r"\bpre.?foreclosure\b",
    r"\bnotice\s+of\s+default\b",
    r"\bnod\b",
    r"\blis\s+pendens\b",
    r"\bdistressed\b",
    r"\bbank.?owned\b",
    r"\breo\b",
    r"\bforeclosure\b",
    r"\bshort\s+sale\b",
    r"\bseller\s+motivated\b",
    r"\bprice\s+reduced\b",
]

# Typical rates for VA/FHA loans by origination year (pre-rate-hike era)
HISTORICAL_RATES = {
    2019: 3.94,
    2020: 3.11,
    2021: 2.96,
    2022: 5.34,
    2023: 6.81,
    2024: 6.72,
    2025: 6.85,
}


@dataclass
class PropertyAnalysis:
    street: str
    city: str
    state: str
    zip_code: str
    list_price: float
    beds: Optional[int]
    baths: Optional[float]
    sqft: Optional[int]
    year_built: Optional[int]
    description: str
    url: Optional[str]

    # Computed
    is_preforeclosure: bool = False
    preforeclosure_signals: list = field(default_factory=list)
    is_assumable: bool = False
    assumable_inferred: bool = False  # True = inferred from sale year, not explicit
    assumable_signals: list = field(default_factory=list)
    assumed_rate: float = 0.0
    estimated_balance: float = 0.0
    monthly_payment_savings: float = 0.0
    equity_discount_pct: float = 0.0
    annual_savings: float = 0.0
    profitability_score: float = 0.0
    profitability_grade: str = ""
    zestimate: Optional[float] = None
    price_per_sqft: Optional[float] = None

    def address(self):
        return f"{self.street}, {self.city}, {self.state} {self.zip_code}"


_NEGATION_PREFIX = re.compile(r"\b(no|not|non|without|non-)\s*$", re.I)

# Phrases that explicitly rule out assumable financing
_NOT_ASSUMABLE_PHRASES = re.compile(
    r"\b(cash\s+only|cash\s+or\s+conventional|conventional\s+only|no\s+fha|no\s+va|"
    r"not\s+assumable|non.?assumable|cash.?conventional)\b",
    re.I,
)

# Phrases that explicitly rule out distressed/pre-foreclosure
_NOT_DISTRESSED_PHRASES = re.compile(
    r"\b(not\s+a\s+(?:distressed|foreclosure)|not\s+distressed|standard\s+sale|"
    r"traditional\s+sale|not\s+a\s+short\s+sale)\b",
    re.I,
)


def _search_text(patterns: list[str], text: str) -> list[str]:
    text_lower = text.lower()
    hits = []
    for p in patterns:
        for m in re.finditer(p, text_lower):
            # Check for negation: look at the 20 chars before the match
            prefix = text_lower[max(0, m.start() - 20) : m.start()]
            if _NEGATION_PREFIX.search(prefix.rstrip()):
                continue
            hits.append(m.group(0))
    return hits


def detect_preforeclosure(desc: str, listing_type: str = "") -> tuple[bool, list[str]]:
    # Hard exclusion — explicitly states it's NOT distressed
    if _NOT_DISTRESSED_PHRASES.search(desc):
        return False, []
    signals = _search_text(PREFORECLOSURE_KEYWORDS, desc)
    if "foreclosure" in listing_type.lower():
        signals.append("listing_type:foreclosure")
    return bool(signals), signals


def detect_assumable(
    desc: str, last_sold_date: str = "", last_sold_price: Optional[float] = None
) -> tuple[bool, list[str], bool]:
    """
    Returns (is_assumable, signals, is_inferred).
    is_inferred=True means we are inferring assumability from loan era, not explicit text.
    """
    # Hard exclusions — description explicitly rules out assumable financing
    if _NOT_ASSUMABLE_PHRASES.search(desc):
        return False, [], False

    signals = _search_text(ASSUMABLE_KEYWORDS, desc)
    if signals:
        return True, signals, False

    # Infer: VA/FHA loans from 2019-2022 are almost certainly assumable and attractive
    infer_signals = []
    if last_sold_date:
        m = re.search(r"(\d{4})", str(last_sold_date))
        if m:
            yr = int(m.group(1))
            if 2019 <= yr <= 2022:
                infer_signals.append(f"sold_{yr} (low-rate era)")
    # VA has no loan limits; FHA limit was ~$331K standard / $765K high-cost
    # Infer FHA for moderate prices, VA for higher prices
    if infer_signals and last_sold_price:
        price = float(last_sold_price)
        if 50_000 <= price <= 800_000:
            loan_type = "VA" if price > 400_000 else "FHA/VA"
            infer_signals.append(f"loan_size_eligible_{loan_type}")
    if len(infer_signals) >= 2:
        return True, infer_signals, True

    return False, [], False


def extract_assumed_rate(desc: str) -> Optional[float]:
    """Try to pull a specific rate from listing text."""
    patterns = [
        r"(\d+\.?\d*)\s*%\s*(?:interest\s+)?rate",
        r"rate\s+of\s+(\d+\.?\d*)\s*%",
        r"assuming\s+(?:a\s+)?(\d+\.?\d*)\s*%",
        r"(\d+\.?\d*)\s*%\s*assumable",
    ]
    for p in patterns:
        m = re.search(p, desc.lower())
        if m:
            rate = float(m.group(1))
            if 1.0 <= rate <= 8.0:  # sanity check
                return rate
    return None


def estimate_assumed_rate(
    desc: str,
    year_built: Optional[int] = None,
    last_sold_date: str = "",
) -> float:
    """
    Estimate the assumed rate. Priority:
    1. Explicit rate in description
    2. Historical average for the origination year (from last_sold_date)
    3. Loan-type keyword heuristic (VA/FHA/USDA)
    4. Conservative default
    """
    explicit = extract_assumed_rate(desc)
    if explicit:
        return explicit

    # Use last sale year to pick historical rate
    orig_year = None
    if last_sold_date:
        m = re.search(r"(\d{4})", str(last_sold_date))
        if m:
            yr = int(m.group(1))
            if 2015 <= yr <= 2025:
                orig_year = yr

    if orig_year and orig_year in HISTORICAL_RATES:
        base = HISTORICAL_RATES[orig_year]
        desc_lower = desc.lower()
        if re.search(r"\bva\b", desc_lower):
            return round(base - 0.25, 2)  # VA historically slightly below average
        if re.search(r"\bfha\b", desc_lower):
            return round(base + 0.15, 2)  # FHA slightly above
        return round(base, 2)

    # Loan-type keyword fallback
    desc_lower = desc.lower()
    if re.search(r"\bva\b", desc_lower):
        return 2.75
    if re.search(r"\bfha\b", desc_lower):
        return 3.25
    if re.search(r"\busda\b", desc_lower):
        return 3.0

    return 3.5


def monthly_payment(principal: float, annual_rate: float, years: int = 30) -> float:
    if principal <= 0 or annual_rate <= 0:
        return 0.0
    r = annual_rate / 100 / 12
    n = years * 12
    return principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def estimate_remaining_balance(
    original_principal: float,
    annual_rate: float,
    years_paid: int = 4,
    total_years: int = 30,
) -> float:
    """Estimate remaining balance assuming some years have been paid."""
    if original_principal <= 0 or annual_rate <= 0:
        return original_principal
    r = annual_rate / 100 / 12
    n = total_years * 12
    paid = years_paid * 12
    pmt = original_principal * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    remaining_n = n - paid
    balance = pmt * (1 - (1 + r) ** (-remaining_n)) / r
    return max(0, balance)


def score_property(
    list_price: float,
    assumed_rate: float,
    zestimate: Optional[float] = None,
    sqft: Optional[int] = None,
    is_preforeclosure: bool = False,
    is_assumable: bool = False,
    assumable_inferred: bool = False,
) -> tuple[float, str]:
    """
    Score 0-100:
      - 35 pts: equity/discount vs. estimated value  (boosted — equity is king)
      - 35 pts: monthly savings vs. current rate
      - 20 pts: assumed rate quality (lower = better)
      - 10 pts: pre-foreclosure bonus (distressed = motivated seller)
    Inferred assumable gets 75% credit (uncertainty discount).
    """
    score = 0.0
    inferred_mult = 0.75 if assumable_inferred else 1.0

    # 1. Equity / discount (35 pts)
    equity_score = 0.0
    if zestimate and zestimate > 0 and list_price > 0:
        discount_pct = max(0, (zestimate - list_price) / zestimate * 100)
        equity_score = min(35, discount_pct * 1.4)
    score += equity_score

    # 2. Monthly savings vs. current rate (35 pts)
    loan = list_price * 0.8
    pmt_current = monthly_payment(loan, CURRENT_RATE)
    pmt_assumed = monthly_payment(loan, assumed_rate) if is_assumable else pmt_current
    savings = max(0, pmt_current - pmt_assumed) * inferred_mult
    savings_score = min(35, (savings / 1200) * 35)
    score += savings_score

    # 3. Assumed rate quality (20 pts)
    if is_assumable and assumed_rate > 0:
        rate_score = max(0, min(20, (CURRENT_RATE - assumed_rate) / CURRENT_RATE * 20)) * inferred_mult
        score += rate_score

    # 4. Pre-foreclosure bonus (10 pts)
    if is_preforeclosure:
        score += 10

    grade_map = [(85, "A+"), (75, "A"), (65, "B+"), (55, "B"), (45, "C+"), (35, "C"), (0, "D")]
    grade = next(g for threshold, g in grade_map if score >= threshold)

    return round(score, 1), grade


def analyze_property(row: dict) -> PropertyAnalysis:
    desc = str(row.get("description") or row.get("text") or "")
    list_price = float(row.get("list_price") or row.get("price") or 0)
    # Reject placeholder/auction prices (< $10K) — not real list prices
    if list_price < 10_000:
        list_price = 0.0
    year_built = row.get("year_built")
    sqft = row.get("sqft") or row.get("square_feet")
    zestimate = row.get("zestimate") or row.get("estimated_value")

    last_sold_date = str(row.get("last_sold_date") or "")
    last_sold_price = row.get("last_sold_price")

    is_pre, pre_signals = detect_preforeclosure(
        desc, str(row.get("listing_type") or "")
    )
    is_assumable, assume_signals, assumable_inferred = detect_assumable(
        desc,
        last_sold_date=last_sold_date,
        last_sold_price=float(last_sold_price) if last_sold_price else None,
    )

    assumed_rate = 0.0
    balance = 0.0
    savings = 0.0
    annual_savings = 0.0

    if is_assumable and list_price > 0:
        assumed_rate = estimate_assumed_rate(desc, year_built, last_sold_date)
        # Use last_sold_price as original loan estimate if available
        original_loan = (
            float(last_sold_price) * 0.85
            if last_sold_price and float(last_sold_price) > 0
            else list_price * 0.85
        )
        # Estimate years paid from last_sold_date
        years_paid = 4
        if last_sold_date:
            m = re.search(r"(\d{4})", last_sold_date)
            if m:
                orig_year = int(m.group(1))
                years_paid = max(1, 2026 - orig_year)

        balance = estimate_remaining_balance(
            original_loan,
            assumed_rate,
            years_paid=years_paid,
        )
        loan = list_price * 0.8
        pmt_now = monthly_payment(loan, CURRENT_RATE)
        pmt_assumed = monthly_payment(loan, assumed_rate)
        savings = max(0, pmt_now - pmt_assumed)
        annual_savings = savings * 12

    if zestimate and list_price:
        equity_pct = (float(zestimate) - list_price) / float(zestimate) * 100
    else:
        equity_pct = 0.0

    score, grade = score_property(
        list_price,
        assumed_rate or CURRENT_RATE,
        zestimate=float(zestimate) if zestimate else None,
        sqft=int(sqft) if sqft else None,
        is_preforeclosure=is_pre,
        is_assumable=is_assumable,
        assumable_inferred=assumable_inferred,
    )

    ppsqft = None
    if sqft and int(sqft) > 0 and list_price > 0:
        ppsqft = round(list_price / int(sqft), 0)

    return PropertyAnalysis(
        street=str(row.get("street") or row.get("address") or ""),
        city=str(row.get("city") or ""),
        state=str(row.get("state") or ""),
        zip_code=str(row.get("zip_code") or row.get("zip") or ""),
        list_price=list_price,
        beds=row.get("beds"),
        baths=row.get("full_baths") or row.get("baths"),
        sqft=int(sqft) if sqft else None,
        year_built=int(year_built) if year_built else None,
        description=desc,
        url=row.get("property_url") or row.get("url"),
        is_preforeclosure=is_pre,
        preforeclosure_signals=pre_signals,
        is_assumable=is_assumable,
        assumable_inferred=assumable_inferred,
        assumable_signals=assume_signals,
        assumed_rate=assumed_rate,
        estimated_balance=balance,
        monthly_payment_savings=savings,
        equity_discount_pct=equity_pct,
        annual_savings=annual_savings,
        profitability_score=score,
        profitability_grade=grade,
        zestimate=float(zestimate) if zestimate else None,
        price_per_sqft=ppsqft,
    )
