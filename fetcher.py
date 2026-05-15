"""
Property data fetching via HomeHarvest + fallback demo data.
"""
import time
import random
from typing import Optional
import pandas as pd


def _homeharvest_fetch(location: str, max_results: int = 200) -> pd.DataFrame:
    from homeharvest import scrape_property

    frames = []

    # Try all listing types that surface distressed/assumable properties
    for ltype in ["for_sale", "pending"]:
        try:
            df = scrape_property(
                location=location,
                listing_type=ltype,
                past_days=60,
            )
            if df is not None and len(df) > 0:
                df["listing_type_fetched"] = ltype
                frames.append(df)
            time.sleep(1)
        except Exception as e:
            print(f"[fetcher] {ltype} fetch error: {e}")

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # Drop duplicates by address
    if "street" in combined.columns:
        combined = combined.drop_duplicates(subset=["street", "zip_code"])
    return combined.head(max_results)


def _safe(val):
    try:
        import pandas as _pd
        return None if _pd.isna(val) else val
    except Exception:
        return val


def _normalize(df: pd.DataFrame) -> list[dict]:
    """Normalize HomeHarvest columns to our standard schema."""
    records = []
    for _, row in df.iterrows():
        rec = {
            "street": _safe(row.get("full_street_line") or row.get("street")),
            "city": _safe(row.get("city")),
            "state": _safe(row.get("state")),
            "zip_code": _safe(row.get("zip_code")),
            "list_price": _safe(row.get("list_price")),
            "beds": _safe(row.get("beds")),
            "full_baths": _safe(row.get("full_baths")),
            "sqft": _safe(row.get("sqft")),
            "year_built": _safe(row.get("year_built")),
            "url": _safe(row.get("property_url")),
            "listing_type": _safe(row.get("status") or row.get("listing_type_fetched")),
            # estimated value from Realtor.com
            "zestimate": _safe(row.get("estimated_value")),
            # last sale info — used to estimate mortgage origination year & rate
            "last_sold_date": str(_safe(row.get("last_sold_date")) or ""),
            "last_sold_price": _safe(row.get("last_sold_price")),
            "days_on_mls": _safe(row.get("days_on_mls")),
            "lot_sqft": _safe(row.get("lot_sqft")),
            "hoa_fee": _safe(row.get("hoa_fee")),
            "primary_photo": _safe(row.get("primary_photo")),
        }
        # Description text
        for col in ["text", "remarks", "public_remarks", "description"]:
            if col in row.index:
                v = _safe(row[col])
                if v:
                    rec["description"] = str(v)
                    break
        if "description" not in rec:
            rec["description"] = ""
        records.append(rec)
    return records


DEMO_LISTINGS = [
    {
        "street": "4821 W Ocotillo Rd",
        "city": "Glendale",
        "state": "AZ",
        "zip_code": "85301",
        "list_price": 285000,
        "beds": 3,
        "full_baths": 2,
        "sqft": 1540,
        "year_built": 2019,
        "description": (
            "Pre-foreclosure opportunity! Motivated seller. VA assumable loan at 2.75% interest rate. "
            "Outstanding 30-year VA mortgage originated in 2021. "
            "Buyer assumes existing VA mortgage — save thousands vs. current rates. "
            "Seller facing hardship, priced below market. Home needs minor cosmetic work."
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo1",
        "zestimate": 320000,
        "listing_type": "for_sale",
    },
    {
        "street": "1102 E Sherman St",
        "city": "Phoenix",
        "state": "AZ",
        "zip_code": "85006",
        "list_price": 340000,
        "beds": 4,
        "full_baths": 2,
        "sqft": 1850,
        "year_built": 2020,
        "description": (
            "Short sale pending bank approval. FHA assumable mortgage at 3.25%, "
            "original loan balance approximately $290,000. Great opportunity to assume "
            "the FHA loan and lock in a low rate. Property is in pre-foreclosure status. "
            "Updated kitchen, new roof 2022."
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo2",
        "zestimate": 375000,
        "listing_type": "for_sale",
    },
    {
        "street": "7834 Painted Desert Dr",
        "city": "Las Vegas",
        "state": "NV",
        "zip_code": "89149",
        "list_price": 420000,
        "beds": 4,
        "full_baths": 3,
        "sqft": 2200,
        "year_built": 2021,
        "description": (
            "Assumable VA loan — original rate 2.5%! This is a rare find. "
            "Veteran seller, loan is fully assumable to qualified buyers. "
            "Notice of default filed. Lender motivated. Home appraised at $465,000. "
            "3-car garage, solar panels owned outright."
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo3",
        "zestimate": 465000,
        "listing_type": "for_sale",
    },
    {
        "street": "2250 Oak Hollow Ln",
        "city": "San Antonio",
        "state": "TX",
        "zip_code": "78253",
        "list_price": 265000,
        "beds": 3,
        "full_baths": 2,
        "sqft": 1620,
        "year_built": 2018,
        "description": (
            "Pre-foreclosure. FHA loan assumable. Seller behind on payments. "
            "Quick close preferred. Priced below market value for fast sale. "
            "Great neighborhood, good school district."
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo4",
        "zestimate": 298000,
        "listing_type": "for_sale",
    },
    {
        "street": "9901 Cypress Creek Pkwy",
        "city": "Houston",
        "state": "TX",
        "zip_code": "77070",
        "list_price": 310000,
        "beds": 4,
        "full_baths": 2,
        "sqft": 2100,
        "year_built": 2020,
        "description": (
            "Bank-owned REO. Priced to sell. Conventional loan, no assumable financing. "
            "As-is condition. Cash or conventional only."
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo5",
        "zestimate": 335000,
        "listing_type": "for_sale",
    },
    {
        "street": "543 Ridgewood Ave",
        "city": "Tampa",
        "state": "FL",
        "zip_code": "33606",
        "list_price": 389000,
        "beds": 3,
        "full_baths": 2,
        "sqft": 1780,
        "year_built": 2021,
        "description": (
            "VA assumable at 2.875% — assuming buyer must be VA eligible or get VA approval. "
            "Pre-foreclosure — seller needs to sell quickly. Lis pendens filed. "
            "Home in great shape, just painted, new AC. Comparable homes selling for $430K+"
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo6",
        "zestimate": 435000,
        "listing_type": "for_sale",
    },
    {
        "street": "1415 Peach Tree St NE",
        "city": "Atlanta",
        "state": "GA",
        "zip_code": "30309",
        "list_price": 480000,
        "beds": 4,
        "full_baths": 3,
        "sqft": 2650,
        "year_built": 2020,
        "description": (
            "USDA assumable loan, 3.0% rate. Seller relocated out of state. "
            "Priced aggressively. This property qualifies for USDA assumption. "
            "Gorgeous open floor plan, hardwood floors throughout. "
            "Distressed sale due to job relocation — priced $40K below recent comps."
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo7",
        "zestimate": 525000,
        "listing_type": "for_sale",
    },
    {
        "street": "876 Blue Heron Way",
        "city": "Orlando",
        "state": "FL",
        "zip_code": "32819",
        "list_price": 350000,
        "beds": 3,
        "full_baths": 2,
        "sqft": 1690,
        "year_built": 2022,
        "description": (
            "Standard sale, well-maintained home near Disney. "
            "Conventional financing. Motivated seller, flexible on closing. "
            "New appliances, updated bathrooms."
        ),
        "url": "https://www.realtor.com/realestateandhomes-detail/demo8",
        "zestimate": 362000,
        "listing_type": "for_sale",
    },
]


def fetch_listings(
    location: str,
    use_live: bool = True,
    max_results: int = 200,
) -> tuple[list[dict], str]:
    """
    Returns (listings, source_label).
    Falls back to demo data if live fetch fails or returns nothing.
    """
    source = "demo"
    listings = []

    if use_live:
        try:
            df = _homeharvest_fetch(location, max_results=max_results)
            if df is not None and len(df) > 0:
                listings = _normalize(df)
                source = f"live ({len(listings)} properties from Realtor.com)"
        except Exception as e:
            print(f"[fetcher] Live fetch failed: {e}")

    if not listings:
        listings = DEMO_LISTINGS
        source = "demo (live fetch unavailable — showing sample data)"

    return listings, source
